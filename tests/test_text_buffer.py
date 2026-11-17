import random

import pytest

from multipanel import clipboard
from multipanel.text_buffer import TextBuffer


def test_typing_replaces_selection_and_undoes_as_one_step():
    buffer = TextBuffer("lead")
    for char in "ing":
        buffer.insert(char)
    assert buffer.text == "leading"
    buffer.undo()
    assert buffer.text == "lead"
    buffer.redo()
    assert buffer.text == "leading"
    buffer.left(select=True)
    buffer.left(select=True)
    buffer.left(select=True)
    assert buffer.selectedText() == "ing"
    buffer.insert("s")
    assert buffer.text == "leads" and buffer.caret == 5


def test_spaces_split_typing_into_undo_steps():
    buffer = TextBuffer("")
    for char in "two words":
        buffer.insert(char)
    buffer.undo()
    assert buffer.text == "two "          # one step per word
    buffer.undo()
    assert buffer.text == ""


def test_word_movement_and_deletion():
    buffer = TextBuffer("density = 11.35 g")
    buffer.home()
    buffer.right(word=True)
    assert buffer.caret == len("density")
    buffer.right(word=True)
    assert buffer.caret == len("density = 11")
    buffer.end()
    buffer.backspace(word=True)
    assert buffer.text == "density = 11.35 "
    buffer.home()
    buffer.delete(word=True)
    assert buffer.text == " = 11.35 "


def test_selection_keys_and_select_word():
    buffer = TextBuffer("lead shield")
    buffer.selectWordAt(7)
    assert buffer.selectedText() == "shield"
    buffer.left()                         # collapses to the selection start
    assert buffer.caret == 5 and not buffer.hasSelection()
    buffer.selectAll()
    assert buffer.selectedText() == "lead shield"
    assert buffer.cut() == "lead shield" and buffer.text == ""


def test_max_length_truncates_inserts():
    buffer = TextBuffer("abc", max_length=5)
    buffer.insert("defgh")
    assert buffer.text == "abcde"
    assert not buffer.insert("x")


def test_sync_adopts_outside_changes():
    buffer = TextBuffer("abc")
    buffer.selectAll()
    buffer.sync("changed", 2)
    assert buffer.text == "changed" and buffer.caret == 2
    assert not buffer.hasSelection()


@pytest.mark.parametrize("seed", range(25))
def test_random_edits_undo_back_to_the_original(seed):
    rng = random.Random(seed)
    original = "".join(rng.choice("ab c_1") for _ in range(rng.randint(0, 12)))
    buffer = TextBuffer(original)
    operations = [
        lambda: buffer.insert(rng.choice("xyz ")),
        lambda: buffer.insert(rng.choice(["pasted", "two words"]), typing=False),
        lambda: buffer.backspace(word=rng.random() < 0.3),
        lambda: buffer.delete(word=rng.random() < 0.3),
        lambda: buffer.left(select=rng.random() < 0.5, word=rng.random() < 0.3),
        lambda: buffer.right(select=rng.random() < 0.5, word=rng.random() < 0.3),
        lambda: buffer.home(select=rng.random() < 0.5),
        lambda: buffer.end(select=rng.random() < 0.5),
        lambda: buffer.selectAll(),
        lambda: buffer.cut(),
    ]
    for _ in range(60):
        rng.choice(operations)()
        assert 0 <= buffer.caret <= len(buffer.text)
        assert 0 <= buffer.anchor <= len(buffer.text)
    while buffer.undo():
        pass
    assert buffer.text == original


def test_internal_clipboard_round_trip(monkeypatch):
    clipboard.set_clipboard_backend("internal")
    try:
        clipboard.set_text("Lead (Pb)")
        assert clipboard.text() == "Lead (Pb)"
        assert clipboard.backend_name() == "internal"
        stored = []
        clipboard.set_clipboard_backend(lambda: "from host", stored.append)
        clipboard.set_text("copied")
        assert stored == ["copied"] and clipboard.text() == "from host"
    finally:
        clipboard.set_clipboard_backend("internal")
