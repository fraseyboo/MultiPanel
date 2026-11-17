"""Charts as widgets (``docs/CHARTS_PROPOSAL.md`` C0, C1, C4).

A :class:`ChartView` shows a chart (:class:`XYChart`) inside the UI: it is
laid out, themed, clipped and hidden like any other widget, and the
:class:`~multipanel.router.EventRouter` hands it the pointer, so the 3D
camera never moves while you pan or zoom a chart. :class:`ChartPanel` puts
one in a scene panel (header, collapse, docking)::

    chart = XYChart(title="Source spectrum")
    chart.axisX().setTitle("Energy (MeV)")
    chart.axisY().setTitle("Probability")
    chart.addStep(edges, probabilities, name="Fission", fill=True)
    chart.addStems([0.662, 1.173, 1.332], [0.85, 1.0, 1.0], name="Lines")

    panel = ChartPanel(renderer, interactor, chart, title="Source spectrum")
    dock.add_panel(panel, tab="sources")

Mouse: wheel zooms, left drag pans, double-click (or Home) resets the view.
Colours come from the theme (``Style`` tokens) with a colour-blind-safe
series palette; fonts are the UI font, scaled with ``ui_scale``.
"""
from __future__ import annotations

import numpy as np
import vtk
from vtkmodules.util.numpy_support import numpy_to_vtk

from ._widget_support import (
    font_scale,
    UI_Z_PANEL_CONTROL,
    apply_ui_font,
    ui_layer,
    ui_scale,
)
from .core import Signal, SizePolicy, WidgetMixin
from .layers import LinkedRenderer
from .standard import _DEFAULT_TOKENS
from .vtk_compat import add_actor_2d, remove_actor_2d

__all__ = [
    "Axis", "BarSeries", "Handle", "ChartPanel", "ChartView", "LineSeries",
    "ScatterSeries", "Series", "StemSeries", "StepSeries", "XYChart",
    "palette",
]

# Okabe-Ito: distinguishable with the common colour-vision deficiencies.
_PALETTE_LIGHT = ["#0072B2", "#D55E00", "#009E73", "#CC79A7", "#E69F00",
                  "#56B4E9", "#000000"]
_PALETTE_DARK = ["#56B4E9", "#E69F00", "#2EC4A0", "#E59CC8", "#F0E442",
                 "#7FB8FF", "#E4E7EB"]


def _rgb(hex_color):
    value = hex_color.lstrip("#")
    return tuple(int(value[i:i + 2], 16) / 255.0 for i in (0, 2, 4))


def palette(dark=False):
    """The series colours (RGB 0-1) for a light or dark theme."""
    return [_rgb(c) for c in (_PALETTE_DARK if dark else _PALETTE_LIGHT)]


def _nice_number(value, round_=False):
    """Heckbert's nice numbers: 1, 2, 5 or 10 times a power of ten."""
    exponent = np.floor(np.log10(value))
    fraction = value / 10 ** exponent
    if round_:
        nice = 1 if fraction < 1.5 else 2 if fraction < 3 else \
            5 if fraction < 7 else 10
    else:
        nice = 1 if fraction <= 1 else 2 if fraction <= 2 else \
            5 if fraction <= 5 else 10
    return nice * 10 ** exponent


def _nice_range(low, high, ticks=5, log=False):
    """Round ``low``/``high`` outwards to tick-friendly values, independent
    of the chart's pixel size (decades on log axes)."""
    if log:
        return (10.0 ** np.floor(np.log10(low)),
                10.0 ** np.ceil(np.log10(high)))
    span = _nice_number(high - low)
    step = _nice_number(span / max(1, ticks - 1), round_=True)
    return (float(np.floor(low / step + 1e-9) * step),
            float(np.ceil(high / step - 1e-9) * step))


def _nice_ticks(low, high, count=3):
    """About ``count`` nicely spaced tick values within ``[low, high]``."""
    if not high > low:
        return [low]
    step = _nice_number((high - low) / max(1, count - 1), round_=True)
    first = np.ceil(low / step - 1e-9) * step
    ticks = np.arange(first, high + step * 1e-6, step)
    return [0.0 if abs(t) < step * 1e-9 else float(t) for t in ticks]


def _mix(a, b, t):
    return tuple(x + (y - x) * t for x, y in zip(a, b))


# ---------------------------------------------------------------------------------------
# Axes and series


class Axis:
    """One axis of an :class:`XYChart` (wraps ``vtkAxis``)."""

    def __init__(self, vtk_axis, chart, index):
        self._axis = vtk_axis
        self._chart = chart
        self._index = index          # 0: horizontal, 1: vertical
        self._fixed = None
        self._include_zero = False
        self._short_ticks = None         # ticks we set on a short axis

    def vtkAxis(self):
        return self._axis

    def title(self):
        return self._axis.GetTitle()

    def setTitle(self, title):
        self._axis.SetTitle(str(title))
        self._chart._changed()

    def range(self):
        """``(minimum, maximum)`` in data units (also on log axes)."""
        if self._axis.GetLogScaleActive():
            return (self._axis.GetUnscaledMinimum(),
                    self._axis.GetUnscaledMaximum())
        return (self._axis.GetMinimum(), self._axis.GetMaximum())

    def _apply_range(self, minimum, maximum):
        # On a log axis vtkAxis.SetRange takes log10 values; data units go
        # through SetUnscaledRange.
        if self._axis.GetLogScale():
            self._axis.SetUnscaledRange(minimum, maximum)
        else:
            self._axis.SetRange(minimum, maximum)

    def setRange(self, minimum, maximum):
        """Fix the range in data units (``resetView`` returns to it)."""
        self._fixed = (float(minimum), float(maximum))
        self._axis.SetBehavior(vtk.vtkAxis.FIXED)
        self._apply_range(*self._fixed)
        self._chart._changed()

    def setAutoRange(self):
        """Fit the data (the default)."""
        self._fixed = None
        self._chart.resetView()

    def includesZero(self):
        return self._include_zero

    def setIncludeZero(self, include=True):
        """Make the automatic range reach zero (e.g. energies, counts), so
        a single value or a narrow spread still has room around it."""
        self._include_zero = bool(include)
        self._chart.resetView()

    def setTickLabels(self, positions, labels):
        """Text labels at data ``positions`` instead of numbers (e.g.
        categories under bars); ``clearTickLabels`` restores numbers."""
        positions = [float(v) for v in positions]
        labels = [str(v) for v in labels]
        if len(positions) != len(labels):
            raise ValueError("one label per position is needed")
        array = vtk.vtkDoubleArray()
        names = vtk.vtkStringArray()
        for position, label in zip(positions, labels):
            array.InsertNextValue(position)
            names.InsertNextValue(label)
        self._axis.SetCustomTickPositions(array, names)
        self._short_ticks = None
        self._tick_labels = (positions, labels)
        self._chart._changed(data=True)

    def tickLabels(self):
        """``(positions, labels)`` set by :meth:`setTickLabels`, or None."""
        return getattr(self, "_tick_labels", None)

    SHORT_AXIS_PX = 120              # below this, VTK may draw one tick

    def _update_short_ticks(self, scale=1.0):
        """Give a short numeric axis three to five nice ticks (VTK spaces its
        automatic ticks by pixels and can leave just one); returns True if
        the ticks changed."""
        if self.tickLabels() is not None or self.isLogScale():
            wanted = None
        else:
            start, end, _low, _high = self._span()
            length = abs(end - start)
            wanted = None
            if 0 < length < self.SHORT_AXIS_PX * scale:
                wanted = tuple(_nice_ticks(*self.range(), count=4))
        if wanted == self._short_ticks:
            return False
        self._short_ticks = wanted
        if wanted is None:
            self._axis.SetCustomTickPositions(None, None)
        else:
            array = vtk.vtkDoubleArray()
            for value in wanted:
                array.InsertNextValue(value)
            self._axis.SetCustomTickPositions(array, None)
        return True

    def clearTickLabels(self):
        self._axis.SetCustomTickPositions(None, None)
        self._tick_labels = None
        self._chart._changed(data=True)

    def isLogScale(self):
        return bool(self._axis.GetLogScale())

    def setLogScale(self, log):
        self._axis.SetLogScale(bool(log))
        self._chart.resetView()

    def setGridVisible(self, visible):
        self._axis.SetGridVisible(bool(visible))
        self._chart._changed()

    def _reset(self):
        if self._fixed is not None:
            self._apply_range(*self._fixed)

    # -- data <-> scene (chart pixels) --------------------------------------------
    def _span(self):
        axis = self._axis
        start = axis.GetPoint1()[self._index]
        end = axis.GetPoint2()[self._index]
        return start, end, axis.GetMinimum(), axis.GetMaximum()

    def toScene(self, value):
        """Chart-scene pixel position of data ``value`` on this axis (a
        number, or an array mapped at once)."""
        start, end, low, high = self._span()
        values = np.asarray(value, dtype=float)
        if self._axis.GetLogScaleActive():
            positive = values > 0
            values = np.where(positive, np.log10(np.where(positive, values,
                                                          1.0)), low)
        if high == low:
            result = np.full(values.shape, float(start))
        else:
            result = start + (values - low) / (high - low) * (end - start)
        return float(result) if result.ndim == 0 else result

    def fromScene(self, position):
        """Data value at chart-scene pixel ``position`` (number or array)."""
        start, end, low, high = self._span()
        positions = np.asarray(position, dtype=float)
        t = (np.zeros(positions.shape) if end == start
             else (positions - start) / (end - start))
        values = low + t * (high - low)
        if self._axis.GetLogScaleActive():
            values = 10.0 ** values
        return float(values) if values.ndim == 0 else values

    def _baseline(self):
        """Scene position of zero, or of the axis start if zero is not
        shown (histograms, bars and stems rise from it)."""
        return self.toScene(max(0.0, self.fromScene(self._span()[0])))


def _nearest(distances, tolerance):
    """``(distance, index)`` of the smallest distance within tolerance."""
    if distances.size == 0:
        return None
    index = int(np.argmin(distances))
    distance = float(distances[index])
    return (distance, index) if distance <= tolerance else None


class Handle:
    """Something draggable in an editable series: a point, a bin value or
    a bin edge (``kind``) at ``index``."""

    __slots__ = ("series", "kind", "index")

    def __init__(self, series, kind, index):
        self.series, self.kind, self.index = series, kind, int(index)

    def __repr__(self):
        return f"Handle({self.series.name()!r}, {self.kind!r}, {self.index})"


