import numpy as np
import pytest

from multipanel.controls import TextWidget, VectorButtonWidget
from multipanel.testing import UiHarness, keysym_for_char
from multipanel.timer import Timer


@pytest.fixture
def ui():
    with UiHarness(size=(640, 480)) as harness:
        yield harness


def make_button(ui, bounds=(0.4, 0.5, 0.4, 0.5)):
    triangle = np.asarray(((0.1, 0.1), (0.9, 0.5), (0.1, 0.9)))
    return VectorButtonWidget(
        ui.renderer, ui.interactor, input_data=[triangle, triangle],
        color=(0.5, 0.5, 0.5), bounds=bounds)


def test_point_of_uses_display_geometry(ui):
    button = make_button(ui, bounds=(0.25, 0.75, 0.5, 1.0))
    assert ui.point_of(button) == (320, 360)
    assert ui.point_of(button, anchor=(0, 0)) == (160, 240)
    assert ui.point_of((10.4, 20.6)) == (10, 21)


def test_click_on_vector_button_emits_pressed(ui):
    button = make_button(ui)
    events = []
    button.pressed.connect(lambda: events.append("pressed"))
    ui.render()

    ui.click(button)
    assert events == ["pressed"]

    ui.click((5, 5))           # outside the button
    assert events == ["pressed"]


def test_key_clicks_type_into_editing_text_widget(ui):
    widget = TextWidget(ui.renderer, ui.interactor, text="", editable=True)
    assert widget.start_editing()

    ui.key_clicks("ab c")
    ui.key("BackSpace")
    ui.key("Return")

    assert widget.textValue() == "ab "
    assert not widget.editing


def test_keysym_mapping_for_punctuation():
    assert keysym_for_char(".") == "period"
    assert keysym_for_char(" ") == "space"
    assert keysym_for_char("Q") == "Q"


def test_process_events_drives_timers(ui):
    fired = []
    Timer.singleShot(ui.interactor, 700, lambda: fired.append(True))
    ui.process_events(699)
    assert not fired
    ui.process_events(1)
    assert fired == [True]


def test_wheel_and_drag_deliver_vtk_events():
    with UiHarness(size=(640, 480), interactor_style=None) as ui:
        _check_wheel_and_drag(ui)


def _check_wheel_and_drag(ui):
    seen = []
    for name in ("MouseWheelForwardEvent", "MouseWheelBackwardEvent",
                 "LeftButtonPressEvent", "MouseMoveEvent",
                 "LeftButtonReleaseEvent"):
        ui.interactor.AddObserver(
            name, lambda caller, event: seen.append(
                (event, caller.GetEventPosition())))

    ui.wheel((10, 10), steps=2)
    ui.wheel((10, 10), steps=-1)
    assert [e for e, _ in seen if "Wheel" in e] == [
        "MouseWheelForwardEvent", "MouseWheelForwardEvent",
        "MouseWheelBackwardEvent"]

    seen.clear()
    ui.drag((0, 0), (40, 0), steps=4)
    # The pointer moves to the start point before the press.
    assert seen[:2] == [("MouseMoveEvent", (0, 0)),
                        ("LeftButtonPressEvent", (0, 0))]
    assert seen[-1] == ("LeftButtonReleaseEvent", (40, 0))
    moves = [pos for event, pos in seen if event == "MouseMoveEvent"]
    assert moves[-1] == (40, 0)
