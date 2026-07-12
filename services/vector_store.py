"""
services/vector_store.py
========================
ChromaDB vector store service.

Handles:
- Storing chunk embeddings with metadata
- Hybrid search (vector + BM25 keyword)
- Cross-encoder reranking
- MMR diversity retrieval
- Document-level delete
- Collection fingerprinting for cache invalidation
"""

from __future__ import annotations

import hashlib
import json
import threading
from typing import Any, Optional

import chromadb
import numpy as np
from chromadb.config import Settings
from rank_bm25 import BM25Okapi

import config
from models.document import ChunkMetadata, DocumentInfo, ProcessingStatus
from models.chat import SourceCitation
from services.embedding_service import embedding_service
from utils.logger import logger
from utils.text_utils import extract_snippet


class VectorStoreService:
    """
    ChromaDB-backed vector store with hybrid search and reranking.

    Thread-safe via a reentrant lock around all mutations.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._client: Optional[chromadb.PersistentClient] = None
        self._collection = None
        self._reranker = None
        self._doc_registry: dict[str, DocumentInfo] = {}  # filename → DocumentInfo
        self._initialize()

    def _initialize(self) -> None:
        """Connect to ChromaDB and load (or create) the collection."""
        logger.info(f"Initialising ChromaDB | path={config.CHROMA_DIR}")
        self._client = chromadb.PersistentClient(
            path=str(config.CHROMA_DIR),
            settings=Settings(anonymized_telemetry=False),
        )
        self._collection = self._client.get_or_create_collection(
            name=config.CHROMA_COLLECTION_NAME,
            metadata={"hnsw:space": config.CHROMA_DISTANCE_FUNCTION},
        )
        logger.info(
            f"ChromaDB ready | collection={config.CHROMA_COLLECTION_NAME} "
            f"| existing chunks={self._collection.count()}"
        )
        self._rebuild_doc_registry()

        if config.RERANK_ENABLED:
            self._load_reranker()

    def _load_reranker(self) -> None:
        """Lazily load the cross-encoder reranker model."""
        try:
            from sentence_transformers import CrossEncoder

            logger.info(f"Loading reranker: {config.RERANK_MODEL}")
            self._reranker = CrossEncoder(config.RERANK_MODEL)
            logger.info("Reranker loaded successfully")
        except Exception as e:
            logger.warning(f"Reranker load failed (disabled): {e}")
            self._reranker = None

    def _rebuild_doc_registry(self) -> None:
        """Rebuild in-memory document registry from ChromaDB metadata."""
        try:
            if self._collection.count() == 0:
                return
            results = self._collection.get(include=["metadatas"])
            filenames: dict[str, set[int]] = {}
            hashes: dict[str, str] = {}

            for meta in results["metadatas"]:
                fname = meta.get("filename", "")
                page = meta.get("page_number", 1)
                fhash = meta.get("file_hash", "")
                if fname:
                    filenames.setdefault(fname, set()).add(page)
                    hashes[fname] = fhash

            for fname, pages in filenames.items():
                # Count chunks for this file
                chunk_count = sum(
                    1 for m in results["metadatas"] if m.get("filename") == fname
                )
                self._doc_registry[fname] = DocumentInfo(
                    filename=fname,
                    file_hash=hashes.get(fname, ""),
                    file_size_bytes=0,
                    page_count=max(pages) if pages else 0,
                    chunk_count=chunk_count,
                    status=ProcessingStatus.COMPLETED,
                )
            logger.info(f"Doc registry rebuilt: {len(self._doc_registry)} documents")
        except Exception as e:
            logger.error(f"Failed to rebuild doc registry: {e}")

    # ─── Insertion ────────────────────────────────────────────────────────────

    def add_chunks(
        self,
        chunks: list[ChunkMetadata],
        doc_info: DocumentInfo,
    ) -> int:
        """
        Add chunk embeddings and metadata to ChromaDB.

        Args:
            chunks: List of ChunkMetadata to embed and store.
            doc_info: Document-level metadata.

        Returns:
            Number of chunks successfully added.
        """
        if not chunks:
            return 0

        with self._lock:
            texts = [c.chunk_text for c in chunks]
            logger.info(f"Embedding {len(texts)} chunks for {doc_info.filename}")

            # Encode in batches
            embeddings = embedding_service.encode_texts(
                texts,
                show_progress=True,
            ).tolist()

            ids = [c.chunk_id for c in chunks]
            metadatas = [
                {
                    "filename": c.filename,
                    "file_hash": c.file_hash,
                    "page_number": c.page_number,
                    "chunk_index": c.chunk_index,
                    "chunk_text": c.chunk_text,
                    "char_start": c.char_start,
                    "char_end": c.char_end,
                    "total_chunks": c.total_chunks,
                }
                for c in chunks
            ]

            # Upsert (idempotent)
            self._collection.upsert(
                ids=ids,
                embeddings=embeddings,
                documents=texts,
                metadatas=metadatas,
            )

            self._doc_registry[doc_info.filename] = doc_info
            logger.info(
                f"Stored {len(chunks)} chunks for {doc_info.filename} | "
                f"total={self._collection.count()}"
            )
            return len(chunks)

    # ─── Search ───────────────────────────────────────────────────────────────

    def search(
        self,
        query: str,
        top_k: int = config.TOP_K,
        filename_filter: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        """
        Hybrid search: vector similarity + BM25 keyword, then rerank.

        Args:
            query: User query string.
            top_k: Number of final results to return.
            filename_filter: Restrict search to a specific filename.

        Returns:
            List of result dicts with keys:
                text, filename, page_number, chunk_id, score, snippet
        """
        if self._collection.count() == 0:
            logger.warning("Search called on empty collection")
            return []

        # Fetch more candidates for hybrid fusion
        fetch_k = min(top_k * 4, self._collection.count())

        # ── Vector Search ────────────────────────────────────────────────────
        vector_results = self._vector_search(query, fetch_k, filename_filter)

        # ── BM25 Keyword Search ──────────────────────────────────────────────
        bm25_results = self._bm25_search(query, fetch_k, filename_filter)

        # ── Reciprocal Rank Fusion ───────────────────────────────────────────
        fused = self._reciprocal_rank_fusion(vector_results, bm25_results, top_k * 2)

        # ── Reranking ────────────────────────────────────────────────────────
        if config.RERANK_ENABLED and self._reranker and len(fused) > 1:
            fused = self._rerank(query, fused, top_k)
        else:
            fused = fused[:top_k]

        # ── Confidence Filtering ─────────────────────────────────────────────
        final = [r for r in fused if r["score"] >= config.CONFIDENCE_THRESHOLD]

        logger.info(
            f"Search | query='{query[:50]}' | "
            f"candidates={len(fused)} | passed_threshold={len(final)}"
        )
        return final

    def _vector_search(
        self,
        query: str,
        fetch_k: int,
        filename_filter: Optional[str],
    ) -> list[dict]:
        """Run ChromaDB vector similarity search."""
        query_embedding = embedding_service.encode_query(query).tolist()

        where = {"filename": filename_filter} if filename_filter else None

        results = self._collection.query(
            query_embeddings=[query_embedding],
            n_results=fetch_k,
            where=where,
            include=["metadatas", "documents", "distances"],
        )

        output: list[dict] = []
        if not results["ids"][0]:
            return output

        for i, chunk_id in enumerate(results["ids"][0]):
            meta = results["metadatas"][0][i]
            distance = results["distances"][0][i]
            # ChromaDB cosine: distance = 1 - similarity
            score = max(0.0, 1.0 - distance)
            output.append(
                {
                    "chunk_id": chunk_id,
                    "text": results["documents"][0][i],
                    "filename": meta.get("filename", ""),
                    "page_number": meta.get("page_number", 1),
                    "score": score,
                    "source": "vector",
                }
            )
        return output

    def _bm25_search(
        self,
        query: str,
        fetch_k: int,
        filename_filter: Optional[str],
    ) -> list[dict]:
        """Run BM25 keyword search over stored documents."""
        try:
            if self._collection.count() == 0:
                return []

            # Retrieve all documents for BM25 index
            where = {"filename": filename_filter} if filename_filter else None
            all_data = self._collection.get(
                where=where,
                include=["metadatas", "documents"],
            )
            if not all_data["ids"]:
                return []

            docs = all_data["documents"]
            ids = all_data["ids"]
            metas = all_data["metadatas"]

            # Tokenise (simple whitespace)
            tokenised = [d.lower().split() for d in docs]
            bm25 = BM25Okapi(tokenised)

            query_tokens = query.lower().split()
            scores = bm25.get_scores(query_tokens)

            # Get top-K indices
            top_indices = np.argsort(scores)[::-1][:fetch_k]

            output: list[dict] = []
            max_score = float(scores[top_indices[0]]) if len(top_indices) > 0 else 1.0
            for idx in top_indices:
                if scores[idx] <= 0:
                    break
                norm_score = scores[idx] / (max_score + 1e-9)
                meta = metas[idx]
                output.append(
                    {
                        "chunk_id": ids[idx],
                        "text": docs[idx],
                        "filename": meta.get("filename", ""),
                        "page_number": meta.get("page_number", 1),
                        "score": float(norm_score),
                        "source": "bm25",
                    }
                )
            return output
        except Exception as e:
            logger.warning(f"BM25 search failed: {e}")
            return []

    def _reciprocal_rank_fusion(
        self,
        vector_results: list[dict],
        bm25_results: list[dict],
        top_k: int,
        k: int = 60,
    ) -> list[dict]:
        """
        Combine vector + BM25 results using Reciprocal Rank Fusion (RRF).

        RRF score = Σ 1/(k + rank_i)  for each list i.
        """
        alpha = config.HYBRID_SEARCH_ALPHA  # weight for vector search

        rrf_scores: dict[str, float] = {}
        chunk_data: dict[str, dict] = {}

        # Score from vector list
        for rank, item in enumerate(vector_results):
            cid = item["chunk_id"]
            rrf_scores[cid] = rrf_scores.get(cid, 0.0) + alpha * (1.0 / (k + rank + 1))
            chunk_data[cid] = item

        # Score from BM25 list
        for rank, item in enumerate(bm25_results):
            cid = item["chunk_id"]
            rrf_scores[cid] = rrf_scores.get(cid, 0.0) + (1 - alpha) * (1.0 / (k + rank + 1))
            if cid not in chunk_data:
                chunk_data[cid] = item

        # Sort by fused score
        sorted_ids = sorted(rrf_scores, key=lambda x: rrf_scores[x], reverse=True)

        fused: list[dict] = []
        for cid in sorted_ids[:top_k]:
            item = chunk_data[cid].copy()
            item["score"] = min(1.0, rrf_scores[cid] * k)  # normalise to ~[0,1]
            fused.append(item)

        return fused

    def _rerank(
        self, query: str, candidates: list[dict], top_k: int
    ) -> list[dict]:
        """
        Use a cross-encoder model to rerank candidates.

        Args:
            query: Original user query.
            candidates: Candidate chunks from hybrid search.
            top_k: Final number to return.

        Returns:
            Reranked and sliced list.
        """
        try:
            pairs = [(query, c["text"]) for c in candidates]
            scores = self._reranker.predict(pairs)  # type: ignore[union-attr]
            for i, candidate in enumerate(candidates):
                candidate["score"] = float(
                    1 / (1 + np.exp(-scores[i]))  # sigmoid normalise
                )
            candidates.sort(key=lambda x: x["score"], reverse=True)
            logger.debug(f"Reranked {len(candidates)} → top {top_k}")
        except Exception as e:
            logger.warning(f"Reranking failed (using original order): {e}")

        return candidates[:top_k]

    # ─── Document Management ──────────────────────────────────────────────────

    def document_exists(self, file_hash: str) -> Optional[str]:
        """
        Check if a document with this hash is already indexed.

        Returns:
            Filename if found, None otherwise.
        """
        for fname, info in self._doc_registry.items():
            if info.file_hash == file_hash:
                return fname
        return None

    def get_all_documents(self) -> list[DocumentInfo]:
        """Return all indexed documents."""
        return list(self._doc_registry.values())

    def get_document(self, filename: str) -> Optional[DocumentInfo]:
        """Return info for a specific document."""
        return self._doc_registry.get(filename)

    def delete_document(self, filename: str) -> int:
        """
        Delete all chunks for a given filename from ChromaDB.

        Args:
            filename: Document to remove.

        Returns:
            Number of chunks deleted.
        """
        with self._lock:
            try:
                # Get all chunk IDs for this file
                results = self._collection.get(
                    where={"filename": filename},
                    include=["metadatas"],
                )
                ids_to_delete = results["ids"]
                if ids_to_delete:
                    self._collection.delete(ids=ids_to_delete)
                    logger.info(
                        f"Deleted {len(ids_to_delete)} chunks for {filename}"
                    )
                self._doc_registry.pop(filename, None)
                return len(ids_to_delete)
            except Exception as e:
                logger.error(f"Failed to delete document '{filename}': {e}")
                return 0

    def delete_all_documents(self) -> tuple[int, int]:
        """
        Delete ALL documents and chunks.

        Returns:
            Tuple of (documents_deleted, chunks_deleted).
        """
        with self._lock:
            doc_count = len(self._doc_registry)
            chunk_count = self._collection.count()
            try:
                self._client.delete_collection(config.CHROMA_COLLECTION_NAME)  # type: ignore[union-attr]
                self._collection = self._client.get_or_create_collection(  # type: ignore[union-attr]
                    name=config.CHROMA_COLLECTION_NAME,
                    metadata={"hnsw:space": config.CHROMA_DISTANCE_FUNCTION},
                )
                self._doc_registry.clear()
                logger.info(f"Deleted all {chunk_count} chunks across {doc_count} documents")
            except Exception as e:
                logger.error(f"delete_all_documents failed: {e}")
            return doc_count, chunk_count

    def total_chunks(self) -> int:
        """Return total number of stored chunks."""
        return self._collection.count()

    def collection_fingerprint(self) -> str:
        """
        Return a short hash representing the current collection state.
        Used as a cache invalidation key.
        """
        doc_hashes = sorted(
            info.file_hash for info in self._doc_registry.values()
        )
        return hashlib.md5("|".join(doc_hashes).encode()).hexdigest()[:12]

    def results_to_citations(
        self, results: list[dict], query: str
    ) -> list[SourceCitation]:
        """
        Convert raw search results into SourceCitation objects.

        Args:
            results: Search result dicts.
            query: Original query (used for snippet extraction).

        Returns:
            List of SourceCitation objects.
        """
        citations: list[SourceCitation] = []
        query_terms = query.lower().split()

        for r in results:
            snippet = extract_snippet(r["text"], query_terms, window=200)
            citation = SourceCitation(
                filename=r["filename"],
                page_number=r["page_number"],
                chunk_id=r["chunk_id"],
                relevance_score=round(r["score"], 4),
                snippet=snippet,
            )
            citations.append(citation)

        return citations


# ─── Singleton ────────────────────────────────────────────────────────────────
vector_store = VectorStoreService()