class Series:
    """Base of the plotted series: name, colour, visibility, data.

    ``setEditable(True)`` lets the user drag the data in a
    :class:`ChartView` (points up and down; with ``move_x`` also sideways),
    within ``minimum``/``maximum`` (and ``x_minimum``/``x_maximum``
    sideways). ``edited(series)`` fires when a drag ends; the chart keeps
    an undo stack.
    """

    PLOT_TYPE = vtk.vtkChart.LINE
    DEFAULT_MINIMUM = None

    def __init__(self, x, y, name="", color=None):
        self._name = str(name)
        self._color = None if color is None else tuple(color[:3])
        self._chart = None
        self._plot = None
        self._table = vtk.vtkTable()
        self._x, self._y = self._points(np.asarray(x, float),
                                        np.asarray(y, float))
        self._editable = False
        self._limits = (self.DEFAULT_MINIMUM, None)
        self._x_limits = (None, None)
        self._move_x = False
        self._clickable = False
        self._highlighted = frozenset()
        self._mark_plot = None                 # accent markers (highlight)
        self._mark_table = vtk.vtkTable()
        self._tooltip = None                   # formatter(index) -> text
        self.edited = Signal()                 # (series) when a drag ends

    # -- tooltips -----------------------------------------------------------------------
    HOVERABLE = True

    def setTooltipFormatter(self, formatter):
        """``formatter(index) -> str`` gives the hover text of item
        ``index`` (None: the default ``name: x, y``)."""
        self._tooltip = formatter

    def tooltipText(self, index):
        if self._tooltip is not None:
            return str(self._tooltip(index))
        return self._default_tooltip(index)

    def _prefix(self):
        return f"{self._name}: " if self._name else ""

    def _default_tooltip(self, index):
        x_text = f"{self._x[index]:.4g}{self._error_text(index, 'x')}"
        y_text = f"{self._y[index]:.4g}{self._error_text(index, 'y')}"
        return f"{self._prefix()}{x_text}, {y_text}"

    def _error_text(self, index, axis):
        """`` ± e`` (or `` −l +u``) from error bars attached with ``of=``."""
        for other in (self._chart.series() if self._chart else ()):
            if getattr(other, "_of", None) is not self or \
                    not other.isVisible() or len(other._x) <= index:
                continue
            errors = other.errors() if axis == "y" else other.xErrors()
            if errors is None:
                continue
            lower, upper = errors[0][index], errors[1][index]
            if lower == 0 and upper == 0:
                continue
            if np.isclose(lower, upper):
                return f" ± {upper:.2g}"
            return f" −{lower:.2g} +{upper:.2g}"
        return ""

    # -- highlighting ---------------------------------------------------------------------
    def highlighted(self):
        return sorted(self._highlighted)

    def setHighlighted(self, indices):
        """Mark the items at ``indices`` in the accent colour (e.g. the
        selected rows of a bound model); ``[]`` clears them. Points get a
        marker; bars are recoloured (:class:`BarSeries`)."""
        self._highlighted = frozenset(int(i) for i in indices)
        self._update_marks()
        if self._chart is not None:
            self._chart._changed()

    def _mark_points(self):
        index = np.array(sorted(i for i in self._highlighted
                                if 0 <= i < len(self._x)), dtype=np.int64)
        return self._x[index], self._y[index]

    def _update_marks(self):
        chart = self._chart
        if chart is None:
            return
        xs, ys = self._mark_points()
        if len(xs) == 0:
            if self._mark_plot is not None:
                self._mark_plot.SetVisible(False)
            return
        table = self._mark_table
        while table.GetNumberOfColumns():
            table.RemoveColumn(0)
        for name, values in (("x", xs), ("y", ys)):
            array = numpy_to_vtk(np.ascontiguousarray(values, dtype=float),
                                 deep=True)
            array.SetName(name)
            table.AddColumn(array)
        table.Modified()
        if self._mark_plot is None:
            plot = chart.vtkChart().AddPlot(vtk.vtkChart.POINTS)
            plot.SetInputData(table, "x", "y")
            plot.SetLegendVisibility(False)
            plot.SetMarkerStyle(vtk.vtkPlotPoints.CIRCLE)
            self._mark_plot = plot
            self._style_marks()
        self._mark_plot.SetVisible(self.isVisible())

    def _style_marks(self):
        if self._mark_plot is None or self._chart is None:
            return
        tokens, scale, _dark = getattr(self._chart, "_theme",
                                       (_DEFAULT_TOKENS, ui_scale(), False))
        self._mark_plot.SetColorF(*tokens["accent"][:3])
        self._mark_plot.SetMarkerSize(10.0 * scale)

    # -- clicking -----------------------------------------------------------------------
    def isClickable(self):
        return self._clickable

    def setClickable(self, clickable=True):
        """Report clicks on this series' items as ``chart.clicked(series,
        index)`` (a bar, a histogram bin or a point)."""
        self._clickable = bool(clickable)

    def _item_at(self, chart, sx, sy, tolerance):
        """Index of the item at chart-scene point ``(sx, sy)``, or None:
        the nearest point within ``tolerance`` px."""
        found = self._nearest_point(chart, sx, sy, tolerance)
        return None if found is None else found[1]

    def _nearest_point(self, chart, sx, sy, tolerance):
        ax, ay = chart.axisX(), chart.axisY()
        with np.errstate(invalid="ignore"):
            distances = np.hypot(ax.toScene(self._x) - sx,
                                 ay.toScene(self._y) - sy)
        return _nearest(np.where(np.isfinite(distances), distances, np.inf),
                        tolerance)

    # -- editing ------------------------------------------------------------------------
    def isEditable(self):
        return self._editable

    def setEditable(self, editable=True, minimum="default", maximum=None,
                    move_x=False, x_minimum=None, x_maximum=None):
        """Allow dragging in the chart; values are kept within
        ``minimum``/``maximum`` (``"default"``: 0 for histograms and stems,
        unlimited otherwise) and x positions within
        ``x_minimum``/``x_maximum``."""
        self._editable = bool(editable)
        low = self.DEFAULT_MINIMUM if minimum == "default" else minimum
        self._limits = (low, maximum)
        self._x_limits = (x_minimum, x_maximum)
        self._move_x = bool(move_x)

    @staticmethod
    def _bound(value, low, high):
        if low is not None:
            value = max(low, value)
        if high is not None:
            value = min(high, value)
        return value

    def _clamp(self, value):
        return self._bound(value, *self._limits)

    def _clamp_x(self, value):
        return self._bound(value, *self._x_limits)

    def _set_quiet(self, x, y):
        """Replace the data without refitting the axes (while dragging)."""
        self._x, self._y = np.asarray(x, float), np.asarray(y, float)
        self._fill_table()
        if self._chart is not None:
            self._chart._changed()

    def _hit(self, chart, sx, sy, tolerance):
        """``(distance, Handle)`` of the nearest handle within
        ``tolerance`` scene px of ``(sx, sy)``, or None."""
        found = self._nearest_point(chart, sx, sy, tolerance)
        return None if found is None else \
            (found[0], Handle(self, "point", found[1]))

    def _drag(self, handle, x, y):
        xs, ys = self._x.copy(), self._y.copy()
        i = handle.index
        ys[i] = self._clamp(y)
        if self._move_x:
            low = xs[i - 1] if i > 0 else -np.inf
            high = xs[i + 1] if i + 1 < len(xs) else np.inf
            xs[i] = min(max(self._clamp_x(x), low), high)
        self._set_quiet(xs, ys)

    def _highlight(self, handle):
        i = handle.index
        return [self._x[i]], [self._y[i]]

    def _anchor(self, handle):
        """Data point a drag moves (``None`` on an axis it ignores); the
        offset from the pointer at the press is kept while dragging."""
        return self._x[handle.index], self._y[handle.index]

    def _cursor(self, handle):
        return vtk.VTK_CURSOR_HAND

    # -- data -------------------------------------------------------------------------
    def _points(self, x, y):
        if x.shape != y.shape:
            raise ValueError("x and y must have the same length")
        return x, y

    def data(self):
        return self._x.copy(), self._y.copy()

    def setData(self, x, y):
        """Replace the data; the plot updates in place."""
        self._x, self._y = self._points(np.asarray(x, float),
                                        np.asarray(y, float))
        self._fill_table()
        self._update_marks()
        if self._chart is not None:
            self._chart._changed(data=True)

    def _columns(self):
        return {"x": self._x, "y": self._y}

    def _extent(self, key, chart):
        """Values the axis ``key`` must show (the fit's input)."""
        return np.asarray(self._columns()[key], float)

    def _fill_table(self):
        table = self._table
        while table.GetNumberOfColumns():
            table.RemoveColumn(0)
        for name, values in self._columns().items():
            array = numpy_to_vtk(np.ascontiguousarray(values, dtype=float),
                                 deep=True)
            array.SetName(name)
            table.AddColumn(array)
        table.Modified()

    # -- appearance ---------------------------------------------------------------------
    def name(self):
        return self._name

    def setName(self, name):
        """Rename the series (its legend entry)."""
        self._name = str(name)
        if self._plot is not None:
            self._plot.SetLabel(self._name)
        if self._chart is not None:
            self._chart._changed()

    def color(self):
        return self._color

    def setColor(self, color):
        self._color = tuple(color[:3])
        if self._chart is not None:
            self._chart._apply_series_style()

    def isVisible(self):
        return self._plot is None or bool(self._plot.GetVisible())

    def setVisible(self, visible):
        if self._plot is not None:
            self._plot.SetVisible(bool(visible))
            if self._mark_plot is not None:
                self._mark_plot.SetVisible(bool(visible) and
                                           bool(self._highlighted))
            self._chart._changed()

    def vtkPlot(self):
        return self._plot

    # -- chart attachment ------------------------------------------------------------------
    def _attach(self, chart):
        self._chart = chart
        self._fill_table()
        self._plot = chart.vtkChart().AddPlot(self.PLOT_TYPE)
        self._plot.SetInputData(self._table, "x", "y")
        self._plot.SetLabel(self._name)
        self._configure(self._plot)

    def _configure(self, plot):
        """Hook: per-type plot settings."""

    def _style(self, color, scale):
        r, g, b = color
        self._plot.SetColorF(r, g, b)
        self._plot.SetWidth(self._width() * scale)

    def _width(self):
        return 2.0


def _m4(x, y, columns):
    """Per pixel column (``columns``, an int array, ascending): the
    first, lowest, highest and last point, in drawing order. A polyline
    through them covers exactly the pixels the full line covers."""
    starts = np.flatnonzero(np.r_[True, np.diff(columns) != 0])
    ends = np.r_[starts[1:], len(columns)] - 1
    lows = np.minimum.reduceat(y, starts)
    highs = np.maximum.reduceat(y, starts)
    # where each column's minimum and maximum fall, to keep the order
    segment = np.repeat(np.arange(len(starts)), np.diff(np.r_[starts,
                                                              len(y)]))
    is_low = y == lows[segment]
    is_high = y == highs[segment]
    index = np.arange(len(y))
    first_low = np.full(len(starts), len(y))
    first_high = np.full(len(starts), len(y))
    np.minimum.at(first_low, segment[is_low], index[is_low])
    np.minimum.at(first_high, segment[is_high], index[is_high])
    picks = np.sort(np.stack([starts, first_low, first_high, ends]), axis=0)
    picks = picks.T.ravel()
    keep = np.r_[True, np.diff(picks) != 0]
    picks = picks[keep]
    return x[picks], y[picks]


class LineSeries(Series):
    """A polyline through the points.

    Long lines (over :attr:`DECIMATE_ABOVE` points, x ascending) are drawn
    decimated: per pixel column the first, lowest, highest and last point
    of the visible range (and one view width either side, so a pan shows
    real data at once), recomputed when the view leaves that margin or
    the zoom changes. Data, hit-testing, tooltips, editing and exports use
    every point.
    """

    DECIMATE_ABOVE = 20_000
    REZOOM = 0.1                    # recompute after this much zoom change

    def __init__(self, x, y, name="", color=None, width=2.0, markers=False):
        self._drawn = None           # (x, y) drawn when decimated
        self._cover = None           # (low, high, scale) it was made for
        super().__init__(x, y, name, color)
        self._line_width = float(width)
        self._markers = bool(markers)

    def _points(self, x, y):
        x, y = super()._points(x, y)
        self._drawn = self._cover = None
        self._ascending = bool(len(x) < 2 or np.all(np.diff(x) >= 0)) and \
            bool(np.all(np.isfinite(x)) and np.all(np.isfinite(y)))
        return x, y

    def _columns(self):
        if self._drawn is not None:
            return {"x": self._drawn[0], "y": self._drawn[1]}
        return super()._columns()

    def _extent(self, key, chart):
        return np.asarray(self._x if key == "x" else self._y, float)

    def isDecimated(self):
        return self._drawn is not None

    def _long(self):
        return self._ascending and len(self._x) > self.DECIMATE_ABOVE

    def setData(self, x, y):
        """Replace the data; a long line is decimated before it reaches
        VTK (no full copy into the plot's table)."""
        self._x, self._y = self._points(np.asarray(x, float),
                                        np.asarray(y, float))
        if self._chart is None or not self._long():
            self._fill_table()
            if self._chart is not None:
                self._chart._changed(data=True)
            return
        self._chart._fit()                       # the axes see every point
        if not self._update_decimation(self._chart):
            self._fill_table()
        self._chart._changed()

    def _nearest_point(self, chart, sx, sy, tolerance):
        """Only points within ``tolerance`` px in x can match: on a long
        ascending line, search just those."""
        if not self._long():
            return super()._nearest_point(chart, sx, sy, tolerance)
        ax, ay = chart.axisX(), chart.axisY()
        low, high = sorted(ax.fromScene([sx - tolerance, sx + tolerance]))
        i0 = int(np.searchsorted(self._x, low))
        i1 = int(np.searchsorted(self._x, high, side="right"))
        if i1 <= i0:
            return None
        distances = np.hypot(ax.toScene(self._x[i0:i1]) - sx,
                             ay.toScene(self._y[i0:i1]) - sy)
        found = _nearest(distances, tolerance)
        return None if found is None else (found[0], found[1] + i0)

    def _set_quiet(self, x, y):
        self._drawn = self._cover = None
        super()._set_quiet(x, y)
        if self._chart is not None:
            self._update_decimation(self._chart)

    def _update_decimation(self, chart, full=False):
        """Re-decimate for the current view if needed; True if the drawn
        data changed."""
        x, y = self._x, self._y
        if full or len(x) <= self.DECIMATE_ABOVE or not self._ascending:
            if self._drawn is None:
                return False
            self._drawn = self._cover = None
            self._fill_table()
            return True
        axis = chart.axisX()
        start, end, _low, _high = axis._span()
        width = abs(end - start)
        if width < 1:
            return False
        low, high = sorted(axis.range())
        scale = width / (high - low) if high > low else 0.0
        cover = self._cover
        if cover is not None and cover[0] <= low and high <= cover[1] and \
                scale and abs(scale / cover[2] - 1.0) <= self.REZOOM:
            return False
        left, right = min(start, end), max(start, end)
        span_low, span_high = sorted(axis.fromScene([left - width,
                                                     right + width]))
        i0 = max(int(np.searchsorted(x, span_low)) - 1, 0)
        i1 = min(int(np.searchsorted(x, span_high, side="right")) + 1,
                 len(x))
        xs, ys = x[i0:i1], y[i0:i1]
        if len(xs) > 4 * 3 * width:
            columns = np.floor(axis.toScene(xs)).astype(np.int64)
            columns = np.maximum.accumulate(columns)    # guard float noise
            xs, ys = _m4(xs, ys, columns)
        self._drawn = (xs, ys)
        self._cover = (span_low, span_high, scale)
        self._fill_table()
        return True

    def _width(self):
        return self._line_width

    def _configure(self, plot):
        plot.SetMarkerStyle(vtk.vtkPlotPoints.CIRCLE if self._markers
                            else vtk.vtkPlotPoints.NONE)


