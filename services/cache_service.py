"""
services/cache_service.py
=========================
LRU + TTL cache for RAG query results to avoid redundant LLM calls.
"""

import hashlib
import time
from collections import OrderedDict
from typing import Any, Optional

import config
from utils.logger import logger


class CacheEntry:
    """Single cached entry with TTL support."""

    __slots__ = ("value", "expires_at")

    def __init__(self, value: Any, ttl: int) -> None:
        self.value = value
        self.expires_at: float = time.monotonic() + ttl

    def is_expired(self) -> bool:
        return time.monotonic() > self.expires_at


class QueryCache:
    """
    Thread-safe LRU cache with TTL for RAG responses.

    Uses an OrderedDict to maintain LRU order (most-recently-used at end).
    """

    def __init__(
        self,
        max_size: int = config.CACHE_MAX_SIZE,
        ttl: int = config.CACHE_TTL_SECONDS,
        enabled: bool = config.CACHE_ENABLED,
    ) -> None:
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self.max_size = max_size
        self.ttl = ttl
        self.enabled = enabled
        self._hits = 0
        self._misses = 0
        logger.info(
            f"QueryCache initialised | max_size={max_size} | ttl={ttl}s | enabled={enabled}"
        )

    def _make_key(self, question: str, collection_fingerprint: str) -> str:
        """Create a deterministic cache key from question + collection state."""
        raw = f"{question.strip().lower()}|{collection_fingerprint}"
        return hashlib.md5(raw.encode()).hexdigest()

    def get(self, question: str, collection_fingerprint: str) -> Optional[Any]:
        """
        Retrieve a cached result.

        Args:
            question: User question.
            collection_fingerprint: Hash representing current document collection.

        Returns:
            Cached value, or None on cache miss / expiry.
        """
        if not self.enabled:
            return None

        key = self._make_key(question, collection_fingerprint)
        entry = self._cache.get(key)

        if entry is None:
            self._misses += 1
            return None

        if entry.is_expired():
            del self._cache[key]
            self._misses += 1
            logger.debug(f"Cache EXPIRED for key {key[:8]}")
            return None

        # Move to end (most recently used)
        self._cache.move_to_end(key)
        self._hits += 1
        logger.debug(f"Cache HIT for key {key[:8]}")
        return entry.value

    def set(self, question: str, collection_fingerprint: str, value: Any) -> None:
        """
        Store a result in the cache.

        Args:
            question: User question.
            collection_fingerprint: Hash representing current document collection.
            value: Response to cache.
        """
        if not self.enabled:
            return

        key = self._make_key(question, collection_fingerprint)

        if key in self._cache:
            self._cache.move_to_end(key)
        self._cache[key] = CacheEntry(value, self.ttl)

        # Evict LRU entry if over capacity
        if len(self._cache) > self.max_size:
            evicted_key, _ = self._cache.popitem(last=False)
            logger.debug(f"Cache EVICT for key {evicted_key[:8]}")

        logger.debug(f"Cache SET for key {key[:8]}")

    def invalidate(self) -> int:
        """Clear all cache entries. Returns number of entries removed."""
        count = len(self._cache)
        self._cache.clear()
        logger.info(f"Cache CLEARED: {count} entries removed")
        return count

    @property
    def stats(self) -> dict:
        """Return cache statistics."""
        total = self._hits + self._misses
        hit_rate = (self._hits / total * 100) if total > 0 else 0.0
        return {
            "size": len(self._cache),
            "max_size": self.max_size,
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate_pct": round(hit_rate, 1),
            "enabled": self.enabled,
        }


# ─── Singleton instance ───────────────────────────────────────────────────────
query_cache = QueryCache()
