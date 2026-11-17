"""Multi-line TextEdit (W6, §10.3) and a TextBuffer undo property test."""
import random

import pytest

from multipanel import clipboard
from multipanel._widget_support import set_ui_scale, ui_scale
from multipanel.animation import animations_enabled, set_animations_enabled
from multipanel.router import EventRouter
from multipanel.standard import PushButton
from multipanel.testing import UiHarness
from multipanel.text_buffer import TextBuffer
from multipanel.textedit import TextEdit
from multipanel.units import px

AREA = (100, 100, 300, 200)


@pytest.fixture
def ui():
    previous, animated = ui_scale(), animations_enabled()
    set_ui_scale(1.0)
    set_animations_enabled(False)
    with UiHarness(size=(800, 600)) as harness:
        EventRouter.install(harness.interactor)
        yield harness
        EventRouter.uninstall(harness.interactor)
    set_ui_scale(previous)
    set_animations_enabled(animated)


def editor(ui, text="", area=AREA, **options):
    widget = TextEdit(ui.renderer, ui.interactor, text, **options)
    widget.setGeometry(*(px(v) for v in area))
    ui.render()
    return widget


def point_of(widget, position):
    """Display point of the boundary before ``position``."""
    geometry = widget._geometry()
    rx, ry, _rw, rh = geometry["rows"]
    ox, oy = geometry["origin"]
    row = widget._line_of(position)
    line = widget._line_px() * geometry["scale"]
    scroll = widget.scrollValue() * geometry["scale"]
    y = ry + oy + rh - geometry["pad"] - (row * line - scroll) - line / 2
    x = rx + ox + geometry["pad"] + widget._x_of(position)
    return (x, y)


def shown_lines(widget):
    return [cell.actor.GetInput() for cell in widget._cells
            if cell.actor.GetVisibility()]


# -- TextBuffer property test (acceptance) ------------------------------------------------
@pytest.mark.parametrize("seed", range(25))
def test_random_edits_then_undo_all_give_back_the_original(seed):
    rng = random.Random(seed)
    original = "".join(rng.choice("ab cd\nef") for _ in range(rng.randint(0, 30)))
    buffer = TextBuffer(original)
    for _ in range(60):
        action = rng.choice(("insert", "type", "backspace", "delete", "move",
                             "select", "cut", "word"))
        if action == "insert":
            buffer.insert(rng.choice(("x", "yz ", "\n", "hello world")),
                          typing=False)
        elif action == "type":
            buffer.insert(rng.choice("abc \n"))
        elif action == "backspace":
            buffer.backspace(word=rng.random() < 0.3)
        elif action == "delete":
            buffer.delete(word=rng.random() < 0.3)
        elif action == "move":
            buffer.move(rng.randint(0, len(buffer.text)))
        elif action == "select":
            buffer.select(rng.randint(0, len(buffer.text)),
                          rng.randint(0, len(buffer.text)))
        elif action == "cut":
            buffer.cut()
        else:
            buffer.left(word=True, select=rng.random() < 0.5)
    while buffer.undo():
        pass
    assert buffer.text == original


# -- text and wrapping ----------------------------------------------------------------------
def test_long_lines_wrap_at_spaces_and_only_visible_lines_get_actors(ui):
    words = " ".join(f"word{i}" for i in range(40))
    widget = editor(ui, words + "\nsecond paragraph")
    lines = widget._visual_lines()
    assert len(lines) > 3
    for start, end in lines[:-2]:
        assert widget.toPlainText()[end - 1] == " "       # broke at a space
    assert shown_lines(widget)[-1] == "second paragraph"
    many = editor(ui, "\n".join(f"line {i}" for i in range(2000)),
                  area=(450, 100, 300, 200))
    visible = 200 // many._line_px() + 2
    assert len(many._cells) <= visible + 1
    assert many.verticalScrollBar().isVisible()


def test_typing_past_the_width_wraps_and_keeps_the_caret_visible(ui):
    widget = editor(ui)
    ui.click(widget)
    ui.key_clicks("word " * 30)
    assert len(widget._visual_lines()) > 1
    assert widget._line_of(widget.textCursorPosition()) == \
        len(widget._visual_lines()) - 1
    for _ in range(12):
        ui.key("Return")
    ui.render()
    assert widget.scrollValue() > 0                   # followed the caret
    assert widget.toPlainText().count("\n") == 12


def test_return_inserts_a_newline_and_tab_moves_focus(ui):
    widget = editor(ui, "a")
    other = PushButton(ui.renderer, ui.interactor, "Next")
    other.setGeometry(px(500), px(100), px(80), px(24))
    ui.click(widget)
    ui.key("End", ctrl=True)
    ui.key("Return")
    ui.key_clicks("b")
    assert widget.toPlainText() == "a\nb"
    assert widget.editing
    ui.key("Tab")
    assert other.hasFocus() and not widget.editing
    widget.setTabChangesFocus(False)
    ui.click(widget)
    ui.key("End", ctrl=True)
    ui.key("Tab")
    assert widget.hasFocus() and widget.toPlainText().endswith("    ")