class ScatterSeries(Series):
    """Unconnected markers."""

    PLOT_TYPE = vtk.vtkChart.POINTS

    def __init__(self, x, y, name="", color=None, size=6.0, marker="circle"):
        super().__init__(x, y, name, color)
        self._size = float(size)
        self._marker = {"circle": vtk.vtkPlotPoints.CIRCLE,
                        "square": vtk.vtkPlotPoints.SQUARE,
                        "diamond": vtk.vtkPlotPoints.DIAMOND,
                        "cross": vtk.vtkPlotPoints.CROSS,
                        "plus": vtk.vtkPlotPoints.PLUS}[marker]

    def _configure(self, plot):
        plot.SetMarkerStyle(self._marker)

    def _style(self, color, scale):
        super()._style(color, scale)
        self._plot.SetMarkerSize(self._size * scale)


class BarSeries(Series):
    """Bars at each x (width set by the chart's bar fraction).

    ``horizontal=True`` draws them along the x axis from zero, at
    positions ``x`` up the y axis (label those with
    ``chart.axisY().setTickLabels``).
    """

    PLOT_TYPE = vtk.vtkChart.BAR

    def __init__(self, x, y, name="", color=None, horizontal=False):
        self._horizontal = bool(horizontal)
        self._highlighted = frozenset()
        super().__init__(x, y, name, color)

    def isHorizontal(self):
        return self._horizontal

    def highlighted(self):
        return sorted(self._highlighted)

    def setHighlighted(self, indices):
        """Draw the bars at ``indices`` in the theme's accent colour, and
        fade the others (e.g. to show the selection); ``[]`` clears it."""
        self._highlighted = frozenset(int(i) for i in indices)
        self._fill_table()
        if self._chart is not None:
            self._chart._apply_series_style()
            self._chart._changed()

    def _update_marks(self):
        """Bars show their highlight by colour (see :meth:`_style`)."""

    def _columns(self):
        columns = super()._columns()
        mark = np.zeros(len(self._x))
        for index in self._highlighted:
            if 0 <= index < len(mark):
                mark[index] = 1.0
        columns["highlight"] = mark
        return columns

    def _default_tooltip(self, index):
        position, value = self._x[index], self._y[index]
        axis = (self._chart.axisY() if self._horizontal
                else self._chart.axisX()) if self._chart else None
        labels = axis.tickLabels() if axis is not None else None
        where = f"{position:.4g}"
        if labels is not None:
            for at, label in zip(*labels):
                if abs(at - position) < 1e-9:
                    where = label
                    break
        return f"{self._prefix()}{where}, {value:.4g}"

    def _half_width(self, chart):
        unique = np.unique(self._x[np.isfinite(self._x)])
        spacing = float(np.diff(unique).min()) if unique.size > 1 else 1.0
        return chart.vtkChart().GetBarWidthFraction() * spacing / 2

    def _item_at(self, chart, sx, sy, tolerance):
        half = self._half_width(chart)
        along, across = chart.axisX(), chart.axisY()
        position, length = sx, sy
        if self._horizontal:
            along, across = across, along
            position, length = sy, sx
        a, b = along.toScene(self._x - half), along.toScene(self._x + half)
        c = np.full(self._y.shape, across.toScene(0.0))
        d = across.toScene(self._y)
        inside = ((np.minimum(a, b) <= position) &
                  (position <= np.maximum(a, b)) &
                  (np.minimum(c, d) <= length) & (length <= np.maximum(c, d)))
        hits = np.flatnonzero(inside)
        return int(hits[0]) if hits.size else None

    def _configure(self, plot):
        plot.SetOrientation(vtk.vtkPlotBar.HORIZONTAL if self._horizontal
                            else vtk.vtkPlotBar.VERTICAL)

    def _style(self, color, scale):
        r, g, b = color
        self._plot.SetColorF(r, g, b)
        if not self._highlighted:
            self._plot.ScalarVisibilityOff()
            return
        tokens = getattr(self._chart, "_theme", (_DEFAULT_TOKENS,))[0]
        table = vtk.vtkLookupTable()
        table.SetNumberOfTableValues(2)
        table.SetTableRange(0.0, 1.0)
        # The others fade towards the panel so the highlight stands out
        # even where the accent and the series colour are alike.
        table.SetTableValue(0, *_mix((r, g, b), tokens["panel"], 0.6), 1.0)
        table.SetTableValue(1, *tokens["accent"][:3], 1.0)
        table.Build()
        self._plot.SetLookupTable(table)
        self._plot.SelectColorArray("highlight")
        self._plot.ScalarVisibilityOn()

    def _extent(self, key, chart):
        # The bars' positions run along y when horizontal.
        along = "y" if self._horizontal else "x"
        values = np.asarray(self._columns()["x" if key == along else "y"],
                            float)
        if key != along:
            return np.append(values, 0.0)       # bars rise from zero
        # vtkChartXY draws bars BarWidthFraction of the closest spacing
        # wide: show the outer bars whole.
        unique = np.unique(values[np.isfinite(values)])
        spacing = float(np.diff(unique).min()) if unique.size > 1 else 1.0
        half = chart.vtkChart().GetBarWidthFraction() * spacing / 2
        return np.concatenate([values - half, values + half])


class StepSeries(Series):
    """A histogram: ``values[i]`` between ``edges[i]`` and ``edges[i+1]``.

    Drawn as a step outline, optionally filled down to zero (source
    spectrum bins, tally energy bins). When editable, bin values
    drag up and down and the inner edges left and right (kept in order,
    at least ``min_width`` apart; ``move_outer_edges`` frees the ends).
    """

    DEFAULT_MINIMUM = 0.0

    def setEditable(self, editable=True, minimum="default", maximum=None,
                    min_width=None, move_outer_edges=False, x_minimum=None,
                    x_maximum=None):
        super().setEditable(editable, minimum, maximum,
                            x_minimum=x_minimum, x_maximum=x_maximum)
        self._min_width = min_width
        self._outer = bool(move_outer_edges)

    def _gap(self):
        width = getattr(self, "_min_width", None)
        if width is not None:
            return float(width)
        return 1e-3 * float(self._x[-1] - self._x[0] or 1.0)

    def _hit(self, chart, sx, sy, tolerance):
        ax, ay = chart.axisX(), chart.axisY()
        edges, values = self._x, self._y
        best = None
        scene_edges = ax.toScene(edges)
        x0, x1 = scene_edges[:-1], scene_edges[1:]
        distances = np.abs(ay.toScene(values) - sy)
        under = (np.minimum(x0, x1) <= sx) & (sx <= np.maximum(x0, x1))
        found = _nearest(np.where(under, distances, np.inf), tolerance)
        if found is not None:
            best = (found[0], Handle(self, "value", found[1]))
        outer = getattr(self, "_outer", False)
        first, last = (0, len(edges)) if outer else (1, len(edges) - 1)
        if last > first:
            j = np.arange(first, last)
            heights = np.maximum(values[np.maximum(j - 1, 0)],
                                 values[np.minimum(j, len(values) - 1)])
            bottom, tops = ay._baseline(), ay.toScene(heights)
            reach = ((np.minimum(bottom, tops) - tolerance <= sy) &
                     (sy <= np.maximum(bottom, tops) + tolerance))
            distances = np.abs(scene_edges[j] - sx)
            found = _nearest(np.where(reach, distances, np.inf), tolerance)
            if found is not None and (best is None or found[0] < best[0]):
                best = (found[0], Handle(self, "edge", int(j[found[1]])))
        return best

    def _drag(self, handle, x, y):
        edges, values = self._x.copy(), self._y.copy()
        i = handle.index
        if handle.kind == "value":
            values[i] = self._clamp(y)
        else:
            gap = self._gap()
            low = edges[i - 1] + gap if i > 0 else -np.inf
            high = edges[i + 1] - gap if i + 1 < len(edges) else np.inf
            edges[i] = min(max(self._clamp_x(x), low), high)
        self._set_quiet(edges, values)

    def _highlight(self, handle):
        i = handle.index
        if handle.kind == "value":
            return [self._x[i], self._x[i + 1]], [self._y[i], self._y[i]]
        height = max(self._y[max(i - 1, 0)], self._y[min(i, len(self._y) - 1)])
        return [self._x[i], self._x[i]], [0.0, height]

    def _cursor(self, handle):
        return vtk.VTK_CURSOR_SIZENS if handle.kind == "value" \
            else vtk.VTK_CURSOR_SIZEWE

    def _extent(self, key, chart):
        values = super()._extent(key, chart)
        if key == "y" and self._fill:
            return np.append(values, 0.0)       # the fill reaches zero
        return values

    def _mark_points(self):
        index = np.array(sorted(i for i in self._highlighted
                                if 0 <= i < len(self._y)), dtype=np.int64)
        return (self._x[index] + self._x[index + 1]) / 2, self._y[index]

    def _default_tooltip(self, index):
        low, high = self._x[index], self._x[index + 1]
        return (f"{self._prefix()}{low:.4g}–{high:.4g}: "
                f"{self._y[index]:.4g}{self._error_text(index, 'y')}")

    def _item_at(self, chart, sx, sy, tolerance):
        """The bin under the point (between zero and its value)."""
        ax, ay = chart.axisX(), chart.axisY()
        edges = ax.toScene(self._x)
        x0, x1 = edges[:-1], edges[1:]
        base, tops = ay._baseline(), ay.toScene(self._y)
        inside = ((np.minimum(x0, x1) <= sx) & (sx <= np.maximum(x0, x1)) &
                  (np.minimum(base, tops) - tolerance <= sy) &
                  (sy <= np.maximum(base, tops) + tolerance))
        hits = np.flatnonzero(inside)
        return int(hits[0]) if hits.size else None

    def _anchor(self, handle):
        if handle.kind == "value":
            return None, self._y[handle.index]
        return self._x[handle.index], None

    def __init__(self, edges, values, name="", color=None, fill=False,
                 width=2.0):
        self._fill = bool(fill)
        self._fill_plot = None
        self._line_width = float(width)
        super().__init__(edges, values, name, color)

    def _points(self, edges, values):
        if edges.shape[0] != values.shape[0] + 1:
            raise ValueError("a histogram needs len(edges) == len(values) + 1")
        return edges, values

    def edges(self):
        return self._x.copy()

    def values(self):
        return self._y.copy()

    def _columns(self):
        x = np.repeat(self._x, 2)[1:-1]
        y = np.repeat(self._y, 2)
        return {"x": x, "y": y, "zero": np.zeros_like(y)}

    def _width(self):
        return self._line_width

    def _attach(self, chart):
        self._chart = chart
        self._fill_table()
        if self._fill:
            area = chart.vtkChart().AddPlot(vtk.vtkChart.AREA)
            area.SetInputData(self._table)
            area.SetInputArray(0, "x")
            area.SetInputArray(1, "zero")
            area.SetInputArray(2, "y")
            area.SetLegendVisibility(False)
            self._fill_plot = area
        self._plot = chart.vtkChart().AddPlot(vtk.vtkChart.LINE)
        self._plot.SetInputData(self._table, "x", "y")
        self._plot.SetLabel(self._name)

    def setVisible(self, visible):
        super().setVisible(visible)
        if self._fill_plot is not None:
            self._fill_plot.SetVisible(bool(visible))

    def _style(self, color, scale):
        super()._style(color, scale)
        if self._fill_plot is not None:
            r, g, b = color
            self._fill_plot.GetBrush().SetColorF(r, g, b, 0.22)
            self._fill_plot.GetPen().SetOpacity(0)


class StemSeries(Series):
    """Vertical lines from zero to each value (discrete source lines).

    When editable, the tops drag up and down (and sideways with
    ``move_x``, e.g. to retune a line energy).
    """

    def _item_at(self, chart, sx, sy, tolerance):
        hit = self._hit(chart, sx, sy, tolerance)
        return None if hit is None else hit[1].index

    DEFAULT_MINIMUM = 0.0

    def _hit(self, chart, sx, sy, tolerance):
        """Anywhere along a stem grabs it (a thin line is hard to hit at
        its top)."""
        ax, ay = chart.axisX(), chart.axisY()
        base, tops = ay._baseline(), ay.toScene(self._y)
        reach = ((np.minimum(base, tops) - tolerance <= sy) &
                 (sy <= np.maximum(base, tops) + tolerance))
        distances = np.abs(ax.toScene(self._x) - sx)
        found = _nearest(np.where(reach, distances, np.inf), tolerance)
        return None if found is None else \
            (found[0], Handle(self, "point", found[1]))

    def _drag(self, handle, x, y):
        xs, ys = self._x.copy(), self._y.copy()
        ys[handle.index] = self._clamp(y)
        if self._move_x:
            xs[handle.index] = self._clamp_x(x)
        self._set_quiet(xs, ys)

    def _highlight(self, handle):
        i = handle.index
        return [self._x[i], self._x[i]], [0.0, self._y[i]]

    def _cursor(self, handle):
        return vtk.VTK_CURSOR_HAND if self._move_x else vtk.VTK_CURSOR_SIZENS

    def __init__(self, x, y, name="", color=None, width=2.5):
        self._line_width = float(width)
        super().__init__(x, y, name, color)

    def _columns(self):
        x = np.repeat(self._x, 2)
        y = np.column_stack([np.zeros_like(self._y), self._y]).ravel()
        return {"x": x, "y": y}

    def _width(self):
        return self._line_width

    def _configure(self, plot):
        plot.SetPolyLine(False)              # each pair of points: a segment


