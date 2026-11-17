"""TextWidget editing: selection, clipboard, undo and caret placement."""
import pytest

from multipanel import clipboard
from multipanel._widget_support import set_ui_scale, ui_scale, user_scale
from multipanel.actions import Shortcut
from multipanel.controls import TextWidget
from multipanel.router import EventRouter
from multipanel.testing import UiHarness

SIZE = (1000, 600)


@pytest.fixture
def ui():
    previous = user_scale()
    set_ui_scale(1.0)
    with UiHarness(size=SIZE) as harness:
        yield harness
        EventRouter.uninstall(harness.interactor)
    set_ui_scale(previous)


def field(ui, text="lead shield", **options):
    options.setdefault("scale_text_to_widget", False)
    widget = TextWidget(ui.renderer, ui.interactor, text=text, editable=True,
                        position=(0.1, 0.5), size=(0.5, 0.05), text_size=16,
                        **options)
    ui.render()
    return widget


def editing(ui, **options):
    widget = field(ui, **options)
    assert widget.start_editing()
    ui.render()
    return widget


def test_shift_arrows_select_and_typing_replaces(ui):
    widget = editing(ui)
    for _ in range(6):
        ui.key("Left", shift=True)
    assert widget.selectedText() == "shield"
    ui.key_clicks("box")
    assert widget.textValue() == "lead box" or widget.text == "lead box"


def test_word_jumps_and_word_delete(ui):
    widget = editing(ui, text="density 11.35 g")
    ui.key("Home")
    ui.key("Right", ctrl=True)
    assert widget.caret_index == len("density")
    ui.key("End")
    ui.key("BackSpace", ctrl=True)
    assert widget.text == "density 11.35 "


def test_copy_cut_paste_through_the_clipboard(ui):
    widget = editing(ui)
    ui.key("a", ctrl=True)
    ui.key("c", ctrl=True)
    assert clipboard.text() == "lead shield"
    ui.key("End")
    for _ in range(6):
        ui.key("Left", shift=True)
    ui.key("x", ctrl=True)
    assert clipboard.text() == "shield" and widget.text == "lead "
    ui.key("Home")
    ui.key("v", ctrl=True)
    assert widget.text == "shieldlead "


def test_paste_replaces_selection_and_flattens_newlines(ui):
    widget = editing(ui)
    clipboard.set_text("water\nsteel")
    ui.key("a", ctrl=True)
    ui.key("v", ctrl=True)
    assert widget.text == "water steel"


def test_undo_and_redo(ui):
    widget = editing(ui, text="lead")
    ui.key_clicks(" box")
    ui.key("z", ctrl=True)
    assert widget.text == "lead "
    ui.key("z", ctrl=True)
    assert widget.text == "lead"
    ui.key("z", ctrl=True, shift=True)
    assert widget.text == "lead "
    ui.key("y", ctrl=True)
    assert widget.text == "lead box"


def test_other_ctrl_keys_still_reach_shortcuts(ui):
    widget = editing(ui)
    saved = []
    Shortcut("Ctrl+S", ui.interactor).activated.connect(lambda: saved.append(1))
    ui.key("s", ctrl=True)
    assert saved == [1] and widget.text == "lead shield"


def caret_point(widget, index):
    x, _box = widget._display_x(widget._display_index(index))
    _x, box = widget._display_x(0)
    return (x + 1, (box[2] + box[3]) / 2)


def test_click_places_the_caret_and_drag_selects(ui):
    widget = editing(ui)
    ui.click(caret_point(widget, 4))
    assert widget.caret_index == 4 and not widget.hasSelectedText()
    ui.render()
    ui.drag(caret_point(widget, 0), caret_point(widget, 4), steps=4)
    assert widget.selectedText() == "lead"


def test_double_click_selects_word_and_triple_selects_all(ui):
    widget = editing(ui)
    point = caret_point(widget, 7)
    ui.click(point)
    ui.click(point)
    assert widget.selectedText() == "shield"
    ui.click(point)
    assert widget.selectedText() == "lead shield"