# -- caret movement --------------------------------------------------------------------------
def test_up_down_keep_the_column_and_home_end_follow_lines(ui):
    widget = editor(ui, "abcdefgh\nab\nabcdefgh")
    ui.click(widget)
    widget.setTextCursorPosition(6)                   # "abcdef|gh"
    ui.key("Down")
    assert widget.textCursorPosition() == 11          # end of "ab"
    ui.key("Down")
    assert widget.textCursorPosition() == 18          # back to column 6
    ui.key("Home")
    assert widget.textCursorPosition() == 12
    ui.key("End", shift=True)
    assert widget.selectedText() == "abcdefgh"
    ui.key("Home", ctrl=True)
    assert widget.textCursorPosition() == 0
    ui.key("End", ctrl=True, shift=True)
    assert widget.selectedText() == widget.toPlainText()


def test_page_down_moves_by_a_page(ui):
    widget = editor(ui, "\n".join(f"line {i}" for i in range(100)))
    ui.click(widget)
    ui.key("Home", ctrl=True)
    ui.key("Next")
    page = int(widget._geometry()["view_h"] // widget._line_px()) - 1
    assert widget._line_of(widget.textCursorPosition()) == page
    assert widget.scrollValue() > 0


def test_end_on_a_soft_wrapped_line_stays_on_it(ui):
    widget = editor(ui, " ".join(f"word{i}" for i in range(40)))
    ui.click(widget)
    ui.key("Home", ctrl=True)
    ui.key("End")
    assert widget._line_of(widget.textCursorPosition()) == 0


# -- mouse ----------------------------------------------------------------------------------
def test_drag_selects_and_copy(ui):
    widget = editor(ui, "lead shield\nwater tank")
    ui.drag(point_of(widget, 5), point_of(widget, 17))
    assert widget.selectedText() == "shield\nwater"
    ui.key("c", ctrl=True)
    assert clipboard.text() == "shield\nwater"


def test_double_and_triple_click_select_word_and_line(ui):
    widget = editor(ui, "lead shield\nwater tank")
    point = point_of(widget, 7)
    ui.click(point)
    ui.click(point)
    assert widget.selectedText() == "shield"
    ui.click(point)
    assert widget.selectedText() == "lead shield"


def test_paste_over_a_selection_and_undo(ui):
    widget = editor(ui, "lead shield")
    ui.click(widget)
    widget.setTextCursorPosition(5)
    widget.setTextCursorPosition(11, select=True)
    clipboard.set_text("wall\nand roof")
    ui.key("v", ctrl=True)
    assert widget.toPlainText() == "lead wall\nand roof"
    ui.key("z", ctrl=True)
    assert widget.toPlainText() == "lead shield"
    ui.key("y", ctrl=True)
    assert widget.toPlainText() == "lead wall\nand roof"


def test_wheel_scrolls(ui):
    widget = editor(ui, "\n".join(f"line {i}" for i in range(100)))
    ui.wheel(widget, steps=-2)
    ui.render()
    assert widget.scrollValue() == pytest.approx(2 * TextEdit.WHEEL_STEP_PX)
    first = int(widget.scrollValue() // widget._line_px())
    assert shown_lines(widget)[0] == f"line {first}"


# -- read-only log ----------------------------------------------------------------------------
def test_read_only_log_follows_appends_and_keeps_a_block_limit(ui):
    log = editor(ui, read_only=True)
    log.setMaximumBlockCount(30)
    for i in range(100):
        log.appendPlainText(f"event {i}")
    ui.render()
    assert log.blockCount() == 30
    assert log.toPlainText().splitlines()[0] == "event 70"
    assert log.scrollValue() == pytest.approx(log.verticalScrollBar().maximum())
    assert shown_lines(log)[-1] == "event 99"
    log.setScrollValue(0)                       # scrolled up: stays put
    log.appendPlainText("event 100")
    assert log.scrollValue() == 0


def test_read_only_selects_and_copies_but_does_not_edit(ui):
    log = editor(ui, "error: lost particle", read_only=True)
    ui.click(log)
    assert not log.editing
    ui.key("a", ctrl=True)
    ui.key("c", ctrl=True)
    assert clipboard.text() == "error: lost particle"
    ui.key_clicks("x")
    ui.key("BackSpace")
    ui.key("Return")
    assert log.toPlainText() == "error: lost particle"
    assert not log._caret_actor.GetVisibility()


def test_typing_does_not_reach_scene_hotkeys(ui):
    widget = editor(ui)
    ui.click(widget)
    router = EventRouter.for_interactor(ui.interactor)
    assert router.isTextInputActive()
    ui.click((700, 500))                        # elsewhere: focus leaves
    assert not router.isTextInputActive()


def test_placeholder_and_hiding(ui):
    widget = editor(ui)
    widget.setPlaceholderText("Notes...")
    ui.render()
    assert widget._placeholder_cell.actor.GetVisibility()
    widget.SetVisibility(False)
    ui.render()
    assert not widget._content.GetDraw()
    assert not widget._placeholder_cell.actor.GetVisibility()


def test_monospace_keeps_columns_aligned(ui):
    widget = editor(ui, "1  1 -11.35\n22 0 -1.0", monospace=True)
    # Bounding boxes measure ink, so glyph edges differ by up to a pixel.
    assert widget._width("iiii") == pytest.approx(widget._width("MMMM"),
                                                  abs=1.5)
    second_line = widget.toPlainText().index("22")
    assert widget._x_of(5) == pytest.approx(widget._x_of(second_line + 5))
    assert all(cell.actor.GetTextProperty().GetFontFamilyAsString() ==
               "Courier" for cell in widget._cells
               if cell.actor.GetVisibility())
    widget.setMonospace(False)
    ui.render()
    assert widget._width("iiii") < widget._width("MMMM")