def box_statistics(values, whisker=1.5):
    """Box-plot statistics of ``values`` (NaNs ignored): a dict with
    ``q1``, ``median``, ``q3``, the whisker ends ``low``/``high`` (the
    furthest values within ``whisker`` x IQR of the box, Tukey's rule),
    the ``outliers`` beyond them and the count ``n``."""
    values = np.asarray(values, dtype=float)
    values = values[np.isfinite(values)]
    if values.size == 0:
        raise ValueError("a box needs at least one finite value")
    q1, median, q3 = np.percentile(values, [25, 50, 75])
    reach = whisker * (q3 - q1)
    inside = values[(values >= q1 - reach) & (values <= q3 + reach)]
    low, high = float(inside.min()), float(inside.max())
    outliers = np.sort(values[(values < low) | (values > high)])
    return {"q1": float(q1), "median": float(median), "q3": float(q3),
            "low": low, "high": high, "outliers": outliers,
            "n": int(values.size)}


class BoxSeries(Series):
    """Box plots of ``groups`` (one sequence of values each) at
    ``positions`` (default 1, 2, ...): the Q1–Q3 box with its median,
    whiskers to the furthest values within ``whisker`` x IQR (with caps)
    and the outliers as points. ``labels`` name the groups on the x axis.
    Hovering a box shows its statistics; points of the series (for
    highlighting) are the medians.
    """

    PLOT_TYPE = vtk.vtkChart.LINE

    def __init__(self, groups, positions=None, labels=None, name="",
                 color=None, width=0.6, whisker=1.5):
        self._box_width = float(width)
        self._whisker = float(whisker)
        self._labels = None if labels is None else [str(v) for v in labels]
        self._fill_plot = None
        self._outlier_plot = None
        self._area_table = vtk.vtkTable()
        self._outlier_table = vtk.vtkTable()
        positions, medians = self._compute(groups, positions)
        super().__init__(positions, medians, name, color)

    def _compute(self, groups, positions):
        groups = [np.asarray(group, dtype=float) for group in groups]
        if positions is None:
            positions = np.arange(1, len(groups) + 1, dtype=float)
        positions = np.asarray(positions, dtype=float)
        if len(positions) != len(groups):
            raise ValueError("one position per group is needed")
        self._groups = groups
        self._stats = [box_statistics(group, self._whisker)
                       for group in groups]
        return positions, np.array([st["median"] for st in self._stats])

    def statistics(self):
        """The :func:`box_statistics` of each group."""
        return [dict(st) for st in self._stats]

    def labels(self):
        return list(self._labels) if self._labels is not None else None

    def setGroups(self, groups, positions=None, labels=None):
        if labels is not None:
            self._labels = [str(v) for v in labels]
        positions, medians = self._compute(
            groups, positions if positions is not None else
            (self._x if len(self._x) == len(groups) else None))
        self.setData(positions, medians)
        if self._chart is not None:
            self._label_axis()

    # -- drawing ------------------------------------------------------------------------
    def _half(self):
        if len(self._x) > 1:
            spacing = float(np.diff(np.unique(self._x)).min())
        else:
            spacing = 1.0
        return self._box_width * spacing / 2.0

    def _columns(self):
        """Segments: box outline, median, whiskers and their caps."""
        half, cap = self._half(), self._half() / 2.0
        xs, ys = [], []

        def segment(x0, y0, x1, y1):
            xs.extend((x0, x1))
            ys.extend((y0, y1))

        for x, st in zip(self._x, self._stats):
            left, right = x - half, x + half
            q1, q3 = st["q1"], st["q3"]
            segment(left, q1, right, q1)
            segment(right, q1, right, q3)
            segment(right, q3, left, q3)
            segment(left, q3, left, q1)
            segment(left, st["median"], right, st["median"])
            segment(x, q3, x, st["high"])
            segment(x, q1, x, st["low"])
            segment(x - cap, st["high"], x + cap, st["high"])
            segment(x - cap, st["low"], x + cap, st["low"])
        return {"x": np.asarray(xs, float), "y": np.asarray(ys, float)}

    def _fill_tables(self):
        half = self._half()
        xs, low, high, mask = [], [], [], []
        for x, st in zip(self._x, self._stats):
            for px, valid in ((x - half, 1), (x + half, 1), (x + half, 0)):
                xs.append(px)
                low.append(st["q1"])
                high.append(st["q3"])
                mask.append(valid)
        self._set_columns(self._area_table,
                          {"x": xs, "low": low, "high": high}, mask=mask)
        outliers = [(x, value) for x, st in zip(self._x, self._stats)
                    for value in st["outliers"]]
        self._set_columns(self._outlier_table,
                          {"x": [o[0] for o in outliers],
                           "y": [o[1] for o in outliers]})

    @staticmethod
    def _set_columns(table, columns, mask=None):
        while table.GetNumberOfColumns():
            table.RemoveColumn(0)
        for name, values in columns.items():
            array = numpy_to_vtk(np.ascontiguousarray(values, dtype=float),
                                 deep=True)
            array.SetName(name)
            table.AddColumn(array)
        if mask is not None:
            array = vtk.vtkCharArray()
            array.SetName("valid")
            for value in mask:
                array.InsertNextValue(chr(int(value)))   # one char each
            table.AddColumn(array)
        table.Modified()

    def _fill_table_and_extras(self):
        Series._fill_table(self)
        self._fill_tables()

    def _attach(self, chart):
        self._chart = chart
        self._fill_table_and_extras()
        area = chart.vtkChart().AddPlot(vtk.vtkChart.AREA)
        area.SetInputData(self._area_table)
        area.SetInputArray(0, "x")
        area.SetInputArray(1, "low")
        area.SetInputArray(2, "high")
        area.SetValidPointMaskName("valid")
        area.SetLegendVisibility(False)
        self._fill_plot = area
        self._plot = chart.vtkChart().AddPlot(vtk.vtkChart.LINE)
        self._plot.SetInputData(self._table, "x", "y")
        self._plot.SetLabel(self._name)
        self._plot.SetPolyLine(False)
        points = chart.vtkChart().AddPlot(vtk.vtkChart.POINTS)
        points.SetInputData(self._outlier_table, "x", "y")
        points.SetLegendVisibility(False)
        points.SetMarkerStyle(vtk.vtkPlotPoints.CIRCLE)
        self._outlier_plot = points
        self._label_axis()

    def _label_axis(self):
        if self._labels is not None and self._chart is not None:
            self._chart.axisX().setTickLabels(self._x, self._labels)

    def _extra_plots(self):
        return (self._outlier_plot,)

    def setData(self, x, y):
        self._x, self._y = self._points(np.asarray(x, float),
                                        np.asarray(y, float))
        self._fill_table_and_extras()
        self._update_marks()
        if self._chart is not None:
            self._chart._changed(data=True)

    def setVisible(self, visible):
        super().setVisible(visible)
        for plot in (self._fill_plot, self._outlier_plot):
            if plot is not None:
                plot.SetVisible(bool(visible))

    def _style(self, color, scale):
        r, g, b = color
        self._plot.SetColorF(r, g, b)
        self._plot.SetWidth(1.5 * scale)
        self._fill_plot.GetBrush().SetColorF(r, g, b, 0.25)
        self._fill_plot.GetPen().SetOpacity(0)
        self._outlier_plot.SetColorF(r, g, b)
        self._outlier_plot.SetMarkerSize(6.0 * scale)

    def _extent(self, key, chart):
        if key == "x":
            half = self._half()
            return np.concatenate([self._x - half, self._x + half])
        values = [st[k] for st in self._stats for k in ("low", "high")]
        values += [v for st in self._stats for v in st["outliers"]]
        return np.asarray(values, float)

    # -- hover and click -----------------------------------------------------------------------
    def _item_at(self, chart, sx, sy, tolerance):
        half = self._half()
        ax, ay = chart.axisX(), chart.axisY()
        for index, (x, st) in enumerate(zip(self._x, self._stats)):
            x0, x1 = sorted((ax.toScene(x - half), ax.toScene(x + half)))
            y0, y1 = sorted((ay.toScene(st["low"]), ay.toScene(st["high"])))
            if x0 <= sx <= x1 and y0 - tolerance <= sy <= y1 + tolerance:
                return index
        return None

    def _default_tooltip(self, index):
        st = self._stats[index]
        label = (self._labels[index] if self._labels is not None
                 else f"{self._x[index]:.4g}")
        text = (f"{self._prefix()}{label}: median {st['median']:.4g}, "
                f"Q1–Q3 {st['q1']:.4g}–{st['q3']:.4g}, "
                f"whiskers {st['low']:.4g}–{st['high']:.4g}, n={st['n']}")
        if len(st["outliers"]):
            text += f", {len(st['outliers'])} outliers"
        return text


class ErrorBarSeries(Series):
    """Error bars at points ``(x, y)``: vertical bars from ``errors``
    (y) and horizontal ones from ``x_errors``; each is one array for
    symmetric bars or a ``(lower, upper)`` pair, in data units. With
    ``caps`` each bar ends in a short perpendicular cap ``cap_px`` logical
    px across (kept that size as the view zooms).

    Not in the legend; ``of=series`` draws them in that series' colour and
    adds them to its tooltips (e.g. points of a scatter, or the bin
    centres of a histogram).
    """

    HOVERABLE = False             # their series' tooltip includes them

    def __init__(self, x, y, errors=None, name="", color=None, of=None,
                 width=1.5, x_errors=None, caps=True, cap_px=4.0):
        count = len(np.atleast_1d(x))
        if errors is None and x_errors is None:
            raise ValueError("give errors (y) or x_errors")
        self._errors = self._split(errors if errors is not None else 0.0,
                                   count)
        self._x_errors = (None if x_errors is None
                          else self._split(x_errors, count))
        self._of = of
        self._line_width = float(width)
        self._caps = bool(caps)
        self._cap_px = float(cap_px)
        self._cap_view = None         # view the caps were sized for
        super().__init__(x, y, name, color)

    @staticmethod
    def _split(errors, count):
        if isinstance(errors, tuple) and len(errors) == 2:
            lower, upper = (np.broadcast_to(np.asarray(e, float), (count,))
                            for e in errors)
        else:
            lower = upper = np.broadcast_to(np.asarray(errors, float),
                                            (count,))
        if np.any(lower < 0) or np.any(upper < 0):
            raise ValueError("error bars must not be negative")
        return lower.copy(), upper.copy()

    def errors(self):
        """``(lower, upper)`` vertical (y) bar lengths."""
        return self._errors[0].copy(), self._errors[1].copy()

    def xErrors(self):
        """``(lower, upper)`` horizontal (x) bar lengths, or None."""
        if self._x_errors is None:
            return None
        return self._x_errors[0].copy(), self._x_errors[1].copy()

    def setData(self, x, y, errors=None, x_errors=None):
        count = len(np.atleast_1d(x))
        if errors is not None:
            self._errors = self._split(errors, count)
        if x_errors is not None:
            self._x_errors = self._split(x_errors, count)
        lengths = [len(self._errors[0])]
        if self._x_errors is not None:
            lengths.append(len(self._x_errors[0]))
        if any(length != count for length in lengths):
            raise ValueError("one error per point is needed")
        self._cap_view = None
        super().setData(x, y)

    def color(self):
        if self._color is None and self._of is not None:
            return self._of.color()
        return self._color

    def _segments(self, chart=None):
        """Segment endpoints ``(x0, y0, x1, y1)`` arrays: the bars and,
        with a chart to size them by, their caps."""
        x, y = self._x, self._y
        low, high = self._errors
        parts = []
        vertical = (low + high) > 0
        parts.append((x[vertical], (y - low)[vertical],
                      x[vertical], (y + high)[vertical]))
        horizontal = None
        if self._x_errors is not None:
            x_low, x_high = self._x_errors
            horizontal = (x_low + x_high) > 0
            parts.append(((x - x_low)[horizontal], y[horizontal],
                          (x + x_high)[horizontal], y[horizontal]))
        if self._caps and chart is not None:
            ax, ay = chart.axisX(), chart.axisY()
            half = self._cap_px * ui_scale() / 2.0
            sx = ax.toScene(x)
            sy = ay.toScene(y)
            for ends in (y - low, y + high):
                ey = ends[vertical]
                parts.append((ax.fromScene(sx[vertical] - half), ey,
                              ax.fromScene(sx[vertical] + half), ey))
            if horizontal is not None:
                x_low, x_high = self._x_errors
                for ends in (x - x_low, x + x_high):
                    ex = ends[horizontal]
                    parts.append((ex, ay.fromScene(sy[horizontal] - half),
                                  ex, ay.fromScene(sy[horizontal] + half)))
        return tuple(np.concatenate([np.atleast_1d(np.asarray(p[i], float))
                                     for p in parts]) for i in range(4))

    def _columns(self):
        x0, y0, x1, y1 = self._segments(self._chart)
        return {"x": np.column_stack([x0, x1]).ravel(),
                "y": np.column_stack([y0, y1]).ravel()}

    def _extent(self, key, chart):
        x0, y0, x1, y1 = self._segments()          # the bars, not the caps
        return np.concatenate([x0, x1] if key == "x" else [y0, y1])

    def _view_key(self, chart):
        return tuple(round(v, 6) for axis in (chart.axisX(), chart.axisY())
                     for v in axis._span())

    def _update_decimation(self, chart, full=False):
        """Re-size the caps (logical px) after the view changed."""
        if not self._caps:
            return False
        key = self._view_key(chart)
        if key == self._cap_view:
            return False
        self._cap_view = key
        self._fill_table()
        return True

    def _attach(self, chart):
        super()._attach(chart)
        self._plot.SetLegendVisibility(False)

    def _configure(self, plot):
        plot.SetPolyLine(False)

    def _width(self):
        return self._line_width


