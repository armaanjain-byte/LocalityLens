"""Centralised logger factory for LocalityLens."""

import logging
import sys
from typing import Optional

from localitylens.config.settings import settings


def get_logger(name: str, level: Optional[str] = None) -> logging.Logger:
    """Return a named logger configured for the application.

    Args:
        name: Module or component name (use ``__name__``).
        level: Override log level string, e.g. ``"DEBUG"``.

    Returns:
        Configured :class:`logging.Logger` instance.
    """
    logger = logging.getLogger(name)

    if logger.handlers:
        return logger  # Already configured.

    resolved_level = level or settings.log_level
    logger.setLevel(resolved_level.upper())

    handler = logging.StreamHandler(sys.stderr)
    handler.setLevel(resolved_level.upper())

    fmt = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )
    handler.setFormatter(fmt)
    logger.addHandler(handler)
    logger.propagate = False

    return logger