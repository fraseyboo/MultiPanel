"""QLineEdit options on TextWidget: max length, echo modes, input masks,
completers and insertText (W6)."""
import pytest

from multipanel import clipboard
from multipanel._widget_support import set_ui_scale, ui_scale
from multipanel.animation import animations_enabled, set_animations_enabled
from multipanel.completer import Completer
from multipanel.controls import TextWidget
from multipanel.models import ListModel
from multipanel.router import EventRouter
from multipanel.testing import UiHarness
from multipanel.text_buffer import InputMask, TextBuffer


@pytest.fixture
def ui():
    previous, animated = ui_scale(), animations_enabled()
    set_ui_scale(1.0)
    set_animations_enabled(False)
    with UiHarness(size=(1000, 600)) as harness:
        EventRouter.install(harness.interactor)
        yield harness
        EventRouter.uninstall(harness.interactor)
    set_ui_scale(previous)
    set_animations_enabled(animated)


def field(ui, text="", **options):
    widget = TextWidget(ui.renderer, ui.interactor, text=text, editable=True,
                        position=(0.1, 0.5), size=(0.4, 0.05), text_size=16,
                        scale_text_to_widget=False, **options)
    ui.render()
    return widget


def shown(widget):
    return widget.text_actor.GetInput()


# -- InputMask and the buffer --------------------------------------------------------------
def test_mask_parsing_blank_and_case():
    mask = InputMask(">AAA-999;_")
    assert mask.empty() == "___-___" and len(mask) == 7
    assert mask.apply("abc123") == "ABC-123"
    assert mask.apply("ab") == "AB_-___"
    assert mask.value("AB_-1__") == "AB-1"
    assert not mask.isAcceptable("AB_-123")
    assert mask.isAcceptable("ABC-123")
    assert InputMask("aa").isAcceptable("  ")          # optional positions


def test_mask_character_classes():
    mask = InputMask("9Hb#\\9")
    assert mask.accept(0, "5") == "5" and mask.accept(0, "x") is None
    assert mask.accept(1, "f") == "f" and mask.accept(1, "g") is None
    assert mask.accept(2, "1") == "1" and mask.accept(2, "2") is None
    assert mask.accept(3, "-") == "-"
    assert not mask.isEditable(4) and mask.empty()[4] == "9"   # escaped


def test_buffer_typing_skips_literals_and_backspace_blanks():
    buffer = TextBuffer("", mask="99:99;_")
    buffer.home()
    for ch in "1234":
        buffer.insert(ch)
    assert buffer.text == "12:34" and buffer.caret == 5
    buffer.backspace()
    buffer.backspace()
    assert buffer.text == "12:__" and buffer.caret == 3
    buffer.backspace()                 # over the ':' into the hours
    assert buffer.text == "1_:__" and buffer.caret == 1


def test_typing_a_separator_jumps_past_it():
    buffer = TextBuffer("", mask="99:99;_")
    buffer.home()
    buffer.insert("1")
    buffer.insert(":")
    buffer.insert("5")
    assert buffer.text == "1_:5_"


def test_rejected_characters_and_selection_clearing():
    buffer = TextBuffer("12:34", mask="99:99;_")
    buffer.home()
    assert not buffer.insert("x")
    assert buffer.text == "12:34"
    buffer.selectAll()
    buffer.deleteSelection()
    assert buffer.text == "__:__"
    assert buffer.undo() and buffer.text == "12:34"


# -- max length ----------------------------------------------------------------------------
def test_max_length_limits_typing_paste_and_set_text(ui):
    widget = field(ui, "abc")
    widget.setMaxLength(5)
    widget.setText("abcdefgh")
    assert widget.text == "abcde"
    widget.setText("ab")
    widget.start_editing()
    ui.key_clicks("xyz")
    assert widget.text == "abxyz"
    clipboard.set_text("123")
    ui.key("Home")
    ui.key("v", ctrl=True)
    assert widget.text == "abxyz"           # no room
    widget.setMaxLength(3)
    widget.finish_editing()
    assert widget.text == "abx"


# -- echo modes ------------------------------------------------------------------------------
def test_password_echo_masks_display_and_blocks_copying(ui):
    widget = field(ui, "secret")
    widget.setEchoMode("password")
    assert shown(widget) == "•" * 6
    clipboard.set_text("unchanged")
    widget.start_editing()
    ui.key("a", ctrl=True)
    ui.key("c", ctrl=True)
    ui.key("x", ctrl=True)
    assert clipboard.text() == "unchanged" and widget.text == "secret"
    ui.key("End")
    ui.key_clicks("!")
    assert widget.text == "secret!" and "secret" not in shown(widget)