# ---------------------------------------------------------------------------------------
# Charts


def _style_text(prop, colour, size, bold=False):
    apply_ui_font(prop, bold=bold)
    prop.SetColor(*colour[:3])
    prop.SetFontSize(size)


def _style_legend(legend, tokens, size):
    _style_text(legend.GetLabelProperties(), tokens["text"], size)
    if hasattr(legend, "SetLabelSize"):
        legend.SetLabelSize(size)
    legend.GetBrush().SetColorF(*tokens["panel"][:3], 0.92)
    legend.GetPen().SetColorF(*tokens["border"][:3])


def _style_tooltip(tooltip, tokens, size):
    _style_text(tooltip.GetTextProperties(), tokens["text"], size)
    tooltip.GetBrush().SetColorF(*tokens.get("tooltip", tokens["panel"])[:3],
                                 0.97)
    tooltip.GetPen().SetColorF(*tokens["border"][:3])


class XYChart:
    """A 2D chart with x/y axes, series and a legend (``vtkChartXY``)."""

    Y_HEADROOM = 0.12        # fraction above the data on linear y axes
    CHART_CLASS = vtk.vtkChartXY
    FORWARD_HOVER = True     # the VTK chart sees pointer moves without a button

    def __init__(self, title=""):
        self._chart = self.CHART_CLASS()
        self._chart.SetTitle(str(title))
        self._series = []
        self._axes = {
            "x": Axis(self._chart.GetAxis(vtk.vtkAxis.BOTTOM), self, 0),
            "y": Axis(self._chart.GetAxis(vtk.vtkAxis.LEFT), self, 1),
        }
        for axis in self._axes.values():
            axis.vtkAxis().SetTitle("")       # not VTK's "X Axis"/"Y Axis"
        self._highlight_plot = None
        self._highlight_table = vtk.vtkTable()
        self._undo, self._redo = [], []
        self.edited = Signal()           # (series) after a drag or undo
        self.clicked = Signal()          # (series, index) on a click
        self._legend = True
        self._chart.SetShowLegend(True)
        legend = self._chart.GetLegend()
        legend.SetHorizontalAlignment(vtk.vtkChartLegend.RIGHT)
        legend.SetVerticalAlignment(vtk.vtkChartLegend.TOP)
        self._chart.SetActionToButton(vtk.vtkChart.PAN,
                                      vtk.vtkContextMouseEvent.LEFT_BUTTON)
        self._chart.SetActionToButton(vtk.vtkChart.ZOOM,
                                      vtk.vtkContextMouseEvent.RIGHT_BUTTON)
        self._view = None
        self.changed = Signal()

    # -- access -----------------------------------------------------------------------
    def vtkChart(self):
        return self._chart

    def title(self):
        return self._chart.GetTitle()

    def setTitle(self, title):
        self._chart.SetTitle(str(title))
        self._update_border()
        self._changed()

    # Space vtkChartXY keeps where an axis is hidden (the top and right):
    # room for a title, or just a margin for the outer tick labels.
    TITLE_BORDER_PX, MARGIN_BORDER_PX = 20, 10

    def _update_border(self):
        _tokens, scale, _dark = getattr(self, "_theme",
                                        (None, ui_scale(), False))
        border = self.TITLE_BORDER_PX if self.title() else \
            self.MARGIN_BORDER_PX
        self._chart.SetHiddenAxisBorder(int(round(border * scale)))

    def axisX(self):
        return self._axes["x"]

    def axisY(self):
        return self._axes["y"]

    def series(self):
        return list(self._series)

    LEGEND_POSITIONS = {
        "top-right": (vtk.vtkChartLegend.RIGHT, vtk.vtkChartLegend.TOP),
        "top-left": (vtk.vtkChartLegend.LEFT, vtk.vtkChartLegend.TOP),
        "bottom-right": (vtk.vtkChartLegend.RIGHT, vtk.vtkChartLegend.BOTTOM),
        "bottom-left": (vtk.vtkChartLegend.LEFT, vtk.vtkChartLegend.BOTTOM),
    }

    def setLegendPosition(self, position):
        """``"top-right"`` (default), ``"top-left"``, ``"bottom-right"`` or
        ``"bottom-left"`` inside the plot area."""
        if position not in self.LEGEND_POSITIONS:
            raise ValueError(f"legend position must be one of "
                             f"{sorted(self.LEGEND_POSITIONS)}")
        horizontal, vertical = self.LEGEND_POSITIONS[position]
        legend = self._chart.GetLegend()
        legend.SetHorizontalAlignment(horizontal)
        legend.SetVerticalAlignment(vertical)
        self._changed()

    def setLegendVisible(self, visible):
        self._legend = bool(visible)
        self._chart.SetShowLegend(self._legend)
        self._changed()

    # -- series ---------------------------------------------------------------------------
    def addSeries(self, series):
        self._series.append(series)
        series._attach(self)
        self._apply_series_style()
        self.resetView()
        return series

    def addLine(self, x, y, **options):
        return self.addSeries(LineSeries(x, y, **options))

    def addScatter(self, x, y, **options):
        return self.addSeries(ScatterSeries(x, y, **options))

    def addBars(self, x, y, **options):
        return self.addSeries(BarSeries(x, y, **options))

    def addStep(self, edges, values, **options):
        return self.addSeries(StepSeries(edges, values, **options))

    def addStems(self, x, y, **options):
        return self.addSeries(StemSeries(x, y, **options))

    def addBoxes(self, groups, **options):
        """Box plots of ``groups`` (see :class:`BoxSeries`)."""
        return self.addSeries(BoxSeries(groups, **options))

    def addErrorBars(self, x, y, errors=None, **options):
        return self.addSeries(ErrorBarSeries(x, y, errors, **options))

    def addErrorScatter(self, x, y, errors=None, x_errors=None, name="",
                        color=None, caps=True, **options):
        """Points with error bars (y ``errors``, ``x_errors``, or both);
        returns ``(points, bars)``. The bars share the points' colour and
        their errors show in the points' tooltips."""
        points = self.addScatter(x, y, name=name, color=color, **options)
        bars = self.addErrorBars(x, y, errors, x_errors=x_errors, of=points,
                                 caps=caps, name=f"{name} errors")
        return points, bars

    def removeSeries(self, series):
        if series not in self._series:
            return
        self._series.remove(series)
        for plot in (series._plot, getattr(series, "_fill_plot", None),
                     series._mark_plot, *getattr(series, "_extra_plots",
                                                  lambda: ())()):
            if plot is not None:
                self._chart.RemovePlotInstance(plot)
        series._chart = series._plot = series._mark_plot = None
        self._apply_series_style()
        self.resetView()

    def clear(self):
        for series in list(self._series):
            self.removeSeries(series)

    # -- editing --------------------------------------------------------------------------------
    def handleAt(self, sx, sy, tolerance=6.0):
        """The editable :class:`Handle` nearest chart-scene point
        ``(sx, sy)`` within ``tolerance`` px, or None."""
        best = None
        for series in reversed(self._series):     # topmost first
            if not series.isEditable() or series._plot is None or \
                    not series.isVisible():
                continue
            hit = series._hit(self, sx, sy, tolerance)
            if hit is not None and (best is None or hit[0] < best[0]):
                best = hit
        return None if best is None else best[1]

    def _update_decimation(self, full=False):
        """Decimate long line series for the current view (``full``: draw
        every point); True if anything changed."""
        changed = False
        for series in self._series:
            update = getattr(series, "_update_decimation", None)
            if update is not None and series._plot is not None:
                changed = update(self, full=full) or changed
        return changed

    def _update_short_axes(self):
        """Short axes get their own nice ticks; True if any changed."""
        scale = getattr(self, "_theme", (None, ui_scale()))[1]
        changed = False
        for axis in self._axes.values():
            changed = axis._update_short_ticks(scale) or changed
        return changed

    def tooltipAt(self, sx, sy, tolerance=6.0):
        """``(series, index, text)`` for the hover tooltip at chart-scene
        point ``(sx, sy)`` (topmost series first), or None."""
        for series in reversed(self._series):
            if not series.HOVERABLE or series._plot is None or \
                    not series.isVisible():
                continue
            index = series._item_at(self, sx, sy, tolerance)
            if index is not None:
                return series, index, series.tooltipText(index)
        return None

    def itemAt(self, sx, sy, tolerance=6.0):
        """``(series, index)`` of the clickable item at chart-scene point
        ``(sx, sy)`` (topmost series first), or None."""
        for series in reversed(self._series):
            if not series.isClickable() or series._plot is None or \
                    not series.isVisible():
                continue
            index = series._item_at(self, sx, sy, tolerance)
            if index is not None:
                return series, index
        return None

    def _record(self, series, before, after):
        self._undo.append((series, before, after))
        del self._undo[:-200]
        self._redo.clear()

    def canUndo(self):
        return bool(self._undo)

    def canRedo(self):
        return bool(self._redo)

    def undo(self):
        """Undo the last edit; returns the series changed (or None)."""
        if not self._undo:
            return None
        series, before, after = self._undo.pop()
        self._redo.append((series, before, after))
        series._set_quiet(*before)
        series.edited.emit(series)
        self.edited.emit(series)
        return series

    def redo(self):
        if not self._redo:
            return None
        series, before, after = self._redo.pop()
        self._undo.append((series, before, after))
        series._set_quiet(*after)
        series.edited.emit(series)
        self.edited.emit(series)
        return series

    # -- export ---------------------------------------------------------------------------
    def export(self, path, size=None, scale=1.0, **options):
        """Write the chart as an image, vector file or CSV, by the
        extension of ``path`` (see :mod:`multipanel.chart_export`)."""
        from .chart_export import export_chart

        return export_chart(self, path, size=size, scale=scale, **options)

    def toCsv(self):
        """The visible series as CSV text."""
        from .chart_export import chart_csv

        return chart_csv(self)

    def clearHistory(self):
        self._undo.clear()
        self._redo.clear()

    def _show_highlight(self, xs, ys):
        table = self._highlight_table
        while table.GetNumberOfColumns():
            table.RemoveColumn(0)
        for name, values in (("x", xs), ("y", ys)):
            array = numpy_to_vtk(np.asarray(values, dtype=float), deep=True)
            array.SetName(name)
            table.AddColumn(array)
        table.Modified()
        if self._highlight_plot is None:
            plot = self._chart.AddPlot(vtk.vtkChart.LINE)
            plot.SetInputData(table, "x", "y")
            plot.SetLegendVisibility(False)
            plot.SetMarkerStyle(vtk.vtkPlotPoints.CIRCLE)
            self._highlight_plot = plot
            self._style_highlight()
        self._highlight_plot.SetVisible(True)
        self._changed()

    def _hide_highlight(self):
        if self._highlight_plot is not None and \
                self._highlight_plot.GetVisible():
            self._highlight_plot.SetVisible(False)
            self._changed()

    def _style_highlight(self):
        if self._highlight_plot is None:
            return
        tokens, scale, _dark = getattr(self, "_theme",
                                       (_DEFAULT_TOKENS, ui_scale(), False))
        self._highlight_plot.SetColorF(*tokens["accent"])
        self._highlight_plot.SetWidth(4.0 * scale)
        self._highlight_plot.SetMarkerSize(9.0 * scale)

    # -- view ------------------------------------------------------------------------------
    def resetView(self):
        """Fit the data (axes with a fixed range return to it)."""
        self._fit()
        self._changed()

    def _data_bounds(self, key, positive=False):
        values = []
        for series in self._series:
            if series._plot is not None and series.isVisible():
                column = series._extent(key, self)
                column = column[np.isfinite(column)]
                if positive:
                    column = column[column > 0]
                values.append(column)
        values = [v for v in values if v.size]
        if not values:
            return None
        joined = np.concatenate(values)
        return float(joined.min()), float(joined.max())

    def _fit(self):
        """Fit automatic axes to the data now (vtkChartXY would only on
        its next paint), rounded to nice ticks as VTK does."""
        self._chart.RecalculateBounds()
        for key, axis in self._axes.items():
            if axis._fixed is not None:
                axis._reset()
                continue
            bounds = self._data_bounds(key, positive=axis.isLogScale())
            if bounds is None:
                continue
            low, high = bounds
            if axis._include_zero and not axis.isLogScale():
                low, high = min(low, 0.0), max(high, 0.0)
            categories = axis.tickLabels() is not None
            if high <= low:
                pad = abs(low) * 0.05 or 0.5
                low, high = low - pad, high + pad
            elif key == "y" and not axis.isLogScale() and not categories \
                    and self._legend:
                high += (high - low) * self.Y_HEADROOM   # room for the legend
            if not categories:      # labelled positions: show them exactly
                low, high = _nice_range(low, high, log=axis.isLogScale())
            vtk_axis = axis.vtkAxis()
            # FIXED keeps this fit: vtkChartXY would refit AUTO axes on
            # every paint, to a range that depends on the axis's pixel
            # length. (The Axis still counts as automatic: _fixed is None.)
            vtk_axis.SetBehavior(vtk.vtkAxis.FIXED)
            axis._apply_range(low, high)

    def _changed(self, data=False):
        if data:
            self._fit()
        self.changed.emit()

    # -- theme -------------------------------------------------------------------------------
    def applyTheme(self, tokens, scale=1.0, dark=False, text_scale=None):
        """Colour and size every part from theme ``tokens``: line widths
        and margins by ``scale`` (display px per logical px), font point
        sizes by ``text_scale`` (default ``scale``; a view on a high-DPI
        window passes the size preference alone, as VTK scales text by
        the DPI)."""
        self._theme = (tokens, scale, dark)
        self._update_border()
        text, muted = tokens["text"], tokens["muted"]
        border = tokens["border"]
        grid = _mix(tokens["panel"], border, 0.55)
        text_scale = scale if text_scale is None else text_scale
        size = max(7, int(round(11 * text_scale)))
        chart = self._chart
        chart.GetBackgroundBrush().SetColorF(0.0, 0.0, 0.0, 0.0)
        title = chart.GetTitleProperties()
        apply_ui_font(title, bold=True)
        title.SetColor(*text)
        title.SetFontSize(max(8, int(round(12 * text_scale))))
        for axis in self._axes.values():
            vtk_axis = axis.vtkAxis()
            vtk_axis.GetPen().SetColorF(*border)
            vtk_axis.GetPen().SetWidth(max(1.0, scale))
            vtk_axis.GetGridPen().SetColorF(*grid)
            vtk_axis.GetGridPen().SetWidth(max(1.0, scale))
            for prop, colour in ((vtk_axis.GetLabelProperties(), muted),
                                 (vtk_axis.GetTitleProperties(), text)):
                apply_ui_font(prop, bold=False)
                prop.SetColor(*colour)
                prop.SetFontSize(size)
        legend = chart.GetLegend()
        if isinstance(legend, vtk.vtkChartLegend):
            _style_legend(legend, tokens, size)
        tooltip = self._tooltip_item()
        if tooltip is not None:
            _style_tooltip(tooltip, tokens, size)
        self._style_extra(tokens, scale, dark, size)
        self._apply_series_style()
        self._style_highlight()
        self._changed()

    def _style_extra(self, tokens, scale, dark, size):
        """Hook: theme parts subclasses add (e.g. a colour legend)."""

    def _tooltip_item(self):
        return self._chart.GetTooltip()

    def _apply_series_style(self):
        tokens, scale, dark = getattr(self, "_theme",
                                      (_DEFAULT_TOKENS, ui_scale(), False))
        colours = palette(dark)
        automatic = 0
        assigned = {}
        for series in self._series:
            colour = series.color()
            follows = getattr(series, "_of", None)
            if colour is None and follows is not None:
                colour = assigned.get(id(follows))
            if colour is None:
                colour = colours[automatic % len(colours)]
                automatic += 1
            assigned[id(series)] = colour
            if series._plot is not None:
                series._style(colour, scale)
                series._style_marks()


