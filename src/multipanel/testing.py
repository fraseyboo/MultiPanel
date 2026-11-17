"""Headless event simulation for widget tests (the ``QTest`` equivalent).

``UiHarness`` creates an off-screen renderer, render window and interactor,
installs a :class:`~multipanel.timer.VirtualClock`, and injects mouse, wheel
and keyboard events through ``SetEventInformation`` + ``InvokeEvent``.
Observers, priorities and abort flags therefore behave as in a running
application, but nothing depends on a real event loop or wall-clock time::

    from multipanel.testing import UiHarness

    with UiHarness(size=(800, 600)) as ui:
        button = VectorButtonWidget(ui.renderer, ui.interactor, ...)
        ui.click(button)
        ui.key_clicks("hello")
        ui.process_events(500)      # advance the virtual clock by 500 ms

Targets may be a widget (its centre is used, from ``geometry("display")``)
or an ``(x, y)`` tuple in display pixels.

Note that VTK's default interactor style calls ``GrabFocus`` on a button
press, after which only the style and passive observers receive events until
the release.  This matches a running application.  Pass
``interactor_style=None`` to observe raw interactor events without a style.
"""
from __future__ import annotations

import vtk

from .timer import VirtualClock

__all__ = ["UiHarness", "keysym_for_char"]

_BUTTON_EVENTS = {
    "left": ("LeftButtonPressEvent", "LeftButtonReleaseEvent"),
    "middle": ("MiddleButtonPressEvent", "MiddleButtonReleaseEvent"),
    "right": ("RightButtonPressEvent", "RightButtonReleaseEvent"),
}

# Key symbols VTK reports for printable characters that are not their own name.
_CHAR_KEYSYMS = {
    " ": "space", "!": "exclam", '"': "quotedbl", "#": "numbersign",
    "$": "dollar", "%": "percent", "&": "ampersand", "'": "apostrophe",
    "(": "parenleft", ")": "parenright", "*": "asterisk", "+": "plus",
    ",": "comma", "-": "minus", ".": "period", "/": "slash", ":": "colon",
    ";": "semicolon", "<": "less", "=": "equal", ">": "greater",
    "?": "question", "@": "at", "[": "bracketleft", "\\": "backslash",
    "]": "bracketright", "^": "asciicircum", "_": "underscore",
    "`": "grave", "{": "braceleft", "|": "bar", "}": "braceright",
    "~": "asciitilde",
}

# Key codes VTK reports alongside special key symbols.
_SPECIAL_KEYCODES = {
    "Return": "\r", "KP_Enter": "\r", "Tab": "\t", "BackSpace": "\b",
    "Escape": "\x1b", "Delete": "\x7f", "space": " ",
}


def keysym_for_char(char):
    """Return the VTK key symbol produced by typing ``char``."""
    if len(char) != 1:
        raise ValueError("expected a single character")
    return _CHAR_KEYSYMS.get(char, char)


