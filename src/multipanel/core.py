"""Qt-like, Qt-independent foundations for VTK UI objects.

The toolkit deliberately keeps its VTK API (``SetEnabled``, ``Modified`` and
friends) while offering the predictable lower-camel-case surface familiar to
Qt users.  This module has no Qt dependency and can also be used in headless
VTK applications.
"""
from __future__ import annotations

from contextlib import contextmanager
import weakref


class Signal:
    """Small synchronous signal with Qt-compatible connect/disconnect names."""

    def __init__(self, owner=None):
        self._owner_ref = weakref.ref(owner) if owner is not None else None
        self._slots = []

    def connect(self, slot, unique=False):
        if not callable(slot):
            raise TypeError("signal connections must be callable")
        if not unique or slot not in self._slots:
            self._slots.append(slot)
        return slot

    def disconnect(self, slot=None):
        if slot is None:
            self._slots.clear()
            return
        try:
            self._slots.remove(slot)
        except ValueError as exc:
            raise ValueError("slot is not connected") from exc

    def emit(self, *args, **kwargs):
        owner = self._owner_ref() if self._owner_ref is not None else None
        if owner is not None and owner.signalsBlocked():
            return
        for slot in tuple(self._slots):
            slot(*args, **kwargs)

    def __len__(self):
        return len(self._slots)


class SignalBlocker:
    """Context manager equivalent of ``QSignalBlocker``."""

    def __init__(self, obj):
        self.obj = obj
        self.previous = False

    def __enter__(self):
        self.previous = self.obj.blockSignals(True)
        return self

    def __exit__(self, _type, _value, _traceback):
        self.obj.blockSignals(self.previous)


class ObserverRegistry:
    """Own VTK observer tags and remove them deterministically."""

    def __init__(self):
        self._observers = []

    def add(self, subject, event, callback, priority=None):
        if priority is None:
            tag = subject.AddObserver(event, callback)
        else:
            tag = subject.AddObserver(event, callback, priority)
        self._observers.append((subject, tag))
        return tag

    def own(self, subject, tag):
        self._observers.append((subject, tag))
        return tag

    def remove(self, subject, tag):
        subject.RemoveObserver(tag)
        try:
            self._observers.remove((subject, tag))
        except ValueError:
            pass

    def clear(self):
        for subject, tag in reversed(self._observers):
            try:
                subject.RemoveObserver(tag)
            except (AttributeError, RuntimeError):
                pass
        self._observers.clear()

    def __len__(self):
        return len(self._observers)


