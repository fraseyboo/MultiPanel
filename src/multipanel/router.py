"""Interactor-level event routing (``docs/QT_PARITY_PROPOSAL.md`` §5).

One :class:`EventRouter` per interactor decides which UI widget receives
pointer, wheel and key events, and stops the 3D interactor style from seeing
events the UI consumed::

    router = EventRouter.install(interactor)
    router.isOverUi(x, y)          # replaces host-side panel hit tests
    router.isTextInputActive()     # replaces host-side text-edit flags

Two kinds of widget are handled:

* **Native** widgets override the ``WidgetMixin`` event handlers
  (``mousePressEvent`` and friends).  The router hit-tests them topmost
  first, delivers events with bubbling to parents, keeps an implicit mouse
  grab between press and release, and aborts the VTK event when a handler
  accepts it.
* **Legacy** widgets receive input through their own interactor observers.
  The router does not deliver presses, moves or releases to them (that would
  double-handle the input), but still counts them for :meth:`isOverUi`,
  routes the wheel to their ``handle_mouse_wheel`` methods, and suppresses
  scene hotkeys while one of them is editing text.

Legacy top-level widgets are discovered from ``renderer.UI_panels`` on each
renderer of the window, so hosts using that registry need no changes.

Observer priorities (higher runs first)::

    300  pointer + wheel routing (this module)
    200  FocusManager (Tab, Escape, Enter, Space)
    150  native key delivery (this module)
    100  legacy text widgets' key handling
     50  text-input guard (this module): consumes KeyPress/Char while editing
      0  interactor style
"""
from __future__ import annotations

import logging
import time
import weakref

import vtk

from .core import FocusManager, Signal, WidgetMixin, native_widgets_exist
from .events import (
    ContextMenuEvent,
    HoverEvent,
    KeyEvent,
    MouseEvent,
    WheelEvent,
    modifiers_from_interactor,
)

__all__ = ["EventRouter"]

logger = logging.getLogger(__name__)

POINTER_PRIORITY = 300.0
NATIVE_KEY_PRIORITY = 150.0
TEXT_GUARD_PRIORITY = 50.0

_BUTTONS = {
    "LeftButtonPressEvent": ("left", True),
    "LeftButtonReleaseEvent": ("left", False),
    "MiddleButtonPressEvent": ("middle", True),
    "MiddleButtonReleaseEvent": ("middle", False),
    "RightButtonPressEvent": ("right", True),
    "RightButtonReleaseEvent": ("right", False),
}


def _alive(widget):
    closed = getattr(widget, "isClosed", None)
    return not (callable(closed) and closed())


def _visible(widget):
    try:
        if not widget.isVisible():
            return False
        # Without a GetVisibility of their own, legacy panels and vtk*Widgets
        # are shown or hidden with SetEnabled (the container protocol), e.g.
        # under an inactive dock tab: isVisible() alone still says True.
        if getattr(widget, "GetVisibility", None) is None:
            enabled = getattr(widget, "GetEnabled", None)
            if callable(enabled) and not enabled():
                return False
        return True
    except (AttributeError, RuntimeError, TypeError):
        return True


def _enabled(widget):
    try:
        return bool(widget.isEnabled())
    except (AttributeError, RuntimeError, TypeError):
        return True


def _is_native(widget):
    return isinstance(widget, WidgetMixin) and type(widget).isEventNative()


def _handles(widget, handler):
    return isinstance(widget, WidgetMixin) and type(widget).handlesEvent(handler)


def _menu_policy(widget):
    policy = getattr(widget, "contextMenuPolicy", None)
    return callable(policy) and policy() in ("custom", "actions")


class _NoScheduler:
    @staticmethod
    def defer(callback):
        callback()


def _call_filter(filter_obj, target, event):
    method = getattr(filter_obj, "eventFilter", None)
    if callable(method):
        return bool(method(target, event))
    return bool(filter_obj(target, event))


