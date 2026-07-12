"""
utils/file_utils.py
===================
File validation, sanitisation, and helper utilities for PDF uploads.
"""

import re
from pathlib import Path

import config
from utils.logger import logger


def sanitize_filename(filename: str) -> str:
    """
    Sanitise an uploaded filename to prevent path traversal and injection.

    Steps:
    - Keep only alphanumeric chars, hyphens, underscores, dots
    - Replace spaces with underscores
    - Strip leading dots (hidden files on Unix)
    - Limit to 200 characters

    Args:
        filename: Original filename from the upload.

    Returns:
        Safe sanitised filename.
    """
    # Get just the name (no directory components)
    name = Path(filename).name

    # Replace spaces with underscores
    name = name.replace(" ", "_")

    # Keep only safe characters
    name = re.sub(r"[^\w\-.]", "", name)

    # Remove leading dots
    name = name.lstrip(".")

    # Limit length (preserve extension)
    stem = Path(name).stem[:190]
    suffix = Path(name).suffix
    name = stem + suffix

    if not name:
        name = "upload.pdf"

    logger.debug(f"Sanitised filename: '{filename}' → '{name}'")
    return name


def validate_pdf_bytes(file_bytes: bytes, filename: str) -> tuple[bool, str]:
    """
    Validate uploaded file bytes for size and PDF magic bytes.

    Args:
        file_bytes: Raw bytes of the uploaded file.
        filename: Original filename (used for extension check).

    Returns:
        Tuple of (is_valid, error_message).
    """
    # Check extension
    ext = Path(filename).suffix.lower()
    if ext not in config.ALLOWED_EXTENSIONS:
        return False, f"Invalid file type '{ext}'. Only PDF files are allowed."

    # Check size
    size = len(file_bytes)
    if size == 0:
        return False, "File is empty."
    if size > config.MAX_FILE_SIZE_BYTES:
        mb = size / (1024 * 1024)
        return (
            False,
            f"File too large ({mb:.1f} MB). Maximum allowed is {config.MAX_FILE_SIZE_MB} MB.",
        )

    # Check PDF magic bytes: %PDF-
    if not file_bytes.startswith(b"%PDF-"):
        return False, "File does not appear to be a valid PDF (missing PDF header)."

    return True, ""


def ensure_upload_dir() -> Path:
    """Ensure the uploads directory exists and return its path."""
    config.UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    return config.UPLOADS_DIR


def get_upload_path(filename: str) -> Path:
    """
    Return the full path where an uploaded file should be saved.

    Args:
        filename: Sanitised filename.

    Returns:
        Absolute Path object.
    """
    return ensure_upload_dir() / filename


def file_exists(filename: str) -> bool:
    """Check whether a file already exists in the uploads directory."""
    return get_upload_path(filename).exists()


def delete_upload(filename: str) -> bool:
    """
    Delete an uploaded PDF from disk.

    Args:
        filename: Filename to delete.

    Returns:
        True if deleted, False if it did not exist.
    """
    path = get_upload_path(filename)
    if path.exists():
        path.unlink()
        logger.info(f"Deleted uploaded file: {filename}")
        return True
    logger.warning(f"Tried to delete '{filename}' but file not found on disk.")
    return False


def format_file_size(size_bytes: int) -> str:
    """Human-readable file size string."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 ** 2:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 ** 3:
        return f"{size_bytes / (1024 ** 2):.1f} MB"
    return f"{size_bytes / (1024 ** 3):.1f} GB"
