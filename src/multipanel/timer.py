"""Qt-style timers on top of VTK interactor timers, with a virtual clock.

``Timer`` mirrors ``QTimer``::

    blink = Timer(interactor, interval_ms=500)
    blink.timeout.connect(toggle_caret)
    blink.start()

    Timer.singleShot(interactor, 250, show_tooltip)

Backends, in order of preference:

* a :class:`VirtualClock` installed on the interactor (tests, headless);
* Qt's ``QTimer`` when a Qt application is running (the binding must already
  be imported by the host; this module never imports Qt). Qt's
  ``QVTKRenderWindowInteractor`` runs every VTK timer on one shared 10 ms
  ``QTimer``: durations are ignored, the reported timer id is the last one
  created, and destroying any timer stops all of them;
* the interactor's ``CreateRepeatingTimer``/``CreateOneShotTimer``, which
  native VTK interactors implement properly.  Tests (and any headless host)
install a :class:`VirtualClock` on the interactor instead; timers then fire
only when the clock is advanced, deterministically and in due-time order.
"""
from __future__ import annotations

import heapq
import itertools
import weakref

import sys

from .core import Signal, timer_observer

__all__ = ["Timer", "VirtualClock", "qt_core"]

_QT_CORE_MODULES = ("PyQt5.QtCore", "PyQt6.QtCore", "PySide6.QtCore",
                    "PySide2.QtCore")


def qt_core():
    """Return the host's Qt core module while a Qt application runs.

    Only bindings the host has already imported are considered, so the
    library itself never imports Qt.
    """
    for name in _QT_CORE_MODULES:
        module = sys.modules.get(name)
        if module is None:
            continue
        try:
            if module.QCoreApplication.instance() is not None:
                return module
        except Exception:          # partially initialised binding
            continue
    return None


class VirtualClock:
    """A manually advanced clock that drives timers for one interactor."""

    _instances = weakref.WeakKeyDictionary()

    def __init__(self, start_ms=0.0):
        self._now = float(start_ms)
        self._queue = []
        self._sequence = itertools.count()
        self._cancelled = set()

    # -- installation ----------------------------------------------------
    @classmethod
    def install(cls, interactor, clock=None):
        """Route all timers on ``interactor`` through ``clock``."""
        clock = cls() if clock is None else clock
        cls._instances[interactor] = clock
        return clock

    @classmethod
    def uninstall(cls, interactor):
        return cls._instances.pop(interactor, None)

    @classmethod
    def for_interactor(cls, interactor):
        if interactor is None:
            return None
        try:
            return cls._instances.get(interactor)
        except TypeError:   # not weak-referenceable
            return None

    # -- scheduling --------------------------------------------------------
    def now(self):
        return self._now

    def call_at(self, due_ms, callback):
        handle = next(self._sequence)
        heapq.heappush(self._queue, (float(due_ms), handle, callback))
        return handle

    def call_later(self, delay_ms, callback):
        return self.call_at(self._now + max(0.0, float(delay_ms)), callback)

    def cancel(self, handle):
        self._cancelled.add(handle)

    def pending(self):
        return sum(1 for _due, handle, _cb in self._queue
                   if handle not in self._cancelled)

    def advance(self, ms=0.0):
        """Advance by ``ms`` and run every callback that falls due.

        Callbacks scheduled while advancing run in the same call if they are
        due by the target time, so zero-delay chains are drained.  Returns
        the number of callbacks run.
        """
        target = self._now + max(0.0, float(ms))
        ran = 0
        while self._queue and self._queue[0][0] <= target:
            due, handle, callback = heapq.heappop(self._queue)
            if handle in self._cancelled:
                self._cancelled.discard(handle)
                continue
            self._now = max(self._now, due)
            callback()
            ran += 1
            if ran > 100000:
                raise RuntimeError("timer callbacks did not settle")
        self._now = target
        return ran


class _VtkTimerHub:
    """One ``TimerEvent`` observer per interactor, dispatching by timer id."""

    _instances = weakref.WeakKeyDictionary()

    def __init__(self, interactor):
        self._interactor_ref = weakref.ref(interactor)
        self._timers = {}
        self._tag = interactor.AddObserver(
            "TimerEvent", timer_observer(self._on_timer), 50.0)

    @classmethod
    def for_interactor(cls, interactor):
        hub = cls._instances.get(interactor)
        if hub is None:
            hub = cls(interactor)
            cls._instances[interactor] = hub
        return hub

    def create(self, timer, interval_ms, single_shot):
        interactor = self._interactor_ref()
        if interactor is None:
            return None
        interval = max(1, int(round(interval_ms)))
        timer_id = (interactor.CreateOneShotTimer(interval) if single_shot
                    else interactor.CreateRepeatingTimer(interval))
        if timer_id is None or timer_id < 0:
            return None
        self._timers[timer_id] = weakref.ref(timer)
        return timer_id

    def destroy(self, timer_id):
        self._timers.pop(timer_id, None)
        interactor = self._interactor_ref()
        if interactor is not None:
            interactor.DestroyTimer(timer_id)

    def _on_timer(self, caller, timer_id):
        reference = self._timers.get(timer_id)
        timer = None if reference is None else reference()
        if timer is None:
            return
        timer._fire()


