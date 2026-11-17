"""Export an :class:`~multipanel.chartview.XYChart`: images, vector files
and CSV (charts proposal C6).

The chart is drawn on its own off-screen window, at the export size times
``scale`` (fonts and lines scale with it), on the theme's panel colour; it
returns to its :class:`~multipanel.chartview.ChartView` afterwards with
its zoom unchanged. Formats come from the file extension:

* ``.png``, ``.jpg``/``.jpeg``, ``.tif``/``.tiff``: images.
* ``.svg``, ``.pdf``, ``.eps``, ``.ps``: vector files through
  ``vtkGL2PSExporter`` (text stays text; fonts are the viewer's
  Helvetica, not the bundled UI font).
* ``.csv``: the data of the visible series (:func:`chart_rows`).
"""
from __future__ import annotations

import csv
import io
from pathlib import Path

import numpy as np
import vtk

IMAGE_WRITERS = {".png": "vtkPNGWriter", ".jpg": "vtkJPEGWriter",
                 ".jpeg": "vtkJPEGWriter", ".tif": "vtkTIFFWriter",
                 ".tiff": "vtkTIFFWriter"}
VECTOR_FORMATS = {".svg": "SVG", ".pdf": "PDF", ".eps": "EPS", ".ps": "PS"}
CSV_COLUMNS = ("series", "kind", "x", "x_low", "x_high", "y", "y_low",
               "y_high")
DEFAULT_SIZE = (640, 420)


def _number(value):
    return format(float(value), ".10g")


def chart_rows(chart):
    """Rows (dicts with :data:`CSV_COLUMNS` keys) for the visible series.

    ``kind`` is ``line``, ``scatter``, ``bar``, ``lines`` (stems),
    ``histogram`` (``x``–``x_high`` bins), ``error`` (``y_low`` to
    ``y_high`` around ``y``, and ``x_low`` to ``x_high`` with x errors),
    ``box`` (Q1 ``y_low``, median ``y``, Q3 ``y_high``; ``series`` is the
    group), ``whisker`` (``y_low``–``y_high``), ``outlier`` (``y``),
    ``cell`` (a 2D histogram bin: ``x_low``–``x_high`` by
    ``y_low``–``y_high``, value ``y``) or ``slice`` (a pie slice: label in
    ``series``, value ``y``); unused cells are empty.
    """
    from .chartview import (BarSeries, BoxSeries, ErrorBarSeries,
                            ScatterSeries, StemSeries, StepSeries)

    own = getattr(chart, "_csv_rows", None)
    if own is not None:              # 2D histograms, pie charts
        return [{column: row.get(column, "") for column in CSV_COLUMNS}
                for row in own()]
    rows = []
    for series in chart.series():
        if not series.isVisible():
            continue
        name = series.name()
        x, y = series.data()
        if isinstance(series, StepSeries):
            for low, high, value in zip(x[:-1], x[1:], y):
                rows.append({"series": name, "kind": "histogram",
                             "x": _number(low), "x_high": _number(high),
                             "y": _number(value)})
            continue
        if isinstance(series, BoxSeries):
            labels = series.labels()
            for index, (px, st) in enumerate(zip(x, series.statistics())):
                group = labels[index] if labels else name
                rows.append({"series": group, "kind": "box",
                             "x": _number(px), "y": _number(st["median"]),
                             "y_low": _number(st["q1"]),
                             "y_high": _number(st["q3"])})
                rows.append({"series": group, "kind": "whisker",
                             "x": _number(px), "y_low": _number(st["low"]),
                             "y_high": _number(st["high"])})
                rows.extend({"series": group, "kind": "outlier",
                             "x": _number(px), "y": _number(value)}
                            for value in st["outliers"])
            continue
        if isinstance(series, ErrorBarSeries):
            lower, upper = series.errors()
            x_errors = series.xErrors()
            for i, (px, py, low, high) in enumerate(zip(x, y, lower, upper)):
                row = {"series": name, "kind": "error", "x": _number(px),
                       "y": _number(py), "y_low": _number(py - low),
                       "y_high": _number(py + high)}
                if x_errors is not None:
                    row["x_low"] = _number(px - x_errors[0][i])
                    row["x_high"] = _number(px + x_errors[1][i])
                rows.append(row)
            continue
        kind = ("lines" if isinstance(series, StemSeries) else
                "scatter" if isinstance(series, ScatterSeries) else
                "bar" if isinstance(series, BarSeries) else "line")
        for px, py in zip(x, y):
            rows.append({"series": name, "kind": kind, "x": _number(px),
                         "y": _number(py)})
    return [{column: row.get(column, "") for column in CSV_COLUMNS}
            for row in rows]


def chart_csv(chart):
    """The CSV text of :func:`chart_rows`."""
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=CSV_COLUMNS,
                            lineterminator="\n")
    writer.writeheader()
    writer.writerows(chart_rows(chart))
    return buffer.getvalue()


def _theme_of(chart, tokens, dark):
    view = getattr(chart, "_view", None)
    if tokens is None:
        if view is not None:
            tokens = view.tokens()
            theme = getattr(view.renderer, "theme", None)
            if dark is None:
                dark = bool(getattr(theme, "dark_mode", False))
        else:
            from .chartview import _DEFAULT_TOKENS
            tokens = _DEFAULT_TOKENS
    return tokens, bool(dark)


