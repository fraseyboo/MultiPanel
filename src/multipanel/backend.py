"""Choosing between the native-VTK controls and their composites (W5 §9.1).

``set_widget_backend("composite")`` rebinds the names of the controls that
have a composite version (see :data:`SWITCHABLE`) in
:mod:`~multipanel.controls`, :mod:`~multipanel.containers`,
:mod:`~multipanel.specialists`, :mod:`~multipanel.layouts` and the
:mod:`~multipanel.widgets` namespace. Code that imports those names after
the call gets the composites, and so do the library's own containers
(rows, dock panes, panels) built after it. ``"legacy"`` (the default)
binds the native classes again; they stay available in
:mod:`multipanel.legacy` whatever the backend.

Call it once, at start-up, before any UI is built: instances already made
keep their class, and ``isinstance`` checks against a rebound name see
only the current backend's class.

The ``MULTIPANEL_BACKEND`` environment variable (``composite`` or
``legacy``) chooses the backend when this module is first imported.
"""
from __future__ import annotations

import importlib
import logging
import os

logger = logging.getLogger(__name__)

BACKENDS = ("legacy", "composite")
# name -> module (of multipanel) that defines the native class.
SWITCHABLE = {
    "ButtonWidget": "controls",
    "PanelBackgroundWidget": "containers",
    "SliderWidget": "controls",
}
_MODULES = ("controls", "containers", "specialists", "layouts", "widgets")

_legacy = {}
_backend = "legacy"


def _module(name):
    return importlib.import_module(f"{__package__}.{name}")


def _capture_legacy():
    """The native classes, captured before any rebinding."""
    if not _legacy:
        for name, home in SWITCHABLE.items():
            _legacy[name] = getattr(_module(home), name)
    return _legacy


def legacy_classes():
    """``{name: native class}`` for every switchable control."""
    return dict(_capture_legacy())


def composite_classes():
    """``{name: composite class}`` for every switchable control."""
    composite = _module("composite")
    return {name: getattr(composite, name) for name in SWITCHABLE}


def widget_backend():
    """The current backend: ``"legacy"`` or ``"composite"``."""
    return _backend


def set_widget_backend(backend):
    """Make the switchable control names resolve to ``backend``'s classes;
    returns the previous backend."""
    global _backend
    if backend not in BACKENDS:
        raise ValueError(f"unknown widget backend {backend!r}; use one of "
                         f"{', '.join(BACKENDS)}")
    previous = _backend
    classes = (_capture_legacy() if backend == "legacy"
               else composite_classes())
    for module_name in _MODULES:
        module = _module(module_name)
        for name, cls in classes.items():
            if name in vars(module):
                setattr(module, name, cls)
    _backend = backend
    if backend != previous:
        logger.debug("widget backend: %s", backend)
    return previous


_capture_legacy()
_from_env = os.environ.get("MULTIPANEL_BACKEND", "").strip().lower()
if _from_env:
    if _from_env in BACKENDS:
        set_widget_backend(_from_env)
    else:
        logger.warning("MULTIPANEL_BACKEND=%r ignored; use one of %s",
                       _from_env, ", ".join(BACKENDS))

__all__ = ["BACKENDS", "SWITCHABLE", "composite_classes", "legacy_classes",
           "set_widget_backend", "widget_backend"]
