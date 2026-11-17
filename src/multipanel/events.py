"""Qt-style event objects delivered by :class:`multipanel.router.EventRouter`.

Events start *ignored*.  A handler calls :meth:`Event.accept` to consume the
event; an ignored event propagates to the receiver's parent and finally to
the 3D scene (the interactor style).
"""
from __future__ import annotations

__all__ = [
    "ALT",
    "CTRL",
    "SHIFT",
    "ContextMenuEvent",
    "Event",
    "HoverEvent",
    "KeyEvent",
    "MouseEvent",
    "WheelEvent",
]

CTRL = "ctrl"
SHIFT = "shift"
ALT = "alt"


def modifiers_from_interactor(interactor):
    """Return the frozenset of modifier names currently held."""
    held = set()
    if interactor.GetControlKey():
        held.add(CTRL)
    if interactor.GetShiftKey():
        held.add(SHIFT)
    if interactor.GetAltKey():
        held.add(ALT)
    return frozenset(held)


class Event:
    """Base class: an event type name plus accept/ignore state."""

    __slots__ = ("_type", "_accepted", "_spontaneous")

    def __init__(self, event_type):
        self._type = event_type
        self._accepted = False
        self._spontaneous = True

    def type(self):
        return self._type

    def accept(self):
        self._accepted = True

    def ignore(self):
        self._accepted = False

    def isAccepted(self):
        return self._accepted

    def setAccepted(self, accepted):
        self._accepted = bool(accepted)

    def spontaneous(self):
        """True when the event came from the interactor, not from code."""
        return self._spontaneous

    def __repr__(self):
        state = "accepted" if self._accepted else "ignored"
        return f"<{type(self).__name__} {self._type} {state}>"


class _PointerEvent(Event):
    """Common position handling for mouse, wheel, hover and context events.

    ``globalPos()`` is in display pixels (``GetEventPosition`` coordinates).
    ``pos()`` is in logical pixels relative to the lower-left corner of the
    widget currently receiving the event; it is updated as the event bubbles.
    """

    __slots__ = ("_global", "_local", "_modifiers")

    def __init__(self, event_type, global_pos, modifiers=frozenset()):
        super().__init__(event_type)
        self._global = (float(global_pos[0]), float(global_pos[1]))
        self._local = self._global
        self._modifiers = frozenset(modifiers)

    def globalPos(self):
        return self._global

    def pos(self):
        return self._local

    def x(self):
        return self._local[0]

    def y(self):
        return self._local[1]

    def modifiers(self):
        return self._modifiers

    def _set_local(self, local):
        self._local = (float(local[0]), float(local[1]))


class MouseEvent(_PointerEvent):
    """Press, release, move or double-click.

    ``button()`` is the button that changed (``None`` for moves);
    ``buttons()`` is the set held after the event.
    """

    __slots__ = ("_button", "_buttons")

    PRESS = "MouseButtonPress"
    RELEASE = "MouseButtonRelease"
    MOVE = "MouseMove"
    DOUBLE_CLICK = "MouseButtonDblClick"

    def __init__(self, event_type, global_pos, button=None,
                 buttons=frozenset(), modifiers=frozenset()):
        super().__init__(event_type, global_pos, modifiers)
        self._button = button
        self._buttons = frozenset(buttons)

    def button(self):
        return self._button

    def buttons(self):
        return self._buttons


class WheelEvent(_PointerEvent):
    """Wheel notches: ``delta()`` is +1 per forward notch, -1 per backward."""

    __slots__ = ("_delta",)

    TYPE = "Wheel"

    def __init__(self, global_pos, delta, modifiers=frozenset()):
        super().__init__(self.TYPE, global_pos, modifiers)
        self._delta = int(delta)

    def delta(self):
        return self._delta


class HoverEvent(_PointerEvent):
    """Sent as ``Enter`` or ``Leave`` when the pointer crosses a widget edge."""

    __slots__ = ()

    ENTER = "Enter"
    LEAVE = "Leave"


class ContextMenuEvent(_PointerEvent):
    """Right-button click (release without a drag) requesting a context menu."""

    __slots__ = ()

    TYPE = "ContextMenu"

    def __init__(self, global_pos, modifiers=frozenset()):
        super().__init__(self.TYPE, global_pos, modifiers)


class KeyEvent(Event):
    """Key press or release.

    ``key()`` is the VTK key symbol (``"Return"``, ``"a"``, ``"Left"``);
    ``text()`` is the character produced, or ``""``.
    """

    __slots__ = ("_key", "_text", "_modifiers", "_auto_repeat")

    PRESS = "KeyPress"
    RELEASE = "KeyRelease"

    def __init__(self, event_type, key, text="", modifiers=frozenset(),
                 auto_repeat=False):
        super().__init__(event_type)
        self._key = key or ""
        self._text = text or ""
        self._modifiers = frozenset(modifiers)
        self._auto_repeat = bool(auto_repeat)

    def key(self):
        return self._key

    def text(self):
        return self._text

    def modifiers(self):
        return self._modifiers

    def isAutoRepeat(self):
        return self._auto_repeat
