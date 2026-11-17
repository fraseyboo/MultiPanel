"""ChartModeFilter: chart-versus-camera switching as a router filter (W1).

Deprecated with the chart actors it serves (multipanel.chart_legacy); kept
working until it is removed.
"""
import pytest
import vtk

from multipanel._widget_support import set_ui_scale, ui_scale, user_scale
from multipanel.router import EventRouter
from multipanel.standard import PushButton
from multipanel.testing import UiHarness
from multipanel.units import px

from multipanel.charts import install_chart_mode


class RecordingStyle:
    """Stands in for DraggableChartInteractorStyle."""

    def __init__(self):
        self.calls = []
        self.mode = "camera"
        self.pressed = False

    def __getattr__(self, name):
        if name.startswith("On"):
            return lambda *_: self.calls.append(name)
        raise AttributeError(name)


@pytest.fixture
def scene():
    previous = user_scale()
    set_ui_scale(1.0)
    with UiHarness(size=(800, 600)) as ui:
        ui.interactor.SetInteractorStyle(
            vtk.vtkInteractorStyleTrackballCamera())
        cube = vtk.vtkActor()
        mapper = vtk.vtkPolyDataMapper()
        source = vtk.vtkCubeSource()            # keep alive: the port needs it
        mapper.SetInputConnection(source.GetOutputPort())
        cube.SetMapper(mapper)
        ui.renderer.AddActor(cube)
        ui.renderer.ResetCamera()
        chart_actor = vtk.vtkContextActor()
        chart = vtk.vtkChartXY()
        chart.SetAutoSize(False)
        chart.SetSize(vtk.vtkRectf(400, 300, 380, 280))
        table = vtk.vtkTable()
        for name in ("x", "y"):
            column = vtk.vtkFloatArray()
            column.SetName(name)
            table.AddColumn(column)
        table.SetNumberOfRows(10)
        for row in range(10):
            table.SetValue(row, 0, row)
            table.SetValue(row, 1, row * row)
        chart.AddPlot(vtk.vtkChart.LINE).SetInputData(table, "x", "y")
        chart_actor.GetScene().AddItem(chart)
        ui.renderer.AddActor(chart_actor)
        ui.render()
        style = RecordingStyle()
        with pytest.deprecated_call():
            chart_filter = install_chart_mode(ui.interactor, chart_actor,
                                              style)
        yield ui, chart_filter, style, chart
        EventRouter.uninstall(ui.interactor)
    set_ui_scale(previous)


def camera(ui):
    return tuple(round(v, 6) for v in ui.renderer.GetActiveCamera()
                 .GetPosition())


def inside(chart):
    (x0, y0), (x1, y1) = chart.GetPoint1(), chart.GetPoint2()
    return ((x0 + x1) / 2, (y0 + y1) / 2)


def test_plot_area_is_detected(scene):
    _ui, chart_filter, _style, chart = scene
    assert chart_filter.isOverChart(*inside(chart))
    assert not chart_filter.isOverChart(100, 100)


def test_drag_over_the_chart_goes_to_the_chart_not_the_camera(scene):
    ui, _filter, style, chart = scene
    before = camera(ui)
    start = inside(chart)
    ui.drag(start, (start[0] + 30, start[1] + 20), steps=3)
    # (the harness moves to the press point first: a hover move)
    pressed = style.calls.index("OnLeftButtonDown")
    assert style.calls[pressed + 1:].count("OnMouseMove") >= 3
    assert style.calls[-1] == "OnLeftButtonUp"
    assert camera(ui) == before


def test_a_drag_that_leaves_the_chart_stays_with_it(scene):
    ui, _filter, style, chart = scene
    before = camera(ui)
    ui.drag(inside(chart), (100, 100), steps=4)
    assert style.calls[-1] == "OnLeftButtonUp"
    assert camera(ui) == before


def test_elsewhere_the_camera_moves(scene):
    ui, _filter, style, _chart = scene
    before = camera(ui)
    ui.drag((150, 150), (250, 220), steps=4)
    assert camera(ui) != before
    assert not [c for c in style.calls if "Button" in c]


def test_wheel_over_the_chart_and_elsewhere(scene):
    ui, _filter, style, chart = scene
    before = camera(ui)
    ui.wheel(inside(chart), steps=1)
    assert style.calls[-1] == "OnMouseWheelForward"
    assert camera(ui) == before
    ui.wheel((150, 150), steps=1)
    assert camera(ui) != before


def test_a_widget_over_the_chart_wins(scene):
    ui, _filter, style, chart = scene
    button = PushButton(ui.renderer, ui.interactor, "Fit")
    x, y = inside(chart)
    button.setGeometry(px(x - 30), px(y - 12), px(60), px(24))
    ui.render()
    clicked = []
    button.clicked.connect(lambda *_: clicked.append(True))
    ui.click((x, y))
    assert clicked and not [c for c in style.calls if "Button" in c]
