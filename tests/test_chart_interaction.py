"""Chart interaction bindings and the right-click context menu (C3)."""
import numpy as np
import pytest
import vtk

from multipanel._widget_support import set_ui_scale, user_scale
from multipanel.chartview import ChartView, Histogram2DChart, PieChart, XYChart
from multipanel.config import theme
from multipanel.router import EventRouter
from multipanel.testing import UiHarness
from multipanel.units import px

SIZE = (900, 600)
VIEW = (250, 100, 500, 400)


@pytest.fixture
def ui():
    previous = user_scale()
    set_ui_scale(1.0)
    with UiHarness(size=SIZE) as harness:
        harness.renderer.theme = theme(dark_mode=False)
        harness.interactor.SetInteractorStyle(
            vtk.vtkInteractorStyleTrackballCamera())
        harness.renderer.ResetCamera()
        EventRouter.install(harness.interactor)
        yield harness
        EventRouter.uninstall(harness.interactor)
    set_ui_scale(previous)


def line_chart(title="Signal"):
    chart = XYChart(title=title)
    chart.addLine(np.linspace(1, 10, 50), np.linspace(1, 100, 50), name="s")
    return chart


def show(ui, chart):
    view = ChartView(ui.renderer, ui.interactor, chart)
    view.setGeometry(*(px(v) for v in VIEW))
    ui.render()
    ui.render()
    return view


def centre(view):
    x, y, w, h = view.geometry("display")
    return x + w / 2, y + h / 2


def width_of(axis):
    low, high = axis.range()
    return high - low


def texts(menu):
    return [item.menu_action.text() if item.menu_action is not None
            else (item.submenu.title() if item.submenu is not None else "-")
            for item in menu.items()]


def submenu(menu, title):
    return next(item.submenu for item in menu.items()
                if item.submenu is not None and item.submenu.title() == title)


def action(menu, text):
    return next(a for a in menu.actions() if a.text() == text)


# -- right click and drag -----------------------------------------------------------------------
def test_right_click_opens_the_menu_and_right_drag_still_zooms(ui):
    chart = line_chart()
    view = show(ui, chart)
    shown = []
    view.contextMenuAboutToShow.connect(shown.append)
    start = width_of(chart.axisX())
    cx, cy = centre(view)
    ui.click((cx, cy), button="right")
    assert len(shown) == 1
    assert texts(shown[0]) == ["Reset view", "Log x axis", "Log y axis",
                               "Legend", "-", "Export"]
    assert width_of(chart.axisX()) == start            # no zero-size zoom
    shown[0].close()
    ui.drag((cx - 80, cy - 60), (cx + 40, cy + 50), button="right", steps=4)
    assert len(shown) == 1                              # a drag: no menu
    assert width_of(chart.axisX()) < start / 2


def test_menu_actions(ui, tmp_path):
    chart = line_chart("My chart")
    view = show(ui, chart)
    view.setExportFolder(tmp_path)
    written = []
    view.exported.connect(written.append)
    menu = view.contextMenu()
    action(menu, "Log y axis").trigger()
    assert chart.axisY().isLogScale()
    action(menu, "Legend").trigger()
    assert not chart._legend
    ui.wheel(centre(view), steps=3)
    action(menu, "Reset view").trigger()
    assert chart.axisX().range() == pytest.approx((0.0, 10.0))
    exports = submenu(menu, "Export")
    action(exports, "PNG image").trigger()
    action(exports, "PNG image").trigger()
    action(exports, "CSV data").trigger()
    assert [p.name for p in written] == ["My_chart.png", "My_chart-2.png",
                                         "My_chart.csv"]
    assert all(p.exists() for p in written)


def test_menus_fit_the_chart_type(ui):
    heat = Histogram2DChart(np.arange(6.0).reshape(2, 3))
    assert "Log colours" in texts(show(ui, heat).contextMenu())
    pie = show(ui, PieChart(["a", "b"], [1.0, 2.0]))
    assert texts(pie.contextMenu()) == ["Reset view", "Legend", "-",
                                        "Export"]
    bars = XYChart()
    bars.addBars([1, 2], [3.0, 4.0], name="b", horizontal=True)
    bars.axisY().setTickLabels([1, 2], ["a", "b"])
    assert "Log y axis" not in texts(show(ui, bars).contextMenu())


def test_the_menu_can_be_disabled(ui):
    view = show(ui, line_chart())
    view.setContextMenuEnabled(False)
    shown = []
    view.contextMenuAboutToShow.connect(shown.append)
    ui.click(centre(view), button="right")
    assert shown == [] and view.showContextMenu() is None


# -- bindings -----------------------------------------------------------------------------------
def test_left_drag_can_zoom_instead_of_pan(ui):
    chart = line_chart()
    view = show(ui, chart)
    start = width_of(chart.axisX())
    cx, cy = centre(view)
    view.setInteraction(left="zoom_box")
    ui.drag((cx - 80, cy - 60), (cx + 40, cy + 50), steps=4)
    assert width_of(chart.axisX()) < start / 2
    view.resetView()
    view.setInteraction(left=None)
    before = chart.axisX().range()
    ui.drag((cx - 80, cy), (cx + 40, cy), steps=4)
    assert chart.axisX().range() == before              # nothing bound


def test_shift_left_zooms_by_default(ui):
    chart = line_chart()
    view = show(ui, chart)
    start = width_of(chart.axisX())
    cx, cy = centre(view)
    ui.drag((cx - 80, cy - 60), (cx + 40, cy + 50), steps=4, shift=True)
    assert width_of(chart.axisX()) < start / 2
    assert view.interaction()["shift_left"] == "zoom_box"


def test_an_unbound_wheel_goes_to_the_scene(ui):
    chart = line_chart()
    view = show(ui, chart)
    view.setInteraction(wheel=None)
    camera = ui.renderer.GetActiveCamera()
    before, x_range = camera.GetPosition(), chart.axisX().range()
    ui.wheel(centre(view), steps=2)
    assert chart.axisX().range() == x_range
    assert camera.GetPosition() != before


def test_bad_bindings_are_refused(ui):
    view = show(ui, line_chart())
    with pytest.raises(ValueError):
        view.setInteraction(left="spin")
    with pytest.raises(ValueError):
        view.setInteraction(alt_left="pan")
    with pytest.raises(ValueError):
        view.setInteraction(wheel="pan")
