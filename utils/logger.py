"""
utils/logger.py
===============
Structured logging setup using Loguru.
Provides a pre-configured logger with file rotation and console output.
"""

import sys
from pathlib import Path

from loguru import logger

import config


def setup_logger() -> None:
    """Configure Loguru logger with console and file sinks."""
    # Remove default handler
    logger.remove()

    # Console handler — coloured, human-readable
    logger.add(
        sys.stderr,
        level=config.LOG_LEVEL,
        format=(
            "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
            "<level>{message}</level>"
        ),
        colorize=True,
    )

    # File handler — JSON structured, rotating
    logger.add(
        str(config.LOG_FILE),
        level=config.LOG_LEVEL,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {name}:{function}:{line} | {message}",
        rotation="10 MB",
        retention="7 days",
        compression="zip",
        enqueue=True,  # thread-safe async logging
    )

    logger.info(
        f"Logger initialised | level={config.LOG_LEVEL} | file={config.LOG_FILE}"
    )


# Initialise on import
setup_logger()

# Re-export for use elsewhere
__all__ = ["logger"]