class Histogram2DChart(XYChart):
    """A 2D histogram (heat map) of ``values`` (``(ny, nx)``, rows along
    y) over ``x_range`` x ``y_range``, coloured by ``colormap`` with a
    colour legend; ``log=True`` colours on a log scale (non-positive bins
    take the lowest colour). Hovering shows a bin and its value.
    (``vtkChartHistogram2D``.)
    """

    CHART_CLASS = vtk.vtkChartHistogram2D

    def __init__(self, values, x_range=(0.0, 1.0), y_range=(0.0, 1.0),
                 title="", colormap="viridis", log=False, value_title=""):
        self._image = vtk.vtkImageData()
        self._colormap = colormap
        self._log = bool(log)
        self._value_title = str(value_title)
        super().__init__(title)
        self._legend = True
        self._chart.SetShowLegend(True)
        self.setData(values, x_range, y_range)

    # -- data -----------------------------------------------------------------------
    def setData(self, values, x_range=None, y_range=None):
        values = np.asarray(values, dtype=float)
        if values.ndim != 2 or 0 in values.shape:
            raise ValueError("values must be a non-empty (ny, nx) array")
        self._values = values.copy()
        if x_range is not None:
            self._x_range = (float(x_range[0]), float(x_range[1]))
        if y_range is not None:
            self._y_range = (float(y_range[0]), float(y_range[1]))
        ny, nx = values.shape
        (x0, x1), (y0, y1) = self._x_range, self._y_range
        if not (x1 > x0 and y1 > y0):
            raise ValueError("ranges must increase")
        image = self._image
        image.SetDimensions(nx, ny, 1)
        image.SetOrigin(x0, y0, 0.0)        # the first bin's lower corner
        image.SetSpacing((x1 - x0) / nx, (y1 - y0) / ny, 1.0)
        scalars = numpy_to_vtk(np.ascontiguousarray(values.ravel()),
                               deep=True)
        scalars.SetName("values")
        image.GetPointData().SetScalars(scalars)
        image.Modified()
        self._chart.SetInputData(image)
        self._update_colours()
        self._changed(data=True)

    def values(self):
        return self._values.copy()

    def ranges(self):
        return self._x_range, self._y_range

    def edges(self):
        """``(x_edges, y_edges)`` of the bins."""
        ny, nx = self._values.shape
        return (np.linspace(*self._x_range, nx + 1),
                np.linspace(*self._y_range, ny + 1))

    def isLogScale(self):
        return self._log

    def setLogScale(self, log):
        self._log = bool(log)
        self._update_colours()
        self._changed()

    def setColormap(self, colormap):
        self._colormap = colormap
        self._update_colours()
        self._changed()

    def colourRange(self):
        finite = self._values[np.isfinite(self._values)]
        if self._log:
            finite = finite[finite > 0]
        if finite.size == 0:
            return (1.0, 10.0) if self._log else (0.0, 1.0)
        low, high = float(finite.min()), float(finite.max())
        if high <= low:
            high = low * 10 if self._log else low + 1.0
        return low, high

    def _update_colours(self):
        from .colormap_utils import make_LUT

        low, high = self.colourRange()
        table = make_LUT(self._colormap, c_range=(low, high),
                         scale_type="logarithmic" if self._log else "linear",
                         set_outside_colors_to_edges=True)
        table.SetRange(low, high)
        self._lut = table
        self._chart.SetTransferFunction(table)
        axis = self._legend_axis()
        if axis is not None:
            axis.SetLogScale(self._log)
            axis.SetRangeLabelsVisible(False)     # no raw data extremes

    def _legend_axis(self):
        """The colour legend's own value axis (its only child item)."""
        legend = self._chart.GetLegend()
        for index in range(legend.GetNumberOfItems() if legend else 0):
            item = legend.GetItem(index)
            if isinstance(item, vtk.vtkAxis):
                return item
        return None

    # -- view -------------------------------------------------------------------------
    def _fit(self):
        """The axes show the bins exactly."""
        for axis, (low, high) in zip((self.axisX(), self.axisY()),
                                     (self._x_range, self._y_range)):
            if axis._fixed is not None:
                axis._reset()
                continue
            axis.vtkAxis().SetBehavior(vtk.vtkAxis.FIXED)
            axis._apply_range(low, high)

    def binAt(self, x, y):
        """``(row, column)`` of the bin at data ``(x, y)``, or None."""
        (x0, x1), (y0, y1) = self._x_range, self._y_range
        ny, nx = self._values.shape
        if not (x0 <= x <= x1 and y0 <= y <= y1):
            return None
        column = min(nx - 1, int((x - x0) / (x1 - x0) * nx))
        row = min(ny - 1, int((y - y0) / (y1 - y0) * ny))
        return row, column

    def tooltipAt(self, sx, sy, tolerance=6.0):
        x = self.axisX().fromScene(sx)
        y = self.axisY().fromScene(sy)
        found = self.binAt(x, y)
        if found is None:
            return None
        row, column = found
        x_edges, y_edges = self.edges()
        text = (f"{x_edges[column]:.4g}–{x_edges[column + 1]:.4g}, "
                f"{y_edges[row]:.4g}–{y_edges[row + 1]:.4g}: "
                f"{self._values[row, column]:.4g}")
        return self, found, text

    def _csv_rows(self):
        from .chart_export import _number

        x_edges, y_edges = self.edges()
        rows = []
        name = self.title() or "histogram2d"
        for row in range(self._values.shape[0]):
            for column in range(self._values.shape[1]):
                rows.append({"series": name, "kind": "cell",
                             "x_low": _number(x_edges[column]),
                             "x_high": _number(x_edges[column + 1]),
                             "y_low": _number(y_edges[row]),
                             "y_high": _number(y_edges[row + 1]),
                             "y": _number(self._values[row, column])})
        return rows

    def _style_extra(self, tokens, scale, dark, size):
        legend = self._chart.GetLegend()
        if legend is None:
            return
        _style_text(legend.GetLabelProperties(), tokens["muted"], size)
        legend.SetTitle(self._value_title)
        axis = self._legend_axis()
        if axis is not None:
            _style_text(axis.GetLabelProperties(), tokens["muted"], size)
            _style_text(axis.GetTitleProperties(), tokens["text"], size)
            axis.GetPen().SetColorF(*tokens["border"][:3])


