"""
services/embedding_service.py
==============================
Sentence Transformer embedding service.

Uses BAAI/bge-small-en-v1.5 by default.
Supports batch encoding with progress tracking.
"""

from __future__ import annotations

import threading
from typing import Optional

import numpy as np
from sentence_transformers import SentenceTransformer

import config
from utils.logger import logger


class EmbeddingService:
    """
    Singleton embedding service backed by a Sentence Transformer model.

    Thread-safe: model is loaded once and reused across requests.
    """

    _instance: Optional["EmbeddingService"] = None
    _lock = threading.Lock()

    def __new__(cls) -> "EmbeddingService":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    instance = super().__new__(cls)
                    instance._model = None
                    instance._model_name = None
                    cls._instance = instance
        return cls._instance

    # ─── Model Loading ────────────────────────────────────────────────────────

    def _load_model(self) -> SentenceTransformer:
        """Lazy-load the Sentence Transformer model."""
        if self._model is None or self._model_name != config.EMBEDDING_MODEL:
            logger.info(
                f"Loading embedding model: {config.EMBEDDING_MODEL} "
                f"on device={config.EMBEDDING_DEVICE}"
            )
            self._model = SentenceTransformer(
                config.EMBEDDING_MODEL,
                device=config.EMBEDDING_DEVICE,
            )
            self._model_name = config.EMBEDDING_MODEL
            logger.info(
                f"Embedding model loaded | dim={self.embedding_dim}"
            )
        return self._model

    @property
    def model(self) -> SentenceTransformer:
        """Return (and lazily load) the embedding model."""
        return self._load_model()

    @property
    def embedding_dim(self) -> int:
        """Return the embedding dimension of the loaded model."""
        return self.model.get_sentence_embedding_dimension()

    # ─── Encoding ─────────────────────────────────────────────────────────────

    def encode_texts(
        self,
        texts: list[str],
        batch_size: int = config.EMBEDDING_BATCH_SIZE,
        show_progress: bool = False,
        normalize: bool = True,
    ) -> np.ndarray:
        """
        Encode a list of texts into embedding vectors.

        Args:
            texts: Input strings to encode.
            batch_size: Number of texts to encode per batch.
            show_progress: Show tqdm progress bar.
            normalize: L2-normalize embeddings (required for cosine similarity).

        Returns:
            numpy array of shape (len(texts), embedding_dim).
        """
        if not texts:
            return np.array([])

        logger.debug(
            f"Encoding {len(texts)} texts | batch_size={batch_size}"
        )
        embeddings = self.model.encode(
            texts,
            batch_size=batch_size,
            show_progress_bar=show_progress,
            normalize_embeddings=normalize,
            convert_to_numpy=True,
        )
        return embeddings  # type: ignore[return-value]

    def encode_query(self, query: str, normalize: bool = True) -> np.ndarray:
        """
        Encode a single query string.

        BGE models benefit from a query instruction prefix.

        Args:
            query: User query string.
            normalize: L2-normalize the output.

        Returns:
            1-D numpy array of shape (embedding_dim,).
        """
        # BGE models use a special instruction prefix for queries
        if "bge" in config.EMBEDDING_MODEL.lower():
            query = f"Represent this sentence for searching relevant passages: {query}"

        embedding = self.model.encode(
            query,
            normalize_embeddings=normalize,
            convert_to_numpy=True,
        )
        return embedding  # type: ignore[return-value]

    def cosine_similarity(
        self, vec_a: np.ndarray, vec_b: np.ndarray
    ) -> float:
        """
        Compute cosine similarity between two normalised vectors.

        Args:
            vec_a: First embedding vector.
            vec_b: Second embedding vector.

        Returns:
            Cosine similarity in range [-1, 1].
        """
        if vec_a.ndim == 1:
            vec_a = vec_a.reshape(1, -1)
        if vec_b.ndim == 1:
            vec_b = vec_b.reshape(1, -1)

        dot = np.dot(vec_a, vec_b.T)
        norm_a = np.linalg.norm(vec_a)
        norm_b = np.linalg.norm(vec_b)
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return float(dot / (norm_a * norm_b))


# ─── Singleton ────────────────────────────────────────────────────────────────
embedding_service = EmbeddingService()
