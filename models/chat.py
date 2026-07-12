"""
models/chat.py
==============
Pydantic data models for chat requests, responses, and history.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class MessageRole(str, Enum):
    """Enumeration of chat message roles."""
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class SourceCitation(BaseModel):
    """Represents a source document citation."""
    filename: str = Field(..., description="Name of the source PDF file")
    page_number: int = Field(..., description="Page number in the PDF (1-indexed)")
    chunk_id: str = Field(..., description="Unique chunk identifier")
    relevance_score: float = Field(..., ge=0.0, le=1.0, description="Cosine similarity score")
    snippet: str = Field(..., description="Short text excerpt from the source chunk")


class ChatMessage(BaseModel):
    """A single message in the conversation."""
    role: MessageRole
    content: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    sources: list[SourceCitation] = Field(default_factory=list)
    confidence: Optional[float] = Field(None, ge=0.0, le=1.0)
    processing_time_ms: Optional[int] = None

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


class ChatRequest(BaseModel):
    """Incoming chat request payload."""
    question: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="User's question",
    )
    session_id: str = Field(
        default="default",
        description="Session identifier for conversation memory",
    )
    top_k: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Number of chunks to retrieve",
    )
    stream: bool = Field(
        default=False,
        description="Whether to stream the response",
    )


class ChatResponse(BaseModel):
    """Response returned by the chat endpoint."""
    answer: str
    sources: list[SourceCitation] = Field(default_factory=list)
    confidence: float = Field(0.0, ge=0.0, le=1.0)
    session_id: str
    processing_time_ms: int
    chunks_retrieved: int
    from_cache: bool = False


class HistoryResponse(BaseModel):
    """Full conversation history for a session."""
    session_id: str
    messages: list[ChatMessage]
    total_messages: int


class ClearHistoryResponse(BaseModel):
    """Response after clearing chat history."""
    session_id: str
    message: str
    cleared_count: int
