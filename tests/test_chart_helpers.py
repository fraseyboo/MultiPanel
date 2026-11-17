"""charts.py: functional helpers on XYChart, and the deprecated chart
actors (charts proposal C8)."""
import numpy as np
import pytest
import vtk

from multipanel import charts
from multipanel.chartview import (
    BarSeries, ChartPanel, LineSeries, ScatterSeries, XYChart,
)


def test_helpers_drive_an_xychart():
    chart = XYChart()
    line = charts.add_line_chart(np.arange(5.0), np.arange(5.0) ** 2,
                                 figure=chart, y_label="squares")
    dots = charts.add_scatter_chart(np.arange(3.0), np.ones(3), axes=chart,
                                    color="red")
    bars = charts.add_bar_chart(np.arange(3.0), [1.0, 2.0, 3.0], axes=chart)
    assert isinstance(line, LineSeries) and line.name() == "squares"
    assert line.color() is None                       # theme palette
    assert isinstance(dots, ScatterSeries)
    assert dots.color() == pytest.approx((1.0, 0.0, 0.0))
    assert isinstance(bars, BarSeries)
    charts.set_x_axis_title(chart, "Energy (keV)")
    charts.set_y_axis_title(chart, "Counts")
    charts.set_title(chart, "Spectrum")
    charts.set_x_axis_limits(chart, 0, 10)
    charts.add_legend(chart)
    charts.add_gridlines(chart)
    assert chart.axisX().title() == "Energy (keV)"
    assert chart.axisY().title() == "Counts" and chart.title() == "Spectrum"
    assert chart.axisX().range() == (0.0, 10.0)
    only_y = charts.add_line_chart([3.0, 1.0, 2.0], figure=chart)
    assert list(only_y.data()[0]) == [0.0, 1.0, 2.0]


def test_helpers_accept_views_and_panels():
    from multipanel.testing import UiHarness

    with UiHarness(size=(600, 400)) as ui:
        panel = ChartPanel(ui.renderer, ui.interactor, XYChart(), title="P")
        series = charts.add_line_chart([0.0, 1.0], [1.0, 2.0], figure=panel)
        assert series in panel.chartView().chart().series()
        charts.set_x_axis_title(panel.chartView(), "x")
        assert panel.chartView().chart().axisX().title() == "x"


def test_raw_vtk_charts_still_work():
    chart = vtk.vtkChartXY()
    plot = charts.add_line_chart(np.arange(4.0), np.arange(4.0), axes=chart)
    assert isinstance(plot, vtk.vtkPlot)
    assert chart.GetNumberOfPlots() == 1


def test_colour_helpers_are_shared():
    from multipanel import colormap_utils

    assert charts.color_to_RGB is colormap_utils.color_to_RGB
    assert charts.color_to_RGBA_255 is colormap_utils.color_to_RGBA_255


def test_chart_actor_helpers_are_deprecated():
    from multipanel import chart_legacy
    from multipanel.testing import UiHarness

    assert charts.add_chart_actor is chart_legacy.add_chart_actor
    with UiHarness(size=(600, 400)) as ui:
        with pytest.deprecated_call(match="ChartPanel or ChartView"):
            actor = charts.add_chart_actor(renderer=ui.renderer,
                                           interactor=ui.interactor,
                                           position=(0.1, 0.1),
                                           size=(0.4, 0.4))
        assert isinstance(actor, vtk.vtkContextActor)
        chart = actor.GetScene().GetItem(0)
        with pytest.deprecated_call():
            drag = charts.DraggableChartInteractorStyle(chart)
        with pytest.deprecated_call():
            charts.HybridInteractorStyle(actor, drag)
