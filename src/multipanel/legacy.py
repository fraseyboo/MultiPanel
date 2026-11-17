"""The native-VTK controls, whatever :func:`~multipanel.backend.set_widget_backend`
chose (W5 §9.1).

These are the classes that subclass ``vtk*Widget``s; they are maintained
for compatibility. Their composite counterparts are in
:mod:`multipanel.composite`.
"""
from __future__ import annotations

from .backend import legacy_classes as _legacy_classes

globals().update(_legacy_classes())

__all__ = sorted(_legacy_classes())