def test_selection_is_highlighted_over_the_selected_characters(ui):
    widget = editing(ui)
    ui.key("End")
    for _ in range(6):
        ui.key("Left", shift=True)
    actor = widget._selection_highlight
    assert actor.GetVisibility()
    bounds = actor.GetMapper().GetInput().GetBounds()
    start, _box = widget._display_x(widget._display_index(5))
    end, _box = widget._display_x(widget._display_index(11))
    assert bounds[0] == pytest.approx(min(start, end), abs=1)
    assert bounds[1] == pytest.approx(max(start, end), abs=1)
    widget.finish_editing()
    assert not actor.GetVisibility()


def test_clicking_to_start_editing_places_the_caret(ui):
    widget = field(ui, text="lead shield")
    ui.click(caret_point(widget, 4))
    assert widget.editing and widget.caret_index == 4


def test_prefixed_fields_map_clicks_past_the_prefix(ui):
    widget = editing(ui, text="p", prepend_text="Particle: ")
    ui.click(caret_point(widget, 0))
    assert widget.caret_index == 0
    ui.key_clicks("e")
    assert widget.text == "ep"


# -- horizontal scrolling -------------------------------------------------------

LONG = "tungsten carbide shielding block with borated polyethylene liner"


def narrow(ui, text=LONG):
    widget = TextWidget(ui.renderer, ui.interactor, text=text, editable=True,
                        position=(0.1, 0.5), size=(0.15, 0.05), text_size=16,
                        scale_text_to_widget=False)
    ui.render()
    assert widget.start_editing()
    ui.render()
    return widget


def shown(widget):
    return widget.text_actor.GetInput()


def fits(widget):
    return widget._text_width_function()(shown(widget)) <= \
        widget._available_text_width()


def caret_visible(widget):
    x, box = widget._display_x(widget._display_index(widget.caret_index))
    return box[0] - 1 <= x <= box[1] + 1


def test_long_text_scrolls_to_keep_the_caret_visible(ui):
    widget = narrow(ui)
    assert shown(widget) != LONG and fits(widget)
    assert LONG.endswith(shown(widget))            # caret at the end
    ui.key("Home")
    assert LONG.startswith(shown(widget)) and fits(widget)
    assert widget._scroll_start == 0 and caret_visible(widget)
    for _ in range(30):
        ui.key("Right")
        assert fits(widget) and caret_visible(widget)
    assert widget._scroll_start > 0
    assert shown(widget) in LONG


def test_typing_and_deleting_scroll_like_a_line_edit(ui):
    widget = narrow(ui, text="")
    ui.key_clicks("abcdefghijklmnopqrstuvwxyz0123456789")
    assert widget.text == "abcdefghijklmnopqrstuvwxyz0123456789"
    assert shown(widget).endswith("789") and widget._scroll_start > 0
    for _ in range(36):
        ui.key("BackSpace")
        assert fits(widget) and caret_visible(widget)
    assert widget.text == "" and widget._scroll_start == 0


def test_view_slides_back_when_text_is_deleted_at_the_end(ui):
    widget = narrow(ui)
    for _ in range(10):
        ui.key("BackSpace")
    # No hidden text on the left while there is room on the right.
    start = widget._scroll_start
    text = widget._compose_display_text(widget.text, widget.caret_index)
    assert start == 0 or widget._text_width_function()(
        text[start - 1:]) > widget._available_text_width()


def test_clicks_in_a_scrolled_field_hit_the_visible_characters(ui):
    widget = narrow(ui)
    start = widget._scroll_start
    ui.click(caret_point(widget, start + 3))
    assert widget.caret_index == start + 3


def test_selection_highlight_is_clipped_to_the_field(ui):
    widget = narrow(ui)
    ui.key("a", ctrl=True)
    bounds = widget._selection_highlight.GetMapper().GetInput().GetBounds()
    _x, box = widget._display_x(0)
    assert bounds[0] >= box[0] - 1 and bounds[1] <= box[1] + 1


def test_finishing_editing_resets_the_scroll(ui):
    widget = narrow(ui)
    assert widget._scroll_start > 0
    widget.finish_editing()
    assert widget._scroll_start == 0


def test_dragging_past_the_right_edge_scrolls_the_selection(ui):
    widget = narrow(ui)
    ui.key("Home")
    visible = len(shown(widget))
    _x, box = widget._display_x(0)
    y = (box[2] + box[3]) / 2
    ui.drag(caret_point(widget, 0), (box[1] + 40, y), steps=visible + 10)
    assert len(widget.selectedText()) > visible
    assert widget._scroll_start > 0 and fits(widget)
