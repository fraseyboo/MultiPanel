"""Series bound to item models and selection sync (charts proposal C2)."""
import numpy as np
import pytest
import vtk

from multipanel._widget_support import set_ui_scale, user_scale
from multipanel.chart_models import bind_series
from multipanel.chartview import ChartView, XYChart
from multipanel.models import SelectionModel, TableModel
from multipanel.router import EventRouter
from multipanel.testing import UiHarness
from multipanel.units import px

SIZE = (900, 600)
VIEW = (300, 100, 500, 400)


def table(rows=10):
    return TableModel([(float(i), float(i * i)) for i in range(rows)],
                      headers=("x", "y"))


def test_appending_reads_only_the_new_row():
    model = table(10_000)
    chart = XYChart()
    line = chart.addLine([], [], name="squares")
    binding = bind_series(line, model)
    assert len(line.data()[0]) == 10_000 and binding.reads == 20_000
    model.append((10_000.0, 1.0))
    assert binding.reads == 20_002                     # just the new row
    x, y = line.data()
    assert len(x) == 10_001 and (x[-1], y[-1]) == (10_000.0, 1.0)


def test_inserts_edits_removals_and_resets():
    model = table(5)
    chart = XYChart()
    bars = chart.addBars([], [], name="bars")
    bind_series(bars, model)
    model.insert(1, (0.5, 7.0))
    assert list(bars.data()[1]) == [0, 7, 1, 4, 9, 16]
    model.setData(model.index(2, 1), "2.5")            # as a table edit
    assert bars.data()[1][2] == 2.5
    model.setData(model.index(2, 0), "x")              # not a number
    assert np.isnan(bars.data()[0][2])
    model.removeRows(0, 2)
    assert list(bars.data()[1]) == [2.5, 4, 9, 16]
    model.setItems([(1.0, 1.0)])
    assert list(bars.data()[1]) == [1.0]


def test_histograms_cannot_be_bound():
    chart = XYChart()
    step = chart.addStep([0, 1], [1.0], name="bins")
    with pytest.raises(TypeError):
        bind_series(step, table())


def test_selection_highlights_points_and_bars():
    model = table(6)
    selection = SelectionModel(model)
    chart = XYChart()
    line = chart.addLine([], [], name="line")
    bars = chart.addBars([], [], name="bars")
    bind_series(line, model, selection=selection)
    bind_series(bars, model, selection=selection)
    selection.select([model.index(2), model.index(4)])
    assert line.highlighted() == [2, 4] and bars.highlighted() == [2, 4]
    marks = line._mark_plot
    assert marks.GetVisible() and marks.GetInput().GetNumberOfRows() == 2
    model.removeRows(0, 1)                              # rows shift
    assert line.highlighted() == [1, 3]
    selection.select([], "clearAndSelect")
    assert line.highlighted() == [] and not marks.GetVisible()


@pytest.fixture
def ui():
    previous = user_scale()
    set_ui_scale(1.0)
    with UiHarness(size=SIZE) as harness:
        harness.interactor.SetInteractorStyle(
            vtk.vtkInteractorStyleTrackballCamera())
        EventRouter.install(harness.interactor)
        yield harness
        EventRouter.uninstall(harness.interactor)
    set_ui_scale(previous)


def display(view, x, y):
    chart = view.chart()
    vx0, vy0, _vx1, _vy1 = view._content.GetViewport()
    return (vx0 * SIZE[0] + chart.axisX().toScene(x),
            vy0 * SIZE[1] + chart.axisY().toScene(y))


def test_clicks_select_rows_and_views_share_the_selection(ui):
    from multipanel.views import TableView

    model = table(6)
    rows = TableView(ui.renderer, ui.interactor)
    rows.setModel(model)
    selection = rows.selectionModel()
    chart = XYChart()
    points = chart.addScatter([], [], name="points")
    view = ChartView(ui.renderer, ui.interactor, chart)
    view.setGeometry(*(px(v) for v in VIEW))
    bind_series(points, model, selection=selection)
    ui.render()
    ui.click(display(view, 3.0, 9.0))
    assert [i.row() for i in selection.selectedRows()] == [3]
    ui.click(display(view, 5.0, 25.0), shift=True)       # add to it
    assert sorted(i.row() for i in selection.selectedRows()) == [3, 5]
    assert points.highlighted() == [3, 5]
    selection.select(model.index(1))                    # from the table
    assert points.highlighted() == [1]
