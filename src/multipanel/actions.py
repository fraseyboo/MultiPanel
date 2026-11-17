"""Actions and keyboard shortcuts (``docs/QT_PARITY_PROPOSAL.md`` §8).

::

    from multipanel.actions import Action

    save = Action("Save scene", shortcut="Ctrl+S", interactor=interactor,
                  status_tip="Save the current scene")
    save.triggered.connect(save_scene)
    save.setEnabled(False)          # bound buttons grey out, shortcut idles
    button.setAction(save)          # VectorButtonWidget

Shortcuts are dispatched by the interactor's
:class:`~multipanel.router.EventRouter` after the focused widget has had the
key. While a text field is editing, keys that edit text (plain characters,
Backspace/Delete, arrows, Home/End, and Ctrl with A/C/V/X/Y/Z) go to the
field instead of firing shortcuts, so typing never triggers scene commands.
When two enabled shortcuts match the same key, neither fires and each emits
``activatedAmbiguously``.
"""
from __future__ import annotations

import weakref

from .core import Signal

__all__ = ["Action", "ActionGroup", "KeySequence", "Shortcut", "ShortcutMap"]

_MODIFIERS = {"ctrl": "ctrl", "control": "ctrl", "shift": "shift",
              "alt": "alt", "option": "alt"}
_KEY_ALIASES = {
    "del": "Delete", "delete": "Delete", "esc": "Escape",
    "escape": "Escape", "enter": "Return", "return": "Return",
    "backspace": "BackSpace", "space": "space", "tab": "Tab",
    "home": "Home", "end": "End", "left": "Left", "right": "Right",
    "up": "Up", "down": "Down", "pageup": "Prior", "pgup": "Prior",
    "pagedown": "Next", "pgdown": "Next", "ins": "Insert",
    "insert": "Insert", "plus": "plus", "minus": "minus",
}
# Keys a focused text field consumes before any shortcut sees them.
_TEXT_EDIT_KEYS = {"backspace", "delete", "left", "right", "up", "down",
                   "home", "end", "return", "kp_enter", "tab", "space",
                   "escape"}              # Escape cancels the edit
_TEXT_EDIT_CTRL = {"a", "c", "v", "x", "y", "z"}


class KeySequence:
    """One key chord such as ``Ctrl+Shift+S`` (no multi-chord sequences)."""

    __slots__ = ("key", "modifiers")

    def __init__(self, key, modifiers=frozenset()):
        self.key = key
        self.modifiers = frozenset(modifiers)

    @classmethod
    def parse(cls, text):
        if isinstance(text, KeySequence):
            return text
        parts = [part.strip() for part in str(text).replace("++", "+plus")
                 .split("+") if part.strip()]
        if not parts:
            raise ValueError(f"empty key sequence {text!r}")
        modifiers = set()
        for part in parts[:-1]:
            name = _MODIFIERS.get(part.lower())
            if name is None:
                raise ValueError(f"unknown modifier {part!r} in {text!r}")
            modifiers.add(name)
        key = parts[-1]
        lowered = key.lower()
        if lowered in _KEY_ALIASES:
            key = _KEY_ALIASES[lowered]
        elif len(key) == 1:
            key = key.lower()
        elif lowered.startswith("f") and lowered[1:].isdigit():
            key = "F" + lowered[1:]
        return cls(key, modifiers)

    def matches(self, keysym, modifiers):
        """True for VTK key symbol ``keysym`` with ``modifiers`` held."""
        if not keysym:
            return False
        if frozenset(modifiers) != self.modifiers:
            return False
        return keysym.lower() == self.key.lower()

    def isTextEditingKey(self):
        """Would a focused text field consume this chord?"""
        key = self.key.lower()
        if not self.modifiers or self.modifiers == {"shift"}:
            return len(key) == 1 or key in _TEXT_EDIT_KEYS
        if self.modifiers == {"ctrl"} or self.modifiers == {"ctrl", "shift"}:
            return key in _TEXT_EDIT_CTRL
        return False

    def toString(self):
        order = [name for name in ("ctrl", "alt", "shift")
                 if name in self.modifiers]
        names = [name.title() for name in order]
        key = self.key.upper() if len(self.key) == 1 else self.key
        return "+".join(names + [key])

    def __eq__(self, other):
        other = KeySequence.parse(other) if isinstance(other, str) else other
        return (isinstance(other, KeySequence) and
                self.key.lower() == other.key.lower() and
                self.modifiers == other.modifiers)

    def __hash__(self):
        return hash((self.key.lower(), self.modifiers))

    def __repr__(self):
        return f"KeySequence({self.toString()!r})"