class PieChart:
    """A pie chart of ``values`` with ``labels`` (``vtkChartPie``), in
    the theme palette, with a legend and hover tooltips (label, value and
    share). Slices start at 3 o'clock and run anticlockwise.
    ``setClickable()`` reports clicks as ``clicked(chart, index)``.
    It has no axes; it works in a :class:`ChartView`/:func:`ChartPanel`
    and exports like an :class:`XYChart`.
    """

    FORWARD_HOVER = False     # its own tooltip (VTK's is not themeable)

    def __init__(self, labels=(), values=(), title="", colors=None):
        self._chart = vtk.vtkChartPie()
        self._chart.SetTitle(str(title))
        self._plot = self._chart.AddPlot(0)
        self._table = vtk.vtkTable()
        self._tooltip = vtk.vtkTooltipItem()
        self._tooltip.SetVisible(False)
        self._chart.AddItem(self._tooltip)
        self._colors = None if colors is None else [tuple(c[:3])
                                                     for c in colors]
        self._clickable = False
        self._legend = True
        self._chart.SetShowLegend(True)
        self._view = None
        self.changed = Signal()
        self.edited = Signal()
        self.clicked = Signal()          # (chart, index)
        self.setData(labels, values)

    def vtkChart(self):
        return self._chart

    def title(self):
        return self._chart.GetTitle()

    def setTitle(self, title):
        self._chart.SetTitle(str(title))
        self._changed()

    def labels(self):
        return list(self._labels)

    def values(self):
        return self._values.copy()

    def setData(self, labels, values):
        values = np.asarray(values, dtype=float)
        labels = [str(label) for label in labels]
        if len(labels) != len(values):
            raise ValueError("one label per value is needed")
        if np.any(values < 0):
            raise ValueError("pie values must not be negative")
        self._labels, self._values = labels, values.copy()
        table = self._table
        while table.GetNumberOfColumns():
            table.RemoveColumn(0)
        column = numpy_to_vtk(np.ascontiguousarray(values), deep=True)
        column.SetName("values")
        table.AddColumn(column)
        self._plot.SetInputData(table)
        self._plot.SetInputArray(0, "values")
        names = vtk.vtkStringArray()
        for label in labels:
            names.InsertNextValue(label)
        self._plot.SetLabels(names)
        self._apply_colours()
        self._changed()

    def setLegendVisible(self, visible):
        self._legend = bool(visible)
        self._chart.SetShowLegend(self._legend)
        self._changed()

    def isClickable(self):
        return self._clickable

    def setClickable(self, clickable=True):
        self._clickable = bool(clickable)

    # -- hit-testing ----------------------------------------------------------------
    def sliceAt(self, sx, sy):
        """Index of the slice at chart-scene point ``(sx, sy)``, or None."""
        total = float(self._values.sum())
        if total <= 0:
            return None
        x, y, width, height = self._plot.GetDimensions()
        radius = min(width, height) / 2.0
        dx, dy = sx - (x + width / 2.0), sy - (y + height / 2.0)
        if radius <= 0 or np.hypot(dx, dy) > radius:
            return None
        turn = (np.arctan2(dy, dx) / (2 * np.pi)) % 1.0
        ends = np.cumsum(self._values) / total
        return int(min(np.searchsorted(ends, turn, side="right"),
                       len(ends) - 1))

    def tooltipAt(self, sx, sy, tolerance=6.0):
        index = self.sliceAt(sx, sy)
        if index is None:
            return None
        share = 100.0 * self._values[index] / self._values.sum()
        return (self, index, f"{self._labels[index]}: "
                f"{self._values[index]:.4g} ({share:.1f}%)")

    def itemAt(self, sx, sy, tolerance=6.0):
        if not self._clickable:
            return None
        index = self.sliceAt(sx, sy)
        return None if index is None else (self, index)

    def handleAt(self, sx, sy, tolerance=6.0):
        return None

    # -- theme ----------------------------------------------------------------------
    def applyTheme(self, tokens, scale=1.0, dark=False, text_scale=None):
        self._theme = (tokens, scale, dark)
        text_scale = scale if text_scale is None else text_scale
        size = max(7, int(round(11 * text_scale)))
        self._chart.GetBackgroundBrush().SetColorF(0.0, 0.0, 0.0, 0.0)
        _style_text(self._chart.GetTitleProperties(), tokens["text"],
                    max(8, int(round(12 * text_scale))), bold=True)
        _style_legend(self._chart.GetLegend(), tokens, size)
        _style_tooltip(self._tooltip, tokens, size)
        self._apply_colours()
        self._changed()

    def _apply_colours(self):
        dark = getattr(self, "_theme", (None, 1.0, False))[2]
        colours = self._colors or palette(dark)
        series = vtk.vtkColorSeries()
        series.SetNumberOfColors(max(1, len(self._values)))
        for index in range(max(1, len(self._values))):
            r, g, b = colours[index % len(colours)]
            series.SetColor(index, vtk.vtkColor3ub(int(r * 255),
                                                   int(g * 255),
                                                   int(b * 255)))
        self._plot.SetColorSeries(series)

    def _tooltip_item(self):
        return self._tooltip

    # -- the ChartView/export protocol (no axes, no editing) ----------------------------
    def _changed(self, data=False):
        self.changed.emit()

    def resetView(self):
        self._changed()

    def series(self):
        return []

    def _update_decimation(self, full=False):
        return False

    def _update_short_axes(self):
        return False

    def _hide_highlight(self):
        pass

    def _show_highlight(self, xs, ys):
        pass

    def _record(self, series, before, after):
        pass

    def undo(self):
        return None

    def redo(self):
        return None

    def export(self, path, size=None, scale=1.0, **options):
        from .chart_export import export_chart

        return export_chart(self, path, size=size, scale=scale, **options)

    def toCsv(self):
        from .chart_export import chart_csv

        return chart_csv(self)

    def _csv_rows(self):
        from .chart_export import _number

        return [{"series": label, "kind": "slice", "y": _number(value)}
                for label, value in zip(self._labels, self._values)]


# ---------------------------------------------------------------------------------------
# The widget


