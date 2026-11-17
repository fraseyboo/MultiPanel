"""Dragging chart data: histogram bins and edges, stems, points; undo (C3)."""
import numpy as np
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
        source = vtk.vtkCubeSource()
        mapper = vtk.vtkPolyDataMapper()
        mapper.SetInputConnection(source.GetOutputPort())
        cube = vtk.vtkActor()
        cube.SetMapper(mapper)
        harness.renderer.AddActor(cube)
        harness.renderer.ResetCamera()
        harness._keep = source
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
    """Display point of data ``(x, y)``."""
    chart = view.chart()
    width, height = SIZE
    vx0, vy0, _vx1, _vy1 = view._content.GetViewport()
    return (vx0 * width + chart.axisX().toScene(x),
            vy0 * height + chart.axisY().toScene(y))


def camera(ui):
    return tuple(round(v, 6) for v in
                 ui.renderer.GetActiveCamera().GetPosition())


def spectrum():
    chart = XYChart()
    step = chart.addStep([0, 1, 2, 4, 8], [0.2, 0.5, 0.3, 0.1], name="bins")
    step.setEditable(True)
    return chart, step


def test_dragging_a_bin_top_changes_its_value(ui):
    chart, step = spectrum()
    view = show(ui, chart)
    edits = []
    step.edited.connect(edits.append)
    before_camera, axes = camera(ui), (chart.axisX().range(),
                                      chart.axisY().range())
    start = display(view, 1.5, 0.5)
    ui.move(start)
    assert view.cursor() == vtk.VTK_CURSOR_SIZENS
    assert chart._highlight_plot.GetVisible()
    ui.drag(start, display(view, 1.5, 0.7), steps=5)
    assert step.values()[1] == pytest.approx(0.7, abs=0.01)
    assert list(step.values()[[0, 2, 3]]) == [0.2, 0.3, 0.1]
    assert edits == [step]                            # once, at release
    assert camera(ui) == before_camera
    assert (chart.axisX().range(), chart.axisY().range()) == axes


def test_values_stay_above_zero(ui):
    chart, step = spectrum()
    view = show(ui, chart)
    ui.drag(display(view, 3, 0.3), display(view, 3, -0.2), steps=4)
    assert step.values()[2] == 0.0


def test_inner_edges_move_but_stay_in_order(ui):
    chart, step = spectrum()
    view = show(ui, chart)
    start = display(view, 2, 0.1)                     # the edge at x = 2
    ui.move(start)
    assert view.cursor() == vtk.VTK_CURSOR_SIZEWE
    ui.drag(start, display(view, 3, 0.1), steps=4)
    assert step.edges()[2] == pytest.approx(3.0, abs=0.05)
    ui.drag(display(view, 3, 0.1), display(view, 0.2, 0.1), steps=6)
    edges = step.edges()
    assert edges[1] < edges[2] < edges[3]             # clamped past edge 1
    assert edges[0] == 0 and edges[-1] == 8           # outer edges fixed


def test_stems_and_points(ui):
    chart = XYChart()
    stems = chart.addStems([0.662, 1.173], [0.85, 1.0], name="lines")
    stems.setEditable(True, move_x=True)
    line = chart.addLine([0.2, 0.6, 1.4], [0.3, 0.4, 0.2], name="curve")
    line.setEditable(True, move_x=True)
    view = show(ui, chart)
    ui.drag(display(view, 1.173, 1.0), display(view, 1.25, 0.6), steps=4)
    x, y = stems.data()
    assert y[1] == pytest.approx(0.6, abs=0.02)
    assert x[1] == pytest.approx(1.25, abs=0.02)
    ui.drag(display(view, 0.6, 0.4), display(view, 1.6, 0.5), steps=4)
    x, y = line.data()
    assert x[1] == pytest.approx(1.4)                 # kept between neighbours
    assert y[1] == pytest.approx(0.5, abs=0.02)


def test_undo_and_redo(ui):
    chart, step = spectrum()
    view = show(ui, chart)
    ui.drag(display(view, 0.5, 0.2), display(view, 0.5, 0.4), steps=4)
    ui.drag(display(view, 5, 0.1), display(view, 5, 0.25), steps=4)
    changed = step.values()
    ui.key("z", ctrl=True)
    assert step.values()[3] == pytest.approx(0.1)
    ui.key("z", ctrl=True)
    assert list(step.values()) == pytest.approx([0.2, 0.5, 0.3, 0.1])
    assert not chart.canUndo()
    ui.key("y", ctrl=True)
    ui.key("z", ctrl=True, shift=True)
    assert list(step.values()) == pytest.approx(list(changed))


def test_non_editable_charts_pan_instead(ui):
    chart = XYChart()
    chart.addStep([0, 1, 2], [0.5, 0.2], name="read only")
    view = show(ui, chart)
    start = chart.axisX().range()
    ui.drag(display(view, 0.5, 0.5), display(view, 1.0, 0.5), steps=4)
    assert chart.axisX().range() != start
    assert chart.series()[0].values()[0] == 0.5


def test_dragging_on_a_log_axis(ui):
    chart, step = spectrum()
    chart.axisY().setLogScale(True)
    view = show(ui, chart)
    ui.drag(display(view, 1.5, 0.5), display(view, 1.5, 0.05), steps=4)
    assert step.values()[1] == pytest.approx(0.05, rel=0.05)


def test_scene_mapping_round_trips(ui):
    chart, _step = spectrum()
    show(ui, chart)
    for axis, value in ((chart.axisX(), 3.3), (chart.axisY(), 0.42)):
        assert axis.fromScene(axis.toScene(value)) == pytest.approx(value)


def test_a_stem_can_be_grabbed_along_its_length(ui):
    chart = XYChart()
    stems = chart.addStems([2.0], [1.0], name="line")
    stems.setEditable(True)
    view = show(ui, chart)
    ui.drag(display(view, 2.0, 0.4), display(view, 2.0, 0.7), steps=4)
    # grabbed mid-way, the top moves with the pointer without jumping to it
    assert stems.data()[1][0] == pytest.approx(1.3, abs=0.02)


def test_moving_a_stem_sideways_keeps_its_height(ui):
    chart = XYChart()
    stems = chart.addStems([1.0, 3.0], [1.0, 0.6], name="lines")
    stems.setEditable(True, move_x=True)
    view = show(ui, chart)
    ui.drag(display(view, 1.0, 0.3), display(view, 2.0, 0.3), steps=4)
    x, y = stems.data()
    assert x[0] == pytest.approx(2.0, abs=0.02) and y[0] == pytest.approx(1.0)


def test_x_limits_keep_moved_points_in_range(ui):
    chart = XYChart()
    stems = chart.addStems([0.5, 1.5], [1.0, 0.5], name="lines")
    stems.setEditable(True, move_x=True, x_minimum=0.1, x_maximum=1.8)
    view = show(ui, chart)
    ui.drag(display(view, 0.5, 0.5), display(view, -0.5, 0.5), steps=4)
    ui.drag(display(view, 1.5, 0.3), display(view, 2.5, 0.3), steps=4)
    assert list(stems.data()[0]) == pytest.approx([0.1, 1.8])
