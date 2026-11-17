"""Backward-compatible aggregate namespace for MultiPanel.

New code should use :mod:`multipanel.controls`,
:mod:`multipanel.containers`, and :mod:`multipanel.specialists`. Existing imports
from this module retain the same class objects and helper functions.
"""

from . import _widget_support as _support
from . import input as _input
from . import controls as _controls
from . import containers as _containers
from . import specialists as _specialists


def _export(module):
    for name, value in vars(module).items():
        if not name.startswith("__"):
            globals()[name] = value


for _module in (_support, _input, _controls, _containers, _specialists):
    _export(_module)

del _module

__all__ = sorted(name for name in globals() if not name.startswith("_"))
