"""Long series: decimation, fast hit-testing, hidden charts (charts C5)."""
import time

import numpy as np
import pytest
import vtk

from multipanel._widget_support import set_ui_scale, ui_scale, user_scale
from multipanel.chart_export import render_chart
from multipanel.chartview import ChartView, LineSeries, XYChart, _m4
from multipanel.config import theme
from multipanel.router import EventRouter
from multipanel.testing import UiHarness
from multipanel.units import px

SIZE = (1200, 800)
VIEW = (100, 100, 900, 500)


def test_m4_keeps_each_columns_extremes_in_order():
    rng = np.random.default_rng(3)
    x = np.sort(rng.uniform(0, 100, 50_000))
    y = rng.normal(size=x.size)
    columns = np.floor(x).astype(np.int64)
    xs, ys = _m4(x, y, columns)
    assert len(xs) <= 4 * 100
    assert np.all(np.diff(xs) >= 0)                     # drawing order
    picked = set(zip(xs.tolist(), ys.tolist()))
    assert picked <= set(zip(x.tolist(), y.tolist()))   # real points only
    for column in range(100):
        inside = columns == column
        assert ys[np.floor(xs).astype(int) == column].min() == y[inside].min()
        assert ys[np.floor(xs).astype(int) == column].max() == y[inside].max()
    assert (xs[0], xs[-1]) == (x[0], x[-1])


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


def long_line(n=200_000, spike=None):
    x = np.linspace(0.0, 1000.0, n)
    y = np.sin(x / 7.0)
    if spike is not None:
        y[spike] = 50.0
    chart = XYChart()
    line = chart.addLine(x, y, name="signal")
    return chart, line, x, y


def show(ui, chart):
    view = ChartView(ui.renderer, ui.interactor, chart)
    view.setGeometry(*(px(v) for v in VIEW))
    ui.render()
    ui.render()                      # the axes know their pixel length
    return view


def drawn_rows(line):
    return line.vtkPlot().GetInput().GetNumberOfRows()


def centre(view):
    x, y, w, h = view.geometry("display")
    return x + w / 2, y + h / 2


def test_long_lines_draw_a_few_points_per_pixel(ui):
    chart, line, x, _y = long_line(spike=123_456)
    view = show(ui, chart)
    assert line.isDecimated()
    width = view.geometry("display")[2]
    assert drawn_rows(line) <= 4 * 3 * width
    assert chart.axisY().range()[1] >= 50                # fit sees the spike
    assert line.data()[0].size == x.size                 # data untouched
    assert 50.0 in line._drawn[1]                        # spike drawn


def test_pans_and_zooms_redecimate(ui):
    chart, line, _x, _y = long_line()
    view = show(ui, chart)
    before = line._cover[1] - line._cover[0]
    cx, cy = centre(view)
    ui.wheel((cx, cy), steps=4)
    ui.render()
    low, high = chart.axisX().range()
    cover = line._cover
    assert cover[0] <= low and high <= cover[1]
    # the visible range and one view width either side, for the new zoom
    assert cover[1] - cover[0] == pytest.approx(3 * (high - low), rel=0.05)
    assert cover[1] - cover[0] < 0.9 * before
    ui.press((cx + 300, cy))
    for step in range(1, 60):
        ui.move((cx + 300 - 20 * step, cy))
    ui.release()
    ui.render()
    low, high = chart.axisX().range()
    assert line._cover[0] <= low and high <= line._cover[1]


def test_hover_and_export_use_every_point(ui):
    chart, line, x, _y = long_line(spike=150_001)
    view = show(ui, chart)
    ax, ay = chart.axisX(), chart.axisY()
    found = chart.tooltipAt(ax.toScene(x[150_001]), ay.toScene(50.0))
    assert found is not None and found[1] == 150_001
    rows = []
    original = LineSeries._fill_table

    def spy(series):
        original(series)
        rows.append(drawn_rows(series))

    LineSeries._fill_table = spy
    try:
        render_chart(chart, size=(300, 200))
    finally:
        LineSeries._fill_table = original
    assert x.size in rows                                # exported in full
    assert line.isDecimated()                            # view's again


def test_short_or_unsorted_lines_draw_everything(ui):
    chart = XYChart()
    short = chart.addLine(np.arange(1000.0), np.arange(1000.0), name="s")
    x = np.random.default_rng(1).uniform(0, 1, 50_000)
    unsorted = chart.addLine(x, x, name="u")
    show(ui, chart)
    assert not short.isDecimated() and not unsorted.isDecimated()
    assert drawn_rows(unsorted) == 50_000


def test_set_data_decimates_before_drawing(ui):
    chart, line, x, y = long_line()
    show(ui, chart)
    line.setData(x, -y)
    assert line.isDecimated() and drawn_rows(line) < 20_000


def test_hidden_charts_do_no_work(ui):
    chart, line, _x, _y = long_line()
    view = show(ui, chart)
    calls = []
    original = chart._update_decimation
    chart._update_decimation = lambda *a, **k: calls.append(1) or \
        original(*a, **k)
    view.SetVisibility(False)
    for _ in range(3):
        ui.render()
    assert calls == [] and not view._content.GetDraw()


def test_hover_on_a_million_points_is_quick(ui):
    chart, _line, _x, _y = long_line(n=1_000_000)
    view = show(ui, chart)
    cx, cy = centre(view)
    ui.move((cx, cy))
    start = time.perf_counter()
    for step in range(20):
        ui.move((cx + step, cy + 2))
    per_move = (time.perf_counter() - start) / 20
    assert per_move < 0.02                               # generous: ~1 ms
