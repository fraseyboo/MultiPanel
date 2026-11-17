"""Lengths expressed in logical pixels or as fractions of the viewport.

MultiPanel accepts both units (see ``docs/QT_PARITY_PROPOSAL.md`` §4.3):

* ``px(8)`` is 8 *logical* pixels.  Logical pixels are multiplied by the
  process-wide ``ui_scale()`` to give display pixels, so they keep their
  apparent size when the UI scale changes and do not stretch with the window.
* ``frac(0.25)`` is 25% of the viewport along the axis it is used on (width
  for x/width, height for y/height).  Fractions track window resizes.

Lengths are resolved lazily, against the viewport extent current at the time
of resolution, so a stored ``Length`` keeps its meaning across resizes.

This module only imports VTK-free code at import time.
"""
from __future__ import annotations

from contextlib import contextmanager
import numbers
import re

PX = "px"
FRAC = "frac"
UNITS = (PX, FRAC)

__all__ = [
    "FRAC",
    "Length",
    "PX",
    "UNITS",
    "frac",
    "is_strict",
    "parse_length",
    "px",
    "strict_mode",
    "to_display",
    "to_frac",
    "to_px",
    "viewport_extent",
    "viewport_origin",
]


def _current_scale():
    # Imported lazily: the scale lives with the other process-wide UI config.
    from ._widget_support import ui_scale

    return ui_scale()


class Length:
    """An immutable length with an explicit unit (``"px"`` or ``"frac"``)."""

    __slots__ = ("_value", "_unit")

    def __init__(self, value, unit):
        if unit not in UNITS:
            raise ValueError(f"unknown length unit {unit!r}; expected one of {UNITS}")
        if isinstance(value, bool) or not isinstance(value, numbers.Real):
            raise TypeError(f"length value must be a real number, not {value!r}")
        object.__setattr__(self, "_value", float(value))
        object.__setattr__(self, "_unit", unit)

    def __setattr__(self, _name, _value):
        raise AttributeError("Length is immutable")

    @property
    def value(self):
        return self._value

    @property
    def unit(self):
        return self._unit

    def resolve(self, extent, scale=None):
        """Return this length in *display* pixels.

        ``extent`` is the viewport size in display pixels along the relevant
        axis.  ``scale`` defaults to the current ``ui_scale()``.
        """
        if self._unit == FRAC:
            return self._value * float(extent)
        return self._value * (_current_scale() if scale is None else float(scale))

    def to_json(self):
        """Return a JSON-compatible ``[value, unit]`` pair."""
        return [self._value, self._unit]

    @classmethod
    def from_json(cls, data):
        value, unit = data
        return cls(value, unit)

    def __neg__(self):
        return Length(-self._value, self._unit)

    def __mul__(self, factor):
        if not isinstance(factor, numbers.Real) or isinstance(factor, bool):
            return NotImplemented
        return Length(self._value * factor, self._unit)

    __rmul__ = __mul__

    def __eq__(self, other):
        if not isinstance(other, Length):
            return NotImplemented
        return self._unit == other._unit and self._value == other._value

    def __hash__(self):
        return hash((self._value, self._unit))

    def __repr__(self):
        value = f"{self._value:g}"
        return f"{self._unit}({value})"


def px(value):
    """Return a length of ``value`` logical pixels."""
    return Length(value, PX)


def frac(value):
    """Return a length of ``value`` times the viewport extent."""
    return Length(value, FRAC)


# --------------------------------------------------------------------------
# Strict mode: rejects bare numbers in APIs that opt in to it.
# --------------------------------------------------------------------------

_STRICT_DEPTH = 0


def is_strict():
    return _STRICT_DEPTH > 0


@contextmanager
def strict_mode():
    """Reject bare numbers passed to new (non-legacy) length parameters.

    Intended for tests, to catch call sites that rely on a default unit.
    """
    global _STRICT_DEPTH
    _STRICT_DEPTH += 1
    try:
        yield
    finally:
        _STRICT_DEPTH -= 1


