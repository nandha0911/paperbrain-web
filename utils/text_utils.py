"""
utils/text_utils.py
===================
Text cleaning and normalisation utilities for extracted PDF content.
"""

import re
import unicodedata

from utils.logger import logger


def clean_text(text: str) -> str:
    """
    Clean and normalise raw PDF text.

    Steps:
    1. Unicode normalisation (NFKC)
    2. Remove null bytes and control characters
    3. Collapse excessive whitespace
    4. Remove repeated punctuation noise
    5. Strip leading/trailing whitespace

    Args:
        text: Raw text extracted from a PDF page.

    Returns:
        Cleaned text string.
    """
    if not text:
        return ""

    # 1. Unicode normalisation
    text = unicodedata.normalize("NFKC", text)

    # 2. Remove null bytes / non-printable control chars (keep newlines/tabs)
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)

    # 3. Remove ligatures and replace with ASCII equivalents
    ligatures = {
        "ﬁ": "fi", "ﬂ": "fl", "ﬀ": "ff", "ﬃ": "ffi",
        "ﬄ": "ffl", "ﬅ": "st", "ﬆ": "st",
    }
    for lig, rep in ligatures.items():
        text = text.replace(lig, rep)

    # 4. Collapse multiple spaces / tabs (but keep single newlines)
    text = re.sub(r"[ \t]+", " ", text)

    # 5. Collapse 3+ consecutive newlines into double newline (paragraph break)
    text = re.sub(r"\n{3,}", "\n\n", text)

    # 6. Remove lines that are just dashes, dots, or underscores (table rules)
    text = re.sub(r"^\s*[-_.=]{3,}\s*$", "", text, flags=re.MULTILINE)

    # 7. Strip leading/trailing whitespace
    text = text.strip()

    return text


def truncate_text(text: str, max_chars: int = 200, suffix: str = "...") -> str:
    """
    Truncate text to max_chars characters, appending suffix if truncated.

    Args:
        text: Input text.
        max_chars: Maximum characters allowed.
        suffix: Appended when truncated.

    Returns:
        Truncated string.
    """
    if len(text) <= max_chars:
        return text
    return text[: max_chars - len(suffix)].rstrip() + suffix


def extract_snippet(text: str, query_terms: list[str], window: int = 150) -> str:
    """
    Extract a relevant snippet from text around the first query term match.

    Args:
        text: Full chunk text.
        query_terms: List of query keywords to search for.
        window: Number of characters to include around match.

    Returns:
        Snippet string with surrounding context.
    """
    lower = text.lower()
    for term in query_terms:
        idx = lower.find(term.lower())
        if idx != -1:
            start = max(0, idx - window // 2)
            end = min(len(text), idx + len(term) + window // 2)
            snippet = text[start:end].strip()
            if start > 0:
                snippet = "..." + snippet
            if end < len(text):
                snippet = snippet + "..."
            return snippet
    return truncate_text(text, window * 2)


def count_tokens_approx(text: str) -> int:
    """
    Approximate token count (1 token ≈ 4 characters).

    Args:
        text: Input text.

    Returns:
        Approximate token count.
    """
    return max(1, len(text) // 4)
