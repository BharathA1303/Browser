"""Project-wide logging setup."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from .config import CONFIG

_LOGGER_NAME = "browser"


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """Return a configured logger that writes to console and browser.log."""

    logger_name = f"{_LOGGER_NAME}.{name}" if name else _LOGGER_NAME
    logger = logging.getLogger(logger_name)
    if logger.handlers:
        return logger

    logger.setLevel(getattr(logging, CONFIG.log_level.upper(), logging.INFO))
    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
    )

    log_path = Path("browser.log")

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setFormatter(formatter)

    logger.addHandler(console_handler)
    logger.addHandler(file_handler)
    logger.propagate = False
    return logger