_LENGTH_RE = re.compile(
    r"^\s*([-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?)\s*(px|%|frac)?\s*$")


def parse_length(value, default_unit=PX, *, legacy=False):
    """Coerce ``value`` to a :class:`Length`.

    Accepted forms: a ``Length``; a bare number, which takes
    ``default_unit``; or a string such as ``"8px"``, ``"25%"`` or
    ``"0.25frac"``.  A unitless string also takes ``default_unit``.

    Under :func:`strict_mode`, bare numbers and unitless strings are
    rejected unless ``legacy`` is true (legacy parameters keep their
    historic default unit permanently).
    """
    if isinstance(value, Length):
        return value
    if default_unit not in UNITS:
        raise ValueError(f"unknown default unit {default_unit!r}")
    if isinstance(value, str):
        match = _LENGTH_RE.match(value)
        if match is None:
            raise ValueError(f"cannot parse length {value!r}")
        number, suffix = float(match.group(1)), match.group(2)
        if suffix == "%":
            return Length(number / 100.0, FRAC)
        if suffix is not None:
            return Length(number, suffix)
        value = number
    if isinstance(value, bool) or not isinstance(value, numbers.Real):
        raise TypeError(f"expected a Length, number or string, not {value!r}")
    if is_strict() and not legacy:
        raise TypeError(
            f"bare number {value!r} passed where an explicit unit is "
            "required; use px(...) or frac(...)")
    return Length(value, default_unit)


# --------------------------------------------------------------------------
# Viewport helpers and conversions
# --------------------------------------------------------------------------

def _axis_index(axis):
    if axis in (0, "x", "width", "horizontal"):
        return 0
    if axis in (1, "y", "height", "vertical"):
        return 1
    raise ValueError(f"unknown axis {axis!r}")


def viewport_extent(source, axis=None):
    """Return the viewport size in display pixels.

    ``source`` may be a ``vtkRenderer`` (its viewport is used), a render
    window, an interactor, or a ``(width, height)`` tuple.  With ``axis``
    given, return only that component.
    """
    size = None
    if isinstance(source, (tuple, list)):
        size = (float(source[0]), float(source[1]))
    elif hasattr(source, "GetVTKWindow") or hasattr(source, "GetViewport"):
        # vtkRenderer.GetSize() is the viewport size in display pixels.
        size = tuple(float(v) for v in source.GetSize()[:2])
    elif hasattr(source, "GetRenderWindow"):
        size = tuple(float(v) for v in source.GetRenderWindow().GetSize()[:2])
    elif hasattr(source, "GetSize"):
        size = tuple(float(v) for v in source.GetSize()[:2])
    if size is None:
        raise TypeError(f"cannot determine a viewport extent from {source!r}")
    size = (max(1.0, size[0]), max(1.0, size[1]))
    return size if axis is None else size[_axis_index(axis)]


def viewport_origin(source):
    """Return the viewport's lower-left corner in display pixels."""
    if hasattr(source, "GetOrigin") and (
            hasattr(source, "GetVTKWindow") or hasattr(source, "GetViewport")):
        return tuple(float(v) for v in source.GetOrigin()[:2])
    return (0.0, 0.0)


def to_display(value, extent, *, default_unit=PX, scale=None, legacy=False):
    """Resolve ``value`` to display pixels against ``extent``."""
    return parse_length(value, default_unit, legacy=legacy).resolve(extent, scale)


def to_px(value, extent, *, default_unit=PX, scale=None, legacy=False):
    """Resolve ``value`` to logical pixels against ``extent``."""
    scale = _current_scale() if scale is None else float(scale)
    return to_display(value, extent, default_unit=default_unit,
                      scale=scale, legacy=legacy) / scale


def to_frac(value, extent, *, default_unit=PX, scale=None, legacy=False):
    """Resolve ``value`` to a fraction of ``extent``."""
    return to_display(value, extent, default_unit=default_unit,
                      scale=scale, legacy=legacy) / max(1.0, float(extent))
