"""styleStateChanged and legacy VectorButtonWidget states from Style (W7)."""
import numpy as np
import pytest
from vtkmodules.util.numpy_support import vtk_to_numpy
import vtk

from multipanel._widget_support import set_ui_scale, ui_scale, user_scale
from multipanel.config import theme as Theme
from multipanel.controls import VectorButtonWidget
from multipanel.router import EventRouter
from multipanel.standard import CheckBox, PushButton
from multipanel.testing import UiHarness
from multipanel.units import px

SIZE = (800, 600)


@pytest.fixture
def ui():
    previous = user_scale()
    set_ui_scale(1.0)
    with UiHarness(size=SIZE) as harness:
        harness.renderer.theme = Theme(dark_mode=False)
        EventRouter.install(harness.interactor)
        yield harness
        EventRouter.uninstall(harness.interactor)
    set_ui_scale(previous)


def recorder(widget):
    changes = []
    widget.styleStateChanged.connect(
        lambda new, old: changes.append((set(new) - set(old),
                                         set(old) - set(new))))
    return changes


def tile_button(ui, bounds=(0.4, 0.46, 0.4, 0.48), **options):
    square = np.asarray(((0.2, 0.2), (0.8, 0.2), (0.8, 0.8), (0.2, 0.8)))
    widget = VectorButtonWidget(ui.renderer, ui.interactor, input_data=[square],
                                color=(0.1, 0.3, 0.8), bounds=bounds, **options)
    widget.background_style = "rounded"
    ui.render()
    return widget


def centre(widget):
    x0, x1, y0, y1 = widget.GetBounds()
    return ((x0 + x1) / 2 * SIZE[0], (y0 + y1) / 2 * SIZE[1])


def pixel(ui, point):
    grab = vtk.vtkWindowToImageFilter()
    grab.SetInput(ui.interactor.GetRenderWindow())
    grab.ReadFrontBufferOff()
    grab.Update()
    image = grab.GetOutput()
    width, height, _ = image.GetDimensions()
    data = vtk_to_numpy(image.GetPointData().GetScalars())
    return data.reshape(height, width, -1)[int(point[1]), int(point[0]), :3] \
        .astype(int)


# -- the signal ----------------------------------------------------------------------------
def test_hover_focus_enabled_and_checked_emit_style_state_changes(ui):
    box = CheckBox(ui.renderer, ui.interactor, "Wireframe")
    box.setGeometry(px(100), px(100), px(160), px(24))
    ui.render()
    changes = recorder(box)
    ui.move(box)
    ui.move((700, 500))
    box.setFocus(reason="tab")
    box.setChecked(True)
    box.setEnabled(False)
    assert changes == [({"hover"}, set()), (set(), {"hover"}),
                       ({"focus"}, set()), ({"checked"}, set()),
                       ({"disabled"}, set())]


def test_no_signal_when_the_state_is_unchanged(ui):
    button = PushButton(ui.renderer, ui.interactor, "Apply")
    button.setGeometry(px(100), px(100), px(80), px(24))
    ui.render()
    changes = recorder(button)
    button.refresh()
    button.setEnabled(True)
    assert changes == []


# -- VectorButtonWidget -------------------------------------------------------------------
def test_tile_background_follows_hover_and_checked(ui):
    button = tile_button(ui)
    tokens = ui.renderer.theme.tokens
    fill, _border = button._tile_colors()
    assert tuple(fill) == tuple(tokens["button"])
    changes = recorder(button)
    corner = (button.pixel_bounds[0] + 4, button.pixel_bounds[2] + 4)
    before = pixel(ui, corner)
    ui.move(centre(button))
    ui.render()
    assert changes and "hover" in changes[-1][0]
    assert tuple(button._tile_colors()[0]) == tuple(tokens["button_hover"])
    assert not np.array_equal(pixel(ui, corner), before)    # repainted
    ui.move((5, 5))
    ui.render()
    assert np.array_equal(pixel(ui, corner), before)


def test_assigning_enabled_notifies_and_dims_the_icon(ui):
    button = tile_button(ui)
    centre_point = centre(button)
    enabled_colour = pixel(ui, centre_point)
    seen = []
    button.enabledChanged.connect(seen.append)
    changes = recorder(button)
    button.enabled = False                # what hosts do
    ui.render()
    assert seen == [False] and ({"disabled"}, set()) in changes
    dimmed = pixel(ui, centre_point)
    assert np.abs(dimmed - enabled_colour).max() > 40      # visibly lighter
    ui.move(centre(button))                    # no hover look while disabled
    fill, _ = button._tile_colors()
    assert tuple(fill) == tuple(ui.renderer.theme.tokens["button"])
    button.setEnabled(True)
    ui.move((5, 5))
    ui.render()
    assert np.array_equal(pixel(ui, centre_point), enabled_colour)


def test_grayscale_buttons_are_not_dimmed_twice(ui):
    button = tile_button(ui)
    button.grayscale = True
    button.pd = None
    button.Modified()
    ui.render()
    grey = pixel(ui, centre(button))
    button.enabled = False
    ui.render()
    assert np.array_equal(pixel(ui, centre(button)), grey)


def test_a_theme_change_updates_the_tile(ui):
    button = tile_button(ui)
    light = tuple(button._tile_colors()[0])
    ui.renderer.theme.update(dark_mode=True)
    assert tuple(button._tile_colors()[0]) != light
    assert tuple(button._tile_colors()[0]) == \
        tuple(ui.renderer.theme.tokens["button"])


def test_disabled_opacity_can_be_turned_off(ui, monkeypatch):
    button = tile_button(ui)
    colour = pixel(ui, centre(button))
    monkeypatch.setattr(VectorButtonWidget, "DISABLED_OPACITY", 1.0)
    button.enabled = False
    ui.render()
    assert np.array_equal(pixel(ui, centre(button)), colour)
