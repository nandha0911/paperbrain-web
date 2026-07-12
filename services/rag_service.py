"""
services/rag_service.py
=======================
Full RAG pipeline orchestrator.

Coordinates:
1. Receive user question
2. Rephrase follow-up questions using conversation history
3. Hybrid search + reranking
4. Confidence filtering
5. Prompt construction
6. LLM generation (sync + streaming)
7. Source citation assembly
8. Conversation memory management
"""

from __future__ import annotations

import time
from collections import defaultdict
from typing import Iterator, Optional

import config
from models.chat import ChatMessage, ChatRequest, ChatResponse, MessageRole, SourceCitation
from prompts.templates import (
    NO_CONTEXT_RESPONSE,
    NO_DOCUMENTS_RESPONSE,
    LOW_CONFIDENCE_RESPONSE,
    RAG_SYSTEM_PROMPT,
    build_rag_prompt,
    build_rephrase_prompt,
    format_context_chunks,
    format_history,
    validate_answer,
)
from services.cache_service import query_cache
from services.embedding_service import embedding_service
from services.llm_service import llm_service
from services.vector_store import vector_store
from utils.logger import logger


class ConversationMemory:
    """
    Per-session conversation history (last N turns).
    Stored in-process memory; reset on server restart.
    """

    def __init__(self, window_size: int = config.MEMORY_WINDOW_SIZE) -> None:
        self._sessions: dict[str, list[ChatMessage]] = defaultdict(list)
        self.window_size = window_size

    def add(self, session_id: str, message: ChatMessage) -> None:
        """Append a message to a session's history."""
        self._sessions[session_id].append(message)
        # Trim to window (keep last N messages)
        if len(self._sessions[session_id]) > self.window_size * 2:
            self._sessions[session_id] = self._sessions[session_id][-self.window_size * 2:]

    def get(self, session_id: str) -> list[ChatMessage]:
        """Retrieve all messages for a session."""
        return self._sessions.get(session_id, [])

    def clear(self, session_id: str) -> int:
        """Clear history for a session. Returns number of messages cleared."""
        count = len(self._sessions.get(session_id, []))
        self._sessions.pop(session_id, None)
        return count

    def get_as_dicts(self, session_id: str) -> list[dict]:
        """Return history as a list of role/content dicts for prompt building."""
        return [
            {"role": m.role.value, "content": m.content}
            for m in self._sessions.get(session_id, [])
        ]

    def all_sessions(self) -> list[str]:
        """Return all active session IDs."""
        return list(self._sessions.keys())