class UiHarness:
    """Off-screen VTK window plus synthetic input and a virtual clock."""

    _DEFAULT_STYLE = object()

    def __init__(self, size=(800, 600), *, renderer=None, interactor=None,
                 offscreen=True, virtual_clock=True,
                 interactor_style=_DEFAULT_STYLE):
        if interactor is None:
            window = vtk.vtkRenderWindow()
            window.SetOffScreenRendering(bool(offscreen))
            window.SetSize(int(size[0]), int(size[1]))
            interactor = vtk.vtkRenderWindowInteractor()
            interactor.SetRenderWindow(window)
        else:
            window = interactor.GetRenderWindow()
        if interactor_style is not UiHarness._DEFAULT_STYLE:
            interactor.SetInteractorStyle(interactor_style)
        if renderer is None:
            renderer = vtk.vtkRenderer()
            window.AddRenderer(renderer)
        self.renderer = renderer
        self.window = window
        self.interactor = interactor
        self.clock = (VirtualClock.install(interactor)
                      if virtual_clock else None)
        self._buttons = set()
        self._last_pos = (0, 0)

    # -- lifecycle -----------------------------------------------------------
    def close(self):
        if self.clock is not None:
            VirtualClock.uninstall(self.interactor)
            self.clock = None
        self.window.Finalize()

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        self.close()

    def render(self):
        self.window.Render()

    # -- time ------------------------------------------------------------------
    def process_events(self, ms=0):
        """Advance the virtual clock by ``ms``, running due timers and renders.

        Returns the number of callbacks run.
        """
        if self.clock is None:
            raise RuntimeError("process_events requires virtual_clock=True")
        return self.clock.advance(ms)

    advance = process_events

    # -- positions ---------------------------------------------------------------
    def point_of(self, target, anchor=(0.5, 0.5)):
        """Return the display-pixel point for ``target``.

        ``anchor`` is relative to the widget's geometry: ``(0.5, 0.5)`` is
        the centre, ``(0, 0)`` the lower-left corner.
        """
        if isinstance(target, (tuple, list)) and len(target) == 2:
            return (int(round(target[0])), int(round(target[1])))
        geometry = target.geometry("display")
        if geometry is None:
            raise ValueError(f"{type(target).__name__} has no geometry")
        x, y, width, height = geometry
        return (int(round(x + anchor[0] * width)),
                int(round(y + anchor[1] * height)))

    # -- low-level injection ----------------------------------------------------
    def _set_info(self, pos, *, ctrl=False, shift=False, alt=False,
                  keycode="\0", repeat=0, keysym=None):
        x, y = pos
        self.interactor.SetEventInformation(
            int(x), int(y), int(bool(ctrl)), int(bool(shift)),
            keycode, int(repeat), keysym)
        self.interactor.SetAltKey(int(bool(alt)))

    def _invoke(self, event):
        self.interactor.InvokeEvent(event)

    # -- mouse -----------------------------------------------------------------
    def move(self, target, *, ctrl=False, shift=False, alt=False):
        pos = self.point_of(target)
        self._set_info(pos, ctrl=ctrl, shift=shift, alt=alt)
        self._invoke("MouseMoveEvent")
        self._last_pos = pos
        return pos

    def press(self, target, button="left", *, ctrl=False, shift=False,
              alt=False, repeat=0):
        pos = self.point_of(target)
        if pos != self._last_pos:
            self.move(pos, ctrl=ctrl, shift=shift, alt=alt)
        self._set_info(pos, ctrl=ctrl, shift=shift, alt=alt, repeat=repeat)
        self._invoke(_BUTTON_EVENTS[button][0])
        self._buttons.add(button)
        return pos

    def release(self, target=None, button="left", *, ctrl=False,
                shift=False, alt=False):
        pos = self._last_pos if target is None else self.point_of(target)
        if pos != self._last_pos:
            self.move(pos, ctrl=ctrl, shift=shift, alt=alt)
        self._set_info(pos, ctrl=ctrl, shift=shift, alt=alt)
        self._invoke(_BUTTON_EVENTS[button][1])
        self._buttons.discard(button)
        return pos

    def click(self, target, button="left", **modifiers):
        pos = self.press(target, button, **modifiers)
        self.release(pos, button, **modifiers)
        return pos

    def double_click(self, target, button="left", interval_ms=50,
                     **modifiers):
        pos = self.click(target, button, **modifiers)
        if self.clock is not None:
            self.process_events(interval_ms)
        self.press(pos, button, repeat=1, **modifiers)
        self.release(pos, button, **modifiers)
        return pos

    def drag(self, start, end, button="left", steps=8, **modifiers):
        """Press at ``start``, move in ``steps`` increments, release at ``end``."""
        x0, y0 = self.press(start, button, **modifiers)
        x1, y1 = self.point_of(end)
        steps = max(1, int(steps))
        for step in range(1, steps + 1):
            t = step / steps
            self.move((x0 + (x1 - x0) * t, y0 + (y1 - y0) * t), **modifiers)
        self.release((x1, y1), button, **modifiers)
        return (x1, y1)

    def wheel(self, target, steps=1, **modifiers):
        """Scroll ``steps`` notches; positive is forward (away from the user)."""
        pos = self.point_of(target)
        if pos != self._last_pos:
            self.move(pos, **modifiers)
        event = ("MouseWheelForwardEvent" if steps > 0
                 else "MouseWheelBackwardEvent")
        for _step in range(abs(int(steps))):
            self._set_info(pos, **modifiers)
            self._invoke(event)
        return pos

    # -- keyboard --------------------------------------------------------------
    def key(self, keysym, text=None, *, ctrl=False, shift=False, alt=False):
        """Send KeyPress, Char (when the key produces text) and KeyRelease.

        ``keysym`` is a VTK key symbol (``"Return"``, ``"Left"``, ``"a"``).
        A single printable character is also accepted and translated.
        """
        if text is None and len(keysym) == 1:
            text = keysym
            keysym = keysym_for_char(keysym)
        keycode = text if text else _SPECIAL_KEYCODES.get(keysym, "\0")
        info = dict(ctrl=ctrl, shift=shift, alt=alt, keycode=keycode,
                    keysym=keysym)
        self._set_info(self._last_pos, **info)
        self._invoke("KeyPressEvent")
        if keycode != "\0":
            self._set_info(self._last_pos, **info)
            self._invoke("CharEvent")
        self._set_info(self._last_pos, **info)
        self._invoke("KeyReleaseEvent")

    def key_clicks(self, text, **modifiers):
        """Type ``text`` one character at a time."""
        for char in text:
            shift = modifiers.get("shift", False) or (
                char.isalpha() and char.isupper())
            self.key(keysym_for_char(char), char,
                     **{**modifiers, "shift": shift})
