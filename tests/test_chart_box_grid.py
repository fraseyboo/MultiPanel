"""Box plots and chart grids with linked axes."""
import numpy as np
import pytest
import vtk

from multipanel._widget_support import set_ui_scale, user_scale
from multipanel.chart_export import chart_rows, image_array, render_chart
from multipanel.chart_grid import ChartGrid, ChartGridPanel
from multipanel.chartview import BoxSeries, ChartView, XYChart, box_statistics
from multipanel.config import theme
from multipanel.router import EventRouter
from multipanel.testing import UiHarness
from multipanel.units import px

SIZE = (1000, 700)


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


# -- box plots -------------------------------------------------------------------------------
def test_box_statistics_follow_tukey():
    values = list(range(1, 10)) + [30]                  # 30 is an outlier
    st = box_statistics(values)
    assert (st["q1"], st["median"], st["q3"]) == (3.25, 5.5, 7.75)
    assert (st["low"], st["high"]) == (1.0, 9.0)
    assert list(st["outliers"]) == [30.0] and st["n"] == 10
    with pytest.raises(ValueError):
        box_statistics([np.nan])


def boxes():
    chart = XYChart(title="Dose")
    series = chart.addBoxes([[1, 2, 3, 4, 5], list(range(1, 10)) + [30]],
                            labels=["water", "lead"], name="dose")
    return chart, series


def test_boxes_draw_label_and_fit():
    chart, series = boxes()
    assert isinstance(series, BoxSeries)
    assert chart.axisX().tickLabels() == ([1.0, 2.0], ["water", "lead"])
    low, high = chart.axisY().range()
    assert low <= 1 and high >= 30                     # outliers in view
    x_low, x_high = chart.axisX().range()
    assert x_low <= 1 - 0.3 and x_high >= 2 + 0.3      # whole boxes
    assert series.data()[1].tolist() == [3.0, 5.5]     # medians
    image = image_array(render_chart(chart, size=(400, 300)))[:, :, :3]
    assert len(np.unique(image.reshape(-1, 3), axis=0)) > 20


def test_box_tooltips_and_csv(ui):
    chart, series = boxes()
    view = ChartView(ui.renderer, ui.interactor, chart)
    view.setGeometry(*(px(v) for v in (100, 100, 600, 400)))
    ui.render()
    ui.render()
    found = chart.tooltipAt(chart.axisX().toScene(2.0),
                            chart.axisY().toScene(5.0))
    assert found is not None and found[1] == 1
    assert found[2] == ("dose: lead: median 5.5, Q1–Q3 3.25–7.75, "
                        "whiskers 1–9, n=10, 1 outliers")
    rows = chart_rows(chart)
    kinds = [(r["series"], r["kind"]) for r in rows]
    assert kinds == [("water", "box"), ("water", "whisker"),
                     ("lead", "box"), ("lead", "whisker"),
                     ("lead", "outlier")]
    assert (rows[2]["y_low"], rows[2]["y"], rows[2]["y_high"]) == \
        ("3.25", "5.5", "7.75")


def test_boxes_update_and_remove():
    chart, series = boxes()
    series.setGroups([[10, 11, 12]], labels=["steel"])
    assert series.data()[1].tolist() == [11.0]
    assert chart.axisX().tickLabels()[1] == ["steel"]
    plots = chart.vtkChart().GetNumberOfPlots()
    chart.removeSeries(series)
    assert chart.vtkChart().GetNumberOfPlots() == plots - 3


# -- grids -----------------------------------------------------------------------------------
def line_chart(scale):
    chart = XYChart()
    chart.addLine(np.linspace(0, 10, 50), scale * np.linspace(0, 1, 50),
                  name=f"x{scale}")
    return chart


def test_grid_places_charts_and_links_x(ui):
    grid = ChartGrid(ui.renderer, ui.interactor, columns=2, link="x")
    grid.setGeometry(*(px(v) for v in (50, 50, 900, 600)))
    top = grid.addChart(line_chart(1))
    right = grid.addChart(line_chart(5))
    wide = grid.addChart(line_chart(20), columnSpan=2)
    ui.process_events()                                 # deferred layout
    ui.render()
    ui.render()
    tx, ty, tw, th = top.geometry("px")
    rx, _ry, _rw, _rh = right.geometry("px")
    wx, wy, ww, _wh = wide.geometry("px")
    assert rx > tx + tw - 1 and ww > tw * 1.9 and wy < ty
    before_y = right.chart().axisY().range()
    x, y, w, h = top.geometry("display")
    ui.wheel((x + w / 2, y + h / 2), steps=3)         # zoom the top-left
    zoomed = top.chart().axisX().range()
    assert zoomed != (0.0, 10.0)
    for view in (right, wide):
        assert view.chart().axisX().range() == pytest.approx(zoomed)
    assert right.chart().axisY().range() == before_y   # y is not linked
    ui.double_click((x + w / 2, y + h / 2))            # reset follows too
    assert wide.chart().axisX().range() == top.chart().axisX().range()


def test_unlinked_grids_and_panels(ui):
    grid = ChartGrid(ui.renderer, ui.interactor, columns=2)
    grid.setGeometry(*(px(v) for v in (50, 50, 800, 400)))
    first = grid.addChart(line_chart(1))
    second = grid.addChart(line_chart(2))
    ui.process_events()
    ui.render()
    x, y, w, h = first.geometry("display")
    ui.wheel((x + w / 2, y + h / 2), steps=3)
    assert second.chart().axisX().range() != first.chart().axisX().range()
    grid.setLink("xy")
    assert second.chart().axisY().range() == first.chart().axisY().range()
    with pytest.raises(ValueError):
        grid.setLink("z")
    panel = ChartGridPanel(ui.renderer, ui.interactor, title="Pair",
                           columns=2, link="x")
    panel.grid().addChart(line_chart(1))
    assert isinstance(panel.grid(), ChartGrid)
