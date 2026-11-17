"""Error-bar scatter (x and y), 2D histograms and pie charts."""
import math

import numpy as np
import pytest
import vtk

from multipanel._widget_support import set_ui_scale, user_scale
from multipanel.chart_export import chart_rows, image_array, render_chart
from multipanel.chartview import (
    ChartView, ErrorBarSeries, Histogram2DChart, PieChart, ScatterSeries,
    XYChart, palette,
)
from multipanel.config import theme
from multipanel.router import EventRouter
from multipanel.testing import UiHarness
from multipanel.units import px

SIZE = (900, 600)
VIEW = (200, 100, 500, 400)


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
    ui.render()
    return view


def display(view, x, y):
    chart = view.chart()
    vx0, vy0, _vx1, _vy1 = view._content.GetViewport()
    return (vx0 * SIZE[0] + chart.axisX().toScene(x),
            vy0 * SIZE[1] + chart.axisY().toScene(y))


def tooltip(ui, view, point):
    ui.move(point)
    tip = view.chart()._tooltip_item()
    return tip.GetText() if tip.GetVisible() else None


# -- error-bar scatter ----------------------------------------------------------------------
def test_error_scatter_has_x_and_y_bars_with_caps(ui):
    chart = XYChart()
    points, bars = chart.addErrorScatter([1.0, 2.0, 3.0], [2.0, 4.0, 3.0],
                                         errors=[0.5, 0.2, 0.0],
                                         x_errors=([0.1, 0.0, 0.3],
                                                   [0.2, 0.0, 0.3]),
                                         name="data")
    assert isinstance(points, ScatterSeries)
    assert isinstance(bars, ErrorBarSeries) and bars._of is points
    view = show(ui, chart)
    x0, y0, x1, y1 = bars._segments(chart)
    # 2 vertical + 2 horizontal bars, 2 caps on each
    assert len(x0) == 2 + 2 + 2 * 2 + 2 * 2
    ax, ay = chart.axisX(), chart.axisY()
    cap = slice(4, 8)                         # the vertical bars' caps
    widths = ax.toScene(x1[cap]) - ax.toScene(x0[cap])
    assert widths == pytest.approx(np.full(4, bars._cap_px), abs=0.01)
    ui.wheel(display(view, 2.0, 3.0), steps=3)  # zoom: caps stay 4 px
    ui.render()
    x0, _y0, x1, _y1 = bars._segments(chart)
    widths = ax.toScene(x1[cap]) - ax.toScene(x0[cap])
    assert widths == pytest.approx(np.full(4, bars._cap_px), abs=0.01)
    assert points.tooltipText(0) == "data: 1 −0.1 +0.2, 2 ± 0.5"
    rows = [r for r in chart_rows(chart) if r["kind"] == "error"]
    assert (rows[0]["x_low"], rows[0]["x_high"]) == ("0.9", "1.2")
    assert (rows[0]["y_low"], rows[0]["y_high"]) == ("1.5", "2.5")


def test_error_bars_need_some_errors():
    with pytest.raises(ValueError):
        ErrorBarSeries([1.0], [1.0])
    no_caps = ErrorBarSeries([1.0], [1.0], [0.5], caps=False)
    assert len(no_caps._segments(None)[0]) == 1


# -- 2D histograms ---------------------------------------------------------------------------
def test_histogram2d_axes_bins_and_tooltips(ui):
    values = np.arange(12.0).reshape(3, 4)          # 3 rows (y), 4 columns
    chart = Histogram2DChart(values, x_range=(0, 8), y_range=(10, 16),
                             title="map", value_title="counts")
    view = show(ui, chart)
    assert chart.axisX().range() == (0.0, 8.0)
    assert chart.axisY().range() == (10.0, 16.0)
    assert chart.binAt(5.0, 13.0) == (1, 2)
    assert chart.binAt(9.0, 13.0) is None
    text = tooltip(ui, view, display(view, 5.0, 13.0))
    assert text == "4–6, 12–14: 6"
    assert len(chart_rows(chart)) == 12
    cell = chart_rows(chart)[6]
    assert (cell["kind"], cell["x_low"], cell["x_high"], cell["y_low"],
            cell["y"]) == ("cell", "4", "6", "12", "6")
    with pytest.raises(ValueError):
        chart.setData(np.arange(3.0))


def test_histogram2d_log_colours():
    values = np.array([[0.0, 1.0], [10.0, 1000.0]])
    chart = Histogram2DChart(values, log=True)
    assert chart.colourRange() == (1.0, 1000.0)
    assert chart._lut.GetScale() == vtk.VTK_SCALE_LOG10
    chart.setLogScale(False)
    assert chart.colourRange() == (0.0, 1000.0)
    image = image_array(render_chart(chart, size=(300, 300)))[:, :, :3]
    assert len(np.unique(image.reshape(-1, 3), axis=0)) > 20


# -- pie charts ------------------------------------------------------------------------------
def test_pie_slices_tooltips_and_clicks(ui):
    pie = PieChart(["water", "lead", "air"], [1.0, 2.0, 1.0], title="Mass")
    pie.setClickable()
    view = show(ui, pie)
    x, y, width, height = pie._plot.GetDimensions()
    centre = (x + width / 2, y + height / 2)
    radius = min(width, height) / 2
    vx0, vy0, _vx1, _vy1 = view._content.GetViewport()

    def at(degrees):
        angle = math.radians(degrees)
        return (vx0 * SIZE[0] + centre[0] + 0.6 * radius * math.cos(angle),
                vy0 * SIZE[1] + centre[1] + 0.6 * radius * math.sin(angle))

    # anticlockwise from 3 o'clock: water 0-90, lead 90-270, air 270-360
    assert tooltip(ui, view, at(45)) == "water: 1 (25.0%)"
    assert tooltip(ui, view, at(180)) == "lead: 2 (50.0%)"
    assert tooltip(ui, view, at(300)) == "air: 1 (25.0%)"
    clicks = []
    pie.clicked.connect(lambda chart, index: clicks.append(index))
    ui.click(at(180))
    assert clicks == [1]
    assert [r["series"] for r in chart_rows(pie)] == ["water", "lead", "air"]


def test_pie_theme_export_and_validation():
    pie = PieChart(["a", "b"], [3.0, 1.0])
    pie.applyTheme(theme(dark_mode=True).tokens, dark=True)
    series = pie._plot.GetColorSeries()
    first = series.GetColor(0)
    expected = [int(c * 255) for c in palette(True)[0]]
    assert [first.GetRed(), first.GetGreen(), first.GetBlue()] == expected
    image = image_array(render_chart(pie, size=(300, 300)))
    assert image.shape[:2] == (300, 300)
    with pytest.raises(ValueError):
        pie.setData(["a"], [1.0, 2.0])
    with pytest.raises(ValueError):
        pie.setData(["a"], [-1.0])
