"""
services/pdf_service.py
=======================
PDF text extraction, cleaning, and chunking service.

Supports:
- Native text PDF (via pdfplumber + pypdf fallback)
- Scanned / image PDF (via pytesseract OCR)
- Multi-page documents
- Metadata extraction per chunk
"""

from __future__ import annotations

import io
import uuid
from pathlib import Path
from typing import Optional

import pdfplumber
import pytesseract
from PIL import Image
from pypdf import PdfReader
from langchain_text_splitters import RecursiveCharacterTextSplitter

import config
from models.document import ChunkMetadata
from utils.logger import logger
from utils.text_utils import clean_text, count_tokens_approx
from utils.hash_utils import compute_file_hash


class PDFService:
    """Handles PDF extraction, cleaning, and chunking."""

    def __init__(
        self,
        chunk_size: int = config.CHUNK_SIZE,
        chunk_overlap: int = config.CHUNK_OVERLAP,
        min_chunk_length: int = config.CHUNK_MIN_LENGTH,
    ) -> None:
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.min_chunk_length = min_chunk_length

        self._splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            length_function=len,
            separators=["\n\n", "\n", ". ", "? ", "! ", " ", ""],
        )
        logger.info(
            f"PDFService ready | chunk_size={chunk_size} | overlap={chunk_overlap}"
        )

    # ─── Public API ───────────────────────────────────────────────────────────

    def process_pdf(
        self, file_bytes: bytes, filename: str
    ) -> tuple[list[ChunkMetadata], int, str]:
        """
        Full pipeline: read → extract → clean → chunk → return metadata.

        Args:
            file_bytes: Raw bytes of the uploaded PDF.
            filename: Sanitised filename (used in metadata).

        Returns:
            Tuple of:
                - List of ChunkMetadata objects
                - Page count
                - File hash (SHA-256)
        """
        file_hash = compute_file_hash(file_bytes)
        logger.info(f"Processing PDF: {filename} | hash={file_hash[:8]}")

        # Extract text per page
        pages_text = self._extract_pages(file_bytes, filename)
        page_count = len(pages_text)
        logger.info(f"Extracted {page_count} pages from {filename}")

        # Build chunks with metadata
        chunks = self._chunk_pages(pages_text, filename, file_hash)
        logger.info(f"Created {len(chunks)} chunks from {filename}")

        return chunks, page_count, file_hash

    def get_page_count(self, file_bytes: bytes) -> int:
        """Return the number of pages in a PDF without full processing."""
        try:
            reader = PdfReader(io.BytesIO(file_bytes))
            return len(reader.pages)
        except Exception:
            return 0

    # ─── Private Methods ──────────────────────────────────────────────────────

    def _extract_pages(self, file_bytes: bytes, filename: str) -> list[str]:
        """
        Extract text from each page, falling back to OCR for image pages.

        Returns:
            List of cleaned text strings, one per page.
        """
        pages_text: list[str] = []

        try:
            with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
                for page_num, page in enumerate(pdf.pages, start=1):
                    raw = page.extract_text() or ""

                    # If pdfplumber got nothing, try OCR
                    if len(raw.strip()) < 30:
                        raw = self._ocr_page(file_bytes, page_num - 1)

                    cleaned = clean_text(raw)
                    pages_text.append(cleaned)
        except Exception as e:
            logger.warning(
                f"pdfplumber failed for {filename}: {e} — falling back to pypdf"
            )
            pages_text = self._extract_with_pypdf(file_bytes, filename)

        return pages_text

    def _extract_with_pypdf(self, file_bytes: bytes, filename: str) -> list[str]:
        """Fallback extraction using pypdf."""
        pages_text: list[str] = []
        try:
            reader = PdfReader(io.BytesIO(file_bytes))
            for page in reader.pages:
                raw = page.extract_text() or ""
                pages_text.append(clean_text(raw))
        except Exception as e:
            logger.error(f"pypdf also failed for {filename}: {e}")
        return pages_text

    def _ocr_page(self, file_bytes: bytes, page_index: int) -> str:
        """
        Run Tesseract OCR on a single PDF page rendered as an image.
        Requires: poppler (pdf2image) and tesseract installed on system.
        """
        try:
            from pdf2image import convert_from_bytes  # lazy import

            images = convert_from_bytes(
                file_bytes,
                first_page=page_index + 1,
                last_page=page_index + 1,
                dpi=200,
            )
            if images:
                text = pytesseract.image_to_string(images[0])
                logger.debug(f"OCR page {page_index + 1}: {len(text)} chars")
                return text
        except Exception as e:
            logger.warning(f"OCR failed for page {page_index + 1}: {e}")
        return ""

    def _chunk_pages(
        self,
        pages_text: list[str],
        filename: str,
        file_hash: str,
    ) -> list[ChunkMetadata]:
        """
        Split each page's text into chunks and build ChunkMetadata objects.

        Args:
            pages_text: Cleaned text for each page (0-indexed → page 1..N).
            filename: Source filename.
            file_hash: SHA-256 hash of the source file.

        Returns:
            List of ChunkMetadata across all pages.
        """
        all_chunks: list[ChunkMetadata] = []
        chunk_index = 0

        for page_num, text in enumerate(pages_text, start=1):
            if not text.strip():
                continue

            splits = self._splitter.split_text(text)
            for split_text in splits:
                # Skip chunks that are too short (noise)
                if len(split_text.strip()) < self.min_chunk_length:
                    continue

                char_start = text.find(split_text)
                char_end = char_start + len(split_text) if char_start != -1 else -1

                chunk = ChunkMetadata(
                    chunk_id=str(uuid.uuid4()),
                    filename=filename,
                    file_hash=file_hash,
                    page_number=page_num,
                    chunk_index=chunk_index,
                    char_start=max(0, char_start),
                    char_end=max(0, char_end),
                    chunk_text=split_text.strip(),
                    total_chunks=0,  # updated below
                )
                all_chunks.append(chunk)
                chunk_index += 1

        # Update total_chunks on all entries
        total = len(all_chunks)
        for chunk in all_chunks:
            chunk.total_chunks = total

        return all_chunks


# ─── Singleton ────────────────────────────────────────────────────────────────
pdf_service = PDFService()