class FocusManager:
    """Coordinate keyboard focus and pointer capture for one VTK interactor.

    VTK widgets normally handle focus independently, which allows several
    text widgets to believe they are editing at once.  This registry provides
    the single-focus semantics expected from desktop UI toolkits while leaving
    VTK's native event dispatch in place.
    """

    _instances = weakref.WeakKeyDictionary()

    def __init__(self, interactor):
        self._interactor_ref = weakref.ref(interactor)
        self._widgets = []
        self._focused_ref = None
        self._focus_reason = None
        self._mouse_grabber_ref = None
        self.focusChanged = Signal()
        self._key_tag = interactor.AddObserver(
            "KeyPressEvent", self._on_key_press, 200.0)

    @classmethod
    def for_interactor(cls, interactor):
        manager = cls._instances.get(interactor)
        if manager is None:
            manager = cls(interactor)
            cls._instances[interactor] = manager
        return manager

    def register(self, widget):
        self._purge()
        if not any(reference() is widget for reference in self._widgets):
            self._widgets.append(weakref.ref(widget))
        return widget

    def unregister(self, widget):
        if self.focusWidget() is widget:
            self.clearFocus(reason="unregister")
        if self.mouseGrabber() is widget:
            self.releaseMouse(widget)
        self._widgets = [
            reference for reference in self._widgets
            if reference() not in (None, widget)
        ]

    def _purge(self):
        self._widgets = [reference for reference in self._widgets
                         if reference() is not None]

    def _focusable_widgets(self):
        self._purge()
        result = []
        for reference in self._widgets:
            widget = reference()
            if widget is None or widget.isClosed():
                continue
            if widget.focusPolicy() == "NoFocus":
                continue
            if not widget.isEnabled() or not widget.isVisible():
                continue
            result.append(widget)
        return result

    def focusWidget(self):
        return None if self._focused_ref is None else self._focused_ref()

    def setFocus(self, widget, reason="other"):
        if widget is not None:
            self.register(widget)
            if widget.focusPolicy() == "NoFocus":
                return False
        previous = self.focusWidget()
        if previous is widget:
            if widget is not None and reason != self._focus_reason:
                self._focus_reason = reason
                self._update_focus_ring(widget, reason)
            return False
        if previous is not None:
            previous.focusOutEvent(reason)
        self._focused_ref = None if widget is None else weakref.ref(widget)
        self._focus_reason = None if widget is None else reason
        if widget is not None:
            widget.focusInEvent(reason)
        for changed in (previous, widget):
            update = getattr(changed, "updateStyleState", None)
            if callable(update):
                update()
        self._update_focus_ring(widget, reason)
        self.focusChanged.emit(widget, previous)
        return True

    def _update_focus_ring(self, widget, reason):
        from .style import update_focus_ring

        update_focus_ring(self, widget, reason)

    def clearFocus(self, reason="other"):
        return self.setFocus(None, reason=reason)

    def focusNext(self, backward=False):
        widgets = self._focusable_widgets()
        if not widgets:
            self.clearFocus(reason="tab")
            return None
        current = self.focusWidget()
        try:
            index = widgets.index(current)
        except ValueError:
            index = 0 if backward else -1
        step = -1 if backward else 1
        target = widgets[(index + step) % len(widgets)]
        self.setFocus(target, reason="backtab" if backward else "tab")
        return target

    def cancelFocused(self):
        """Escape: cancel the focus widget's editing (or popup) and clear focus.

        Returns True only when something was actually cancelled, so a widget
        that merely has focus (e.g. a clicked button) does not swallow
        Escape from the host application.
        """
        widget = self.focusWidget()
        if widget is None:
            return False
        cancelled = False
        cancel = getattr(widget, "cancelEditing", None)
        if callable(cancel):
            cancelled = bool(cancel())
        else:
            finish = getattr(widget, "finish_editing", None)
            if callable(finish) and getattr(widget, "editing", False):
                finish(commit=False)
                cancelled = True
            else:
                cancel = getattr(widget, "cancel", None)
                if callable(cancel):
                    cancelled = cancel() is not False
        self.clearFocus(reason="escape")
        return cancelled

    def focusReason(self):
        """Why the current focus widget got focus (``"tab"``, ``"mouse"``, ...)."""
        return self._focus_reason if self.focusWidget() is not None else None

    def activateFocused(self):
        """Activate the focus widget for Enter/Space.

        An editing widget commits.  Otherwise the widget is clicked (or starts
        editing) only when it was focused from the keyboard or from code:
        focus that a widget took because it was clicked does not make a later
        Enter press, aimed elsewhere, click it again.
        """
        widget = self.focusWidget()
        if widget is None:
            return False
        if getattr(widget, "editing", False):
            finish = getattr(widget, "finish_editing", None)
            if callable(finish):
                finish(commit=True)
                return True
        if self._focus_reason == "mouse":
            return False
        start = getattr(widget, "start_editing", None)
        if callable(start) and getattr(widget, "editable", False):
            return bool(start())
        click = getattr(widget, "click", None)
        if callable(click):
            click()
            return True
        if callable(start):
            return bool(start())
        return False

    def grabMouse(self, widget):
        current = self.mouseGrabber()
        if current not in (None, widget):
            return False
        self._mouse_grabber_ref = weakref.ref(widget)
        return True

    def releaseMouse(self, widget=None):
        current = self.mouseGrabber()
        if widget is not None and current is not widget:
            return False
        self._mouse_grabber_ref = None
        return current is not None

    def mouseGrabber(self):
        return (None if self._mouse_grabber_ref is None
                else self._mouse_grabber_ref())

    def _foreign_text_input_active(self, interactor):
        """True while a text field other than the focus widget is editing.

        Covers host widgets that only set ``interactor.text_edit_mode`` and
        registered widgets editing without focus.  Navigation keys then
        belong to that field.
        """
        focused = self.focusWidget()
        if getattr(focused, "editing", False):
            return False
        if getattr(interactor, "text_edit_mode", False):
            return True
        for reference in self._widgets:
            widget = reference()
            if widget is not None and widget is not focused and getattr(
                    widget, "editing", False):
                return True
        return False

    def _on_key_press(self, caller, _event):
        key = (caller.GetKeySym() or "").lower()
        if self._foreign_text_input_active(caller):
            return
        handled = False
        # The focus widget may claim navigation keys first (a field whose
        # completion list is open takes Escape, Enter and Tab for the list).
        intercept = getattr(self.focusWidget(), "focusKeyIntercept", None)
        if callable(intercept) and intercept(key):
            handled = True
        elif key == "tab":
            self.focusNext(backward=bool(caller.GetShiftKey()))
            handled = True
        elif key in {"escape", "esc"}:
            handled = self.cancelFocused()
        elif key in {"return", "enter", "kp_enter"}:
            handled = self.activateFocused()
        elif key == "space" and not getattr(
                self.focusWidget(), "editing", False):
            handled = self.activateFocused()
        if handled:
            command = caller.GetCommand(self._key_tag)
            if command is not None:
                command.SetAbortFlag(1)

    def close(self):
        interactor = self._interactor_ref()
        if interactor is not None and self._key_tag is not None:
            interactor.RemoveObserver(self._key_tag)
        if interactor is not None:
            self._instances.pop(interactor, None)
        self._key_tag = None
        self.clearFocus(reason="close")
        self._widgets.clear()
        self._mouse_grabber_ref = None


def timer_observer(handler):
    """Wrap ``handler(caller, timer_id)`` as a VTK ``TimerEvent`` observer.

    The firing timer's id arrives as the event's call data. Interactors
    differ in whether ``GetTimerEventId()`` is also set: VTK's native Cocoa
    interactor leaves it at 0, so code that relied on it never recognised
    its own timers on macOS.
    """
    try:
        from vtkmodules.vtkCommonCore import VTK_INT
    except ImportError:          # VTK-free unit tests
        VTK_INT = 6

    def callback(caller, _event, calldata=None):
        timer_id = calldata
        if timer_id is None:
            getter = getattr(caller, "GetTimerEventId", None)
            timer_id = getter() if callable(getter) else None
        handler(caller, timer_id)

    callback.CallDataType = VTK_INT
    return callback


