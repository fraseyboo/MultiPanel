"""Multi-line text editing (``QPlainTextEdit``; ``QT_PARITY_PROPOSAL`` §10.3).

::

    notes = TextEdit(renderer, interactor)
    notes.setPlainText("c Cell cards\n1 1 -11.35 -1 imp:n=1")
    notes.textChanged.connect(save_notes)

    log = TextEdit(renderer, interactor, read_only=True)
    log.setMaximumBlockCount(500)        # keep the last 500 lines
    log.appendPlainText("Loaded 12 cells")

Text wraps at the widget's width (at spaces where possible) and scrolls
vertically, clipped exactly by the widget's own renderer; only visible
lines have text actors, so long logs stay cheap. Editing is a
:class:`~multipanel.text_buffer.TextBuffer`: Shift extends the selection,
Ctrl (Cmd on macOS) or Alt moves and deletes by word, Up/Down move by line
keeping the column, PageUp/PageDown by a page, Home/End to the line's ends
and Ctrl+Home/End to the document's. Ctrl+A/C/X/V/Z/Y as usual. Mouse:
click places the caret, drag selects, double-click selects a word and a
triple-click the line. A read-only editor still selects and copies, and
follows appended text while scrolled to the bottom.
"""
from __future__ import annotations

import bisect
import math

import vtk

from ._widget_support import (
    font_scale,
    UI_Z_PANEL_CONTROL,
    rounded_rect_polydata,
    ui_layer,
    ui_scale,
)
from .core import Signal, SizePolicy, WidgetMixin
from .events import ALT, CTRL, SHIFT
from .layers import LinkedRenderer
from .scrollarea import ScrollBar
from .standard import _DEFAULT_TOKENS, _merge, _polyline, _rgba, _shape_actor
from .style import Style
from .text_buffer import TextBuffer
from .units import px
from .views import _TextCell, _measure, _quad
from .vtk_compat import add_actor_2d, remove_actor_2d

__all__ = ["TextEdit"]


