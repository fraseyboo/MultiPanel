"""MultiPanel: a UI framework built with VTK."""

__version__ = "0.1.0"

from .core import (
    FocusManager,
    ObserverRegistry,
    RenderScheduler,
    Signal,
    SignalBlocker,
    WidgetMixin,
    refresh_renderer_theme,
)
from .logs import _from_environment, enable_logging
from .resources import FONT_ROOT, ICON_ROOT
from .timer import Timer, VirtualClock
from .units import Length, frac, px

__all__ = [
    "__version__",
    "FONT_ROOT",
    "FocusManager",
    "ICON_ROOT",
    "Length",
    "ObserverRegistry",
    "RenderScheduler",
    "Signal",
    "SignalBlocker",
    "Timer",
    "VirtualClock",
    "WidgetMixin",
    "enable_logging",
    "frac",
    "px",
    "refresh_renderer_theme",
    "set_widget_backend",
    "widget_backend",
]

_from_environment()


def __getattr__(name):
    # The backend switch imports the controls: only when asked for.
    if name in ("set_widget_backend", "widget_backend"):
        from . import backend

        return getattr(backend, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def _backend_from_environment():
    import os

    if os.environ.get("MULTIPANEL_BACKEND", "").strip():
        from . import backend  # noqa: F401  (applies the variable)


_backend_from_environment()