class RenderScheduler:
    """Coalesce nested UI invalidations into one render-window render."""

    _instances = weakref.WeakKeyDictionary()

    def __init__(self, render_window, interactor=None):
        self.render_window = render_window
        self.interactor = interactor
        self._depth = 0
        self._pending = False
        self._timer_tag = None
        self._timer_id = None
        self._clock_handle = None
        self._qt_pending = False
        self._deferred = []

    @classmethod
    def for_window(cls, render_window, interactor=None):
        scheduler = cls._instances.get(render_window)
        if scheduler is None:
            scheduler = cls(render_window, interactor)
            cls._instances[render_window] = scheduler
        elif interactor is not None:
            scheduler.interactor = interactor
        return scheduler

    def request(self):
        self._pending = True
        if self._depth or self._timer_tag is not None:
            return
        if self._clock_handle is not None or self._qt_pending:
            return
        interactor = self.interactor
        clock = self._virtual_clock()
        if clock is not None:
            self._clock_handle = clock.call_later(0, self._on_clock)
            return
        from .timer import qt_core

        qt = qt_core()
        if qt is not None:
            # Qt's VTK interactor shares one QTimer between all VTK timers,
            # so schedule the render on Qt directly.
            self._qt_pending = True
            qt.QTimer.singleShot(0, self._on_qt)
            return
        if interactor is not None and hasattr(interactor, "CreateOneShotTimer"):
            self._timer_tag = interactor.AddObserver(
                "TimerEvent", timer_observer(self._on_timer), 100.0)
            self._timer_id = interactor.CreateOneShotTimer(0)
            if self._timer_id >= 0:
                return
            interactor.RemoveObserver(self._timer_tag)
            self._timer_tag = None
        self.flush()

    def defer(self, callback):
        self._deferred.append(callback)
        self.request()

    def _virtual_clock(self):
        if self.interactor is None:
            return None
        from .timer import VirtualClock

        return VirtualClock.for_interactor(self.interactor)

    def _on_clock(self):
        self._clock_handle = None
        self.flush()

    def _on_qt(self):
        self._qt_pending = False
        self.flush()

    def _on_timer(self, caller, event_id):
        if event_id is not None and self._timer_id not in (None, event_id):
            return
        if self._timer_tag is not None:
            caller.RemoveObserver(self._timer_tag)
        self._timer_tag = None
        self._timer_id = None
        self.flush()

    def flush(self):
        callbacks, self._deferred = self._deferred, []
        for callback in callbacks:
            callback()
        if self._pending:
            self._pending = False
            self.render_window.Render()

    @contextmanager
    def batch(self):
        self._depth += 1
        try:
            yield self
        finally:
            self._depth -= 1
            if self._depth == 0 and self._pending:
                self.request()


def refresh_renderer_theme(renderer):
    """Refresh every registered widget on *renderer* after theme mutation."""
    registry = getattr(renderer, "widgets", ())
    values = registry.values() if isinstance(registry, dict) else registry
    seen = set()

    def refresh(widget):
        identity = id(widget)
        if identity in seen or not isinstance(widget, WidgetMixin):
            return
        seen.add(identity)
        widget.refreshTheme(recursive=False)
        for child in widget.children():
            refresh(child)

    for widget in tuple(values):
        refresh(widget)
    return len(seen)


class SizePolicy:
    """How a widget's size may deviate from its size hint (as in Qt).

    Each direction combines GROW (may be larger than the hint), SHRINK (may
    be smaller, down to the minimum), EXPAND (wants spare space) and IGNORE
    (the hint is ignored).  Stretch factors weight how spare space is
    shared; a non-zero stretch takes precedence over policy.
    """

    GROW, EXPAND, SHRINK, IGNORE = 1, 2, 4, 8

    Fixed = 0
    Minimum = GROW
    Maximum = SHRINK
    Preferred = GROW | SHRINK
    MinimumExpanding = GROW | EXPAND
    Expanding = GROW | SHRINK | EXPAND
    Ignored = GROW | SHRINK | IGNORE

    __slots__ = ("horizontal", "vertical", "horizontalStretch",
                 "verticalStretch", "retainSizeWhenHidden")

    def __init__(self, horizontal=Preferred, vertical=Preferred,
                 horizontalStretch=0, verticalStretch=0,
                 retainSizeWhenHidden=False):
        self.horizontal = int(horizontal)
        self.vertical = int(vertical)
        self.horizontalStretch = int(horizontalStretch)
        self.verticalStretch = int(verticalStretch)
        self.retainSizeWhenHidden = bool(retainSizeWhenHidden)

    def policy(self, axis):
        return self.horizontal if axis == 0 else self.vertical

    def stretch(self, axis):
        return self.horizontalStretch if axis == 0 else self.verticalStretch

    def copy(self):
        return SizePolicy(self.horizontal, self.vertical,
                          self.horizontalStretch, self.verticalStretch,
                          self.retainSizeWhenHidden)

    def __eq__(self, other):
        return isinstance(other, SizePolicy) and all(
            getattr(self, name) == getattr(other, name)
            for name in self.__slots__)

    def __repr__(self):
        return (f"SizePolicy(horizontal={self.horizontal}, "
                f"vertical={self.vertical})")


QWIDGETSIZE_MAX = 16777215.0


# Widgets with a context-menu policy; they also need full pointer routing.
_CONTEXT_MENU_WIDGETS = weakref.WeakSet()

# Live widgets that receive input through the WidgetMixin event handlers.
# The EventRouter skips per-event hit-testing entirely while this is empty.
_NATIVE_WIDGETS = weakref.WeakSet()
_NATIVE_CLASS_CACHE = {}


def native_widgets_exist():
    return len(_NATIVE_WIDGETS) > 0 or len(_CONTEXT_MENU_WIDGETS) > 0


