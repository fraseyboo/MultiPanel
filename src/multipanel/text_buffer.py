"""Editable single-line text model (``docs/QT_PARITY_PROPOSAL.md`` §10).

Pure Python, no VTK: the caret, the selection anchor, word-wise movement and
deletion, an optional maximum length, and undo/redo that groups consecutive
typing into one step (as ``QLineEdit`` does)::

    buffer = TextBuffer("lead")
    buffer.end(); buffer.insert("s")          # "leads"
    buffer.left(select=True)                  # "s" selected
    buffer.insert("ing")                      # "leading"
    buffer.undo()                             # "leads"
"""
from __future__ import annotations

__all__ = ["InputMask", "TextBuffer"]


def _is_word(char):
    return char.isalnum() or char == "_"


class InputMask:
    """A ``QLineEdit`` input mask (the common subset of Qt's syntax).

    Mask characters (upper case: required, lower case: optional):

    ====  ===========================================
    A a   letter            N n   letter or digit
    X x   any character     9 0   digit
    D d   digit 1-9         #     digit, + or - (optional)
    H h   hexadecimal       B b   binary
    ====  ===========================================

    ``>`` upper-cases the following characters, ``<`` lower-cases them and
    ``!`` turns case conversion off; ``\\`` makes the next character a
    literal. Anything else is a literal shown as-is. ``;c`` at the end sets
    the blank character (default a space)::

        InputMask("99:99")          # a time; "12:3_"-style with ";_"
        InputMask(">AAA-999;_")     # "ABC-123", upper-cased, "_" blanks

    The edited text always has one character per mask position: literals,
    accepted characters and blanks.
    """

    _CLASSES = {
        "a": str.isalpha,
        "n": str.isalnum,
        "x": lambda ch: True,
        "9": str.isdigit,
        "0": str.isdigit,
        "d": lambda ch: ch in "123456789",
        "#": lambda ch: ch.isdigit() or ch in "+-",
        "h": lambda ch: ch in "0123456789abcdefABCDEF",
        "b": lambda ch: ch in "01",
    }
    _REQUIRED = set("ANX9DHB")

    def __init__(self, mask):
        mask = str(mask)
        self.blank = " "
        if len(mask) >= 2 and mask[-2] == ";":
            self.blank = mask[-1]
            mask = mask[:-2]
        self.mask = mask
        self.slots = []           # (literal or None, kind, required, case)
        case = None
        escaped = False
        for ch in mask:
            if escaped:
                self.slots.append((ch, None, False, None))
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == ">":
                case = "upper"
            elif ch == "<":
                case = "lower"
            elif ch == "!":
                case = None
            elif ch.lower() in self._CLASSES or ch in "90#":
                kind = ch if ch in "90#" else ch.lower()
                self.slots.append((None, kind, ch in self._REQUIRED, case))
            else:
                self.slots.append((ch, None, False, None))

    def __len__(self):
        return len(self.slots)

    def isEditable(self, index):
        return 0 <= index < len(self.slots) and self.slots[index][0] is None

    def nextEditable(self, index):
        for position in range(max(0, index), len(self.slots)):
            if self.isEditable(position):
                return position
        return None

    def previousEditable(self, index):
        for position in range(min(index, len(self.slots) - 1), -1, -1):
            if self.isEditable(position):
                return position
        return None

    def accept(self, index, ch):
        """``ch`` as stored at ``index`` (case applied), or None."""
        if not self.isEditable(index) or not ch or ch == self.blank:
            return None
        _literal, kind, _required, case = self.slots[index]
        if not self._CLASSES[kind.lower() if kind not in "90#" else kind](ch):
            return None
        if case == "upper":
            return ch.upper()
        if case == "lower":
            return ch.lower()
        return ch

    def empty(self):
        """The text with every editable position blank."""
        return "".join(literal if literal is not None else self.blank
                       for literal, *_rest in self.slots)

    def apply(self, text):
        """Fit ``text`` (with or without literals) into the mask."""
        out = list(self.empty())
        source = list(str(text))
        position = 0
        for ch in source:
            # A character matching the literal at the position skips it.
            while position < len(self.slots) and not self.isEditable(position):
                if ch == self.slots[position][0]:
                    break
                position += 1
            if position >= len(self.slots):
                break
            if not self.isEditable(position):
                position += 1               # consumed the literal
                continue
            accepted = self.accept(position, ch)
            if accepted is not None:
                out[position] = accepted
                position += 1
        return "".join(out)

    def value(self, text):
        """``text`` without blanks (what ``QLineEdit.text()`` returns)."""
        return "".join(ch for index, ch in enumerate(str(text))
                       if not (self.isEditable(index) and ch == self.blank))

    def isAcceptable(self, text):
        """True when every required position is filled."""
        text = str(text)
        if len(text) != len(self.slots):
            return False
        return all(not (required and text[index] == self.blank)
                   for index, (literal, _kind, required, _case)
                   in enumerate(self.slots) if literal is None)


