"""
prompts/templates.py
====================
All prompt templates used in the RAG pipeline.
STRICT enforcement: chatbot ONLY answers from uploaded PDFs.
"""

from string import Template


# ─── Main RAG System Prompt (Very Strict) ────────────────────────────────────
RAG_SYSTEM_PROMPT = """You are a STRICT document-only assistant. You have NO general knowledge and NO ability to answer from memory.

YOUR ONLY SOURCE OF TRUTH: The context blocks provided below. Nothing else.

ABSOLUTE RULES — never break these:
1. ONLY use information explicitly written in the provided context blocks.
2. If the exact answer is NOT found in the context, you MUST reply EXACTLY:
   "I don't have information about that in the uploaded documents."
3. NEVER use your training knowledge, general facts, or assumptions.
4. NEVER say things like "generally", "typically", "in most cases" — these imply outside knowledge.
5. NEVER guess or infer beyond what the context explicitly states.
6. If context is partially relevant, share only what is stated and say the rest is not in the documents.
7. Do NOT confirm or deny facts not in the context — just say it's not in the documents.

VIOLATION CHECK: Before answering, ask yourself — "Is this answer word-for-word supported by the context?" If NO → reply with the standard not-found message."""


# ─── Main RAG User Prompt ─────────────────────────────────────────────────────
RAG_USER_PROMPT_TEMPLATE = Template("""=== DOCUMENT CONTEXT (YOUR ONLY SOURCE) ===
$context
=== END OF DOCUMENT CONTEXT ===

=== CONVERSATION HISTORY ===
$history
=== END OF CONVERSATION HISTORY ===

=== QUESTION ===
$question

=== YOUR TASK ===
1. Search ONLY in the DOCUMENT CONTEXT above for the answer.
2. If the answer exists in the context → answer it clearly and cite the source.
3. If the answer does NOT exist in the context → reply EXACTLY with this phrase:
   "I don't have information about that in the uploaded documents."
4. Do NOT use any knowledge from your training. Only the context above.

=== ANSWER ===
""")


# ─── Standalone Question Rephrasing Prompt ───────────────────────────────────
REPHRASE_SYSTEM_PROMPT = """You are a question reformulator.
Given a conversation history and a follow-up question, rephrase the follow-up question
to be standalone and self-contained, preserving the original intent.
Return ONLY the rephrased question, nothing else. No explanation."""

REPHRASE_USER_TEMPLATE = Template("""Conversation History:
$history

Follow-up Question: $question

Rephrased standalone question:""")


# ─── Standard Response Strings ────────────────────────────────────────────────
NO_CONTEXT_RESPONSE = (
    "I don't have information about that in the uploaded documents."
)

LOW_CONFIDENCE_RESPONSE = (
    "I don't have information about that in the uploaded documents."
)

NO_DOCUMENTS_RESPONSE = (
    "No documents have been uploaded yet. Please upload one or more PDF files to get started."
)

# Keywords that indicate the LLM answered from its own knowledge (hallucination signals)
HALLUCINATION_SIGNALS = [
    "generally speaking",
    "in general",
    "typically",
    "usually",
    "it is commonly known",
    "as we know",
    "as is well known",
    "from my knowledge",
    "based on my training",
    "i believe",
    "i think",
    "i know that",
    "it is a fact",
    "historically",
    "in most cases",
    "broadly speaking",
    "as a general rule",
]


def validate_answer(answer: str, context: str) -> str:
    """
    Post-process LLM answer to catch hallucinations.

    If the answer contains hallucination signals AND the question topic
    is not in the context, replace with the standard not-found response.

    Args:
        answer: Raw LLM output.
        context: The context string used in the prompt.

    Returns:
        Validated answer string.
    """
    if not answer or not answer.strip():
        return NO_CONTEXT_RESPONSE

    answer_lower = answer.lower().strip()

    # If LLM already said the not-found phrase, keep it clean
    if "i don't have information" in answer_lower or "i do not have information" in answer_lower:
        return NO_CONTEXT_RESPONSE

    # Check for hallucination signal phrases
    for signal in HALLUCINATION_SIGNALS:
        if signal in answer_lower:
            return NO_CONTEXT_RESPONSE

    # If context was empty/not found, force the standard response
    if context.strip() in ("No relevant context found.", ""):
        return NO_CONTEXT_RESPONSE

    return answer.strip()


def build_rag_prompt(
    context: str,
    question: str,
    history: str = "",
) -> str:
    """
    Build the complete RAG user prompt.

    Args:
        context: Retrieved and formatted chunk context.
        question: User's (possibly rephrased) question.
        history: Formatted conversation history string.

    Returns:
        Formatted prompt string.
    """
    return RAG_USER_PROMPT_TEMPLATE.substitute(
        context=context,
        question=question,
        history=history or "No previous conversation.",
    )


def build_rephrase_prompt(question: str, history: str) -> str:
    """
    Build the question rephrasing prompt.

    Args:
        question: Follow-up question from the user.
        history: Recent conversation history.

    Returns:
        Formatted rephrase prompt string.
    """
    return REPHRASE_USER_TEMPLATE.substitute(
        history=history,
        question=question,
    )


def format_context_chunks(chunks: list[dict]) -> str:
    """
    Format a list of retrieved chunks into a numbered context string.

    Args:
        chunks: List of dicts with keys: text, filename, page_number, score.

    Returns:
        Formatted multi-line context string.
    """
    if not chunks:
        return "No relevant context found."

    parts: list[str] = []
    for i, chunk in enumerate(chunks, start=1):
        source_label = (
            f"[Source {i} | File: {chunk['filename']} | Page: {chunk['page_number']} "
            f"| Relevance: {round(chunk.get('score', 0) * 100)}%]"
        )
        parts.append(f"{source_label}\n{chunk['text'].strip()}")

    return "\n\n---\n\n".join(parts)


def format_history(messages: list[dict], max_turns: int = 10) -> str:
    """
    Format conversation history for inclusion in prompts.

    Args:
        messages: List of dicts with keys: role, content.
        max_turns: Maximum number of turns to include.

    Returns:
        Formatted history string.
    """
    if not messages:
        return ""

    recent = messages[-max_turns:]
    lines: list[str] = []
    for msg in recent:
        role = "User" if msg["role"] == "user" else "Assistant"
        lines.append(f"{role}: {msg['content']}")
    return "\n".join(lines)
