"""
Centralized structured logger configuration for Strop.
Supports STROP_DEBUG environment variable and --verbose CLI flags.
"""

import os
import logging
import sys

_logger_initialized = False


def setup_logger(name: str = "strop", level: int = None) -> logging.Logger:
    """Configures and returns the main Strop logger."""
    global _logger_initialized
    logger = logging.getLogger(name)

    if level is None:
        if os.environ.get("STROP_DEBUG", "").lower() in ("1", "true", "yes") or "--verbose" in sys.argv or "-v" in sys.argv:
            level = logging.DEBUG
        else:
            level = logging.INFO

    logger.setLevel(level)

    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(level)
        formatter = logging.Formatter(
            fmt="[%(levelname)s] (%(name)s) %(message)s",
            datefmt="%H:%M:%S"
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    _logger_initialized = True
    return logger


def get_logger(name: str = "strop") -> logging.Logger:
    """Returns the logger for the specified component."""
    if not _logger_initialized:
        return setup_logger(name)
    return logging.getLogger(name)