class TextBuffer:
    """Text with a caret and a selection (between ``anchor`` and ``caret``)."""

    UNDO_LIMIT = 200

    def __init__(self, text="", max_length=None, mask=None):
        self.mask = mask if mask is None or isinstance(mask, InputMask) \
            else InputMask(mask)
        if self.mask is not None:
            text = self.mask.apply(text) if len(str(text)) != len(self.mask) \
                else str(text)
        self.text = str(text)
        self.caret = len(self.text)
        self.anchor = self.caret
        self.max_length = max_length
        self._undo = []           # (text, caret, anchor) before each change
        self._redo = []
        self._typing = False      # the last change was typing that can merge

    # -- state ---------------------------------------------------------------------
    def setText(self, text, keep_history=False):
        """Replace the text (caret to the end); clears history by default."""
        if keep_history and str(text) != self.text:
            self._push()
        self.text = str(text)
        self.caret = self.anchor = len(self.text)
        self._typing = False
        if not keep_history:
            self._undo.clear()
            self._redo.clear()

    def sync(self, text, caret):
        """Adopt state changed from outside (e.g. host code setting text)."""
        caret = max(0, min(int(caret), len(str(text))))
        if str(text) != self.text:
            self.text = str(text)
            self.anchor = caret
            self._typing = False
        elif caret != self.caret:
            self.anchor = caret
        self.caret = caret

    def hasSelection(self):
        return self.anchor != self.caret

    def selection(self):
        """``(start, end)`` of the selection (equal when empty)."""
        return min(self.anchor, self.caret), max(self.anchor, self.caret)

    def selectedText(self):
        start, end = self.selection()
        return self.text[start:end]

    # -- movement ---------------------------------------------------------------------
    def move(self, position, select=False):
        self.caret = max(0, min(int(position), len(self.text)))
        if not select:
            self.anchor = self.caret
        self._typing = False

    def left(self, select=False, word=False):
        if not select and self.hasSelection() and not word:
            self.move(self.selection()[0])
            return
        self.move(self.wordStart(self.caret) if word else self.caret - 1,
                  select)

    def right(self, select=False, word=False):
        if not select and self.hasSelection() and not word:
            self.move(self.selection()[1])
            return
        self.move(self.wordEnd(self.caret) if word else self.caret + 1,
                  select)

    def home(self, select=False):
        self.move(0, select)

    def end(self, select=False):
        self.move(len(self.text), select)

    def selectAll(self):
        self.anchor, self.caret = 0, len(self.text)
        self._typing = False

    def select(self, start, end):
        self.anchor = max(0, min(int(start), len(self.text)))
        self.caret = max(0, min(int(end), len(self.text)))
        self._typing = False

    def wordStart(self, index):
        """Start of the word at or before ``index`` (skipping spaces)."""
        index = max(0, min(index, len(self.text)))
        while index > 0 and not _is_word(self.text[index - 1]):
            index -= 1
        while index > 0 and _is_word(self.text[index - 1]):
            index -= 1
        return index

    def wordEnd(self, index):
        """End of the word at or after ``index`` (skipping spaces)."""
        index = max(0, min(index, len(self.text)))
        while index < len(self.text) and not _is_word(self.text[index]):
            index += 1
        while index < len(self.text) and _is_word(self.text[index]):
            index += 1
        return index

    def selectWordAt(self, index):
        """Select the word containing ``index`` (double-click)."""
        index = max(0, min(index, len(self.text)))
        if index < len(self.text) and _is_word(self.text[index]) or (
                index > 0 and _is_word(self.text[index - 1])):
            start = index
            while start > 0 and _is_word(self.text[start - 1]):
                start -= 1
            end = index
            while end < len(self.text) and _is_word(self.text[end]):
                end += 1
        else:
            start, end = index, min(len(self.text), index + 1)
        self.select(start, end)

    # -- editing -----------------------------------------------------------------------
    def _push(self):
        self._undo.append((self.text, self.caret, self.anchor))
        if len(self._undo) > self.UNDO_LIMIT:
            del self._undo[0]
        self._redo.clear()

    def _replace(self, start, end, new_text, typing=False):
        # Typing merges into one undo step per word: a space joins the word
        # before it, and the first character after a space starts a new step.
        starts_word = (bool(new_text) and not new_text[0].isspace()
                       and start > 0 and self.text[start - 1].isspace())
        merge = (typing and self._typing and not self.hasSelection()
                 and bool(new_text) and not starts_word)
        if not merge:
            self._push()
        self.text = self.text[:start] + new_text + self.text[end:]
        self.caret = self.anchor = start + len(new_text)
        self._typing = bool(typing)
        return True

    def insert(self, text, typing=True):
        """Insert at the caret, replacing any selection. Returns success."""
        text = str(text)
        if self.mask is not None:
            return self._mask_insert(text, typing)
        start, end = self.selection()
        if self.max_length is not None:
            room = self.max_length - (len(self.text) - (end - start))
            text = text[:max(0, room)]
        if not text and start == end:
            return False
        return self._replace(start, end, text, typing=typing)

    def deleteSelection(self):
        if not self.hasSelection():
            return False
        start, end = self.selection()
        if self.mask is not None:
            return self._mask_clear(start, end, start)
        return self._replace(start, end, "")

    def backspace(self, word=False):
        if self.hasSelection():
            return self.deleteSelection()
        if self.caret == 0:
            return False
        if self.mask is not None:
            position = self.mask.previousEditable(self.caret - 1)
            if position is None:
                self.move(0)
                return False
            return self._mask_clear(position, position + 1, position)
        start = self.wordStart(self.caret) if word else self.caret - 1
        return self._replace(start, self.caret, "")

    def delete(self, word=False):
        if self.hasSelection():
            return self.deleteSelection()
        if self.caret >= len(self.text):
            return False
        if self.mask is not None:
            position = self.mask.nextEditable(self.caret)
            if position is None:
                return False
            return self._mask_clear(position, position + 1, self.caret)
        end = self.wordEnd(self.caret) if word else self.caret + 1
        return self._replace(self.caret, end, "")

    # -- input masks ---------------------------------------------------------------
    def _mask_clear(self, start, end, caret):
        """Blank the editable positions in ``start:end``; caret to ``caret``."""
        chars = list(self.text)
        for index in range(start, min(end, len(chars))):
            if self.mask.isEditable(index):
                chars[index] = self.mask.blank
        new = "".join(chars)
        if new == self.text:
            self.caret = self.anchor = caret
            return False
        self._push()
        self.text = new
        self.caret = self.anchor = caret
        self._typing = False
        return True

    def _mask_insert(self, text, typing):
        mask = self.mask
        chars = list(self.text)
        start, end = self.selection()
        for index in range(start, end):            # typing replaces a selection
            if mask.isEditable(index):
                chars[index] = mask.blank
        caret = start
        placed = False
        for ch in text:
            position = mask.nextEditable(caret)
            accepted = None if position is None else mask.accept(position, ch)
            if accepted is None:
                # Typing a separator jumps past it, leaving any positions
                # before it blank ("1:" in "99:99" gives "1_:").
                literal_at = next(
                    (i for i in range(caret, len(chars))
                     if not mask.isEditable(i) and chars[i] == ch), None)
                if literal_at is not None:
                    caret = literal_at + 1
                    placed = True
                continue
            chars[position] = accepted
            caret = position + 1
            placed = True
        # Skip the literals after the caret, as QLineEdit does.
        following = mask.nextEditable(caret)
        if placed and following is not None:
            caret = following
        new = "".join(chars)
        if new == self.text and caret == self.caret and not self.hasSelection():
            return False
        merge = typing and self._typing and start == end
        if not merge and new != self.text:
            self._push()
        self.text = new
        self.caret = self.anchor = caret
        self._typing = bool(typing)
        return new != self.text or placed

    def cut(self):
        """Remove and return the selected text ('' when nothing selected)."""
        selected = self.selectedText()
        if selected:
            self.deleteSelection()
        return selected

    # -- history -------------------------------------------------------------------------
    def canUndo(self):
        return bool(self._undo)

    def canRedo(self):
        return bool(self._redo)

    def undo(self):
        if not self._undo:
            return False
        self._redo.append((self.text, self.caret, self.anchor))
        self.text, self.caret, self.anchor = self._undo.pop()
        self._typing = False
        return True

    def redo(self):
        if not self._redo:
            return False
        self._undo.append((self.text, self.caret, self.anchor))
        self.text, self.caret, self.anchor = self._redo.pop()
        self._typing = False
        return True
