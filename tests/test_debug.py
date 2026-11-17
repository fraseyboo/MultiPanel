"""Inspector and dump_tree (W10)."""
import io

import pytest

from multipanel._widget_support import set_ui_scale, ui_scale, user_scale
from multipanel.containers import Frame
from multipanel.debug import Inspector, describe, dump_tree
from multipanel.layouts import VBoxLayout
from multipanel.router import EventRouter
from multipanel.standard import CheckBox, PushButton
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


def panel(ui):
    frame = Frame(ui.renderer, ui.interactor, background=True,
                  object_name="settings")
    frame.setGeometry(px(100), px(100), px(240), px(120))
    column = VBoxLayout()
    box = CheckBox(ui.renderer, ui.interactor, "Wireframe",
                   object_name="wireframe")
    box.setToolTip("Draw edges only")
    button = PushButton(ui.renderer, ui.interactor, "Apply")
    column.addWidget(box)
    column.addWidget(button)
    frame.setLayout(column)
    frame.contentLayout().activate()
    ui.render()
    return frame, box, button


def test_describe_lists_name_geometry_hints_policy_and_state(ui):
    _frame, box, _button = panel(ui)
    box.setChecked(True)
    text = describe(box)
    assert text.splitlines()[0] == "CheckBox 'wireframe'"
    assert "geometry (" in text and "sizeHint (" in text
    assert "policy " in text and "checked" in text
    assert "toolTip 'Draw edges only'" in text


def test_dump_tree_indents_children(ui):
    panel(ui)
    stream = io.StringIO()
    text = dump_tree(ui.interactor, stream)
    lines = text.splitlines()
    top = next(i for i, l in enumerate(lines) if l.startswith("Frame 'settings'"))
    assert lines[top + 1].startswith("  CheckBox 'wireframe'")
    assert lines[top + 2].startswith("  PushButton")
    assert stream.getvalue() == text + "\n"


def test_inspector_outlines_the_widget_under_the_pointer(ui):
    _frame, box, button = panel(ui)
    inspector = Inspector(ui.interactor, ui.renderer)
    ui.move(box)
    assert inspector.inspected() is None             # off by default
    ui.key("i", ctrl=True, alt=True)                 # Ctrl+Alt+I
    assert inspector.isEnabled()
    ui.move(button)
    assert inspector.inspected() is button
    assert inspector._outline_actor.GetVisibility()
    assert inspector._text_actor.GetInput().strip().startswith("PushButton")
    ui.move((20, 20))                                 # nothing there
    assert inspector.inspected() is None
    assert not inspector._text_actor.GetVisibility()
    ui.key("i", ctrl=True, alt=True)
    assert not inspector.isEnabled()
    inspector.close()


def test_inspector_does_not_swallow_clicks(ui):
    _frame, box, _button = panel(ui)
    inspector = Inspector(ui.interactor, ui.renderer, enabled=True)
    ui.click(box)
    assert box.isChecked()
    inspector.close()
