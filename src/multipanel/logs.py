"""Logging for the library (``QT_PARITY_PROPOSAL`` §4, hygiene).

Every module logs to ``logging.getLogger(__name__)`` under ``multipanel``;
nothing is printed. Without configuration only warnings and errors reach
the console (Python's last-resort handler). To see debug output::

    MULTIPANEL_LOG=debug python main.py        # environment variable

    import multipanel
    multipanel.enable_logging("debug")         # or in code

Both add one handler to the ``multipanel`` logger only; the host's root
logger is never configured.
"""
from __future__ import annotations

import logging
import os

__all__ = ["enable_logging"]

LOGGER_NAME = "multipanel"
_FORMAT = "%(levelname)s %(name)s: %(message)s"


def enable_logging(level="debug", stream=None):
    """Show the library's messages at ``level`` and above on ``stream``
    (default stderr). Returns the handler, so it can be removed again."""
    logger = logging.getLogger(LOGGER_NAME)
    numeric = level if isinstance(level, int) else \
        logging.getLevelName(str(level).upper())
    if not isinstance(numeric, int):
        raise ValueError(f"unknown log level {level!r}")
    for handler in list(logger.handlers):
        if getattr(handler, "_multipanel_handler", False):
            logger.removeHandler(handler)
    handler = logging.StreamHandler(stream)
    handler.setFormatter(logging.Formatter(_FORMAT))
    handler._multipanel_handler = True
    logger.addHandler(handler)
    logger.setLevel(numeric)
    return handler


def _from_environment():
    value = os.environ.get("MULTIPANEL_LOG", "").strip()
    if value:
        try:
            enable_logging(value)
        except ValueError:
            logging.getLogger(LOGGER_NAME).warning(
                "ignoring MULTIPANEL_LOG=%r (use debug, info, warning, "
                "error)", value)
