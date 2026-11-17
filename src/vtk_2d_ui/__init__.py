"""Deprecated alias of :mod:`multipanel` (the project's former name).

``import vtk_2d_ui`` and ``import vtk_2d_ui.<module>`` return the
``multipanel`` modules themselves, so classes and module state are shared
(``vtk_2d_ui.controls.TextWidget is multipanel.controls.TextWidget``).
Update imports to ``multipanel``; this alias will be removed in a future
release.
"""
from __future__ import annotations

import importlib
import importlib.abc
import importlib.util
import sys
import warnings

_OLD, _NEW = "vtk_2d_ui", "multipanel"

warnings.warn(
    "the 'vtk_2d_ui' package has been renamed 'multipanel'; update your "
    "imports (the alias will be removed in a future release)",
    DeprecationWarning, stacklevel=2)


class _AliasLoader(importlib.abc.Loader):
    def __init__(self, target):
        self.target = target

    def create_module(self, spec):
        return importlib.import_module(self.target)

    def exec_module(self, module):
        sys.modules[module.__spec__.name] = module


class _AliasFinder(importlib.abc.MetaPathFinder):
    """Maps ``vtk_2d_ui.x.y`` to the already-importable ``multipanel.x.y``."""

    def find_spec(self, fullname, path=None, target=None):
        if not fullname.startswith(_OLD + "."):
            return None
        new_name = _NEW + fullname[len(_OLD):]
        if importlib.util.find_spec(new_name) is None:
            return None
        return importlib.util.spec_from_loader(
            fullname, _AliasLoader(new_name))


if not any(isinstance(finder, _AliasFinder) for finder in sys.meta_path):
    sys.meta_path.insert(0, _AliasFinder())

_package = importlib.import_module(_NEW)
# This module becomes the multipanel package itself.
sys.modules[_OLD] = _package