class ShortcutMap:
    """Shortcuts registered on one interactor.

    The map owns its shortcuts (like a ``QShortcut``'s parent), so a
    shortcut created without keeping a reference keeps working until
    ``release()`` or its parent widget is destroyed.
    """

    _instances = weakref.WeakKeyDictionary()

    def __init__(self):
        self._shortcuts = []

    @classmethod
    def for_interactor(cls, interactor):
        mapping = cls._instances.get(interactor)
        if mapping is None:
            mapping = cls()
            cls._instances[interactor] = mapping
        return mapping

    @classmethod
    def existing(cls, interactor):
        return cls._instances.get(interactor)

    def add(self, shortcut):
        if shortcut not in self._shortcuts:
            self._shortcuts.append(shortcut)

    def remove(self, shortcut):
        if shortcut in self._shortcuts:
            self._shortcuts.remove(shortcut)

    def shortcuts(self):
        return list(self._shortcuts)

    def dispatch(self, keysym, modifiers, focus_widget=None,
                 text_input_active=False):
        """Activate the shortcut for this key; return True if one claimed it."""
        candidates = [shortcut for shortcut in self.shortcuts()
                      if shortcut.isEnabled()
                      and shortcut.key().matches(keysym, modifiers)
                      and shortcut._context_active(focus_widget)]
        if text_input_active:
            candidates = [shortcut for shortcut in candidates
                          if not shortcut.key().isTextEditingKey()]
        if not candidates:
            return False
        if len(candidates) > 1:
            for shortcut in candidates:
                shortcut.activatedAmbiguously.emit()
            return True
        candidates[0].activated.emit()
        return True


class Shortcut:
    """A key chord that emits ``activated``, like ``QShortcut``.

    ``context`` is ``"application"`` (any time; also ``"window"``),
    ``"widget"`` (while ``parent`` has focus) or ``"widgetWithChildren"``
    (while focus is in ``parent``'s subtree). Application shortcuts with a
    ``parent`` only fire while the parent is visible.
    """

    CONTEXTS = ("application", "window", "widget", "widgetWithChildren")

    def __init__(self, key, interactor, context="application", parent=None,
                 enabled=True):
        if context not in self.CONTEXTS:
            raise ValueError(f"unknown shortcut context {context!r}")
        self.activated = Signal()
        self.activatedAmbiguously = Signal()
        self._key = KeySequence.parse(key)
        self._context = context
        self._parent_ref = None if parent is None else weakref.ref(parent)
        self._enabled = bool(enabled)
        self._interactor_ref = weakref.ref(interactor)
        ShortcutMap.for_interactor(interactor).add(self)
        destroyed = getattr(parent, "destroyed", None)
        if destroyed is not None:
            destroyed.connect(lambda *_: self.release())
        from .router import EventRouter

        EventRouter.install(interactor)

    def key(self):
        return self._key

    def setKey(self, key):
        self._key = KeySequence.parse(key)

    def context(self):
        return self._context

    def isEnabled(self):
        return self._enabled

    def setEnabled(self, enabled):
        self._enabled = bool(enabled)

    def parentWidget(self):
        return None if self._parent_ref is None else self._parent_ref()

    def _context_active(self, focus_widget):
        parent = self.parentWidget()
        if self._context in ("application", "window"):
            if parent is None:
                return True
            visible = getattr(parent, "isVisible", None)
            return bool(visible()) if callable(visible) else True
        if parent is None or focus_widget is None:
            return False
        if self._context == "widget":
            return focus_widget is parent
        widget = focus_widget
        while widget is not None:
            if widget is parent:
                return True
            parent_of = getattr(widget, "parentWidget", None)
            widget = parent_of() if callable(parent_of) else None
        return False

    def release(self):
        """Stop listening; also happens when the parent widget is destroyed."""
        interactor = self._interactor_ref()
        if interactor is not None:
            ShortcutMap.for_interactor(interactor).remove(self)