class EventRouter:
    """Route interactor events to UI widgets; see the module docstring."""

    _instances = weakref.WeakKeyDictionary()

    def __init__(self, interactor):
        self._interactor_ref = weakref.ref(interactor)
        self._registered = []           # weakrefs, registration order
        self._filters = []
        self._tags = []
        self._grabber_ref = None
        self._buttons = set()
        self._hover = []                # weakrefs, deepest first
        self.hoverChanged = Signal()    # deepest widget under the pointer
        self._cursor_set = False
        self._last_press = None         # (button, time_ms, x, y)
        self._right_press = None        # (x, y)
        self._double_click_interval = 400.0
        self._drag_threshold = 4.0      # logical px

        for event in ("MouseMoveEvent", *_BUTTONS):
            self._observe(interactor, event, self._on_pointer, POINTER_PRIORITY)
        for event in ("MouseWheelForwardEvent", "MouseWheelBackwardEvent"):
            self._observe(interactor, event, self._on_wheel, POINTER_PRIORITY)
        self._observe(interactor, "LeaveEvent", self._on_leave_window,
                      POINTER_PRIORITY)
        for event in ("KeyPressEvent", "KeyReleaseEvent"):
            self._observe(interactor, event, self._on_native_key,
                          NATIVE_KEY_PRIORITY)
        for event in ("KeyPressEvent", "CharEvent"):
            self._observe(interactor, event, self._on_text_guard,
                          TEXT_GUARD_PRIORITY)

    # -- installation ----------------------------------------------------------
    @classmethod
    def install(cls, interactor):
        """Return the router for ``interactor``, creating it if needed."""
        router = cls._instances.get(interactor)
        if router is None:
            router = cls(interactor)
            cls._instances[interactor] = router
            window = interactor.GetRenderWindow()
            if window is not None:
                # Re-layout when the window changes display (size/DPI)
                # without a resize event (see multipanel.display).
                from .display import DisplayWatcher
                DisplayWatcher.install(window, interactor)
        return router

    @classmethod
    def for_interactor(cls, interactor):
        """Return the installed router, or ``None``."""
        if interactor is None:
            return None
        return cls._instances.get(interactor)

    @classmethod
    def uninstall(cls, interactor):
        router = cls._instances.pop(interactor, None)
        if router is not None:
            router.close()
            window = interactor.GetRenderWindow()
            if window is not None:
                from .display import DisplayWatcher
                DisplayWatcher.uninstall(window)
        return router

    def close(self):
        interactor = self._interactor_ref()
        if interactor is not None:
            for tag in self._tags:
                interactor.RemoveObserver(tag)
        self._tags.clear()
        self._registered.clear()
        self._filters.clear()
        self._hover.clear()
        self._grabber_ref = None

    def _observe(self, interactor, event, handler, priority):
        holder = {}

        def callback(caller, event_name):
            if handler(caller, event_name):
                command = caller.GetCommand(holder["tag"])
                if command is not None:
                    command.SetAbortFlag(1)

        holder["tag"] = interactor.AddObserver(event, callback, priority)
        self._tags.append(holder["tag"])

    # -- settings ----------------------------------------------------------------
    def doubleClickInterval(self):
        return self._double_click_interval

    def setDoubleClickInterval(self, ms):
        self._double_click_interval = max(0.0, float(ms))

    # -- registration ------------------------------------------------------------
    def register(self, widget):
        """Register a top-level widget; its children are found through it."""
        if not any(ref() is widget for ref in self._registered):
            self._registered.append(weakref.ref(widget))
        return widget

    def unregister(self, widget):
        self._registered = [ref for ref in self._registered
                            if ref() not in (None, widget)]
        self._hover = [ref for ref in self._hover if ref() is not widget]
        if self.mouseGrabber() is widget:
            self._grabber_ref = None

    def installEventFilter(self, filter_obj):
        """Offer every routed event to ``filter_obj`` before any widget.

        ``filter_obj.eventFilter(target, event)`` returns True to consume
        the event.  ``target`` is the deepest widget under the pointer (or
        the focus widget for keys), or ``None`` for the 3D scene.
        """
        if filter_obj in self._filters:
            self._filters.remove(filter_obj)
        self._filters.insert(0, filter_obj)

    def removeEventFilter(self, filter_obj):
        if filter_obj in self._filters:
            self._filters.remove(filter_obj)

    def mouseGrabber(self):
        return None if self._grabber_ref is None else self._grabber_ref()

    # -- discovery and hit-testing -----------------------------------------------
    def _interactor(self):
        return self._interactor_ref()

    def _window_size(self):
        window = self._interactor().GetRenderWindow()
        width, height = window.GetSize()[:2]
        return max(1, width), max(1, height)

    def _legacy_panels(self):
        interactor = self._interactor()
        renderers = interactor.GetRenderWindow().GetRenderers()
        renderers.InitTraversal()
        panels = []
        for _index in range(renderers.GetNumberOfItems()):
            renderer = renderers.GetNextItem()
            registry = getattr(renderer, "UI_panels", None)
            if isinstance(registry, dict):
                panels.extend(registry.values())
        return panels

    def _candidates(self):
        """Top-level widgets in registration order, without duplicates."""
        self._registered = [ref for ref in self._registered
                            if ref() is not None]
        found, seen = [], set()
        for widget in (*self._legacy_panels(),
                       *(ref() for ref in self._registered)):
            if widget is None or id(widget) in seen or not _alive(widget):
                continue
            seen.add(id(widget))
            found.append(widget)
        ids = {id(widget) for widget in found}

        def has_candidate_ancestor(widget):
            parent_of = getattr(widget, "parentWidget", None)
            parent = parent_of() if callable(parent_of) else None
            while parent is not None:
                if id(parent) in ids:
                    return True
                parent_of = getattr(parent, "parentWidget", None)
                parent = parent_of() if callable(parent_of) else None
            return False

        return [widget for widget in found if not has_candidate_ancestor(widget)]

    @staticmethod
    def _stacking(widgets):
        """Topmost first: higher z-order, then later registration."""
        indexed = list(enumerate(widgets))
        indexed.sort(key=lambda item: (
            item[1].uiZOrder() if isinstance(item[1], WidgetMixin) else 0,
            item[0]), reverse=True)
        return [widget for _index, widget in indexed]

    def _hits_top_level(self, widget, x, y):
        try:
            return self._hits_top_level_unsafe(widget, x, y)
        except Exception:      # a broken widget must not break routing
            logger.debug("hit test failed for %r", widget, exc_info=True)
            return False

    def _hits_top_level_unsafe(self, widget, x, y):
        if not _visible(widget):
            return False
        if not _is_native(widget):
            contains = getattr(widget, "is_within_bounds", None)
            if callable(contains):
                width, height = self._window_size()
                try:
                    return bool(contains(x / width, y / height))
                except (TypeError, ValueError, RuntimeError):
                    return False
        hit = getattr(widget, "hitTest", None)
        return bool(hit(x, y)) if callable(hit) else False

    def _child_hit(self, widget, x, y):
        children = getattr(widget, "children", None)
        if not callable(children):
            return None
        for child in self._stacking(list(children())):
            try:
                if _alive(child) and _visible(child) and child.hitTest(x, y):
                    return child
            except Exception:  # a broken widget must not break routing
                logger.debug("hit test failed for %r", child, exc_info=True)
        return None

    def hitChain(self, x, y):
        """Widgets under display point ``(x, y)``, deepest first."""
        for top in self._stacking(self._candidates()):
            if not self._hits_top_level(top, x, y):
                continue
            chain = [top]
            child = self._child_hit(top, x, y)
            while child is not None:
                chain.append(child)
                child = self._child_hit(child, x, y)
            return chain[::-1]
        return []

    def widgetAt(self, x, y):
        """Return the deepest widget at display point ``(x, y)``, or None."""
        chain = self.hitChain(x, y)
        return chain[0] if chain else None

    def isOverUi(self, x=None, y=None):
        """True when the display point (default: last event) is over UI."""
        if x is None or y is None:
            x, y = self._interactor().GetEventPosition()
        return bool(self.hitChain(x, y))

    def isTextInputActive(self):
        """True while any UI text field is editing.

        Covers the library's text widgets (via focus or registration) and
        legacy hosts that set ``interactor.text_edit_mode``.
        """
        interactor = self._interactor()
        if getattr(interactor, "text_edit_mode", False):
            return True
        manager = FocusManager._instances.get(interactor)
        focused = manager.focusWidget() if manager is not None else None
        if focused is not None and getattr(focused, "editing", False):
            return True
        if manager is not None:
            for ref in manager._widgets:
                widget = ref()
                if widget is not None and getattr(widget, "editing", False):
                    return True
        return False

    # -- delivery ------------------------------------------------------------------
    def _now_ms(self):
        from .timer import VirtualClock

        clock = VirtualClock.for_interactor(self._interactor())
        return clock.now() if clock is not None else time.monotonic() * 1000.0

    def _scale(self):
        from ._widget_support import ui_scale

        return ui_scale()

    def _filtered(self, target, event):
        for filter_obj in tuple(self._filters):
            if _call_filter(filter_obj, target, event):
                event.accept()
                return True
        return False

    @staticmethod
    def _local_pos(widget, global_pos):
        try:
            x, y, _w, _h = widget.geometry("display")
        except (TypeError, ValueError, RuntimeError):
            return global_pos
        if x is None:
            return global_pos
        from ._widget_support import ui_scale

        scale = ui_scale()
        return ((global_pos[0] - x) / scale, (global_pos[1] - y) / scale)

    def _send(self, widget, handler, event):
        """Deliver to one widget (filters first). Returns True if accepted."""
        for filter_obj in widget.eventFilters():
            if _call_filter(filter_obj, widget, event):
                event.accept()
                return True
        if hasattr(event, "_set_local"):
            event._set_local(self._local_pos(widget, event.globalPos()))
        event.ignore()
        getattr(widget, handler)(event)
        return event.isAccepted()

    def _bubble(self, chain, handler, event):
        """Offer ``event`` up ``chain``; return the accepting widget or None."""
        for widget in chain:
            if not _handles(widget, handler):
                continue
            if not _enabled(widget):
                # A disabled native widget swallows input, as in Qt.
                event.accept()
                return widget
            if self._send(widget, handler, event):
                return widget
        return None

    # -- hover -----------------------------------------------------------------------
    def _update_hover(self, x, y, chain):
        old = [ref() for ref in self._hover]
        old = [widget for widget in old if widget is not None]
        new_ids = {id(widget) for widget in chain}
        old_ids = {id(widget) for widget in old}
        mods = modifiers_from_interactor(self._interactor())
        for widget in old:
            if id(widget) not in new_ids and isinstance(widget, WidgetMixin):
                widget._ui_under_mouse = False
                event = HoverEvent(HoverEvent.LEAVE, (x, y), mods)
                event._set_local(self._local_pos(widget, (x, y)))
                widget.leaveEvent(event)
                widget.updateStyleState()
        for widget in reversed(chain):          # outermost enters first
            if id(widget) not in old_ids and isinstance(widget, WidgetMixin):
                widget._ui_under_mouse = True
                event = HoverEvent(HoverEvent.ENTER, (x, y), mods)
                event._set_local(self._local_pos(widget, (x, y)))
                widget.enterEvent(event)
                widget.updateStyleState()
        previous = old[0] if old else None
        self._hover = [weakref.ref(widget) for widget in chain]
        current = chain[0] if chain else None
        if current is not previous:
            self.hoverChanged.emit(current)
        self._apply_cursor(chain)

    def _apply_cursor(self, chain):
        shape = None
        grabber = self.mouseGrabber()
        for widget in ((grabber,) if grabber is not None else chain):
            getter = getattr(widget, "cursor", None)
            shape = getter() if callable(getter) else None
            if shape is not None:
                break
        window = self._interactor().GetRenderWindow()
        if shape is not None:
            window.SetCurrentCursor(shape)
            self._cursor_set = True
        elif self._cursor_set:
            window.SetCurrentCursor(vtk.VTK_CURSOR_DEFAULT)
            self._cursor_set = False

    def _on_leave_window(self, caller, _event):
        if self._hover:
            x, y = caller.GetEventPosition()
            self._update_hover(x, y, [])
        return False

    # -- pointer ---------------------------------------------------------------------
    def _routing_active(self):
        """Pointer delivery is only needed for native widgets or filters."""
        return bool(self._filters) or native_widgets_exist()

    def _on_pointer(self, caller, event_name):
        if not self._routing_active():
            # Fast path: legacy widgets handle pointers through their own
            # observers, so there is nothing to hit-test or deliver.
            if self._hover or self._grabber_ref is not None:
                self._hover = []
                self._grabber_ref = None
                self._buttons.clear()
            return False
        x, y = caller.GetEventPosition()
        mods = modifiers_from_interactor(caller)
        chain = self.hitChain(x, y)
        target = chain[0] if chain else None
        grabber = self.mouseGrabber()
        if grabber is None:
            self._update_hover(x, y, chain)

        if event_name == "MouseMoveEvent":
            event = MouseEvent(MouseEvent.MOVE, (x, y), None,
                               self._buttons, mods)
            if self._filtered(grabber or target, event):
                return True
            if grabber is not None:
                self._send(grabber, "mouseMoveEvent", event)
                return True       # the scene must not see drags we own
            explicit = self._explicit_grabber()
            if explicit is not None:
                self._send(explicit, "mouseMoveEvent", event)
                return event.isAccepted()
            # Hover moves are never consumed: legacy widgets use them too.
            self._bubble(chain, "mouseMoveEvent", event)
            return False

        button, pressed = _BUTTONS[event_name]
        if pressed:
            return self._on_press(caller, button, x, y, mods, chain, grabber)
        return self._on_release(caller, button, x, y, mods, chain, grabber)

    def _explicit_grabber(self):
        manager = FocusManager._instances.get(self._interactor())
        grabber = manager.mouseGrabber() if manager is not None else None
        return grabber if _is_native(grabber) else None

    def _is_double_click(self, caller, button, x, y, now):
        if caller.GetRepeatCount() > 0:
            return True
        if self._last_press is None:
            return False
        last_button, last_time, last_x, last_y = self._last_press
        limit = self._drag_threshold * self._scale()
        return (last_button == button
                and now - last_time <= self._double_click_interval
                and abs(x - last_x) <= limit and abs(y - last_y) <= limit)

    def _on_press(self, caller, button, x, y, mods, chain, grabber):
        now = self._now_ms()
        double = self._is_double_click(caller, button, x, y, now)
        self._last_press = None if double else (button, now, x, y)
        self._buttons.add(button)
        if button == "right":
            self._right_press = (x, y)
        kind = MouseEvent.DOUBLE_CLICK if double else MouseEvent.PRESS
        handler = "mouseDoubleClickEvent" if double else "mousePressEvent"
        event = MouseEvent(kind, (x, y), button, self._buttons, mods)
        target = chain[0] if chain else None
        if self._filtered(grabber or target, event):
            return True
        if grabber is not None:
            self._send(grabber, handler, event)
            return True
        receiver = self._bubble(chain, handler, event)
        if receiver is None and button == "right":
            # A right press over a widget with a context menu must not start
            # a scene gesture: the style would grab VTK focus and the router
            # would never see the release that triggers the menu.
            receiver = next((widget for widget in chain
                             if _handles(widget, "contextMenuEvent")
                             or _menu_policy(widget)), None)
            if receiver is not None:
                self._grabber_ref = weakref.ref(receiver)
                return True
        if receiver is None:
            if not chain and button == "left":
                self._release_text_focus()
            return False
        self._grabber_ref = weakref.ref(receiver)
        if (_enabled(receiver)
                and receiver.focusPolicy() in ("StrongFocus", "ClickFocus")):
            interactor = self._interactor()
            if receiver.focusManager() is None:
                receiver.registerFocus(interactor, receiver.focusPolicy())
            receiver.setFocus(reason="mouse")
        return True

    def _release_text_focus(self):
        """A press on the scene takes focus from a native text editor, as
        clicking a QVTK view does in Qt, so later keys reach the scene.
        (Legacy text widgets end their own editing on outside clicks.)"""
        manager = FocusManager._instances.get(self._interactor())
        focused = manager.focusWidget() if manager is not None else None
        if focused is not None and _is_native(focused) and \
                getattr(focused, "editing", False):
            manager.clearFocus(reason="mouse")

    def _on_release(self, caller, button, x, y, mods, chain, grabber):
        self._buttons.discard(button)
        event = MouseEvent(MouseEvent.RELEASE, (x, y), button,
                           self._buttons, mods)
        target = chain[0] if chain else None
        consumed = False
        if self._filtered(grabber or target, event):
            consumed = True
        elif grabber is not None:
            self._send(grabber, "mouseReleaseEvent", event)
            consumed = True
        else:
            consumed = self._bubble(chain, "mouseReleaseEvent", event) is not None
        if not self._buttons:
            self._grabber_ref = None
            self._update_hover(x, y, chain)
        if button == "right" and self._right_press is not None:
            px, py = self._right_press
            self._right_press = None
            limit = self._drag_threshold * self._scale()
            if abs(x - px) <= limit and abs(y - py) <= limit:
                menu = ContextMenuEvent((x, y), mods)
                if self._filtered(target, menu):
                    consumed = True
                elif self._bubble(chain, "contextMenuEvent", menu) is not None:
                    consumed = True
                elif self._policy_context_menu(chain, x, y):
                    consumed = True
        return consumed

    def _policy_context_menu(self, chain, x, y):
        """Serve ``setContextMenuPolicy`` for the nearest widget asking."""
        widget = next((item for item in chain if _menu_policy(item)), None)
        if widget is None:
            return False
        policy = widget.contextMenuPolicy()
        if policy == "custom":
            widget.customContextMenuRequested.emit(
                self._local_pos(widget, (x, y)))
            return True
        actions = [action for action in widget.actions()
                   if action.isVisible()]
        if not actions:
            return False
        from .standard import Menu

        renderer = getattr(widget, "renderer", None)
        if renderer is None:
            return False
        menu = Menu(renderer, self._interactor())
        for action in actions:
            menu.addAction(action)
        menu.closed.connect(
            lambda: (widget.renderScheduler() or _NoScheduler()).defer(
                menu.close))
        scale = self._scale()
        origin = (0.0, 0.0)
        try:
            from .units import viewport_origin

            origin = viewport_origin(menu.viewportSource())
        except (TypeError, AttributeError):
            pass
        menu.popup(at=((x - origin[0]) / scale, (y - origin[1]) / scale))
        return True

    # -- wheel -------------------------------------------------------------------------
    def _on_wheel(self, caller, event_name):
        x, y = caller.GetEventPosition()
        delta = 1 if event_name == "MouseWheelForwardEvent" else -1
        if not self._routing_active():
            return self._legacy_wheel(x, y, delta)
        event = WheelEvent((x, y), delta, modifiers_from_interactor(caller))
        chain = self.hitChain(x, y)
        target = chain[0] if chain else None
        if self._filtered(target, event):
            return True
        if self._bubble(chain, "wheelEvent", event) is not None:
            return True
        return self._legacy_wheel(x, y, delta)

    def _legacy_wheel(self, x, y, direction):
        """Offer the wheel to legacy containers, matching host behaviour.

        Containers registered later are tried first, and containers that
        own nested panels (dock panes) before plain panels, so the innermost
        scrollable region wins.
        """
        width, height = self._window_size()
        nx, ny = x / width, y / height
        unique, seen = [], set()
        for widget in reversed(self._candidates()):
            if id(widget) not in seen and not _is_native(widget):
                seen.add(id(widget))
                unique.append(widget)
        unique.sort(key=lambda widget: hasattr(widget, "panels"), reverse=True)
        for widget in unique:
            handler = getattr(widget, "handle_mouse_wheel", None)
            contains = getattr(widget, "is_within_bounds", None)
            if handler is None:
                continue
            if contains is not None and not contains(nx, ny):
                continue
            if handler(nx, ny, direction):
                return True
        return False

    # -- keys ----------------------------------------------------------------------------
    def _focus_chain(self):
        manager = FocusManager._instances.get(self._interactor())
        widget = manager.focusWidget() if manager is not None else None
        chain = []
        while widget is not None:
            chain.append(widget)
            parent_of = getattr(widget, "parentWidget", None)
            widget = parent_of() if callable(parent_of) else None
        return chain

    def _on_native_key(self, caller, event_name):
        if self._routing_active() and self._deliver_key(caller, event_name):
            return True
        if event_name == "KeyPressEvent":
            return self._dispatch_shortcut(caller)
        return False

    def _dispatch_shortcut(self, caller):
        """Offer an unhandled key press to the interactor's shortcuts."""
        from .actions import ShortcutMap

        mapping = ShortcutMap.existing(caller)
        if mapping is None:
            return False
        manager = FocusManager._instances.get(caller)
        focus = manager.focusWidget() if manager is not None else None
        return mapping.dispatch(caller.GetKeySym(),
                                modifiers_from_interactor(caller),
                                focus_widget=focus,
                                text_input_active=self.isTextInputActive())

    def _deliver_key(self, caller, event_name):
        chain = self._focus_chain()
        kind = KeyEvent.PRESS if event_name == "KeyPressEvent" else KeyEvent.RELEASE
        keycode = caller.GetKeyCode()
        text = keycode if (isinstance(keycode, str) and len(keycode) == 1
                           and ord(keycode) >= 32 and keycode != "\x7f") else ""
        event = KeyEvent(kind, caller.GetKeySym(), text,
                         modifiers_from_interactor(caller),
                         caller.GetRepeatCount() > 0)
        if self._filtered(chain[0] if chain else None, event):
            return True
        handler = "keyPressEvent" if kind == KeyEvent.PRESS else "keyReleaseEvent"
        return self._bubble(chain, handler, event) is not None

    def _on_text_guard(self, _caller, _event_name):
        # Runs after text widgets (priority 100) and before the interactor
        # style (priority 0): typing must never trigger scene hotkeys.
        return self.isTextInputActive()
