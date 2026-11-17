"""Tooltips appear (and disappear) on hover, not on the next click.

Regression: HoverTextOverlay toggled its text actor on mouse move but never
requested a render, and hover moves do not render on their own, so the
tooltip only showed up when something else (usually a click) rendered.
"""
import numpy as np
import pytest

from multipanel.controls import (
    VectorButtonWidget,
    get_hover_text_overlay,
    set_tooltip_delay,
    tooltip_delay,
)
from multipanel.testing import UiHarness

SIZE = (800, 600)


@pytest.fixture
def ui():
    with UiHarness(size=SIZE) as harness:
        yield harness


DELAY = tooltip_delay()


def button(ui, text="Place a cube", bounds=(0.4, 0.45, 0.4, 0.45)):
    square = np.asarray(((0.2, 0.2), (0.8, 0.2), (0.8, 0.8), (0.2, 0.8)))
    widget = VectorButtonWidget(ui.renderer, ui.interactor, input_data=[square],
                                color=(0.3, 0.3, 0.3), hover_text=text,
                                bounds=bounds)
    ui.render()
    return widget


def centre(widget):
    x0, x1, y0, y1 = widget.GetBounds()
    return ((x0 + x1) / 2 * SIZE[0], (y0 + y1) / 2 * SIZE[1])


def test_hover_shows_and_leave_hides_with_a_render(ui):
    widget = button(ui)
    overlay = get_hover_text_overlay(ui.renderer, ui.interactor)
    renders = []
    ui.window.AddObserver("StartEvent", lambda *_: renders.append(1))
    x0, x1, y0, y1 = widget.GetBounds()

    ui.move(((x0 + x1) / 2 * SIZE[0], (y0 + y1) / 2 * SIZE[1]))
    ui.process_events(DELAY - 1)
    assert not overlay.text_actor.GetVisibility()     # resting delay first
    ui.process_events(1)
    assert overlay.text_actor.GetVisibility()
    assert "Place a cube" in overlay.text_actor.GetInput()
    assert len(renders) == 1

    ui.move((5, 5))
    ui.process_events()
    assert not overlay.text_actor.GetVisibility()
    assert len(renders) == 2


def test_moving_within_the_button_does_not_re_render(ui):
    widget = button(ui)
    renders = []
    ui.window.AddObserver("StartEvent", lambda *_: renders.append(1))
    x0, x1, y0, y1 = widget.GetBounds()
    for fx in (0.3, 0.5, 0.7):
        ui.move(((x0 + fx * (x1 - x0)) * SIZE[0], (y0 + y1) / 2 * SIZE[1]))
        ui.process_events(DELAY)
    assert len(renders) == 1


def test_hidden_button_shows_no_tooltip(ui):
    widget = button(ui)
    overlay = get_hover_text_overlay(ui.renderer, ui.interactor)
    widget.SetVisibility(False)
    x0, x1, y0, y1 = widget.GetBounds()
    ui.move(((x0 + x1) / 2 * SIZE[0], (y0 + y1) / 2 * SIZE[1]))
    ui.process_events(DELAY)
    assert not overlay.text_actor.GetVisibility()


def test_passing_over_quickly_shows_nothing(ui):
    widget = button(ui)
    overlay = get_hover_text_overlay(ui.renderer, ui.interactor)
    ui.move(centre(widget))
    ui.process_events(DELAY // 2)
    ui.move((5, 5))
    ui.process_events(DELAY)
    assert not overlay.text_actor.GetVisibility()


def test_neighbour_switches_immediately_once_showing(ui):
    first = button(ui, "First", bounds=(0.40, 0.45, 0.4, 0.45))
    second = button(ui, "Second", bounds=(0.46, 0.51, 0.4, 0.45))
    overlay = get_hover_text_overlay(ui.renderer, ui.interactor)
    ui.move(centre(first))
    ui.process_events(DELAY)
    ui.move(centre(second))
    ui.process_events()
    assert "Second" in overlay.text_actor.GetInput()


def test_press_hides_until_the_pointer_leaves(ui):
    widget = button(ui)
    overlay = get_hover_text_overlay(ui.renderer, ui.interactor)
    ui.move(centre(widget))
    ui.process_events(DELAY)
    ui.press(centre(widget))
    ui.release(centre(widget))
    assert not overlay.text_actor.GetVisibility()
    x, y = centre(widget)
    ui.move((x + 1, y))
    ui.process_events(DELAY)
    assert not overlay.text_actor.GetVisibility()     # still suppressed
    ui.move((5, 5))
    ui.move(centre(widget))
    ui.process_events(DELAY)
    assert overlay.text_actor.GetVisibility()


def test_delay_is_configurable():
    previous = tooltip_delay()
    try:
        set_tooltip_delay(0)
        with UiHarness(size=SIZE) as harness:
            widget = button(harness)
            overlay = get_hover_text_overlay(harness.renderer, harness.interactor)
            harness.move(centre(widget))
            assert overlay.text_actor.GetVisibility()
    finally:
        set_tooltip_delay(previous)
