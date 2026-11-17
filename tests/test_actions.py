import numpy as np
import pytest

from multipanel.actions import Action, ActionGroup, KeySequence, Shortcut
from multipanel.controls import TextWidget, VectorButtonWidget
from multipanel.core import WidgetMixin
from multipanel.router import EventRouter
from multipanel.testing import UiHarness

SIZE = (800, 600)


@pytest.fixture
def ui():
    with UiHarness(size=SIZE) as harness:
        harness.scene_keys = []
        harness.interactor.AddObserver(
            "KeyPressEvent",
            lambda caller, _e: harness.scene_keys.append(caller.GetKeySym()),
            10.0)
        yield harness
        EventRouter.uninstall(harness.interactor)


def square_button(ui, **options):
    square = np.asarray(((0.2, 0.2), (0.8, 0.2), (0.8, 0.8), (0.2, 0.8)))
    button = VectorButtonWidget(ui.renderer, ui.interactor, input_data=[square],
                                color=(0.3, 0.3, 0.3),
                                bounds=(0.4, 0.45, 0.4, 0.45), **options)
    ui.render()
    return button


def centre(button):
    x0, x1, y0, y1 = button.GetBounds()
    return ((x0 + x1) / 2 * SIZE[0], (y0 + y1) / 2 * SIZE[1])


# -- key sequences ---------------------------------------------------------------

def test_key_sequence_parsing_and_matching():
    sequence = KeySequence.parse("ctrl+Shift+s")
    assert sequence == "Ctrl+Shift+S"
    assert sequence.toString() == "Ctrl+Shift+S"
    assert sequence.matches("S", {"ctrl", "shift"})
    assert not sequence.matches("s", {"ctrl"})
    assert KeySequence.parse("Del").key == "Delete"
    assert KeySequence.parse("Esc").matches("Escape", set())
    assert KeySequence.parse("F5").toString() == "F5"
    assert KeySequence.parse("Ctrl++").key == "plus"
    with pytest.raises(ValueError):
        KeySequence.parse("Hyper+X")


def test_text_editing_keys():
    assert KeySequence.parse("Ctrl+C").isTextEditingKey()
    assert KeySequence.parse("Delete").isTextEditingKey()
    assert KeySequence.parse("a").isTextEditingKey()
    assert not KeySequence.parse("Ctrl+S").isTextEditingKey()
    assert KeySequence.parse("Escape").isTextEditingKey()   # cancels edits
    assert not KeySequence.parse("F2").isTextEditingKey()


# -- shortcuts ------------------------------------------------------------------------

def test_shortcut_fires_and_hides_the_key_from_the_scene(ui):
    fired = []
    shortcut = Shortcut("Ctrl+S", ui.interactor)
    shortcut.activated.connect(lambda: fired.append(1))
    ui.key("s", ctrl=True)
    assert fired == [1]
    assert ui.scene_keys == []
    ui.key("s")                                   # no Ctrl: not ours
    assert fired == [1] and ui.scene_keys == ["s"]


def test_text_editing_keys_go_to_the_editing_field(ui):
    copies, saves = [], []
    Shortcut("Ctrl+C", ui.interactor).activated.connect(lambda: copies.append(1))
    Shortcut("Delete", ui.interactor).activated.connect(lambda: copies.append(2))
    Shortcut("Ctrl+S", ui.interactor).activated.connect(lambda: saves.append(1))
    field = TextWidget(ui.renderer, ui.interactor, text="abc", editable=True)
    assert field.start_editing()
    ui.key("c", ctrl=True)
    ui.key("Delete")
    ui.key("s", ctrl=True)                        # not a text-editing key
    assert copies == [] and saves == [1]
    field.finish_editing()
    ui.key("c", ctrl=True)
    assert copies == [1]


def test_ambiguous_shortcuts_fire_neither(ui):
    calls = []
    first = Shortcut("Ctrl+D", ui.interactor)
    second = Shortcut("Ctrl+D", ui.interactor)
    first.activated.connect(lambda: calls.append("first"))
    second.activated.connect(lambda: calls.append("second"))
    first.activatedAmbiguously.connect(lambda: calls.append("ambiguous"))
    ui.key("d", ctrl=True)
    assert calls == ["ambiguous"]
    second.setEnabled(False)
    ui.key("d", ctrl=True)
    assert calls == ["ambiguous", "first"]


