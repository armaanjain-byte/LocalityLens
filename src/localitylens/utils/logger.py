"""Centralised logger factory with dynamic level updates support."""

import logging
import sys
from typing import Optional

from localitylens.config.settings import settings


def get_logger(name: str, level: Optional[str] = None) -> logging.Logger:
    """Return a named logger configured for the application."""
    logger = logging.getLogger(name)
    resolved_level = (level or settings.log_level).upper()

    if not logger.handlers:
        handler = logging.StreamHandler(sys.stderr)
        fmt = logging.Formatter(
            fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S",
        )
        handler.setFormatter(fmt)
        logger.addHandler(handler)
        logger.propagate = False

    # L-1: Always honour explicit overrides on re-calls (essential for --verbose operations)
    if level is not None:
        logger.setLevel(resolved_level)
        for h in logger.handlers:
            h.setLevel(resolved_level)
    elif not logger.level:
        logger.setLevel(resolved_level)

    return logger