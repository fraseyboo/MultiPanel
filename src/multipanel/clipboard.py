"""System clipboard access for text fields.

The backend is chosen on first use, in this order:

1. a host hook set with :func:`set_clipboard_backend` ``(get_text, set_text)``;
2. Qt's clipboard, when a Qt application is running (the binding must
   already be imported by the host; this module never imports Qt);
3. the platform tool: ``pbcopy``/``pbpaste`` (macOS), ``wl-copy``/``wl-paste``
   (Wayland), ``xclip`` or ``xsel`` (X11), ``clip.exe`` with PowerShell
   ``Get-Clipboard`` (Windows). They run without a shell, with a 1 s timeout,
   passing text through stdin/stdout;
4. an in-process buffer, so copy and paste still work within the app.

``set_clipboard_backend("internal")`` or the environment variable
``MULTIPANEL_CLIPBOARD=internal`` skips the platform tools.
"""
from __future__ import annotations

import logging
import os
import shutil
import subprocess
import sys

__all__ = ["backend_name", "set_clipboard_backend", "text", "set_text"]

logger = logging.getLogger(__name__)

_BUFFER = {"text": ""}
_HOOK = None
_FORCE_INTERNAL = False
_CHOSEN = None
_TIMEOUT = 1.0


def set_clipboard_backend(backend=None, setter=None):
    """Choose the clipboard.

    ``set_clipboard_backend(get_text, set_text)`` installs host callables;
    ``set_clipboard_backend("internal")`` uses the in-process buffer only;
    ``set_clipboard_backend(None)`` restores automatic selection.
    """
    global _HOOK, _FORCE_INTERNAL, _CHOSEN
    _CHOSEN = None
    if backend == "internal":
        _HOOK, _FORCE_INTERNAL = None, True
    elif backend is None:
        _HOOK, _FORCE_INTERNAL = None, False
    else:
        if setter is None:
            raise TypeError("set_clipboard_backend needs get_text and set_text")
        _HOOK, _FORCE_INTERNAL = (backend, setter), False


def _qt_clipboard():
    from .timer import qt_core

    if qt_core() is None:
        return None
    for name in ("PyQt5.QtWidgets", "PyQt6.QtWidgets", "PySide6.QtWidgets",
                 "PySide2.QtWidgets", "PyQt5.QtGui", "PyQt6.QtGui",
                 "PySide6.QtGui", "PySide2.QtGui"):
        module = sys.modules.get(name)
        application = getattr(module, "QApplication", None) or getattr(
            module, "QGuiApplication", None)
        if application is not None and application.instance() is not None:
            return application.clipboard()
    return None


def _command_pair():
    """``(copy_argv, paste_argv)`` for this platform, or None."""
    candidates = []
    if sys.platform == "darwin":
        candidates.append((["pbcopy"], ["pbpaste"]))
    elif sys.platform.startswith("win"):
        candidates.append((["clip.exe"],
                           ["powershell", "-NoProfile", "-Command",
                            "Get-Clipboard"]))
    else:
        if os.environ.get("WAYLAND_DISPLAY"):
            candidates.append((["wl-copy"], ["wl-paste", "--no-newline"]))
        candidates.append((["xclip", "-selection", "clipboard"],
                           ["xclip", "-selection", "clipboard", "-o"]))
        candidates.append((["xsel", "--clipboard", "--input"],
                           ["xsel", "--clipboard", "--output"]))
    for copy, paste in candidates:
        if shutil.which(copy[0]) and shutil.which(paste[0]):
            return copy, paste
    return None


def _choose():
    global _CHOSEN
    if _HOOK is not None:
        return "hook"
    if _FORCE_INTERNAL or os.environ.get(
            "MULTIPANEL_CLIPBOARD", "").strip().lower() == "internal":
        return "internal"
    if _qt_clipboard() is not None:
        return "qt"                     # re-checked each time; Qt may start late
    if _CHOSEN is None:
        _CHOSEN = ("command", _command_pair()) if _command_pair() else \
            ("internal", None)
        logger.debug("clipboard backend: %s", _CHOSEN[0])
    return _CHOSEN[0]


def backend_name():
    return _choose()


def text():
    """Return the clipboard text ('' when unavailable)."""
    choice = _choose()
    if choice == "hook":
        return str(_HOOK[0]() or "")
    if choice == "qt":
        return str(_qt_clipboard().text() or "")
    if choice == "command":
        try:
            result = subprocess.run(_CHOSEN[1][1], capture_output=True,
                                    timeout=_TIMEOUT, check=False)
            if result.returncode == 0:
                value = result.stdout.decode("utf-8", errors="replace")
                return value.replace("\r\n", "\n")
        except (OSError, subprocess.SubprocessError):
            logger.debug("clipboard paste failed", exc_info=True)
    return _BUFFER["text"]


def set_text(value):
    """Put ``value`` on the clipboard (always kept in-process as well)."""
    value = str(value)
    _BUFFER["text"] = value
    choice = _choose()
    if choice == "hook":
        _HOOK[1](value)
    elif choice == "qt":
        _qt_clipboard().setText(value)
    elif choice == "command":
        try:
            subprocess.run(_CHOSEN[1][0], input=value.encode("utf-8"),
                           timeout=_TIMEOUT, check=False,
                           capture_output=True)
        except (OSError, subprocess.SubprocessError):
            logger.debug("clipboard copy failed", exc_info=True)