def _size_of(chart, size):
    if size is not None:
        return tuple(int(round(v)) for v in size)
    view = getattr(chart, "_view", None)
    if view is not None and view.isVisible():
        _x, _y, width, height = view.geometry("display")
        if width >= 1 and height >= 1:
            return int(round(width)), int(round(height))
    return DEFAULT_SIZE


class _Borrowed:
    """The chart moved onto an off-screen window for the ``with`` block."""

    def __init__(self, chart, size, scale, tokens, dark):
        self.chart, self.scale = chart, float(scale)
        self.size = (max(1, int(round(size[0] * self.scale))),
                     max(1, int(round(size[1] * self.scale))))
        self.tokens, self.dark = tokens, dark

    def __enter__(self):
        chart = self.chart
        chart._hide_highlight()
        chart._update_decimation(full=True)      # exports draw every point
        self._axes = ((chart.axisX(), chart.axisY())
                      if hasattr(chart, "axisX") else ())   # a pie has none
        self._saved_ranges = [axis.range() for axis in self._axes]
        chart.applyTheme(self.tokens, self.scale, self.dark)
        window = vtk.vtkRenderWindow()
        window.SetOffScreenRendering(True)
        window.SetSize(*self.size)
        renderer = vtk.vtkRenderer()
        renderer.SetBackground(*self.tokens["panel"])
        window.AddRenderer(renderer)
        actor = vtk.vtkContextActor()
        renderer.AddViewProp(actor)
        actor.GetScene().AddItem(chart.vtkChart())
        self.window, self.actor = window, actor
        window.Render()
        # Keep the on-screen view's zoom: the axes are FIXED, but restore
        # them in case the first paint adjusted them.
        for axis, (low, high) in zip(self._axes, self._saved_ranges):
            axis._apply_range(low, high)
        # Sizes that follow the view (error bar caps) for this window.
        chart._update_decimation(full=True)
        window.Render()
        return self

    def __exit__(self, *_):
        chart = self.chart
        self.actor.GetScene().RemoveItem(chart.vtkChart())
        self.window.Finalize()
        view = getattr(chart, "_view", None)
        if view is not None:
            # Back in the view's scene, in the view's theme and scale.
            scene = view._actor.GetScene()
            scene.RemoveItem(chart.vtkChart())
            scene.AddItem(chart.vtkChart())
            view._applyTheme()
            chart._update_decimation()           # the view's own again
            view.requestRender()
        else:
            from .chartview import _DEFAULT_TOKENS
            from ._widget_support import ui_scale
            chart.applyTheme(self.tokens or _DEFAULT_TOKENS, ui_scale(),
                             self.dark)
        return False

    def image(self):
        grab = vtk.vtkWindowToImageFilter()
        grab.SetInput(self.window)
        grab.ReadFrontBufferOff()
        grab.Update()
        image = vtk.vtkImageData()
        image.DeepCopy(grab.GetOutput())
        return image


def render_chart(chart, size=None, scale=1.0, tokens=None, dark=None):
    """The chart drawn off-screen as ``vtkImageData`` (``size`` logical px,
    times ``scale``; by default the size of its view, or 640×420)."""
    tokens, dark = _theme_of(chart, tokens, dark)
    with _Borrowed(chart, _size_of(chart, size), scale, tokens,
                   dark) as borrowed:
        return borrowed.image()


def export_chart(chart, path, size=None, scale=1.0, tokens=None, dark=None):
    """Write the chart to ``path``; the extension picks the format (see
    the module docstring). Returns the path written."""
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix == ".csv":
        path.write_text(chart_csv(chart), encoding="utf-8")
        return path
    if suffix not in IMAGE_WRITERS and suffix not in VECTOR_FORMATS:
        raise ValueError(f"unsupported chart export format {suffix!r}; use "
                         f"{', '.join(sorted({*IMAGE_WRITERS, *VECTOR_FORMATS, '.csv'}))}")
    tokens, dark = _theme_of(chart, tokens, dark)
    with _Borrowed(chart, _size_of(chart, size), scale, tokens,
                   dark) as borrowed:
        if suffix in IMAGE_WRITERS:
            writer = getattr(vtk, IMAGE_WRITERS[suffix])()
            writer.SetFileName(str(path))
            image = borrowed.image()
            if suffix in (".jpg", ".jpeg"):
                extract = vtk.vtkImageExtractComponents()   # no alpha
                extract.SetInputData(image)
                extract.SetComponents(0, 1, 2)
                extract.Update()
                image = extract.GetOutput()
            writer.SetInputData(image)
            writer.Write()
        else:
            exporter = vtk.vtkGL2PSExporter()
            exporter.SetRenderWindow(borrowed.window)
            getattr(exporter, f"SetFileFormatTo{VECTOR_FORMATS[suffix]}")()
            exporter.SetFilePrefix(str(path.with_suffix("")))
            exporter.CompressOff()
            exporter.SetSortToOff()
            exporter.DrawBackgroundOn()
            exporter.TextAsPathOff()
            exporter.Write()
            written = path.with_suffix(f".{VECTOR_FORMATS[suffix].lower()}")
            if written != path and written.exists():
                written.replace(path)              # e.g. .PS case, .eps
    return path


def image_array(image):
    """``(height, width, channels)`` uint8 array of a ``vtkImageData``,
    top row first."""
    from vtkmodules.util.numpy_support import vtk_to_numpy

    width, height, _ = image.GetDimensions()
    data = vtk_to_numpy(image.GetPointData().GetScalars())
    return data.reshape(height, width, -1)[::-1]