class RAGService:
    """
    Orchestrates the full Retrieval-Augmented Generation pipeline.
    """

    def __init__(self) -> None:
        self.memory = ConversationMemory()
        logger.info("RAGService initialised")

    # ─── Public: Synchronous Chat ─────────────────────────────────────────────

    def chat(self, request: ChatRequest) -> ChatResponse:
        """
        Process a chat request through the full RAG pipeline.

        Args:
            request: Validated ChatRequest containing question and session_id.

        Returns:
            ChatResponse with answer, sources, and confidence.
        """
        start_time = time.time()
        session_id = request.session_id

        # ── Guard: no documents uploaded ────────────────────────────────────
        if vector_store.total_chunks() == 0:
            return self._no_docs_response(request, start_time)

        # ── Rephrase follow-up questions ─────────────────────────────────────
        standalone_question = self._rephrase_if_needed(
            request.question, session_id
        )
        logger.info(
            f"[{session_id}] Q: '{request.question}' → "
            f"Standalone: '{standalone_question}'"
        )

        # ── Cache check ───────────────────────────────────────────────────────
        fingerprint = vector_store.collection_fingerprint()
        cached = query_cache.get(standalone_question, fingerprint)
        if cached:
            logger.info(f"[{session_id}] Cache HIT")
            response = cached
            response.from_cache = True
            self._save_to_memory(session_id, request.question, response.answer, response.sources)
            return response

        # ── Hybrid Search ─────────────────────────────────────────────────────
        search_results = vector_store.search(
            standalone_question, top_k=request.top_k
        )
        chunks_retrieved = len(search_results)

        # ── Confidence check ─────────────────────────────────────────────────
        if not search_results:
            return self._low_confidence_response(
                request, session_id, start_time, LOW_CONFIDENCE_RESPONSE
            )

        max_score = max(r["score"] for r in search_results)
        if max_score < config.CONFIDENCE_THRESHOLD:
            return self._low_confidence_response(
                request, session_id, start_time, LOW_CONFIDENCE_RESPONSE, max_score
            )

        # ── Build prompt ──────────────────────────────────────────────────────
        context_str = format_context_chunks(search_results)
        history_str = format_history(
            self.memory.get_as_dicts(session_id),
            max_turns=config.MEMORY_WINDOW_SIZE,
        )
        user_prompt = build_rag_prompt(
            context=context_str,
            question=standalone_question,
            history=history_str,
        )

        # ── LLM call ─────────────────────────────────────────────────────────
        try:
            raw_answer = llm_service.generate(RAG_SYSTEM_PROMPT, user_prompt)
            # Post-process: catch hallucinations / outside-knowledge answers
            answer = validate_answer(raw_answer, context_str)
        except Exception as e:
            logger.error(f"LLM error: {e}")
            answer = f"I encountered an error while generating the answer: {str(e)}"

        # ── Build citations ───────────────────────────────────────────────────
        citations = vector_store.results_to_citations(search_results, standalone_question)

        processing_ms = int((time.time() - start_time) * 1000)
        response = ChatResponse(
            answer=answer,
            sources=citations,
            confidence=round(max_score, 4),
            session_id=session_id,
            processing_time_ms=processing_ms,
            chunks_retrieved=chunks_retrieved,
            from_cache=False,
        )

        # ── Cache + Memory ────────────────────────────────────────────────────
        query_cache.set(standalone_question, fingerprint, response)
        self._save_to_memory(session_id, request.question, answer, citations)

        logger.info(
            f"[{session_id}] Answer generated | confidence={max_score:.3f} | "
            f"chunks={chunks_retrieved} | time={processing_ms}ms"
        )
        return response

    # ─── Public: Streaming Chat ───────────────────────────────────────────────

    def chat_stream(
        self, request: ChatRequest
    ) -> Iterator[dict]:
        """
        Stream chat response tokens.

        Yields dicts:
          {"type": "token", "content": "..."}
          {"type": "sources", "sources": [...]}
          {"type": "done", "confidence": 0.xx, "processing_time_ms": N}
        """
        start_time = time.time()
        session_id = request.session_id

        if vector_store.total_chunks() == 0:
            yield {"type": "token", "content": NO_DOCUMENTS_RESPONSE}
            yield {"type": "done", "confidence": 0.0, "processing_time_ms": 0}
            return

        standalone_question = self._rephrase_if_needed(request.question, session_id)

        search_results = vector_store.search(
            standalone_question, top_k=request.top_k
        )
        max_score = max((r["score"] for r in search_results), default=0.0)

        if not search_results or max_score < config.CONFIDENCE_THRESHOLD:
            yield {"type": "token", "content": LOW_CONFIDENCE_RESPONSE}
            yield {"type": "done", "confidence": 0.0, "processing_time_ms": 0}
            return

        context_str = format_context_chunks(search_results)
        history_str = format_history(
            self.memory.get_as_dicts(session_id),
            max_turns=config.MEMORY_WINDOW_SIZE,
        )
        user_prompt = build_rag_prompt(
            context=context_str,
            question=standalone_question,
            history=history_str,
        )

        # Stream tokens
        full_answer = ""
        try:
            for token in llm_service.stream(RAG_SYSTEM_PROMPT, user_prompt):
                full_answer += token
                yield {"type": "token", "content": token}
        except Exception as e:
            logger.error(f"LLM stream error: {e}")
            yield {"type": "token", "content": f"\n[Error: {e}]"}

        # Post-process streamed answer for hallucinations
        validated = validate_answer(full_answer, context_str)
        if validated != full_answer.strip():
            # Answer was replaced — emit correction
            yield {"type": "correction", "content": validated}
            full_answer = validated

        citations = vector_store.results_to_citations(search_results, standalone_question)
        processing_ms = int((time.time() - start_time) * 1000)

        yield {
            "type": "sources",
            "sources": [c.model_dump() for c in citations],
        }
        yield {
            "type": "done",
            "confidence": round(max_score, 4),
            "processing_time_ms": processing_ms,
        }

        self._save_to_memory(session_id, request.question, full_answer, citations)

    # ─── History Management ───────────────────────────────────────────────────

    def get_history(self, session_id: str) -> list[ChatMessage]:
        """Return conversation history for a session."""
        return self.memory.get(session_id)

    def clear_history(self, session_id: str) -> int:
        """Clear history for a session. Returns messages cleared."""
        return self.memory.clear(session_id)

    # ─── Private Helpers ──────────────────────────────────────────────────────

    def _rephrase_if_needed(
        self, question: str, session_id: str
    ) -> str:
        """
        Rephrase follow-up questions to be standalone.
        Only runs if there is prior history in the session.
        """
        history = self.memory.get_as_dicts(session_id)
        if not history:
            return question  # First message — no need to rephrase

        # Check for pronouns / references that suggest follow-up
        follow_up_signals = [
            "he", "she", "they", "it", "his", "her", "their", "its",
            "that", "this", "these", "those", "there", "the same",
        ]
        lower_q = question.lower()
        is_follow_up = any(
            f" {signal} " in f" {lower_q} " or lower_q.startswith(signal + " ")
            for signal in follow_up_signals
        )

        if not is_follow_up:
            return question

        # Ask LLM to rephrase
        try:
            history_str = format_history(history, max_turns=6)
            rephrase_prompt = build_rephrase_prompt(question, history_str)
            from prompts.templates import REPHRASE_SYSTEM_PROMPT
            standalone = llm_service.generate(REPHRASE_SYSTEM_PROMPT, rephrase_prompt)
            standalone = standalone.strip().strip('"').strip("'")
            logger.debug(f"Rephrased: '{question}' → '{standalone}'")
            return standalone if standalone else question
        except Exception as e:
            logger.warning(f"Rephrase failed: {e} — using original question")
            return question

    def _save_to_memory(
        self,
        session_id: str,
        question: str,
        answer: str,
        citations: list[SourceCitation],
    ) -> None:
        """Persist Q&A pair to conversation memory."""
        user_msg = ChatMessage(role=MessageRole.USER, content=question)
        assistant_msg = ChatMessage(
            role=MessageRole.ASSISTANT,
            content=answer,
            sources=citations,
        )
        self.memory.add(session_id, user_msg)
        self.memory.add(session_id, assistant_msg)

    def _no_docs_response(
        self, request: ChatRequest, start_time: float
    ) -> ChatResponse:
        """Return response when no documents are uploaded."""
        return ChatResponse(
            answer=NO_DOCUMENTS_RESPONSE,
            sources=[],
            confidence=0.0,
            session_id=request.session_id,
            processing_time_ms=int((time.time() - start_time) * 1000),
            chunks_retrieved=0,
        )

    def _low_confidence_response(
        self,
        request: ChatRequest,
        session_id: str,
        start_time: float,
        message: str,
        confidence: float = 0.0,
    ) -> ChatResponse:
        """Return response when confidence threshold not met."""
        self._save_to_memory(session_id, request.question, message, [])
        return ChatResponse(
            answer=message,
            sources=[],
            confidence=round(confidence, 4),
            session_id=session_id,
            processing_time_ms=int((time.time() - start_time) * 1000),
            chunks_retrieved=0,
        )


# ─── Singleton ────────────────────────────────────────────────────────────────
rag_service = RAGService()