class ChartView(WidgetMixin):
    """Shows an :class:`XYChart` as a widget (``QChartView``).

    The chart draws on the view's own :class:`~multipanel.layers.LinkedRenderer`
    (exact clipping inside panels, docks and scroll areas). Pointer input is
    delivered to the chart by the router; the camera never sees it.
    Signals: ``viewChanged`` after a pan or zoom.
    """

    FOCUS_POLICY = "ClickFocus"
    _BUTTONS = {"left": vtk.vtkContextMouseEvent.LEFT_BUTTON,
                "middle": vtk.vtkContextMouseEvent.MIDDLE_BUTTON,
                "right": vtk.vtkContextMouseEvent.RIGHT_BUTTON}

    def __init__(self, renderer, interactor, chart=None, parent=None,
                 object_name="chart_view", ui_z_order=UI_Z_PANEL_CONTROL):
        self.renderer = renderer
        self.interactor = interactor
        self.ui_z_order = int(ui_z_order)
        self._bounds = (0.0, 0.0, 0.0, 0.0)
        self._shown = True
        self._chart = None
        self._button = None
        self._last = None
        self._edit = None    # (handle, data before, grab offset) while dragging
        self._hover_handle = None
        self._hover_item = None
        self._press = None               # scene point of a left press
        self.initWidget(object_name, parent)
        self.registerFocus(interactor, self.FOCUS_POLICY)
        layer = ui_layer(renderer)
        self._content = LinkedRenderer().link(layer)
        self._content.SetLayer(layer.GetLayer())
        self._content.SetViewport(0.0, 0.0, 0.0, 0.0)
        self._content.SetDraw(False)
        interactor.GetRenderWindow().AddRenderer(self._content)
        self._actor = vtk.vtkContextActor()
        self._actor.IsUI = True
        add_actor_2d(self._content, self._actor)
        # After each paint the axes know their pixel lengths: give short
        # ones readable ticks (one more render if that changed them).
        self._content.AddObserver("EndEvent", self._after_paint)
        self.viewChanged = Signal(self)
        self.exported = Signal(self)               # (path)
        self.contextMenuAboutToShow = Signal(self)  # (menu)
        self._pending = None             # a press not yet a drag
        self.registerWithRouter(interactor)
        self.ownObserver(interactor.GetRenderWindow(), "WindowResizeEvent",
                         lambda *_: self._relayout())
        self.setChart(chart if chart is not None else XYChart())

    # -- chart -------------------------------------------------------------------------------
    def chart(self):
        return self._chart

    def setChart(self, chart):
        scene = self._actor.GetScene()
        if self._chart is not None:
            scene.RemoveItem(self._chart.vtkChart())
            self._chart.changed.disconnect(self._on_chart_changed)
        self._chart = chart
        scene.AddItem(chart.vtkChart())
        chart._view = self
        chart.changed.connect(self._on_chart_changed)
        self._applyTheme()

    def _after_paint(self, *_):
        if self._chart is None or not self._shown:
            return
        ticks = self._chart._update_short_axes()
        if self._chart._update_decimation() or ticks:
            self.requestRender()

    def _on_chart_changed(self):
        self.requestRender()

    def resetView(self):
        self._chart.resetView()
        self._chart._update_decimation()
        self.viewChanged.emit()

    # -- theme --------------------------------------------------------------------------------
    def tokens(self):
        theme = getattr(self.renderer, "theme", None)
        tokens = getattr(theme, "tokens", None)
        return tokens if tokens else _DEFAULT_TOKENS

    def _applyTheme(self):
        theme = getattr(self.renderer, "theme", None)
        dark = bool(getattr(theme, "dark_mode", False))
        self._chart.applyTheme(self.tokens(), ui_scale(), dark,
                               text_scale=font_scale())

    # -- container protocol ----------------------------------------------------------------------
    def GetBounds(self):
        return self._bounds

    def SetBounds(self, x0, x1, y0, y1):
        self._bounds = (float(x0), float(x1), float(y0), float(y1))
        self._relayout()

    def GetVisibility(self):
        return self._shown

    def SetVisibility(self, visible):
        visible = bool(visible)
        if visible != self._shown:
            self._shown = visible
            self._relayout()

    def GetEnabled(self):
        return self._shown

    def SetEnabled(self, enabled):
        self.SetVisibility(enabled)

    def isVisible(self):
        return self._shown

    def defaultSizePolicy(self):
        return SizePolicy(SizePolicy.Expanding, SizePolicy.Expanding)

    def sizeHint(self):
        return (320.0, 220.0)

    def minimumSizeHint(self):
        return (160.0, 120.0)

    def _relayout(self):
        width, height = self.viewportExtent()
        x0, x1, y0, y1 = self._bounds
        shown = self._shown and x1 > x0 and y1 > y0
        self._content.SetDraw(bool(shown))
        self._actor.SetVisibility(bool(shown))
        if shown:
            dx, dy, dw, dh = self.geometry("display")
            window = self.interactor.GetRenderWindow()
            win_w, win_h = (max(1, v) for v in window.GetSize())
            self._content.SetViewport(dx / win_w, dy / win_h,
                                      (dx + dw) / win_w, (dy + dh) / win_h)
        else:
            self._content.SetViewport(0.0, 0.0, 0.0, 0.0)
        self.requestRender()

    # -- events ---------------------------------------------------------------------------------
    def _scene_pos(self, event):
        x, y = event.globalPos()
        width, height = self.interactor.GetRenderWindow().GetSize()
        vx0, vy0, _vx1, _vy1 = self._content.GetViewport()
        return (x - vx0 * width, y - vy0 * height)

    def _context_event(self, event, button=None):
        return self._context_at(self._scene_pos(event), button)

    def _context_at(self, position, button=None):
        x, y = position
        last = self._last or (x, y)
        context = vtk.vtkContextMouseEvent()
        context.SetInteractor(self.interactor)
        if button is not None:
            context.SetButton(button)
        context.SetScreenPos(vtk.vtkVector2i(int(round(x)), int(round(y))))
        context.SetLastScreenPos(vtk.vtkVector2i(int(round(last[0])),
                                                 int(round(last[1]))))
        for setter, value in (("SetPos", (x, y)), ("SetScenePos", (x, y)),
                              ("SetLastPos", last),
                              ("SetLastScenePos", last)):
            getattr(context, setter)(vtk.vtkVector2f(*value))
        self._last = (x, y)
        return context

    # -- editing -------------------------------------------------------------------------------
    EDIT_TOLERANCE_PX = 6.0

    def _handle_at(self, event):
        sx, sy = self._scene_pos(event)
        return self._chart.handleAt(sx, sy,
                                    self.EDIT_TOLERANCE_PX * ui_scale())

    def _set_hover_handle(self, handle):
        if handle is None:
            if self._hover_handle is not None:
                self._hover_handle = None
                self.unsetCursor()
                self._chart._hide_highlight()
            return
        self._hover_handle = handle
        self.setCursor(handle.series._cursor(handle))
        self._chart._show_highlight(*handle.series._highlight(handle))

    def _grab_offset(self, handle, event):
        """Scene px from the pointer to the handle's anchor at the press,
        so grabbing a stem midway does not make its top jump."""
        sx, sy = self._scene_pos(event)
        ax, ay = handle.series._anchor(handle)
        return (0.0 if ax is None else self._chart.axisX().toScene(ax) - sx,
                0.0 if ay is None else self._chart.axisY().toScene(ay) - sy)

    CLICK_SLOP_PX = 3.0

    def _item_at(self, event):
        sx, sy = self._scene_pos(event)
        return self._chart.itemAt(sx, sy, self.EDIT_TOLERANCE_PX * ui_scale())

    def _set_hover_item(self, item):
        if item is not None:
            self._hover_item = item
            self.setCursor(vtk.VTK_CURSOR_HAND)
        elif self._hover_item is not None:
            self._hover_item = None
            self.unsetCursor()

    def _drag_to(self, event):
        handle, _before, (dx, dy) = self._edit
        sx, sy = self._scene_pos(event)
        x = self._chart.axisX().fromScene(sx + dx)
        y = self._chart.axisY().fromScene(sy + dy)
        handle.series._drag(handle, x, y)
        self._chart._show_highlight(*handle.series._highlight(handle))
        self.requestRender()

    # -- interaction ----------------------------------------------------------------
    ACTIONS = {"pan": vtk.vtkChart.PAN, "zoom_box": vtk.vtkChart.ZOOM,
               "zoom_axis": vtk.vtkChart.ZOOM_AXIS,
               "select": vtk.vtkChart.SELECT,
               "select_box": vtk.vtkChart.SELECT_RECTANGLE}
    DEFAULT_INTERACTION = {"left": "pan", "middle": None,
                           "right": "zoom_box", "shift_left": "zoom_box",
                           "wheel": "zoom"}
    _BINDING_KEYS = tuple(f"{mod}{button}" for mod in ("", "shift_", "ctrl_")
                          for button in ("left", "middle", "right"))

    def interaction(self):
        """The current bindings (see :meth:`setInteraction`)."""
        return dict(getattr(self, "_interaction", self.DEFAULT_INTERACTION))

    def setInteraction(self, **bindings):
        """Choose what each pointer button does: ``left``, ``middle``,
        ``right`` and their ``shift_``/``ctrl_`` variants take ``"pan"``,
        ``"zoom_box"``, ``"zoom_axis"``, ``"select"``, ``"select_box"`` or
        None; ``wheel`` is ``"zoom"`` or None (the scene gets the wheel).
        Unnamed bindings keep their value. A right *click* still opens the
        context menu; editing handles still take a plain left press."""
        current = self.interaction()
        for key, value in bindings.items():
            if key == "wheel":
                if value not in ("zoom", None):
                    raise ValueError("wheel must be 'zoom' or None")
            elif key not in self._BINDING_KEYS:
                raise ValueError(f"unknown binding {key!r}; use one of "
                                 f"{self._BINDING_KEYS + ('wheel',)}")
            elif value is not None and value not in self.ACTIONS:
                raise ValueError(f"unknown action {value!r}; use one of "
                                 f"{sorted(self.ACTIONS)} or None")
            current[key] = value
        self._interaction = current

    def _action_for(self, event):
        bindings = self.interaction()
        modifiers = event.modifiers() if hasattr(event, "modifiers") else ()
        for modifier in ("shift", "ctrl"):
            key = f"{modifier}_{event.button()}"
            if modifier in modifiers and key in bindings:
                return bindings[key]
        return bindings.get(event.button())

    def _start_drag(self):
        """The pointer left the click slop: hand the press to VTK with the
        bound action on that button (at the original press point)."""
        pending = self._pending
        self._pending = None
        if pending["action"] is None:
            return
        chart = self._chart.vtkChart()
        for code in self.ACTIONS.values():
            chart.SetActionToButton(code, vtk.vtkContextMouseEvent.NO_BUTTON)
        chart.SetActionToButton(self.ACTIONS[pending["action"]],
                                pending["button"])
        self._last = None
        self._button = pending["button"]
        chart.MouseButtonPressEvent(self._context_at(pending["at"],
                                                     pending["button"]))

    def _moved_past_slop(self, event, start):
        sx, sy = self._scene_pos(event)
        limit = self.CLICK_SLOP_PX * ui_scale()
        return abs(sx - start[0]) > limit or abs(sy - start[1]) > limit

    def mousePressEvent(self, event):
        button = self._BUTTONS.get(event.button())
        if button is None or not self._shown:
            event.ignore()
            return
        event.accept()
        self.setFocus(reason="mouse")
        self._hide_tooltip()
        if event.button() == "left" and not (
                hasattr(event, "modifiers") and event.modifiers()):
            handle = self._handle_at(event)
            if handle is not None:
                self._edit = (handle, handle.series.data(),
                              self._grab_offset(handle, event))
                self._set_hover_handle(handle)
                return
        # Held until the pointer moves: a press that does not move is a
        # click (left: items; right: the context menu).
        self._pending = {"button": button, "name": event.button(),
                         "action": self._action_for(event),
                         "at": self._scene_pos(event)}
        self._press = self._pending["at"]

    def mouseMoveEvent(self, event):
        if self._edit is not None:
            event.accept()
            self._drag_to(event)
            return
        pending = getattr(self, "_pending", None)
        if pending is not None:
            if not self._moved_past_slop(event, pending["at"]):
                event.accept()
                return
            self._start_drag()
            if self._button is None:     # no action bound: just a drag
                event.accept()
                return
        if self._button is None:
            handle = self._handle_at(event)
            self._set_hover_handle(handle)
            self._set_hover_item(None if handle is not None
                                 else self._item_at(event))
        context = self._context_event(event, self._button)
        if self._button is not None or self._chart.FORWARD_HOVER:
            self._chart.vtkChart().MouseMoveEvent(context)
        self._update_tooltip(event)
        if self._button is not None:
            self._chart._update_decimation()
            event.accept()
            self.requestRender()
            self.viewChanged.emit()
        else:
            event.ignore()               # hover: tooltips only
            self.requestRender()

    def mouseReleaseEvent(self, event):
        if self._edit is not None:
            event.accept()
            handle, before, _offset = self._edit
            self._edit = None
            series = handle.series
            after = series.data()
            if any(not np.array_equal(a, b) for a, b in zip(before, after)):
                self._chart._record(series, before, after)
                series.edited.emit(series)
                self._chart.edited.emit(series)
            self._set_hover_handle(self._handle_at(event))
            self.requestRender()
            return
        pending = getattr(self, "_pending", None)
        if pending is not None:          # a click
            self._pending = self._press = None
            event.accept()
            if pending["name"] == "right":
                self.showContextMenu(event)
            elif pending["name"] == "left":
                item = self._item_at(event)
                if item is not None:
                    self._chart.clicked.emit(*item)
            self.requestRender()
            return
        if self._button is None:
            event.ignore()
            return
        event.accept()
        self._chart.vtkChart().MouseButtonReleaseEvent(
            self._context_event(event, self._button))
        self._button = None
        self._press = None
        self._chart._update_decimation()
        self.viewChanged.emit()          # a box zoom applies on release
        self.requestRender()

    # -- context menu --------------------------------------------------------------------
    def isContextMenuEnabled(self):
        return getattr(self, "_context_menu_enabled", True)

    def setContextMenuEnabled(self, enabled):
        self._context_menu_enabled = bool(enabled)

    def exportFolder(self):
        from pathlib import Path
        return Path(getattr(self, "_export_folder", None) or Path.cwd())

    def setExportFolder(self, folder):
        """Where the menu's Export items write (default: the working
        folder); ``exported(path)`` is emitted after each export."""
        from pathlib import Path
        self._export_folder = Path(folder)

    def exportTo(self, suffix):
        """Export the chart to a new file in :meth:`exportFolder` named
        after its title (``.png`` at twice the view's size); returns the
        path and emits ``exported(path)``."""
        import re

        folder = self.exportFolder()
        folder.mkdir(parents=True, exist_ok=True)
        title = getattr(self._chart, "title", lambda: "")() or "chart"
        stem = re.sub(r"[^A-Za-z0-9.+-]+", "_", title).strip("_") or "chart"
        path = folder / f"{stem}{suffix}"
        number = 2
        while path.exists():
            path = folder / f"{stem}-{number}{suffix}"
            number += 1
        self._chart.export(path, scale=2.0 if suffix == ".png" else 1.0)
        self.exported.emit(path)
        return path

    def contextMenu(self):
        """A new menu of the chart's actions (what a right click shows);
        ``contextMenuAboutToShow(menu)`` lets an app add its own."""
        from .actions import Action
        from .standard import Menu

        chart = self._chart
        menu = Menu(self.renderer, self.interactor)
        menu.addAction("Reset view", self.resetView)
        if isinstance(chart, Histogram2DChart):
            log = Action("Log colours", checkable=True,
                         checked=chart.isLogScale())
            log.toggled.connect(lambda checked: self._apply(
                chart.setLogScale, checked))
            menu.addAction(log)
        elif hasattr(chart, "axisX"):
            for label, axis in (("Log x axis", chart.axisX()),
                                ("Log y axis", chart.axisY())):
                if axis.tickLabels() is not None:
                    continue                 # a category axis
                action = Action(label, checkable=True,
                                checked=axis.isLogScale())
                action.toggled.connect(
                    lambda checked, axis=axis: self._apply(
                        axis.setLogScale, checked))
                menu.addAction(action)
        if hasattr(chart, "setLegendVisible"):
            legend = Action("Legend", checkable=True,
                            checked=bool(getattr(chart, "_legend", True)))
            legend.toggled.connect(lambda checked: self._apply(
                chart.setLegendVisible, checked))
            menu.addAction(legend)
        menu.addSeparator()
        export = menu.addMenu("Export")
        for label, suffix in (("PNG image", ".png"), ("SVG", ".svg"),
                              ("PDF", ".pdf"), ("CSV data", ".csv")):
            export.addAction(label, lambda suffix=suffix: self.exportTo(
                suffix))
        self.contextMenuAboutToShow.emit(menu)
        return menu

    def _apply(self, setter, value):
        setter(value)
        self._chart._update_decimation()
        self.requestRender()
        self.viewChanged.emit()

    def showContextMenu(self, event=None, at=None):
        """Pop the context menu up at the pointer (or ``at``, logical px);
        returns it, or None when disabled."""
        if not self.isContextMenuEnabled():
            return None
        if at is None and event is not None:
            x, y = event.globalPos()
            at = (x / ui_scale(), y / ui_scale())
        self._menu = self.contextMenu()
        self._menu.popup(at=at)
        return self._menu

    def mouseDoubleClickEvent(self, event):
        if event.button() != "left":
            event.ignore()
            return
        event.accept()
        self.resetView()

    def wheelEvent(self, event):
        if not self._shown or self.interaction().get("wheel") is None:
            event.ignore()               # unbound: the scene gets it
            return
        event.accept()
        self._last = None
        self._chart.vtkChart().MouseWheelEvent(self._context_event(event),
                                               int(event.delta()))
        self._chart._update_decimation()
        self.requestRender()
        self.viewChanged.emit()

    TOOLTIP_TOLERANCE_PX = 8.0

    def tooltipsEnabled(self):
        return getattr(self, "_tooltips", True)

    def setTooltipsEnabled(self, enabled):
        self._tooltips = bool(enabled)
        if not enabled:
            self._hide_tooltip()

    def _hide_tooltip(self):
        tip = self._chart._tooltip_item() if self._chart else None
        if tip is not None and tip.GetVisible():
            tip.SetVisible(False)
            self.requestRender()

    def _update_tooltip(self, event):
        """Series-aware hover text: a histogram bin anywhere inside it, a
        bar or stem along its length, else the nearest point (vtkChartXY
        alone only reports the plotted vertices). Hidden while dragging."""
        tip = self._chart._tooltip_item()
        if tip is None:
            return
        found = None
        if self.tooltipsEnabled() and self._button is None and \
                self._edit is None:
            sx, sy = self._scene_pos(event)
            found = self._chart.tooltipAt(
                sx, sy, self.TOOLTIP_TOLERANCE_PX * ui_scale())
        if found is None:
            tip.SetVisible(False)
            return
        _series, _index, text = found
        tip.SetText(text)
        tip.SetPosition(*self._scene_pos(event))
        tip.SetVisible(True)

    def leaveEvent(self, event):
        self._hide_tooltip()
        if self._edit is None:
            self._set_hover_handle(None)
        self._last = None
        self._chart.vtkChart().MouseLeaveEvent(self._context_event(event))
        self.requestRender()

    def keyPressEvent(self, event):
        from .events import CTRL, SHIFT

        key = event.key().lower()
        modifiers = event.modifiers()
        if key == "home":
            event.accept()
            self.resetView()
        elif CTRL in modifiers and key == "z" and SHIFT not in modifiers:
            event.accept()
            if self._chart.undo() is not None:
                self.requestRender()
        elif CTRL in modifiers and (key == "y" or
                                    (key == "z" and SHIFT in modifiers)):
            event.accept()
            if self._chart.redo() is not None:
                self.requestRender()
        else:
            event.ignore()

    def close(self):
        remove_actor_2d(self._content, self._actor)
        window = self.interactor.GetRenderWindow()
        if window is not None:
            window.RemoveRenderer(self._content)
        return super().close()


def ChartPanel(renderer, interactor, chart, title="Chart",
               position=(0.6, 0.6), width=0.3, chart_height=220,
               caption=None, **panel_options):
    """A scene panel holding a :class:`ChartView` of ``chart``.

    It is a :class:`~multipanel.containers.WidgetPanel`: it has the panel
    header, collapses, floats or docks (``dock.add_panel(panel, tab=...)``)
    and hides with its dock tab. ``panel.chartView()`` returns the view.
    ``chart_height`` is the chart's height in logical px.

    ``caption`` (text, possibly empty) adds a centred label above the
    chart, ``panel.caption()``. Prefer it to a chart title in narrow
    panels: ``vtkChartXY`` draws its title a fixed distance above the
    plot, where it collides with the top axis label.
    """
    from .containers import WidgetPanel
    from .layouts import VBoxLayout
    from .units import px

    # Theme colours by default: panels recognise them and follow theme
    # changes (as the containers' own panels do).
    theme = getattr(renderer, "theme", None)
    for option, role in (("panel_color", "panel_background_color"),
                         ("text_color", "text_color")):
        value = getattr(theme, role, None)
        if value is not None:
            panel_options.setdefault(option, value)
    panel = WidgetPanel(renderer, interactor, {}, panel_title=title,
                        panel_position=position, panel_width=width,
                        keep_aspect_ratio=False, **panel_options)
    view = ChartView(renderer, interactor, chart,
                     object_name=f"{title}/chart")
    view.setMinimumHeight(px(chart_height))
    column = VBoxLayout(margins=(4, 2, 4, 4))
    label = None
    if caption is not None:
        from .standard import Label

        label = Label(renderer, interactor, str(caption), alignment="center",
                      bold=True, object_name=f"{title}/caption")
        column.addWidget(label)
    column.addWidget(view, stretch=1)
    panel.setLayout(column)
    panel.chartView = lambda: view
    panel.caption = lambda: label
    return panel