class WidgetMixin:
    """Qt-like common API for VTK-native and composite widget classes."""

    def _ensure_widget_api(self):
        if getattr(self, "_ui_api_ready", False):
            return
        self._ui_api_ready = True
        if type(self).isEventNative():
            _NATIVE_WIDGETS.add(self)
        self._ui_object_name = ""
        self._ui_parent = None
        self._ui_children = []
        self._ui_enabled = True
        self._ui_visible = True
        self._ui_tooltip = ""
        self._ui_status_tip = ""
        self._ui_geometry = None
        self._ui_signals_blocked = False
        self._ui_closed = False
        self._ui_observers = ObserverRegistry()
        self._ui_focus_policy = "NoFocus"
        self._ui_focus_manager = None
        self.enabledChanged = Signal(self)
        self.visibilityChanged = Signal(self)
        self.geometryChanged = Signal(self)
        self.focusIn = Signal(self)
        self.focusOut = Signal(self)
        self.themeChanged = Signal(self)
        # (new_states, old_states) whenever styleState() changes.
        self.styleStateChanged = Signal(self)
        self._ui_style_state = frozenset()
        self.destroyed = Signal(self)

    def initWidget(self, object_name=None, parent=None):
        self._ensure_widget_api()
        if object_name is not None:
            self.setObjectName(object_name)
        if parent is not None:
            self.setParent(parent)
        return self

    def objectName(self):
        self._ensure_widget_api()
        getter = getattr(self, "GetObjectName", None)
        if callable(getter):
            value = getter()
            if value:
                return value
        return self._ui_object_name

    def setObjectName(self, name):
        self._ensure_widget_api()
        self._ui_object_name = str(name)
        setter = getattr(self, "SetObjectName", None)
        if callable(setter):
            setter(self._ui_object_name)

    def parentWidget(self):
        self._ensure_widget_api()
        return self._ui_parent

    def setParent(self, parent):
        self._ensure_widget_api()
        if parent is self._ui_parent:
            return
        old_parent = self._ui_parent
        if old_parent is not None:
            old_parent._ensure_widget_api()
            if self in old_parent._ui_children:
                old_parent._ui_children.remove(self)
        self._ui_parent = parent
        if parent is not None:
            parent._ensure_widget_api()
            if self not in parent._ui_children:
                parent._ui_children.append(self)

    def children(self):
        self._ensure_widget_api()
        return tuple(self._ui_children)

    def blockSignals(self, block):
        self._ensure_widget_api()
        previous = self._ui_signals_blocked
        self._ui_signals_blocked = bool(block)
        return previous

    def signalsBlocked(self):
        self._ensure_widget_api()
        return self._ui_signals_blocked

    def signalBlocker(self):
        return SignalBlocker(self)

    def observerRegistry(self):
        self._ensure_widget_api()
        return self._ui_observers

    def ownObserver(self, subject, event, callback, priority=None):
        return self.observerRegistry().add(
            subject, event, callback, priority=priority)

    def registerFocus(self, interactor, policy="StrongFocus"):
        self._ensure_widget_api()
        self._ui_focus_policy = str(policy)
        self._ui_focus_manager = FocusManager.for_interactor(interactor)
        self._ui_focus_manager.register(self)
        return self

    def focusPolicy(self):
        self._ensure_widget_api()
        return self._ui_focus_policy

    def setFocusPolicy(self, policy):
        self._ensure_widget_api()
        self._ui_focus_policy = str(policy)

    def focusManager(self):
        self._ensure_widget_api()
        return self._ui_focus_manager

    def hasFocus(self):
        manager = self.focusManager()
        return manager is not None and manager.focusWidget() is self

    def setFocus(self, reason="other"):
        manager = self.focusManager()
        return False if manager is None else manager.setFocus(self, reason)

    def clearFocus(self, reason="other"):
        manager = self.focusManager()
        if manager is None or manager.focusWidget() is not self:
            return False
        return manager.clearFocus(reason)

    def focusInEvent(self, reason="other"):
        self.focusIn.emit(reason)

    def focusOutEvent(self, reason="other"):
        self.focusOut.emit(reason)

    def grabMouse(self):
        manager = self.focusManager()
        return False if manager is None else manager.grabMouse(self)

    def releaseMouse(self):
        manager = self.focusManager()
        return False if manager is None else manager.releaseMouse(self)

    def hasMouseCapture(self):
        manager = self.focusManager()
        return manager is not None and manager.mouseGrabber() is self

    # -- event handlers (delivered by multipanel.router.EventRouter) ---------
    #
    # Each default ignores the event, so it propagates to the parent and
    # then to the 3D scene.  Subclasses override the handlers they need and
    # call ``event.accept()``.  Widgets that override none of them are
    # "legacy" widgets: the router leaves their own VTK observers in charge.

    EVENT_HANDLERS = (
        "mousePressEvent", "mouseReleaseEvent", "mouseMoveEvent",
        "mouseDoubleClickEvent", "wheelEvent", "keyPressEvent",
        "keyReleaseEvent", "contextMenuEvent",
    )

    def mousePressEvent(self, event):
        event.ignore()

    def mouseReleaseEvent(self, event):
        event.ignore()

    def mouseMoveEvent(self, event):
        event.ignore()

    def mouseDoubleClickEvent(self, event):
        # As in Qt, an unhandled double-click is treated as a second press.
        self.mousePressEvent(event)

    def wheelEvent(self, event):
        event.ignore()

    def keyPressEvent(self, event):
        event.ignore()

    def keyReleaseEvent(self, event):
        event.ignore()

    def contextMenuEvent(self, event):
        event.ignore()

    def enterEvent(self, event):
        pass

    def leaveEvent(self, event):
        pass

    @classmethod
    def handlesEvent(cls, handler_name):
        """True when ``cls`` overrides the named event handler."""
        own = getattr(cls, handler_name, None)
        base = getattr(WidgetMixin, handler_name, None)
        if handler_name == "mouseDoubleClickEvent" and own is base:
            return cls.handlesEvent("mousePressEvent")
        return own is not None and own is not base

    @classmethod
    def isEventNative(cls):
        """True when the widget receives input through the event handlers."""
        cached = _NATIVE_CLASS_CACHE.get(cls)
        if cached is None:
            cached = any(cls.handlesEvent(name)
                         for name in WidgetMixin.EVENT_HANDLERS)
            _NATIVE_CLASS_CACHE[cls] = cached
        return cached

    def hitTest(self, x, y):
        """Return True when display-pixel point ``(x, y)`` hits the widget."""
        try:
            geometry = self.geometry("display")
        except (RuntimeError, TypeError, ValueError):
            return False
        if geometry is None:
            return False
        gx, gy, width, height = geometry
        if not (gx <= x <= gx + width and gy <= y <= gy + height):
            return False
        source = self.viewportSource()
        if getattr(source, "_ui_clips_children", False):
            # Content of a scroll area: only the part inside its clipped
            # viewport is visible, so only that part can be hit.
            from .units import viewport_extent, viewport_origin

            ox, oy = viewport_origin(source)
            vw, vh = viewport_extent(source)
            return ox <= x <= ox + vw and oy <= y <= oy + vh
        return True

    def uiZOrder(self):
        """Stacking band used for hit-testing; higher values are on top."""
        return int(getattr(self, "ui_z_order", 0) or 0)

    def underMouse(self):
        self._ensure_widget_api()
        return getattr(self, "_ui_under_mouse", False)

    def styleState(self):
        """Current style states (``hover``, ``pressed``, ``focus``,
        ``disabled``, ``checked``, ...) as a frozenset, for
        :class:`multipanel.style.Style`."""
        states = set()
        if self.underMouse() or getattr(self, "_hovered", False):
            states.add("hover")
        if getattr(self, "_pressed", False):
            states.add("pressed")
        if self.hasFocus():
            states.add("focus")
        if not self.isEnabled():
            states.add("disabled")
        checked = getattr(self, "isChecked", None)
        if callable(checked):
            try:
                if checked():
                    states.add("checked")
            except (RuntimeError, TypeError):
                pass
        return frozenset(states)

    def updateStyleState(self):
        """Recompute :meth:`styleState`; emit ``styleStateChanged`` if it
        changed. The router (hover), the focus manager (focus) and
        ``setEnabled`` call this; widgets call it for their own states
        (pressed, checked)."""
        self._ensure_widget_api()
        try:
            new = self.styleState()
        except (RuntimeError, TypeError, AttributeError):
            return False
        old = self._ui_style_state
        if new == old:
            return False
        self._ui_style_state = new
        self.styleStateChanged.emit(new, old)
        return True

    def cursor(self):
        self._ensure_widget_api()
        return getattr(self, "_ui_cursor", None)

    def setCursor(self, shape):
        """Set the cursor shown while hovering: a ``vtk.VTK_CURSOR_*`` value."""
        self._ensure_widget_api()
        self._ui_cursor = shape

    def unsetCursor(self):
        self._ensure_widget_api()
        self._ui_cursor = None

    def installEventFilter(self, filter_obj):
        """Offer every event for this widget to ``filter_obj`` first.

        ``filter_obj.eventFilter(widget, event)`` (or a plain callable
        ``filter_obj(widget, event)``) returns True to consume the event.
        Filters installed later run first, as in Qt.
        """
        self._ensure_widget_api()
        filters = self.__dict__.setdefault("_ui_event_filters", [])
        if filter_obj in filters:
            filters.remove(filter_obj)
        filters.insert(0, filter_obj)

    def removeEventFilter(self, filter_obj):
        filters = self.__dict__.get("_ui_event_filters", [])
        if filter_obj in filters:
            filters.remove(filter_obj)

    def eventFilters(self):
        return tuple(self.__dict__.get("_ui_event_filters", ()))

    # -- context menus -----------------------------------------------------------
    CONTEXT_MENU_POLICIES = ("none", "default", "custom", "actions")

    def contextMenuPolicy(self):
        return getattr(self, "_ui_context_policy", "default")

    def setContextMenuPolicy(self, policy):
        """``"custom"`` emits ``customContextMenuRequested(pos)`` on a right
        click; ``"actions"`` pops up a menu of :meth:`actions`.

        Works for legacy widgets as well as native ones.
        """
        if policy not in self.CONTEXT_MENU_POLICIES:
            raise ValueError(f"unknown context menu policy {policy!r}")
        self._ensure_widget_api()
        self._ui_context_policy = policy
        if policy in ("custom", "actions"):
            _CONTEXT_MENU_WIDGETS.add(self)
        else:
            _CONTEXT_MENU_WIDGETS.discard(self)

    @property
    def customContextMenuRequested(self):
        signal = self.__dict__.get("_ui_context_signal")
        if signal is None:
            signal = Signal(self)
            self.__dict__["_ui_context_signal"] = signal
        return signal

    def addAction(self, action):
        """Add an action (used by the ``"actions"`` context menu policy)."""
        actions = self.__dict__.setdefault("_ui_actions", [])
        if action not in actions:
            actions.append(action)
        return action

    def removeAction(self, action):
        actions = self.__dict__.get("_ui_actions", [])
        if action in actions:
            actions.remove(action)

    def actions(self):
        return list(self.__dict__.get("_ui_actions", []))

    def registerWithRouter(self, interactor=None):
        """Register this top-level widget with the interactor's EventRouter.

        Installs the router if needed.  Native widgets call this from their
        constructors; children are reached through their parent instead.
        """
        self._ensure_widget_api()
        from .router import EventRouter

        if interactor is None:
            interactor = getattr(self, "interactor", None)
        if interactor is None and hasattr(self, "GetInteractor"):
            interactor = self.GetInteractor()
        if interactor is None:
            raise RuntimeError("registerWithRouter needs an interactor")
        router = EventRouter.install(interactor)
        router.register(self)
        self._ui_router_ref = weakref.ref(router)
        return router

    # -- size negotiation (layouts) -----------------------------------------
    #
    # Sizes are logical pixels (display px / ui_scale()).  Minimum and maximum
    # sizes may be given as px()/frac() lengths; fractions resolve against
    # the widget's viewport whenever they are read, so they track resizes.

    def sizeHint(self):
        """Preferred ``(width, height)`` in logical pixels.

        The default is the widget's current size, so widgets without a
        specific hint keep the size they were created with.
        """
        try:
            geometry = self.geometry("px")
        except (RuntimeError, TypeError, ValueError):
            geometry = None
        return (0.0, 0.0) if geometry is None else (geometry[2], geometry[3])

    def minimumSizeHint(self):
        """Smallest sensible ``(width, height)`` in logical pixels."""
        return (0.0, 0.0)

    def _resolve_size_pair(self, pair, default):
        if pair is None:
            return default
        from .units import Length, to_px

        extent = None
        values = []
        for axis, value in enumerate(pair):
            if isinstance(value, Length) and value.unit == "frac":
                if extent is None:
                    extent = self.viewportExtent()
                values.append(to_px(value, extent[axis]))
            elif isinstance(value, Length):
                values.append(value.value)
            else:
                values.append(float(value))
        return tuple(values)

    def _store_size_pair(self, name, width, height):
        from .units import parse_length

        self._ensure_widget_api()
        pair = (parse_length(width, "px"), parse_length(height, "px"))
        setattr(self, name, pair)
        self.updateGeometry()

    def minimumSize(self):
        """Explicit minimum ``(width, height)`` in logical px (0 when unset)."""
        return self._resolve_size_pair(
            getattr(self, "_ui_minimum_size", None), (0.0, 0.0))

    def maximumSize(self):
        return self._resolve_size_pair(
            getattr(self, "_ui_maximum_size", None),
            (QWIDGETSIZE_MAX, QWIDGETSIZE_MAX))

    def setMinimumSize(self, width, height):
        """Set the minimum size; accepts numbers (px), ``px()``/``frac()``."""
        self._store_size_pair("_ui_minimum_size", width, height)

    def setMaximumSize(self, width, height):
        self._store_size_pair("_ui_maximum_size", width, height)

    def setFixedSize(self, width, height):
        self._store_size_pair("_ui_minimum_size", width, height)
        self._store_size_pair("_ui_maximum_size", width, height)

    def setMinimumWidth(self, width):
        self.setMinimumSize(width, self._raw_pair("_ui_minimum_size", 0.0)[1])

    def setMinimumHeight(self, height):
        self.setMinimumSize(self._raw_pair("_ui_minimum_size", 0.0)[0], height)

    def setMaximumWidth(self, width):
        self.setMaximumSize(
            width, self._raw_pair("_ui_maximum_size", QWIDGETSIZE_MAX)[1])

    def setMaximumHeight(self, height):
        self.setMaximumSize(
            self._raw_pair("_ui_maximum_size", QWIDGETSIZE_MAX)[0], height)

    def setFixedWidth(self, width):
        self.setMinimumWidth(width)
        self.setMaximumWidth(width)

    def setFixedHeight(self, height):
        self.setMinimumHeight(height)
        self.setMaximumHeight(height)

    def _raw_pair(self, name, default):
        pair = getattr(self, name, None)
        return (default, default) if pair is None else pair

    def defaultSizePolicy(self):
        """Policy used when none was set; controls override this."""
        return SizePolicy(SizePolicy.Preferred, SizePolicy.Preferred)

    def sizePolicy(self):
        policy = getattr(self, "_ui_size_policy", None)
        return self.defaultSizePolicy() if policy is None else policy.copy()

    def setSizePolicy(self, horizontal, vertical=None):
        """Accept a ``SizePolicy`` or two policy values."""
        if isinstance(horizontal, SizePolicy):
            policy = horizontal.copy()
        else:
            policy = self.sizePolicy()
            policy.horizontal = int(horizontal)
            policy.vertical = int(horizontal if vertical is None else vertical)
        self._ui_size_policy = policy
        self.updateGeometry()

    def updateGeometry(self):
        """Tell the layout managing this widget that its hints changed."""
        layout_ref = getattr(self, "_ui_parent_layout", None)
        layout = layout_ref() if layout_ref is not None else None
        if layout is not None:
            layout.invalidate()

    # -- layouts -------------------------------------------------------------
    #
    # ``layout()`` is not used as the getter because existing containers
    # (DockPane, ViewportDisplayPanel) already define a ``layout()`` method
    # that performs their own relayout.

    def setLayout(self, layout):
        """Install ``layout`` to manage this widget's children."""
        self._ensure_widget_api()
        old = self.contentLayout()
        if old is layout:
            return
        if old is not None:
            old._detach()
        self._ui_layout = layout
        if layout is not None:
            layout._attach(self)

    def contentLayout(self):
        return getattr(self, "_ui_layout", None)

    def contentsMargins(self):
        """Margins (left, top, right, bottom) in logical px inside geometry."""
        margins = getattr(self, "_ui_contents_margins", None)
        if margins is None:
            return (0.0, 0.0, 0.0, 0.0)
        from .units import Length, to_px

        extent = None
        values = []
        for index, value in enumerate(margins):
            if isinstance(value, Length) and value.unit == "frac":
                if extent is None:
                    extent = self.viewportExtent()
                values.append(to_px(value, extent[index % 2]))
            else:
                values.append(value.value if isinstance(value, Length)
                              else float(value))
        return tuple(values)

    def setContentsMargins(self, left, top, right, bottom):
        from .units import parse_length

        self._ui_contents_margins = tuple(
            parse_length(value, "px") for value in (left, top, right, bottom))
        layout = self.contentLayout()
        if layout is not None:
            layout.invalidate()

    def contentsRect(self):
        """Inner rectangle ``(x, y, w, h)`` in logical px for the layout."""
        geometry = self.geometry("px")
        if geometry is None:
            return None
        left, top, right, bottom = self.contentsMargins()
        x, y, width, height = geometry
        return (x + left, y + bottom, max(0.0, width - left - right),
                max(0.0, height - top - bottom))

    def isEnabled(self):
        self._ensure_widget_api()
        getter = getattr(self, "GetEnabled", None)
        if callable(getter):
            try:
                return bool(getter())
            except RuntimeError:
                pass
        return self._ui_enabled

    def setEnabled(self, enabled):
        self._ensure_widget_api()
        enabled = bool(enabled)
        old = self.isEnabled()
        setter = getattr(self, "SetEnabled", None)
        if callable(setter):
            setter(enabled)
        self._ui_enabled = enabled
        if old != enabled:
            self.enabledChanged.emit(enabled)
            self.updateStyleState()

    def isVisible(self):
        self._ensure_widget_api()
        getter = getattr(self, "GetVisibility", None)
        if callable(getter):
            try:
                return bool(getter())
            except RuntimeError:
                pass
        return self._ui_visible

    def setVisible(self, visible):
        self._ensure_widget_api()
        visible = bool(visible)
        old = self.isVisible()
        setter = getattr(self, "SetVisibility", None)
        if callable(setter):
            setter(visible)
        else:
            # VTK widgets such as vtkSliderWidget have no visibility switch;
            # enabling is what shows or hides them.
            enabler = getattr(self, "SetEnabled", None)
            if callable(enabler) and callable(getattr(self, "GetEnabled", None)):
                enabler(visible)
        self._ui_visible = visible
        if old != visible:
            self.visibilityChanged.emit(visible)

    def isHidden(self):
        """True when hidden explicitly with ``hide()``/``setVisible(False)``.

        Unlike ``isVisible()`` this ignores containers hiding the widget
        with its panel or tab, so layouts keep reserving its space.
        """
        self._ensure_widget_api()
        return not self._ui_visible

    def show(self):
        self.setVisible(True)

    def hide(self):
        self.setVisible(False)

    def _nativeGeometry(self):
        getter = getattr(self, "GetBounds", None)
        if callable(getter):
            try:
                x0, x1, y0, y1 = getter()[:4]
                return (x0, y0, x1 - x0, y1 - y0)
            except (TypeError, RuntimeError, ValueError):
                pass
        return self._ui_geometry

    def viewportSource(self):
        """Return the object whose viewport defines ``frac`` units.

        This is the widget's renderer when one can be found, otherwise its
        interactor (whose render window size is used).
        """
        renderer = getattr(self, "renderer", None)
        if renderer is None:
            for name in ("GetCurrentRenderer", "GetDefaultRenderer"):
                getter = getattr(self, name, None)
                if callable(getter):
                    try:
                        renderer = getter()
                    except (TypeError, RuntimeError):
                        renderer = None
                    if renderer is not None:
                        break
        if renderer is not None:
            # UI is drawn on the renderer's overlay layer when it has one;
            # the scene renderer's viewport may be clipped to a sub-region.
            overlay = getattr(renderer, "ui_overlay", None)
            return renderer if overlay is None else overlay
        interactor = getattr(self, "interactor", None)
        if interactor is None and hasattr(self, "GetInteractor"):
            interactor = self.GetInteractor()
        return interactor

    def viewportExtent(self):
        """Return the ``(width, height)`` of the widget's viewport in display px."""
        from .units import viewport_extent

        source = self.viewportSource()
        if source is None:
            raise RuntimeError(
                f"{type(self).__name__} has no renderer or interactor, so "
                "pixel geometry cannot be resolved")
        return viewport_extent(source)

    def geometry(self, units="frac"):
        """Return ``(x, y, width, height)``.

        ``units`` selects the coordinate system:

        * ``"frac"`` (default): fractions of the viewport, as reported by the
          widget's ``GetBounds``. Widgets without ``GetBounds`` return the
          values last passed to ``setGeometry``.
        * ``"px"``: logical pixels relative to the viewport origin.
        * ``"display"``: display pixels relative to the render window origin,
          the coordinate system of ``interactor.GetEventPosition()``.
        """
        self._ensure_widget_api()
        native = self._nativeGeometry()
        if native is None or units == "frac":
            return native
        if units not in ("px", "display"):
            raise ValueError(f"unknown geometry units {units!r}")
        from .units import _current_scale, viewport_origin

        width, height = self.viewportExtent()
        x, y, w, h = native
        if units == "display":
            ox, oy = viewport_origin(self.viewportSource())
            return (ox + x * width, oy + y * height, w * width, h * height)
        scale = _current_scale()
        return (x * width / scale, y * height / scale,
                w * width / scale, h * height / scale)

    def geometrySpec(self):
        """Return the ``Length`` values last passed to ``setGeometry``.

        ``None`` if geometry was only ever set with bare numbers.
        """
        self._ensure_widget_api()
        return getattr(self, "_ui_geometry_spec", None)

    def setGeometry(self, x, y, width, height, units=None):
        """Set geometry from numbers, ``Length`` values or length strings.

        Bare numbers are fractions of the viewport (the historical meaning)
        unless ``units`` is given.  When any value carries an explicit unit,
        the specification is remembered and written by :meth:`saveState`, so
        a restored widget keeps scaling (``frac``) or not (``px``).
        """
        self._ensure_widget_api()
        from .units import FRAC, Length, parse_length

        values = (x, y, width, height)
        explicit = units is not None or any(
            isinstance(value, (Length, str)) for value in values)
        default_unit = FRAC if units is None else units
        lengths = tuple(parse_length(value, default_unit, legacy=units is None)
                        for value in values)
        if all(length.unit == FRAC for length in lengths):
            geometry = tuple(length.value for length in lengths)
        else:
            extent = self.viewportExtent()
            geometry = tuple(
                length.resolve(extent[index % 2]) / extent[index % 2]
                for index, length in enumerate(lengths))
        self._ui_geometry_spec = lengths if explicit else None
        geometry = tuple(float(value) for value in geometry)
        x, y, width, height = geometry
        if geometry == self.geometry():
            return
        setter = getattr(self, "SetBounds", None)
        if callable(setter):
            setter(x, x + width, y, y + height)
        else:
            position = getattr(self, "SetPosition", None)
            size = getattr(self, "SetSize", None)
            if callable(position):
                position(x, y)
            if callable(size):
                size(width, height)
        self._ui_geometry = geometry
        self.geometryChanged.emit(geometry)

    def pos(self):
        geometry = self.geometry()
        return None if geometry is None else geometry[:2]

    def _retainedLengths(self, indices):
        spec = self.geometrySpec()
        geometry = self.geometry()
        if spec is not None:
            return [spec[index] for index in indices]
        if geometry is None:
            return [0.0 for _index in indices]
        return [geometry[index] for index in indices]

    def move(self, x, y, units=None):
        width, height = self._retainedLengths((2, 3))
        if units is not None:
            from .units import parse_length

            x, y = (parse_length(value, units) for value in (x, y))
        self.setGeometry(x, y, width, height)

    def size(self, units="frac"):
        geometry = self.geometry(units)
        return None if geometry is None else geometry[2:]

    def resize(self, width, height, units=None):
        x, y = self._retainedLengths((0, 1))
        if units is not None:
            from .units import parse_length

            width, height = (parse_length(value, units)
                             for value in (width, height))
        self.setGeometry(x, y, width, height)

    def toolTip(self):
        self._ensure_widget_api()
        return self._ui_tooltip

    def setToolTip(self, text):
        self._ensure_widget_api()
        self._ui_tooltip = str(text)

    def statusTip(self):
        self._ensure_widget_api()
        return self._ui_status_tip

    def setStatusTip(self, text):
        self._ensure_widget_api()
        self._ui_status_tip = str(text)

    def renderScheduler(self):
        interactor = getattr(self, "interactor", None)
        if interactor is None and hasattr(self, "GetInteractor"):
            interactor = self.GetInteractor()
        window = (interactor.GetRenderWindow()
                  if interactor is not None else None)
        if window is None:
            renderer = getattr(self, "renderer", None)
            window = renderer.GetRenderWindow() if renderer is not None else None
        return (None if window is None else
                RenderScheduler.for_window(window, interactor))

    def requestRender(self):
        scheduler = self.renderScheduler()
        if scheduler is not None:
            scheduler.request()

    def update(self):
        modified = getattr(self, "Modified", None)
        if callable(modified):
            modified()
        self.requestRender()

    def refreshTheme(self, recursive=True):
        """Re-read host theme tokens and invalidate this widget tree."""
        hook = getattr(self, "_applyTheme", None)
        if callable(hook):
            hook()
        if recursive:
            for child in self.children():
                child.refreshTheme(recursive=True)
        self.themeChanged.emit()
        modified = getattr(self, "Modified", None)
        if callable(modified):
            modified()
        self.requestRender()

    def saveState(self):
        """Return JSON-serializable common widget state."""
        return {
            "objectName": self.objectName(),
            "enabled": self.isEnabled(),
            "visible": self.isVisible(),
            "geometry": self._geometryState(),
            "toolTip": self.toolTip(),
            "statusTip": self.statusTip(),
        }

    def _geometryState(self):
        spec = self.geometrySpec()
        if spec is not None:
            return [length.to_json() for length in spec]
        geometry = self.geometry()
        if geometry is None:
            return None
        return [[float(value), "frac"] for value in geometry]

    def _restoreGeometry(self, data):
        from .units import Length

        values = list(data)
        if len(values) != 4:
            raise ValueError("geometry state must have four values")
        if all(isinstance(value, (list, tuple)) for value in values):
            values = [Length.from_json(value) for value in values]
            # Untagged-equivalent state restores exactly as numbers do.
            if all(value.unit == "frac" for value in values):
                self.setGeometry(*(value.value for value in values))
                return
        self.setGeometry(*values)

    def restoreState(self, state):
        """Restore common state produced by :meth:`saveState`."""
        if not isinstance(state, dict):
            raise TypeError("widget state must be a dictionary")
        with self.signalBlocker():
            if "objectName" in state:
                self.setObjectName(state["objectName"])
            if "geometry" in state and state["geometry"] is not None:
                self._restoreGeometry(state["geometry"])
            if "enabled" in state:
                self.setEnabled(state["enabled"])
            if "visible" in state:
                self.setVisible(state["visible"])
            if "toolTip" in state:
                self.setToolTip(state["toolTip"])
            if "statusTip" in state:
                self.setStatusTip(state["statusTip"])
        return True

    def isClosed(self):
        self._ensure_widget_api()
        return self._ui_closed

    def close(self):
        self._ensure_widget_api()
        if self._ui_closed:
            return False
        self._ui_closed = True
        _NATIVE_WIDGETS.discard(self)
        if self._ui_focus_manager is not None:
            self._ui_focus_manager.unregister(self)
            self._ui_focus_manager = None
        router_ref = getattr(self, "_ui_router_ref", None)
        router = router_ref() if router_ref is not None else None
        if router is not None:
            router.unregister(self)
        self._ui_observers.clear()
        for child in tuple(self._ui_children):
            child.close()
        delete = getattr(self, "Delete", None)
        if callable(delete):
            delete()
        self.destroyed.emit(self)
        return True

    def deleteLater(self):
        scheduler = self.renderScheduler()
        if scheduler is None:
            self.close()
        else:
            scheduler.defer(self.close)

