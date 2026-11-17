"""Docks in narrow windows: content minimum and automatic collapsing."""
import pytest
import vtk

from multipanel._widget_support import set_ui_scale, user_scale
from multipanel.containers import DockPane
from multipanel.router import EventRouter
from multipanel.testing import UiHarness


@pytest.fixture
def ui():
    previous = user_scale()
    set_ui_scale(1.0)
    with UiHarness(size=(1400, 900)) as harness:
        EventRouter.install(harness.interactor)
        yield harness
        EventRouter.uninstall(harness.interactor)
    set_ui_scale(previous)


def docks(ui):
    left = DockPane(ui.renderer, ui.interactor, side="left", width=0.22)
    left.add_tab("one", "add_shape")
    left.add_tab("two", "GRI")
    right = DockPane(ui.renderer, ui.interactor, side="right", width=0.16)
    return left, right


def resize(ui, width):
    window = ui.interactor.GetRenderWindow()
    window.SetSize(width, 900)
    window.InvokeEvent("WindowResizeEvent")
    ui.render()


def content_px(dock, width):
    x0, x1, _y0, _y1 = dock._content_bounds()
    return (x1 - x0) * width


def test_content_keeps_a_readable_width(ui):
    left, _right = docks(ui)
    resize(ui, 1000)
    assert content_px(left, 1000) == pytest.approx(DockPane.MIN_CONTENT_PX)
    resize(ui, 2400)
    assert left.width == pytest.approx(0.22)          # the fraction wins


def test_narrow_windows_collapse_the_newest_dock_first(ui):
    left, right = docks(ui)
    resize(ui, 1400)
    assert not left.isCollapsed() and not right.isCollapsed()
    resize(ui, 650)
    assert right.isCollapsed() and not left.isCollapsed()
    assert right.collapse_button.GetRepresentation().GetState() == 1
    resize(ui, 400)
    assert left.isCollapsed() and left.content_collapsed
    resize(ui, 1400)                                  # room again
    assert not left.isCollapsed() and not right.isCollapsed()


def test_hand_choices_stick_until_the_next_resize(ui):
    left, right = docks(ui)
    resize(ui, 400)
    assert left.isCollapsed()
    left.select_tab(left.active_tab)                  # opened by hand
    assert not left.isCollapsed()
    ui.render()
    assert not left.isCollapsed()
    resize(ui, 1400)
    resize(ui, 1300)
    assert not left.isCollapsed()


def test_hand_collapsed_docks_stay_collapsed_when_widening(ui):
    left, _right = docks(ui)
    left.select_tab(left.active_tab)                  # closed by hand
    resize(ui, 400)
    resize(ui, 1400)
    assert left.isCollapsed()