class TextEdit(WidgetMixin):
    """An editable (or read-only) multi-line plain text field."""

    FOCUS_POLICY = "StrongFocus"
    FONT_SIZE = 12
    PAD_PX = 6
    BAR_PX = 10
    LINE_SPACING = 1.35          # line height as a multiple of the font's
    WHEEL_STEP_PX = 60
    SCROLL_MS = 140
    MULTI_CLICK_MS = 400
    TAB_SPACES = 4

    def __init__(self, renderer, interactor, text="", parent=None,
                 read_only=False, monospace=False, object_name="text_edit",
                 ui_z_order=UI_Z_PANEL_CONTROL):
        self.renderer = renderer
        self.interactor = interactor
        self.ui_z_order = int(ui_z_order)
        self._bounds = (0.0, 0.0, 0.0, 0.0)
        self._shown = True
        self._available = True
        self._read_only = bool(read_only)
        self._monospace = bool(monospace)
        self._buffer = TextBuffer(str(text))
        self._buffer.caret = self._buffer.anchor = 0
        self._placeholder = ""
        self._max_blocks = 0
        self._tab_changes_focus = True
        self._lines = None           # [(start, end)] visual lines
        self._wrap_cache = {}
        self._wrap_width = None
        self._goal_x = None          # Up/Down keep this x
        self._drag = False
        self._clicks = (0, -1e9, None)
        self._target = 0.0
        self._animation = None
        self._dirty = True
        self._frame_key = None
        self._shape_key = None
        self._cells = []
        self.initWidget(object_name, parent)
        self.registerFocus(interactor, self.FOCUS_POLICY)

        layer = ui_layer(renderer)
        self._frame_actor = _shape_actor()
        self._frame_actor.SetVisibility(False)
        add_actor_2d(layer, self._frame_actor)
        self._content = LinkedRenderer().link(layer)
        self._content.SetLayer(layer.GetLayer())
        self._content.SetViewport(0.0, 0.0, 0.0, 0.0)
        self._content.SetDraw(False)
        interactor.GetRenderWindow().AddRenderer(self._content)
        # Selection first, so it draws behind the text actors added later.
        self._selection_actor = _shape_actor()
        self._caret_actor = _shape_actor(point_colors=True)
        self._caret_actor.GetProperty().SetLineWidth(max(1.0, ui_scale()))
        self._placeholder_cell = None
        for prop in (self._selection_actor, self._caret_actor):
            prop.SetVisibility(False)
            add_actor_2d(self._content, prop)

        self._bar = ScrollBar(renderer, interactor, parent=self,
                              object_name=f"{object_name}/bar")
        self._bar.ui_z_order = self.ui_z_order + 1
        self._bar.valueChanged.connect(self._on_bar_value)

        self.textChanged = Signal(self)
        self.cursorPositionChanged = Signal(self)
        self.selectionChanged = Signal(self)
        self.registerWithRouter(interactor)
        window = interactor.GetRenderWindow()
        self.ownObserver(window, "WindowResizeEvent",
                         lambda *_: self._invalidate(relayout=True))
        self.ownObserver(window, "StartEvent", self._before_render)

    # -- text ------------------------------------------------------------------------
    def toPlainText(self):
        return self._buffer.text

    def setPlainText(self, text):
        """Replace the text (clears undo history; caret to the start)."""
        self._buffer.setText(str(text).replace("\r\n", "\n"))
        self._buffer.caret = self._buffer.anchor = 0
        self._trim_blocks()
        self._text_changed(scroll_to_caret=False)
        self._target = 0.0
        self._bar.setValue(0.0)

    def appendPlainText(self, text):
        """Add ``text`` as a new paragraph at the end (logs)."""
        follow = self._bar.value() >= self._bar.maximum() - 1
        buffer = self._buffer
        caret, anchor = buffer.caret, buffer.anchor
        joined = buffer.text + ("\n" if buffer.text else "") + str(text)
        buffer.setText(joined, keep_history=not self._read_only)
        buffer.caret, buffer.anchor = caret, anchor
        removed = self._trim_blocks()
        if removed:
            buffer.caret = max(0, caret - removed)
            buffer.anchor = max(0, anchor - removed)
        self._text_changed(scroll_to_caret=False)
        if follow:
            self._scroll_to_value(float("inf"), animated=False)

    def insertPlainText(self, text):
        """Insert at the caret, replacing any selection."""
        if self._buffer.insert(str(text).replace("\r\n", "\n"), typing=False):
            self._trim_blocks()
            self._text_changed()

    def clear(self):
        self.setPlainText("")

    def placeholderText(self):
        return self._placeholder

    def setPlaceholderText(self, text):
        self._placeholder = str(text)
        self._invalidate()

    def isReadOnly(self):
        return self._read_only

    def setReadOnly(self, read_only):
        self._read_only = bool(read_only)
        self._invalidate()

    def maximumBlockCount(self):
        return self._max_blocks

    def setMaximumBlockCount(self, count):
        """Keep at most ``count`` lines (oldest dropped); 0 is unlimited."""
        self._max_blocks = max(0, int(count))
        if self._trim_blocks():
            self._text_changed(scroll_to_caret=False)

    def _trim_blocks(self):
        """Drop the oldest lines over the limit; returns chars removed."""
        if not self._max_blocks:
            return 0
        text = self._buffer.text
        extra = text.count("\n") + 1 - self._max_blocks
        if extra <= 0:
            return 0
        cut = 0
        for _ in range(extra):
            cut = text.index("\n", cut) + 1
        buffer = self._buffer
        caret, anchor = buffer.caret, buffer.anchor
        buffer.setText(text[cut:])               # history refers to old text
        buffer.caret, buffer.anchor = max(0, caret - cut), max(0, anchor - cut)
        return cut

    def tabChangesFocus(self):
        return self._tab_changes_focus

    def setTabChangesFocus(self, changes):
        """True (default): Tab moves focus; False: Tab inserts spaces."""
        self._tab_changes_focus = bool(changes)

    def blockCount(self):
        return self._buffer.text.count("\n") + 1

    # -- caret and selection -----------------------------------------------------------
    @property
    def editing(self):
        """True while focused and editable (the router then keeps typed
        keys away from scene hotkeys)."""
        return self.hasFocus() and not self._read_only and self._available

    def textCursorPosition(self):
        return self._buffer.caret

    def setTextCursorPosition(self, position, select=False):
        self._buffer.move(max(0, min(int(position), len(self._buffer.text))),
                          select=select)
        self._goal_x = None
        self._caret_moved()

    def selectedText(self):
        return self._buffer.selectedText()

    def hasSelectedText(self):
        return self._buffer.hasSelection()

    def selectAll(self):
        self._buffer.selectAll()
        self._caret_moved(scroll=False)

    def copy(self):
        from . import clipboard

        if self._buffer.hasSelection():
            clipboard.set_text(self._buffer.selectedText())

    def cut(self):
        from . import clipboard

        if self._read_only or not self._buffer.hasSelection():
            return
        clipboard.set_text(self._buffer.cut())
        self._text_changed()

    def paste(self):
        from . import clipboard

        if not self._read_only:
            self.insertPlainText(clipboard.text())

    def undo(self):
        if not self._read_only and self._buffer.undo():
            self._text_changed()

    def redo(self):
        if not self._read_only and self._buffer.redo():
            self._text_changed()

    def _text_changed(self, scroll_to_caret=True):
        self._lines = None
        self._goal_x = None
        self.textChanged.emit()
        self._caret_moved(scroll=scroll_to_caret)

    def _caret_moved(self, scroll=True):
        if scroll:
            self.ensureCursorVisible()
        self.cursorPositionChanged.emit()
        self.selectionChanged.emit()
        self._invalidate()

    # -- geometry ------------------------------------------------------------------------
    def GetBounds(self):
        return self._bounds

    def SetBounds(self, x0, x1, y0, y1):
        self._bounds = (float(x0), float(x1), float(y0), float(y1))
        self._invalidate(relayout=True)

    def GetVisibility(self):
        return self._shown

    def SetVisibility(self, visible):
        visible = bool(visible)
        if visible != self._shown:
            self._shown = visible
            self.doLayout()

    def GetEnabled(self):
        return self._shown

    def SetEnabled(self, enabled):
        self.SetVisibility(enabled)

    def isVisible(self):
        return self._shown

    def isEnabled(self):
        return self._available

    def setEnabled(self, enabled):
        enabled = bool(enabled)
        if enabled != self._available:
            self._available = enabled
            self.enabledChanged.emit(enabled)
            self._invalidate()

    def defaultSizePolicy(self):
        return SizePolicy(SizePolicy.Expanding, SizePolicy.Expanding)

    def sizeHint(self):
        return (240.0, 6 * self._line_px() + 2 * self.PAD_PX + 2)

    def minimumSizeHint(self):
        return (80.0, 2 * self._line_px() + 2 * self.PAD_PX + 2)

    def rect(self):
        width, height = self.viewportExtent()
        x0, x1, y0, y1 = self._bounds
        return (x0 * width, y0 * height, (x1 - x0) * width, (y1 - y0) * height)

    # -- measuring and wrapping ------------------------------------------------------------
    def _font_size(self):
        return max(8, int(round(self.FONT_SIZE * font_scale())))

    def _dpi(self):
        return max(1, self.interactor.GetRenderWindow().GetDPI())

    def isMonospace(self):
        return self._monospace

    def setMonospace(self, monospace):
        """Draw in a fixed-width font (keeps columns of input decks aligned)."""
        self._monospace = bool(monospace)
        for cell in self._cells:
            self._style_cell(cell)
        self._wrap_cache.clear()
        self._line_height_cache = None
        self._invalidate(relayout=True)

    def _style_cell(self, cell):
        prop = cell.actor.GetTextProperty()
        if self._monospace:
            prop.SetFontFamilyToCourier()
        else:
            from ._widget_support import apply_ui_font

            apply_ui_font(prop)
        cell.key = None                       # redraw with the new font

    def _new_cell(self):
        cell = _TextCell(self._content)
        self._style_cell(cell)
        return cell

    def _width(self, text):
        return _measure().width(text.replace("\t", " " * self.TAB_SPACES),
                                self._font_size(), self._dpi(),
                                monospace=self._monospace)

    def _line_px(self):
        """Line height in logical px."""
        height = getattr(self, "_line_height_cache", None)
        key = (self._font_size(), ui_scale(), self._monospace)
        if height is None or height[0] != key:
            prop = vtk.vtkTextProperty()
            from ._widget_support import apply_ui_font

            if self._monospace:
                prop.SetFontFamilyToCourier()
            else:
                apply_ui_font(prop)
            prop.SetFontSize(self._font_size())
            box = [0, 0, 0, 0]
            vtk.vtkTextRenderer.GetInstance().GetBoundingBox(
                prop, "Hg", box, self._dpi())
            value = (box[3] - box[2] + 1) * self.LINE_SPACING / ui_scale()
            height = self._line_height_cache = (key, math.ceil(value))
        return height[1]

    def _geometry(self):
        scale = ui_scale()
        x, y, width, height = self.rect()
        dx, dy = self.geometry("display")[:2] if width > 0 else (x, y)
        inner_h = max(0.0, height - 2)
        pad = self.PAD_PX * scale
        view_h = max(0.0, inner_h - 2 * pad) / scale
        # Wrapped at the full width the text may fit; if not, the bar takes
        # its width and the text is wrapped again, narrower.
        bar = self._shown and \
            self._content_px_for(width - 2 - 2 * pad) > view_h + 0.5
        bar_w = self.BAR_PX * scale if bar else 0.0
        rows_w = max(0.0, width - 2 - bar_w)
        return {"scale": scale, "rect": (x, y, width, height),
                "origin": (dx - x, dy - y),
                "rows": (x + 1, y + 1, rows_w, inner_h), "bar": bar,
                "pad": pad, "view_h": max(0.0, inner_h - 2 * pad) / scale}

    def _content_px_for(self, wrap_width):
        return len(self._visual_lines(wrap_width)) * self._line_px()

    def _wrap(self, line, width):
        """Break offsets of one logical line at ``width`` display px."""
        key = (line, round(width), self._font_size(), self._monospace)
        breaks = self._wrap_cache.get(key)
        if breaks is not None:
            return breaks
        if len(self._wrap_cache) > 20000:
            self._wrap_cache.clear()
        breaks = []
        start = 0
        if width > 0 and self._width(line) > width:
            while start < len(line) and \
                    self._width(line[start:]) > width:
                low, high = 1, len(line) - start
                while low < high:            # longest piece that fits
                    middle = (low + high + 1) // 2
                    if self._width(line[start:start + middle]) <= width:
                        low = middle
                    else:
                        high = middle - 1
                end = start + low
                space = line.rfind(" ", start, end)
                if space >= start and end < len(line) and \
                        line[end] != " ":
                    end = space + 1          # break after the last space
                elif end < len(line) and line[end] == " ":
                    end += 1                 # keep the space on this line
                breaks.append(end)
                start = end
        self._wrap_cache[key] = breaks
        return breaks

    def _visual_lines(self, wrap_width=None):
        """``[(start, end), ...]``: character ranges of the visual lines."""
        if wrap_width is None:
            geometry = self._geometry()
            wrap_width = geometry["rows"][2] - 2 * geometry["pad"]
        wrap_width = max(1.0, wrap_width)
        if self._lines is not None and self._wrap_width == round(wrap_width):
            return self._lines
        lines, offset = [], 0
        for logical in self._buffer.text.split("\n"):
            start = 0
            for end in self._wrap(logical, wrap_width):
                lines.append((offset + start, offset + end))
                start = end
            lines.append((offset + start, offset + len(logical)))
            offset += len(logical) + 1
        self._lines, self._wrap_width = lines, round(wrap_width)
        self._line_starts = [start for start, _end in lines]
        return lines

    def _line_of(self, position):
        lines = self._visual_lines()
        row = bisect.bisect_right(self._line_starts, position) - 1
        return max(0, min(row, len(lines) - 1))

    def _x_of(self, position):
        """Display-px x of ``position`` from the line's text start."""
        start, _end = self._visual_lines()[self._line_of(position)]
        return self._width(self._buffer.text[start:position])

    def _position_at(self, row, x):
        """Nearest position on visual line ``row`` to display-px ``x``."""
        lines = self._visual_lines()
        row = max(0, min(row, len(lines) - 1))
        start, end = lines[row]
        text = self._buffer.text
        # A soft-wrapped line's trailing space belongs before the break.
        last = end - 1 if end > start and row + 1 < len(lines) and \
            lines[row + 1][0] == end and text[end - 1] == " " else end
        best, best_distance = start, abs(x)
        low, high = start, last
        while low < high:                    # first position right of x
            middle = (low + high) // 2
            if self._width(text[start:middle + 1]) < x:
                low = middle + 1
            else:
                high = middle
        for candidate in (low - 1, low, low + 1):
            if start <= candidate <= last:
                distance = abs(self._width(text[start:candidate]) - x)
                if distance < best_distance:
                    best, best_distance = candidate, distance
        return best

    # -- scrolling ----------------------------------------------------------------------------
    def verticalScrollBar(self):
        return self._bar

    def scrollValue(self):
        return self._bar.value()

    def setScrollValue(self, value):
        self._update_range()
        self._bar.setValue(value)

    def _update_range(self):
        geometry = self._geometry()
        content = len(self._visual_lines()) * self._line_px()
        maximum = max(0.0, content - geometry["view_h"])
        page = max(1.0, geometry["view_h"])
        if (page, maximum) != (self._bar.pageStep(), self._bar.maximum()):
            self._bar.setPageStep(page)
            self._bar.setSingleStep(self._line_px())
            self._bar.setRange(0.0, maximum)
        self._target = min(max(self._target, 0.0), maximum)
        return geometry

    def _on_bar_value(self, value):
        if self._animation is None or self._animation.state() != "running":
            self._target = value
        self._invalidate()

    def _scroll_to_value(self, value, animated=True):
        from .animation import PropertyAnimation, animations_enabled

        self._update_range()
        value = min(max(float(value), 0.0), self._bar.maximum())
        self._target = value
        if self._animation is not None:
            self._animation.stop()
            self._animation = None
        if not animated or not animations_enabled() or \
                value == self._bar.value():
            self._bar.setValue(value)
            return
        self._animation = PropertyAnimation(
            self, "scrollValue", duration_ms=self.SCROLL_MS,
            easing="outCubic", end_value=value)
        self._animation.start()

    def ensureCursorVisible(self):
        geometry = self._update_range()
        row = self._line_of(self._buffer.caret)
        line = self._line_px()
        top, bottom = row * line, (row + 1) * line
        value = self._target
        if top < value:
            value = top
        elif bottom > value + geometry["view_h"]:
            value = bottom - geometry["view_h"]
        if value != self._target:
            self._scroll_to_value(value, animated=False)

    # -- input --------------------------------------------------------------------------------
    def _hit(self, event):
        """``(row, x)`` of a pointer event in text coordinates."""
        geometry = self._geometry()
        rx, ry, _rw, rh = geometry["rows"]
        ox, oy = geometry["origin"]
        gx, gy = event.globalPos()
        pad, scale = geometry["pad"], geometry["scale"]
        from_top = (ry + oy + rh - pad - gy) / scale + self._bar.value()
        row = int(from_top // self._line_px()) if from_top >= 0 else -1
        lines = len(self._visual_lines())
        if row >= lines:
            return lines - 1, float("inf")
        if row < 0:
            return 0, -1.0
        return row, gx - (rx + ox + pad)

    def mousePressEvent(self, event):
        if event.button() != "left" or not self._available:
            event.ignore()
            return
        event.accept()
        self.setFocus(reason="mouse")
        row, x = self._hit(event)
        position = self._position_at(row, x)
        count, last_time, last_pos = self._clicks
        now = self._now()
        count = count + 1 if now - last_time <= self.MULTI_CLICK_MS and \
            last_pos == position else 1
        self._clicks = (count, now, position)
        buffer = self._buffer
        if count == 2:
            buffer.selectWordAt(position)
        elif count >= 3:
            start, end = self._paragraph(position)
            buffer.select(start, end)
        else:
            buffer.move(position, select=SHIFT in event.modifiers())
        self._drag = count == 1
        self._goal_x = None
        self._caret_moved(scroll=False)

    def mouseDoubleClickEvent(self, event):
        self.mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if not self._drag:
            event.ignore()
            return
        event.accept()
        row, x = self._hit(event)
        self._buffer.move(self._position_at(row, x), select=True)
        self._caret_moved()

    def mouseReleaseEvent(self, event):
        if not self._drag:
            event.ignore()
            return
        event.accept()
        self._drag = False

    def wheelEvent(self, event):
        self._update_range()
        if self._bar.maximum() <= 0:
            event.ignore()
            return
        event.accept()
        self._scroll_to_value(self._target - event.delta() * self.WHEEL_STEP_PX)

    def _now(self):
        import time

        from .timer import VirtualClock

        clock = VirtualClock.for_interactor(self.interactor)
        return clock.now() if clock is not None else time.monotonic() * 1000.0

    def _paragraph(self, position):
        text = self._buffer.text
        start = text.rfind("\n", 0, position) + 1
        end = text.find("\n", position)
        return start, len(text) if end < 0 else end

    def focusKeyIntercept(self, key):
        """Enter inserts a newline (and Tab spaces, if Tab does not change
        focus) instead of the FocusManager acting on them."""
        if self._read_only or not self._available:
            return False
        if key in ("return", "enter", "kp_enter"):
            self.insertPlainText("\n")
            return True
        if key == "tab" and not self._tab_changes_focus:
            self.insertPlainText(" " * self.TAB_SPACES)
            return True
        return False

    def keyPressEvent(self, event):
        key = event.key().lower()
        modifiers = event.modifiers()
        ctrl, shift = CTRL in modifiers, SHIFT in modifiers
        word = ctrl or ALT in modifiers
        buffer = self._buffer
        editable = not self._read_only and self._available
        moved = changed = False
        if key in ("left", "right"):
            (buffer.left if key == "left" else buffer.right)(select=shift,
                                                             word=word)
            self._goal_x = None
            moved = True
        elif key in ("up", "down", "prior", "next"):
            self._move_rows(key, shift)
            moved = True
        elif key in ("home", "end"):
            if ctrl:
                buffer.move(0 if key == "home" else len(buffer.text),
                            select=shift)
            else:
                start, end = self._visual_lines()[self._line_of(buffer.caret)]
                if key == "end" and end > start and \
                        buffer.text[end - 1:end] == " " and \
                        end < len(buffer.text) and \
                        buffer.text[end] != "\n":
                    end -= 1              # stay on a soft-wrapped line
                buffer.move(start if key == "home" else end, select=shift)
            self._goal_x = None
            moved = True
        elif ctrl and key == "a":
            self.selectAll()
            event.accept()
            return
        elif ctrl and key == "c":
            self.copy()
            event.accept()
            return
        elif ctrl and key == "x" and editable:
            self.cut()
            event.accept()
            return
        elif ctrl and key == "v" and editable:
            self.paste()
            event.accept()
            return
        elif ctrl and key == "z" and not shift and editable:
            self.undo()
            event.accept()
            return
        elif ctrl and (key == "y" or (key == "z" and shift)) and editable:
            self.redo()
            event.accept()
            return
        elif ctrl:
            event.ignore()                # leave Ctrl+S etc. to shortcuts
            return
        elif key == "backspace" and editable:
            changed = buffer.backspace(word=word)
        elif key == "delete" and editable:
            changed = buffer.delete(word=word)
        elif editable and event.text():
            changed = buffer.insert(event.text())
        else:
            event.ignore()
            return
        event.accept()
        if changed:
            self._trim_blocks()
            self._text_changed()
        elif moved:
            self._caret_moved()

    def _move_rows(self, key, select):
        buffer = self._buffer
        lines = self._visual_lines()
        row = self._line_of(buffer.caret)
        if self._goal_x is None:
            self._goal_x = self._x_of(buffer.caret)
        page = max(1, int(self._geometry()["view_h"] // self._line_px()) - 1)
        step = {"up": -1, "down": 1, "prior": -page, "next": page}[key]
        target = row + step
        if target < 0:
            position = 0
        elif target >= len(lines):
            position = len(buffer.text)
        else:
            position = self._position_at(target, self._goal_x)
        buffer.move(position, select=select)
        if key in ("prior", "next"):
            self._scroll_to_value(self._target + step * self._line_px())

    def focusInEvent(self, reason="other"):
        super().focusInEvent(reason)
        self._invalidate()

    def focusOutEvent(self, reason="other"):
        super().focusOutEvent(reason)
        self._invalidate()

    # -- drawing ----------------------------------------------------------------------------------
    def tokens(self):
        theme = getattr(self.renderer, "theme", None)
        tokens = getattr(theme, "tokens", None)
        return tokens if tokens else _DEFAULT_TOKENS

    def _color(self, role, part, states=()):
        states = set(states)
        if not self._available:
            states.add("disabled")
        return Style.for_renderer(self.renderer).color(role, part, states,
                                                       widget=self)

    def _invalidate(self, relayout=False):
        if relayout:
            self._lines = None
        self._dirty = True
        self.requestRender()

    def _before_render(self, *_args):
        if self._dirty:
            self.doLayout()

    def doLayout(self):
        """Sync every actor now (normally done once before a frame)."""
        self._dirty = False
        x, y, width, height = self.rect()
        if not self._shown or width <= 2 or height <= 2:
            self._content.SetDraw(False)
            self._bar.SetVisibility(False)
            for prop in (self._frame_actor, self._selection_actor,
                         self._caret_actor):
                prop.SetVisibility(False)
            for cell in self._cells:
                cell.hide()
            if self._placeholder_cell is not None:
                self._placeholder_cell.hide()
            self._frame_key = self._shape_key = None
            self.requestRender()
            return
        geometry = self._update_range()
        ax, ay, aw, ah = self.geometry("px")
        self._bar.setGeometry(px(ax + aw - 1 - self.BAR_PX), px(ay + 1),
                              px(self.BAR_PX), px(max(0.0, ah - 2)))
        self._bar.SetVisibility(geometry["bar"])
        window = self.interactor.GetRenderWindow()
        win_w, win_h = (max(1, v) for v in window.GetSize())
        rx, ry, rw, rh = geometry["rows"]
        ox, oy = geometry["origin"]
        self._content.SetDraw(rw > 0 and rh > 0)
        self._content.SetViewport((rx + ox) / win_w, (ry + oy) / win_h,
                                  (rx + ox + rw) / win_w,
                                  (ry + oy + rh) / win_h)
        self._paint_frame(geometry)
        self._paint_text(geometry, rw, rh)
        self.requestRender()

    def _paint_frame(self, geometry):
        x, y, width, height = geometry["rect"]
        border = self._color("field", "border",
                             ("focus",) if self.hasFocus() else ())
        fill = self._color("field", "background")
        key = (geometry["rect"], border, fill)
        if key == self._frame_key:
            return
        self._frame_key = key
        radius = 4 * geometry["scale"]
        self._frame_actor.GetMapper().SetInputData(_merge([
            rounded_rect_polydata(x, y, width, height, [radius] * 4,
                                  _rgba(border)),
            rounded_rect_polydata(x + 1, y + 1, width - 2, height - 2,
                                  [radius - 1] * 4, _rgba(fill))]))
        self._frame_actor.SetVisibility(True)

    def _paint_text(self, geometry, rows_w, rows_h):
        scale, pad = geometry["scale"], geometry["pad"]
        lines = self._visual_lines(rows_w - 2 * pad)
        line_h = self._line_px() * scale
        scroll = self._bar.value() * scale
        size = self._font_size()
        text = self._buffer.text
        top_edge = rows_h - pad
        first = max(0, int(scroll // line_h))
        last = min(len(lines) - 1, int((scroll + rows_h) // line_h) + 1)
        color = self._color("text", "text")
        # Placeholder while empty and unfocused.
        if not text and self._placeholder and not self.hasFocus():
            if self._placeholder_cell is None:
                self._placeholder_cell = _TextCell(self._content)
            self._placeholder_cell.show(
                self._placeholder, pad, top_edge - line_h / 2,
                self._color("muted", "text"), size)
        elif self._placeholder_cell is not None:
            self._placeholder_cell.hide()
        used = 0
        for row in range(first, last + 1):
            start, end = lines[row]
            centre = top_edge - (row * line_h - scroll) - line_h / 2
            while len(self._cells) <= used:
                self._cells.append(self._new_cell())
            content = text[start:end].replace("\t", " " * self.TAB_SPACES)
            self._cells[used].show(content.rstrip("\n"), pad, centre, color,
                                   size)
            used += 1
        for cell in self._cells[used:]:
            cell.hide()
        # Selection rectangles and the caret.
        buffer = self._buffer
        selection = []
        sel_start, sel_end = buffer.selection()
        focused = self.hasFocus()
        highlight = self._color("item", "background",
                                ("selected", "focus") if focused
                                else ("selected",))
        if sel_start != sel_end:
            for row in range(first, last + 1):
                start, end = lines[row]
                lo, hi = max(start, sel_start), min(end, sel_end)
                newline = sel_end > end and end < len(text) and \
                    text[end:end + 1] == "\n"
                if lo > hi or (lo == hi and not newline):
                    continue
                x0 = self._width(text[start:lo])
                x1 = self._width(text[start:hi]) + \
                    (self._width(" ") if newline else 0)
                bottom = top_edge - (row * line_h - scroll) - line_h
                selection.append((pad + x0, bottom, x1 - x0, line_h))
        key = (tuple(selection), highlight)
        if key != self._shape_key:
            self._shape_key = key
            if selection:
                self._selection_actor.GetMapper().SetInputData(_merge(
                    [_quad(*rect, _rgba(highlight)) for rect in selection]))
                self._selection_actor.SetVisibility(True)
            else:
                self._selection_actor.SetVisibility(False)
        show_caret = focused and not self._read_only and self._available
        if show_caret:
            row = self._line_of(buffer.caret)
            x = pad + self._x_of(buffer.caret)
            top = top_edge - (row * line_h - scroll)
            inset = line_h * 0.15
            self._caret_actor.GetMapper().SetInputData(_polyline(
                [(x, top - inset), (x, top - line_h + inset)],
                _rgba(color)))
        self._caret_actor.SetVisibility(show_caret)

    # -- teardown -------------------------------------------------------------------------------
    def close(self):
        if self._animation is not None:
            self._animation.stop()
        remove_actor_2d(ui_layer(self.renderer), self._frame_actor)
        for cell in self._cells:
            cell.remove(self._content)
        self._cells = []
        window = self.interactor.GetRenderWindow()
        if window is not None:
            window.RemoveRenderer(self._content)
        self._bar.close()
        return super().close()
