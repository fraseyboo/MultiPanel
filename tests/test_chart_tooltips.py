"""Series-aware hover tooltips in a ChartView."""
import pytest
import vtk

from multipanel._widget_support import set_ui_scale, ui_scale, user_scale
from multipanel.chartview import ChartView, XYChart
from multipanel.config import theme
from multipanel.router import EventRouter
from multipanel.testing import UiHarness
from multipanel.units import px

SIZE = (900, 600)
VIEW = (300, 100, 500, 400)


@pytest.fixture
def ui():
    previous = user_scale()
    set_ui_scale(1.0)
    with UiHarness(size=SIZE) as harness:
        harness.renderer.theme = theme(dark_mode=False)
        harness.interactor.SetInteractorStyle(
            vtk.vtkInteractorStyleTrackballCamera())
        EventRouter.install(harness.interactor)
        yield harness
        EventRouter.uninstall(harness.interactor)
    set_ui_scale(previous)


def show(ui, chart):
    view = ChartView(ui.renderer, ui.interactor, chart)
    view.setGeometry(*(px(v) for v in VIEW))
    ui.render()
    return view


def display(view, x, y):
    chart = view.chart()
    vx0, vy0, _vx1, _vy1 = view._content.GetViewport()
    return (vx0 * SIZE[0] + chart.axisX().toScene(x),
            vy0 * SIZE[1] + chart.axisY().toScene(y))


def tip_after_move(ui, view, x, y):
    ui.move(display(view, x, y))
    tip = view.chart().vtkChart().GetTooltip()
    return tip.GetText() if tip.GetVisible() else None


def test_histogram_bins_anywhere_inside(ui):
    chart = XYChart()
    step = chart.addStep([0, 1, 2, 4], [3.0, 5.0, 2.0], name="flux",
                         fill=True)
    chart.addErrorBars([0.5, 1.5, 3.0], [3.0, 5.0, 2.0], [0.3, 0.5, 0.2],
                       of=step)
    view = show(ui, chart)
    assert tip_after_move(ui, view, 1.5, 2.0) == "flux: 1–2: 5 ± 0.5"
    assert tip_after_move(ui, view, 3.2, 0.5) == "flux: 2–4: 2 ± 0.2"
    assert tip_after_move(ui, view, 3.2, 4.5) is None     # above the bin


def test_stems_bars_and_points(ui):
    chart = XYChart()
    chart.addStems([2.0], [4.0], name="lines")
    chart.addLine([0.0, 1.0, 3.0], [1.0, 1.5, 1.0], name="curve")
    view = show(ui, chart)
    assert tip_after_move(ui, view, 2.0, 1.0) == "lines: 2, 4"  # mid-stem
    assert tip_after_move(ui, view, 1.0, 1.5) == "curve: 1, 1.5"

    bars = XYChart()
    series = bars.addBars([2, 1], [6.0, 2.0], name="volume", horizontal=True)
    bars.axisY().setTickLabels([2, 1], ["lead", "water"])
    view = show(ui, bars)
    assert tip_after_move(ui, view, 3.0, 2.0) == "volume: lead, 6"
    series.setTooltipFormatter(lambda i: f"custom {i}")
    assert tip_after_move(ui, view, 1.0, 1.0) == "custom 1"


def test_hidden_while_dragging_and_when_disabled(ui):
    chart = XYChart()
    chart.addStep([0, 1, 2], [3.0, 5.0], name="flux", fill=True)
    view = show(ui, chart)
    tip = chart.vtkChart().GetTooltip()
    assert tip_after_move(ui, view, 0.5, 1.0) is not None
    ui.drag(display(view, 0.5, 1.0), display(view, 0.7, 1.0), steps=3)
    assert not tip.GetVisible()
    view.setTooltipsEnabled(False)
    assert tip_after_move(ui, view, 1.5, 1.0) is None
