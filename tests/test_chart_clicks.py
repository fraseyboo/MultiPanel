"""Clicking chart items and highlighting bars (charts C7d support)."""
import numpy as np
import pytest
import vtk

from multipanel._widget_support import set_ui_scale, ui_scale, user_scale
from multipanel.chart_export import image_array, render_chart
from multipanel.chartview import ChartView, XYChart, _DEFAULT_TOKENS
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


def horizontal_bars():
    chart = XYChart()
    bars = chart.addBars([3, 2, 1], [6.0, 3.0, 1.0], name="volumes",
                         horizontal=True)
    chart.axisY().setTickLabels([3, 2, 1], ["a", "b", "c"])
    bars.setClickable()
    return chart, bars


def test_clicking_a_bar_reports_it(ui):
    chart, bars = horizontal_bars()
    view = show(ui, chart)
    clicks = []
    chart.clicked.connect(lambda series, index: clicks.append((series, index)))
    ui.click(display(view, 2.0, 2.0))                 # inside bar "b"
    ui.click(display(view, 2.0, 1.0))                 # past bar "c"'s end
    ui.click(display(view, 0.5, 1.0))                 # inside bar "c"
    assert clicks == [(bars, 1), (bars, 2)]
    start = chart.axisX().range()
    ui.drag(display(view, 2.0, 2.0), display(view, 3.0, 2.0), steps=4)
    assert len(clicks) == 2                           # a drag pans instead
    assert chart.axisX().range() != start


def test_hovering_a_clickable_item_shows_a_hand(ui):
    chart, bars = horizontal_bars()
    view = show(ui, chart)
    ui.move(display(view, 2.0, 3.0))
    assert view.cursor() == vtk.VTK_CURSOR_HAND
    ui.move(display(view, 5.5, 1.0))
    assert view.cursor() != vtk.VTK_CURSOR_HAND
    bars.setClickable(False)
    ui.move(display(view, 2.0, 3.0))
    assert view.cursor() != vtk.VTK_CURSOR_HAND


def test_bins_and_points_are_items(ui):
    chart = XYChart()
    step = chart.addStep([0, 1, 2], [4.0, 2.0], name="bins")
    line = chart.addLine([0.5, 1.5], [5.0, 5.0], name="points")
    step.setClickable()
    line.setClickable()
    show(ui, chart)
    ax, ay = chart.axisX(), chart.axisY()
    # (the unfilled histogram's axis starts at 2: bins reach down to it)
    assert chart.itemAt(ax.toScene(0.5), ay.toScene(3.0)) == (step, 0)
    assert chart.itemAt(ax.toScene(1.5), ay.toScene(5.0)) == (line, 1)
    assert chart.itemAt(ax.toScene(1.5), ay.toScene(3.5)) is None


def test_highlighted_bars_use_the_accent_colour():
    chart, bars = horizontal_bars()
    accent = np.array([round(255 * c) for c in _DEFAULT_TOKENS["accent"]])

    def accent_pixels():
        image = image_array(render_chart(chart, size=(400, 300)))[:, :, :3]
        return int((np.abs(image.astype(int) - accent).max(axis=2)
                    <= 6).sum())

    assert accent_pixels() < 50
    bars.setHighlighted([1])
    assert bars.highlighted() == [1]
    lit = accent_pixels()
    assert lit > 500
    bars.setHighlighted([0, 1])
    assert accent_pixels() > lit * 1.5                # the longer bar too
    bars.setHighlighted([])
    assert accent_pixels() < 50
