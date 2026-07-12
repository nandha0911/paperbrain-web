"""
models/document.py
==================
Pydantic data models for PDF documents and upload responses.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class ProcessingStatus(str, Enum):
    """Document processing status."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class ChunkMetadata(BaseModel):
    """Metadata attached to every stored vector chunk."""
    chunk_id: str
    filename: str
    file_hash: str
    page_number: int
    chunk_index: int
    char_start: int
    char_end: int
    chunk_text: str
    total_chunks: int


class DocumentInfo(BaseModel):
    """Information about an uploaded and indexed document."""
    filename: str
    file_hash: str
    file_size_bytes: int
    page_count: int
    chunk_count: int
    status: ProcessingStatus
    uploaded_at: datetime = Field(default_factory=datetime.utcnow)
    error_message: Optional[str] = None

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


class UploadResponse(BaseModel):
    """Response returned after uploading a PDF."""
    filename: str
    file_hash: str
    file_size_bytes: int
    page_count: int
    chunk_count: int
    status: ProcessingStatus
    message: str
    already_exists: bool = False
    processing_time_ms: int


class DocumentListResponse(BaseModel):
    """List of all indexed documents."""
    documents: list[DocumentInfo]
    total_documents: int
    total_chunks: int


class DeleteDocumentResponse(BaseModel):
    """Response after deleting a document."""
    filename: str
    message: str
    chunks_deleted: int


class DeleteAllResponse(BaseModel):
    """Response after deleting all documents."""
    message: str
    documents_deleted: int
    chunks_deleted: int
