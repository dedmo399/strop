"""
Centralized structured logger configuration for Strop.
Supports STROP_DEBUG environment variable and --verbose CLI flags.
"""

import os
import logging
import sys
from typing import Optional

_logger_initialized = False


def setup_logger(name: str = "strop", level: Optional[int] = None) -> logging.Logger:
    """Configures and returns the Strop package logger."""
    global _logger_initialized

    if level is None:
        if os.environ.get("STROP_DEBUG", "").lower() in ("1", "true", "yes") or "--verbose" in sys.argv or "-v" in sys.argv:
            level = logging.DEBUG
        else:
            level = logging.INFO

    formatter = logging.Formatter(
        fmt="[%(levelname)s] (%(name)s) %(message)s",
        datefmt="%H:%M:%S",
    )

    for root_name in ("strop", "strop_core"):
        root_logger = logging.getLogger(root_name)
        root_logger.setLevel(level)
        root_logger.propagate = False
        if not root_logger.handlers:
            handler = logging.StreamHandler(sys.stdout)
            handler.setLevel(level)
            handler.setFormatter(formatter)
            root_logger.addHandler(handler)
        else:
            for existing_handler in root_logger.handlers:
                existing_handler.setLevel(level)

    _logger_initialized = True
    return logging.getLogger(name)


def get_logger(name: str = "strop") -> logging.Logger:
    """Returns the logger for the specified component."""
    if not _logger_initialized:
        setup_logger("strop")
    return logging.getLogger(name)