def test_password_echo_on_edit_shows_text_only_while_editing(ui):
    widget = field(ui, "pin")
    widget.setEchoMode("passwordEchoOnEdit")
    assert shown(widget) == "•" * 3
    widget.start_editing()
    assert "pin" in shown(widget)
    widget.finish_editing()
    assert shown(widget) == "•" * 3


def test_no_echo_shows_nothing_and_keeps_the_caret_at_the_start(ui):
    widget = field(ui, "hidden")
    widget.setEchoMode("noEcho")
    assert shown(widget) == ""
    widget.start_editing()
    ui.key_clicks("abc")
    assert widget.text == "hiddenabc"
    assert widget._full_display_index(widget.caret_index) == 0
    with pytest.raises(ValueError):
        widget.setEchoMode("loud")


# -- input masks in the widget -----------------------------------------------------------------
def test_input_mask_in_a_field(ui):
    widget = field(ui)
    widget.setInputMask("99:99;_")
    assert widget.text == "__:__" and widget.textValue() == ":"
    assert not widget.hasAcceptableInput()
    widget.start_editing()
    assert widget.caret_index == 0                  # first blank position
    ui.key_clicks("0930")
    assert widget.text == "09:30" and widget.hasAcceptableInput()
    ui.key("Return")
    assert widget.textValue() == "09:30"


def test_unfinished_mask_input_is_not_committed(ui):
    widget = field(ui, "12:00")
    widget.setInputMask("99:99;_")
    finished = []
    widget.editingFinished.connect(lambda: finished.append(widget.text))
    widget.start_editing()
    ui.key("BackSpace")
    assert widget.text == "12:0_"
    ui.key("Return")
    assert widget.text == "12:00"                    # reverted
    widget.setInputMask("")
    assert widget.text == "12:00" and widget.inputMask() == ""


# -- insertText ----------------------------------------------------------------------------------
def test_insert_text_replaces_the_selection_and_respects_limits(ui):
    widget = field(ui, "lead")
    changes = []
    widget.textChanged.connect(changes.append)
    widget.caret_index = 0
    assert widget.insertText("hot ")
    assert widget.text == "hot lead" and changes == ["hot lead"]
    widget.start_editing()
    ui.key("a", ctrl=True)
    widget.insertText("été")              # composed text
    assert widget.text == "été"
    widget.setMaxLength(4)
    widget.insertText("abc")
    assert widget.text == "étéa"


# -- completer -----------------------------------------------------------------------------------
MATERIALS = ["Aluminium", "Air", "Argon", "Lead", "Lithium"]


def test_completer_filtering():
    completer = Completer(MATERIALS)
    assert completer.completions("a") == ["Aluminium", "Air", "Argon"]
    assert completer.completions("") == []
    contains = Completer(MATERIALS, filter_mode="contains")
    assert contains.completions("i") == ["Aluminium", "Air", "Lithium"]
    strict = Completer(MATERIALS, case_sensitive=True)
    assert strict.completions("a") == []
    model = ListModel(MATERIALS)
    assert Completer(model).completions("li") == ["Lithium"]
    model.append("Lime")
    assert Completer(model).completions("li") == ["Lithium", "Lime"]


def test_completions_show_while_typing_and_keep_focus(ui):
    widget = field(ui)
    widget.setCompleter(MATERIALS)
    widget.start_editing()
    ui.key_clicks("a")
    assert widget.isCompletionVisible() and widget.editing
    menu = widget._completer_menu
    assert [item.text() for item in menu.items()] == [
        "Aluminium", "Air", "Argon"]
    ui.key("Down")
    ui.key("Down")
    ui.key("Return")                                # accepts, keeps editing
    assert widget.text == "Air" and widget.editing
    assert not widget.isCompletionVisible()
    ui.key_clicks("g")                              # "Airg": no match
    assert not widget.isCompletionVisible()
    ui.key("Return")                                # now finishes
    assert not widget.editing and widget.text == "Airg"


def test_escape_closes_the_list_first_and_a_click_accepts(ui):
    widget = field(ui)
    accepted = []
    completer = Completer(MATERIALS)
    completer.activated.connect(accepted.append)
    widget.setCompleter(completer)
    widget.start_editing()
    ui.key_clicks("l")
    ui.key("Escape")
    assert not widget.isCompletionVisible() and widget.editing
    ui.key_clicks("e")
    menu = widget._completer_menu
    assert widget.isCompletionVisible()
    ui.click(menu.items()[0])
    assert widget.text == "Lead" and accepted == ["Lead"]
    assert not widget.isCompletionVisible()


def test_no_list_for_an_exact_single_match(ui):
    widget = field(ui)
    widget.setCompleter(["Lead"])
    widget.start_editing()
    ui.key_clicks("lead")
    assert not widget.isCompletionVisible()