class Focusable(WidgetMixin):
    def __init__(self, ui, name, parent=None):
        self.interactor = ui.interactor
        self.initWidget(name, parent)
        self.registerFocus(ui.interactor)


def test_widget_context_shortcuts_need_focus(ui):
    panel = Focusable(ui, "panel")
    child = Focusable(ui, "child", parent=panel)
    calls = []
    Shortcut("F2", ui.interactor, context="widget", parent=panel) \
        .activated.connect(lambda: calls.append("widget"))
    Shortcut("F3", ui.interactor, context="widgetWithChildren", parent=panel) \
        .activated.connect(lambda: calls.append("children"))
    ui.key("F2")
    ui.key("F3")
    assert calls == []
    child.setFocus(reason="tab")
    ui.key("F2")
    ui.key("F3")
    assert calls == ["children"]
    panel.setFocus(reason="tab")
    ui.key("F2")
    assert calls == ["children", "widget"]


# -- actions ----------------------------------------------------------------------

def test_action_shortcut_follows_enabled_state(ui):
    triggered = []
    save = Action("Save", interactor=ui.interactor, shortcut="Ctrl+S")
    save.triggered.connect(lambda checked: triggered.append(checked))
    ui.key("s", ctrl=True)
    save.setEnabled(False)
    ui.key("s", ctrl=True)
    assert triggered == [False]
    assert save.toolTip() == "Save (Ctrl+S)"


def test_checkable_actions_and_exclusive_group():
    group = ActionGroup()
    move, rotate = Action("Move"), Action("Rotate")
    group.addAction(move)
    group.addAction(rotate)
    move.trigger()
    assert move.isChecked() and not rotate.isChecked()
    rotate.trigger()
    assert rotate.isChecked() and not move.isChecked()
    rotate.trigger()                     # exclusive: cannot uncheck the last
    assert rotate.isChecked()
    assert group.checkedAction() is rotate


def test_button_bound_to_action(ui):
    button = square_button(ui)
    triggered = []
    action = Action("Place cube", tool_tip="Place a cube")
    action.triggered.connect(lambda checked: triggered.append(checked))
    button.setAction(action)
    assert button.hover_text == "Place a cube"
    ui.click(centre(button))
    assert triggered == [False]
    action.setEnabled(False)
    ui.click(centre(button))
    assert triggered == [False] and not button.enabled


def test_checkable_action_and_two_state_button_stay_in_sync(ui):
    button = square_button(ui)
    button.input_states = [button.input_data, button.input_data]
    button.total_states = 2
    toggled = []
    action = Action("Wireframe", checkable=True)
    action.toggled.connect(toggled.append)
    button.setAction(action)
    ui.click(centre(button))
    assert action.isChecked() and toggled == [True]
    action.setChecked(False)
    assert button.state == 0


def test_escape_after_clicking_a_button_reaches_the_scene(ui):
    button = square_button(ui)
    ui.click(centre(button))
    assert button.hasFocus()
    ui.key("Escape")
    assert ui.scene_keys == ["Escape"]
    assert not button.hasFocus()


def test_shortcut_lifetime_is_owned_by_the_map(ui):
    import gc

    calls = []
    Shortcut("F6", ui.interactor).activated.connect(lambda: calls.append(1))
    gc.collect()
    ui.key("F6")
    assert calls == [1]                     # no reference kept, still alive

    owner = Focusable(ui, "owner")
    owned = Shortcut("F7", ui.interactor, parent=owner)
    owned.activated.connect(lambda: calls.append(2))
    ui.key("F7")
    owner.close()                           # parent destroyed: released
    ui.key("F7")
    assert calls == [1, 2]

    released = Shortcut("F8", ui.interactor)
    released.activated.connect(lambda: calls.append(3))
    released.release()
    ui.key("F8")
    assert calls == [1, 2]