class Timer:
    """A repeating or single-shot timer with a ``timeout`` signal."""

    _keepalive = set()

    def __init__(self, interactor, interval_ms=0, single_shot=False,
                 parent=None):
        self._interactor_ref = weakref.ref(interactor)
        self._interval = max(0.0, float(interval_ms))
        self._single_shot = bool(single_shot)
        self._active = False
        self._vtk_id = None
        self._clock_handle = None
        self._qt_timer = None
        self._parent = parent
        # A parent widget being destroyed stops the timer, as in Qt.
        self.timeout = Signal()
        if parent is not None and hasattr(parent, "destroyed"):
            parent.destroyed.connect(lambda *_: self.stop())

    @classmethod
    def singleShot(cls, interactor, interval_ms, callback):
        """Call ``callback`` once after ``interval_ms``. Returns the timer."""
        timer = cls(interactor, interval_ms, single_shot=True)
        timer.timeout.connect(callback)
        cls._keepalive.add(timer)
        timer.timeout.connect(lambda: cls._keepalive.discard(timer))
        timer.start()
        return timer

    # -- properties ----------------------------------------------------------
    def interval(self):
        return self._interval

    def setInterval(self, interval_ms):
        self._interval = max(0.0, float(interval_ms))
        if self._active:
            self.start()

    def isSingleShot(self):
        return self._single_shot

    def setSingleShot(self, single_shot):
        self._single_shot = bool(single_shot)
        if self._active:
            self.start()

    def isActive(self):
        return self._active

    # -- control -----------------------------------------------------------
    def start(self, interval_ms=None):
        """(Re)start the timer, optionally with a new interval."""
        if interval_ms is not None:
            self._interval = max(0.0, float(interval_ms))
        self._cancel()
        interactor = self._interactor_ref()
        if interactor is None:
            self._active = False
            return
        self._active = True
        clock = VirtualClock.for_interactor(interactor)
        if clock is not None:
            first = self._interval if self._single_shot else max(
                self._interval, 1.0)
            self._clock_handle = clock.call_later(first, self._fire)
            return
        qt = qt_core()
        if qt is not None:
            timer = qt.QTimer()
            timer.setSingleShot(self._single_shot)
            timer.setInterval(int(round(self._interval if self._single_shot
                                        else max(self._interval, 1.0))))
            timer.timeout.connect(self._fire)
            timer.start()
            self._qt_timer = timer
            return
        self._vtk_id = _VtkTimerHub.for_interactor(interactor).create(
            self, self._interval, self._single_shot)
        if self._vtk_id is None:
            self._active = False

    def stop(self):
        self._cancel()
        self._active = False
        Timer._keepalive.discard(self)

    def _cancel(self):
        interactor = self._interactor_ref()
        if self._qt_timer is not None:
            self._qt_timer.stop()
            self._qt_timer = None
        if self._clock_handle is not None:
            clock = VirtualClock.for_interactor(interactor)
            if clock is not None:
                clock.cancel(self._clock_handle)
            self._clock_handle = None
        if self._vtk_id is not None:
            if interactor is not None:
                _VtkTimerHub.for_interactor(interactor).destroy(self._vtk_id)
            self._vtk_id = None

    def _fire(self):
        if not self._active:
            return
        self._clock_handle = None
        if self._single_shot:
            self._active = False
            self._qt_timer = None
            if self._vtk_id is not None:
                interactor = self._interactor_ref()
                if interactor is not None:
                    _VtkTimerHub.for_interactor(interactor)._timers.pop(
                        self._vtk_id, None)
                self._vtk_id = None
        else:
            interactor = self._interactor_ref()
            clock = VirtualClock.for_interactor(interactor)
            if clock is not None:
                # Repeat relative to the scheduled time, like a real timer.
                self._clock_handle = clock.call_later(
                    max(self._interval, 1.0), self._fire)
        self.timeout.emit()
