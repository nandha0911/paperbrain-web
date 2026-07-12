"""
utils/hash_utils.py
===================
SHA-256 based file hashing for duplicate PDF detection.
"""

import hashlib
from pathlib import Path

from utils.logger import logger


def compute_file_hash(file_bytes: bytes) -> str:
    """
    Compute SHA-256 hash of raw file bytes.

    Args:
        file_bytes: Raw bytes of the uploaded file.

    Returns:
        Hex-encoded SHA-256 digest string.
    """
    sha256 = hashlib.sha256()
    sha256.update(file_bytes)
    digest = sha256.hexdigest()
    logger.debug(f"Computed SHA-256: {digest[:16]}...")
    return digest


def compute_path_hash(file_path: Path) -> str:
    """
    Compute SHA-256 hash by reading a file from disk.

    Args:
        file_path: Path to the file on disk.

    Returns:
        Hex-encoded SHA-256 digest string.
    """
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


def short_hash(file_hash: str, length: int = 8) -> str:
    """Return the first `length` characters of a hash (for display)."""
    return file_hash[:length]