class Action:
    """A user command shared by buttons, menus and shortcuts (``QAction``)."""

    def __init__(self, text="", interactor=None, shortcut=None,
                 shortcut_context="application", icon=None, tool_tip="",
                 status_tip="", checkable=False, checked=False, enabled=True,
                 visible=True, data=None, parent=None):
        self.triggered = Signal()
        self.toggled = Signal()
        self.changed = Signal()
        self.hovered = Signal()
        self._text = str(text)
        self._icon = icon
        self._tool_tip = str(tool_tip)
        self._status_tip = str(status_tip)
        self._checkable = bool(checkable)
        self._checked = bool(checked) and self._checkable
        self._enabled = bool(enabled)
        self._visible = bool(visible)
        self._data = data
        self._group_ref = None
        self._shortcut = None
        self._shortcut_context = shortcut_context
        self._parent_ref = None if parent is None else weakref.ref(parent)
        self._interactor_ref = (None if interactor is None
                                else weakref.ref(interactor))
        if shortcut is not None:
            self.setShortcut(shortcut)

    # -- properties ---------------------------------------------------------
    def _set(self, name, value):
        if getattr(self, name) != value:
            setattr(self, name, value)
            self._sync_shortcut()
            self.changed.emit()

    def text(self):
        return self._text

    def setText(self, text):
        self._set("_text", str(text))

    def icon(self):
        return self._icon

    def setIcon(self, icon):
        self._set("_icon", icon)

    def toolTip(self):
        """Tool tip, defaulting to the text plus its shortcut."""
        if self._tool_tip:
            return self._tool_tip
        shortcut = self.shortcut()
        suffix = f" ({shortcut.toString()})" if shortcut is not None else ""
        return f"{self._text}{suffix}"

    def setToolTip(self, tip):
        self._set("_tool_tip", str(tip))

    def statusTip(self):
        return self._status_tip

    def setStatusTip(self, tip):
        self._set("_status_tip", str(tip))

    def isCheckable(self):
        return self._checkable

    def setCheckable(self, checkable):
        self._set("_checkable", bool(checkable))
        if not self._checkable and self._checked:
            self._checked = False

    def isChecked(self):
        return self._checked

    def setChecked(self, checked):
        checked = bool(checked) and self._checkable
        if checked == self._checked:
            return
        group = self.actionGroup()
        if group is not None and group.isExclusive():
            if not checked and group.checkedAction() is self:
                return                  # an exclusive group keeps one checked
            if checked:
                for other in group.actions():
                    if other is not self and other.isChecked():
                        other._checked = False
                        other.toggled.emit(False)
                        other.changed.emit()
        self._checked = checked
        self.toggled.emit(checked)
        self.changed.emit()

    def isEnabled(self):
        group = self.actionGroup()
        return self._enabled and (group is None or group.isEnabled())

    def setEnabled(self, enabled):
        self._set("_enabled", bool(enabled))

    def isVisible(self):
        return self._visible

    def setVisible(self, visible):
        self._set("_visible", bool(visible))

    def data(self):
        return self._data

    def setData(self, data):
        self._data = data

    def actionGroup(self):
        return None if self._group_ref is None else self._group_ref()

    def setActionGroup(self, group):
        old = self.actionGroup()
        if old is not None and old is not group:
            old.removeAction(self)
        if group is not None:
            group.addAction(self)

    # -- shortcut ----------------------------------------------------------------
    def shortcut(self):
        return None if self._shortcut is None else self._shortcut.key()

    def setShortcut(self, key, interactor=None):
        """Bind a shortcut; needs the interactor (here or at construction)."""
        if interactor is not None:
            self._interactor_ref = weakref.ref(interactor)
        if self._shortcut is not None:
            self._shortcut.release()
            self._shortcut = None
        if key is not None:
            target = (None if self._interactor_ref is None
                      else self._interactor_ref())
            if target is None:
                raise ValueError("Action.setShortcut needs an interactor")
            parent = None if self._parent_ref is None else self._parent_ref()
            self._shortcut = Shortcut(key, target, self._shortcut_context,
                                      parent)
            self._shortcut.activated.connect(self._on_shortcut)
            self._sync_shortcut()
        self.changed.emit()

    def _sync_shortcut(self):
        if self._shortcut is not None:
            self._shortcut.setEnabled(self.isEnabled() and self._visible)

    def _on_shortcut(self):
        self.trigger()

    # -- activation ---------------------------------------------------------------
    def trigger(self):
        """Activate as a user would: toggles checkable actions first."""
        if not self.isEnabled():
            return False
        if self._checkable:
            self.setChecked(not self._checked)
        self.triggered.emit(self._checked)
        return True

    def toggle(self):
        if self._checkable:
            self.setChecked(not self._checked)

    def hover(self):
        self.hovered.emit()


class ActionGroup:
    """Groups checkable actions; exclusive by default (radio behaviour)."""

    def __init__(self, exclusive=True):
        self._actions = []
        self._exclusive = bool(exclusive)
        self._enabled = True
        self.triggered = Signal()

    def addAction(self, action):
        if action not in self._actions:
            self._actions.append(action)
            action._group_ref = weakref.ref(self)
            action.setCheckable(True)
            action.triggered.connect(
                lambda _checked=None, current=action: self.triggered.emit(current))
            if self._exclusive and action.isChecked():
                for other in self._actions:
                    if other is not action and other.isChecked():
                        other._checked = False
                        other.toggled.emit(False)
        return action

    def removeAction(self, action):
        if action in self._actions:
            self._actions.remove(action)
            action._group_ref = None

    def actions(self):
        return tuple(self._actions)

    def checkedAction(self):
        return next((action for action in self._actions
                     if action.isChecked()), None)

    def isExclusive(self):
        return self._exclusive

    def setExclusive(self, exclusive):
        self._exclusive = bool(exclusive)

    def isEnabled(self):
        return self._enabled

    def setEnabled(self, enabled):
        self._enabled = bool(enabled)
        for action in self._actions:
            action._sync_shortcut()
            action.changed.emit()
