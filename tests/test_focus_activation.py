"""Enter/Space activation rules for FocusManager.

Regression: clicking a button gave it focus, so a later Enter press, for
example to commit a host text label that only sets text_edit_mode, clicked
the button again and never reached the label.
"""
import numpy as np
import pytest

from multipanel.controls import VectorButtonWidget
from multipanel.testing import UiHarness


@pytest.fixture
def ui():
    with UiHarness(size=(640, 480)) as harness:
        yield harness


def make_button(ui):
    triangle = np.asarray(((0.1, 0.1), (0.9, 0.5), (0.1, 0.9)))
    button = VectorButtonWidget(
        ui.renderer, ui.interactor, input_data=[triangle, triangle],
        color=(0.5, 0.5, 0.5), bounds=(0.4, 0.5, 0.4, 0.5))
    presses = []
    button.pressed.connect(lambda: presses.append(1))
    ui.render()
    return button, presses


class HostLabel:
    """Mimics a host's editable 3D text: own observer, priority 100."""

    def __init__(self, interactor):
        self.interactor = interactor
        self.keys = []
        interactor.AddObserver("KeyPressEvent", self.on_key, 100.0)

    def start(self):
        self.interactor.text_edit_mode = True

    def on_key(self, caller, _event):
        if getattr(self.interactor, "text_edit_mode", False):
            self.keys.append(caller.GetKeySym())
            if caller.GetKeySym() == "Return":
                self.interactor.text_edit_mode = False


def test_enter_does_not_reclick_a_mouse_focused_button(ui):
    button, presses = make_button(ui)
    ui.click(button)
    assert presses == [1] and button.hasFocus()
    ui.key("Return")
    ui.key("space")
    assert presses == [1]


def test_keyboard_focus_still_activates(ui):
    button, presses = make_button(ui)
    button.setFocus(reason="tab")
    ui.key("Return")
    assert presses == [1]
    ui.click(button)              # mouse focus on the same widget
    ui.key("Return")
    assert presses == [1, 1]


def test_host_text_label_receives_enter_tab_and_escape(ui):
    button, presses = make_button(ui)
    label = HostLabel(ui.interactor)
    button.setFocus(reason="tab")       # even keyboard focus must yield
    label.start()
    ui.key("Tab")
    ui.key("Escape")
    ui.key("Return")
    assert label.keys == ["Tab", "Escape", "Return"]
    assert presses == []
    assert button.hasFocus()            # Escape/Tab did not move focus
