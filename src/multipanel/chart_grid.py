"""Several charts in one widget, optionally with linked axes.

``ChartGrid`` is a :class:`~multipanel.containers.Frame` holding
:class:`~multipanel.chartview.ChartView` cells in a grid; put it in any
layout, or in a panel with :func:`ChartGridPanel`::

    grid = ChartGrid(renderer, interactor, columns=2, link="x")
    grid.addChart(spectrum)            # filled row by row
    grid.addChart(efficiency)
    grid.addChart(response, columnSpan=2)

With ``link="x"`` (or ``"y"``, ``"xy"``) a pan, zoom, box zoom or reset in
one chart sets the same range on that axis of the others, e.g. stacked
spectra over one energy axis.
"""
from __future__ import annotations

from functools import partial

from .chartview import ChartView
from .containers import Frame
from .layouts import GridLayout

LINKS = (None, "x", "y", "xy")


class ChartGrid(Frame):
    """Charts in a grid of ``columns`` with optionally linked axes."""

    def __init__(self, renderer, interactor, columns=2, link=None,
                 spacing=8, parent=None, object_name="chart_grid"):
        super().__init__(renderer, interactor, parent=parent,
                         object_name=object_name)
        if link not in LINKS:
            raise ValueError(f"link must be one of {LINKS}")
        self._columns = int(columns)
        self._link = link
        self._views = []
        self._next = 0                   # next free cell, row by row
        self._syncing = False
        self._grid = GridLayout(margins=(0, 0, 0, 0), spacing=spacing)
        for column in range(self._columns):
            self._grid.setColumnStretch(column, 1)
        self.setLayout(self._grid)

    def addChart(self, chart, row=None, column=None, rowSpan=1,
                 columnSpan=1, minimum_height=120):
        """Add ``chart`` in a new :class:`ChartView` (at the next free
        cell unless ``row``/``column`` are given); returns the view."""
        from .units import px

        if row is None or column is None:
            row, column = divmod(self._next, self._columns)
        self._next = max(self._next, row * self._columns + column +
                         columnSpan)
        view = ChartView(self.renderer, self.interactor, chart)
        view.setMinimumHeight(px(minimum_height))
        self._grid.addWidget(view, row, column, rowSpan, columnSpan)
        self._grid.setRowStretch(row, 1)
        view.viewChanged.connect(partial(self._on_view_changed, view))
        self._views.append(view)
        return view

    def views(self):
        return list(self._views)

    def charts(self):
        return [view.chart() for view in self._views]

    def link(self):
        return self._link

    def setLink(self, link):
        if link not in LINKS:
            raise ValueError(f"link must be one of {LINKS}")
        self._link = link
        if link and self._views:
            self._on_view_changed(self._views[0])

    def _linked_axes(self, chart):
        axes = []
        if self._link and "x" in self._link and hasattr(chart, "axisX"):
            axes.append("axisX")
        if self._link and "y" in self._link and hasattr(chart, "axisY"):
            axes.append("axisY")
        return axes

    def _on_view_changed(self, source):
        if self._syncing or not self._link:
            return
        self._syncing = True
        try:
            chart = source.chart()
            ranges = {name: getattr(chart, name)().range()
                      for name in self._linked_axes(chart)}
            for view in self._views:
                if view is source:
                    continue
                other = view.chart()
                for name in self._linked_axes(other):
                    if name in ranges:
                        axis = getattr(other, name)()
                        axis.vtkAxis().SetBehavior(axis.vtkAxis().FIXED)
                        axis._apply_range(*ranges[name])
                other._update_decimation()
                view.requestRender()
        finally:
            self._syncing = False


def ChartGridPanel(renderer, interactor, grid=None, title="Charts",
                   position=(0.6, 0.6), width=0.4, columns=2, link=None,
                   **panel_options):
    """A scene panel holding a :class:`ChartGrid` (a new one with
    ``columns`` and ``link`` unless ``grid`` is given); ``panel.grid()``
    returns it."""
    from .containers import WidgetPanel
    from .layouts import VBoxLayout

    theme = getattr(renderer, "theme", None)
    for option, role in (("panel_color", "panel_background_color"),
                         ("text_color", "text_color")):
        value = getattr(theme, role, None)
        if value is not None:
            panel_options.setdefault(option, value)
    if grid is None:
        grid = ChartGrid(renderer, interactor, columns=columns, link=link)
    panel = WidgetPanel(renderer, interactor, {}, panel_title=title,
                        panel_position=position, panel_width=width,
                        keep_aspect_ratio=False, **panel_options)
    column = VBoxLayout(margins=(4, 2, 4, 4))
    column.addWidget(grid, stretch=1)
    panel.setLayout(column)
    panel.grid = lambda: grid
    return panel


__all__ = ["ChartGrid", "ChartGridPanel"]
