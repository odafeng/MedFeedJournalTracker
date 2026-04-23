"""Logger utility for journal tracker."""

from __future__ import annotations

import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Optional


def setup_logger(
    name: str = "journal_tracker",
    level: Optional[str] = None,
) -> logging.Logger:
    """Set up and return a configured logger.

    Args:
        name: Logger name (namespace).
        level: Log level as a string — "DEBUG", "INFO", "WARNING", "ERROR",
            or "CRITICAL". If None, falls back to the LOG_LEVEL env var,
            which itself defaults to "INFO" when unset.
    """
    if level is None:
        level = os.getenv("LOG_LEVEL", "INFO")
    numeric_level = getattr(logging, level.upper())

    logger = logging.getLogger(name)
    logger.setLevel(numeric_level)

    # Avoid duplicate handlers on repeated calls (e.g. in tests)
    if logger.handlers:
        return logger

    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    console_handler = logging.StreamHandler()
    console_handler.setLevel(numeric_level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # File handler — best-effort; on read-only filesystems we still want
    # stdout logging to continue to work.
    try:
        log_dir = Path("logs")
        log_dir.mkdir(exist_ok=True)
        log_file = log_dir / f"journal_tracker_{datetime.now().strftime('%Y%m%d')}.log"
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(numeric_level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except (OSError, PermissionError):
        # Ephemeral containers (Render) ingest stdout directly; file
        # logs are just a convenience for local dev.
        logger.warning("File logging disabled (filesystem not writable)")

    return logger
