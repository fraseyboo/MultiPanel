"""Display changes: unannounced size/DPI changes re-lay out the UI."""
import pytest
import vtk

from multipanel._widget_support import set_ui_scale, ui_scale, user_scale
from multipanel.chartview import ChartView, XYChart
from multipanel.display import DisplayWatcher, fit_window_to_screen
from multipanel.router import EventRouter
from multipanel.testing import UiHarness
from multipanel.units import px


@pytest.fixture
def ui():
    previous = user_scale()
    set_ui_scale(1.0)
    with UiHarness(size=(800, 600)) as harness:
        EventRouter.install(harness.interactor)
        yield harness
        EventRouter.uninstall(harness.interactor)
    set_ui_scale(previous)


def count_events(ui):
    seen = []
    window = ui.interactor.GetRenderWindow()
    window.AddObserver("WindowResizeEvent", lambda *_: seen.append("window"))
    ui.interactor.AddObserver("ConfigureEvent",
                              lambda *_: seen.append("interactor"))
    return seen


def test_unannounced_display_changes_send_one_resize(ui):
    window = ui.interactor.GetRenderWindow()
    assert DisplayWatcher._instances.get(window) is not None
    seen = count_events(ui)
    # As when the window moves to a Retina display: twice the pixels, twice
    # the DPI, no event.
    window.SetSize(1600, 1200)
    window.SetDPI(144)
    seen.clear()
    ui.render()
    assert seen == []                        # not during the render
    ui.process_events()
    assert seen == ["window", "interactor"]
    ui.render()
    ui.process_events()
    assert seen == ["window", "interactor"]  # once


def test_real_resizes_are_not_repeated(ui):
    window = ui.interactor.GetRenderWindow()
    seen = count_events(ui)
    window.SetSize(900, 700)
    window.InvokeEvent("WindowResizeEvent")  # the platform announced it
    seen.clear()
    ui.render()
    ui.process_events()
    assert seen == []


def test_layouts_follow_the_new_display(ui):
    from multipanel.containers import ScrollablePanel

    window = ui.interactor.GetRenderWindow()
    panel = ScrollablePanel(ui.interactor, ["a", "b", "c"], x=0.1, y=0.5,
                            width=0.2, height=0.3, title="List")
    ui.render()
    assert panel._last_layout_window_size == (800, 600)
    window.SetSize(1600, 1200)              # unannounced, as on a display move
    ui.render()
    ui.process_events()
    assert panel._last_layout_window_size == (1600, 1200)


def test_uninstall_removes_the_watcher(ui):
    window = ui.interactor.GetRenderWindow()
    EventRouter.uninstall(ui.interactor)
    assert DisplayWatcher._instances.get(window) is None
    EventRouter.install(ui.interactor)
    assert DisplayWatcher._instances.get(window) is not None


class FakeWindow:
    def __init__(self, size, screen, dpi=72):
        self.size, self.screen, self.dpi = list(size), screen, dpi

    def GetSize(self):
        return self.size

    def GetScreenSize(self):
        return self.screen

    def GetDPI(self):
        return self.dpi

    def SetSize(self, width, height):
        self.size = [width, height]


def test_requested_sizes_fit_the_screen():
    window = FakeWindow((1500, 1500), (2560, 1440))
    assert fit_window_to_screen(window) == (1500, 1320)
    retina = FakeWindow((4000, 3000), (3024, 1964), dpi=144)
    assert fit_window_to_screen(retina) == (3024 - 80, 1964 - 240)
    small = FakeWindow((800, 600), (2560, 1440))
    assert fit_window_to_screen(small) == (800, 600) and \
        small.size == [800, 600]


def test_tabs_shrink_to_fit_a_short_window(ui):
    from multipanel.containers import DockPane

    window = ui.interactor.GetRenderWindow()
    dock = DockPane(ui.renderer, ui.interactor, side="left", width=0.3)
    for index in range(10):
        dock.add_tab(f"t{index}", "add_shape")
    ui.render()

    def tab_boxes():
        return sorted((tab["button"].GetBounds()[2], tab["button"].GetBounds()[3])
                      for tab in dock.tabs)

    boxes = tab_boxes()                     # 600 px tall: too many tabs
    assert boxes[0][0] >= 0.0 and boxes[-1][1] <= 1.0
    assert all(a[1] <= b[0] + 1e-9 for a, b in zip(boxes, boxes[1:]))
    assert dock._tab_scale < 1.0
    window.SetSize(800, 1400)
    window.InvokeEvent("WindowResizeEvent")
    ui.render()
    assert dock._tab_scale == pytest.approx(1.0)


def test_density_scales_geometry_not_fonts(ui):
    from multipanel._widget_support import (
        device_scale, font_scale, ui_scale, user_scale,
    )
    from multipanel.standard import PushButton
    from multipanel.units import px as length_px

    button = PushButton(ui.renderer, ui.interactor, "OK")
    font_1x = button.fontSize()
    window = ui.interactor.GetRenderWindow()
    window.SetSize(1600, 1200)
    window.SetDPI(144)
    ui.render()
    ui.process_events()
    assert device_scale() == 2.0
    assert ui_scale() == pytest.approx(2.0 * user_scale())
    assert font_scale() == user_scale()
    assert button.fontSize() == font_1x     # VTK applies the DPI to text
    assert length_px(10).resolve(1600) == pytest.approx(20.0)
