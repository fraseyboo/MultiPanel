"""Chart series bound to item models (charts proposal C2).

:func:`bind_series` keeps a series' points equal to two columns of an
:class:`~multipanel.models.ItemModel` (a :class:`~multipanel.models.TableModel`
row per point)::

    model = TableModel(rows, headers=("Energy", "Counts"))
    line = chart.addLine([], [], name="counts")
    binding = bind_series(line, model, x=0, y=1, selection=selection)

* ``rowsInserted`` reads only the new rows and splices them in;
  ``dataChanged`` re-reads only the changed rows; ``rowsRemoved`` splices
  them out; ``modelReset`` reads everything again.
* With a :class:`~multipanel.models.SelectionModel`, the selected rows are
  highlighted in the chart (bars recoloured, points marked), and clicking
  a point or bar selects its row (shift: add to the selection).

Values come from the ``"edit"`` role (what a table view edits; a number
stored in a cell reads back exactly) and are converted with ``float``; a
cell that cannot be converted is NaN (the point is not drawn). Point ``i``
is row ``i`` of the root.
"""
from __future__ import annotations

import numpy as np

EDIT = "edit"


def _number(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return float("nan")


class SeriesBinding:
    """Keeps ``series`` in step with ``model`` (see the module docs)."""

    def __init__(self, series, model, x=0, y=1, role=EDIT, selection=None):
        from .chartview import StepSeries

        if isinstance(series, StepSeries):
            raise TypeError("a histogram has one more edge than values; "
                            "bind a line, scatter, bar or stem series")
        self.series = series
        self.model = model
        self.columns = (int(x), int(y))
        self.role = role
        self.selection = selection
        self.reads = 0                  # cells read (to check incremental use)
        self._connections = []
        self._syncing = False
        for signal, slot in ((model.rowsInserted, self._on_inserted),
                             (model.rowsRemoved, self._on_removed),
                             (model.dataChanged, self._on_changed),
                             (model.modelReset, self._on_reset)):
            signal.connect(slot)
            self._connections.append((signal, slot))
        if selection is not None:
            selection.selectionChanged.connect(self._on_selection)
            self._connections.append((selection.selectionChanged,
                                      self._on_selection))
            series.setClickable(True)
            chart = series._chart
            if chart is not None:
                chart.clicked.connect(self._on_clicked)
                self._connections.append((chart.clicked, self._on_clicked))
        self._on_reset()

    # -- reading ------------------------------------------------------------------------
    def _read(self, first, last):
        """``(x, y)`` arrays of rows ``first..last``."""
        count = max(0, last - first + 1)
        xs, ys = np.empty(count), np.empty(count)
        cx, cy = self.columns
        for offset, row in enumerate(range(first, last + 1)):
            xs[offset] = _number(self.model.data(
                self.model.index(row, cx), self.role))
            ys[offset] = _number(self.model.data(
                self.model.index(row, cy), self.role))
        self.reads += 2 * count
        return xs, ys

    def _publish(self, x, y):
        self.series.setData(x, y)
        self._on_selection()

    # -- model signals ------------------------------------------------------------------
    def _top_level(self, parent):
        return parent is None or not parent.isValid()

    def _on_reset(self, *_):
        self._publish(*self._read(0, self.model.rowCount() - 1))

    def _on_inserted(self, parent, first, last):
        if not self._top_level(parent):
            return
        x, y = self.series.data()
        new_x, new_y = self._read(first, last)
        self._publish(np.insert(x, first, new_x), np.insert(y, first, new_y))

    def _on_removed(self, parent, first, last):
        if not self._top_level(parent):
            return
        x, y = self.series.data()
        keep = np.r_[0:first, last + 1:len(x)]
        self._publish(x[keep], y[keep])

    def _on_changed(self, top_left, bottom_right, roles=None):
        if not self._top_level(top_left.parent()):
            return
        columns = range(top_left.column(), bottom_right.column() + 1)
        if not any(column in columns for column in self.columns):
            return
        x, y = self.series.data()
        first, last = top_left.row(), bottom_right.row()
        x[first:last + 1], y[first:last + 1] = self._read(first, last)
        self._publish(x, y)

    # -- selection ----------------------------------------------------------------------
    def _on_selection(self, *_):
        if self.selection is None:
            return
        rows = sorted({index.row() for index in self.selection.selectedRows()
                       if self._top_level(index.parent())})
        if rows != self.series.highlighted():
            self.series.setHighlighted(rows)

    def _on_clicked(self, series, index):
        if series is not self.series or self.selection is None:
            return
        interactor = getattr(getattr(series._chart, "_view", None),
                             "interactor", None)
        shift = bool(interactor is not None and interactor.GetShiftKey())
        row = self.model.index(index, 0)
        self.selection.setCurrentIndex(row)
        self.selection.select(row, "toggle" if shift else "clearAndSelect")

    def close(self):
        """Stop following the model and selection."""
        for signal, slot in self._connections:
            signal.disconnect(slot)
        self._connections = []


def bind_series(series, model, x=0, y=1, role=EDIT, selection=None):
    """Bind ``series`` (already added to a chart, for click-to-select) to
    columns ``x`` and ``y`` of ``model``; returns the
    :class:`SeriesBinding` (``close()`` to unbind)."""
    return SeriesBinding(series, model, x, y, role, selection)


__all__ = ["SeriesBinding", "bind_series"]
