"""Property animations (``docs/QT_PARITY_PROPOSAL.md`` §12, W8).

``PropertyAnimation`` mirrors ``QPropertyAnimation``: it drives a property
(a ``setX`` method, a plain attribute, or any setter callable) from a start
value to an end value over a duration with an easing curve, on the W0
:class:`~multipanel.timer.Timer`::

    fade = PropertyAnimation(popup, "opacity", duration_ms=120,
                             easing="outCubic")
    fade.setStartValue(0.0)
    fade.setEndValue(1.0)
    fade.finished.connect(on_shown)
    fade.start()

Numbers and tuples/lists of numbers (colours, positions) interpolate
element-wise. ``set_animations_enabled(False)`` (or the environment
variable ``MULTIPANEL_ANIMATIONS=0``) makes every animation jump straight to
its end value, for remote sessions, screenshots and tests that do not want
to advance a clock. Animations started and not stored are kept alive until
they finish, as ``QAbstractAnimation.DeleteWhenStopped`` would.
"""
from __future__ import annotations

import math
import os
import time
import weakref

from .core import Signal
from .timer import Timer, VirtualClock

__all__ = [
    "EASINGS", "PropertyAnimation", "animate", "animations_enabled",
    "set_animations_enabled",
]

FRAME_MS = 16


def _out_back(t):
    c1 = 1.70158
    return 1 + (c1 + 1) * (t - 1) ** 3 + c1 * (t - 1) ** 2


EASINGS = {
    "linear": lambda t: t,
    "inQuad": lambda t: t * t,
    "outQuad": lambda t: 1 - (1 - t) * (1 - t),
    "inOutQuad": lambda t: 2 * t * t if t < 0.5 else 1 - (-2 * t + 2) ** 2 / 2,
    "inCubic": lambda t: t ** 3,
    "outCubic": lambda t: 1 - (1 - t) ** 3,
    "inOutCubic": lambda t: 4 * t ** 3 if t < 0.5
    else 1 - (-2 * t + 2) ** 3 / 2,
    "inOutSine": lambda t: -(math.cos(math.pi * t) - 1) / 2,
    "outBack": _out_back,
}

_ENABLED = {"value": os.environ.get("MULTIPANEL_ANIMATIONS", "1").strip()
            .lower() not in ("0", "off", "false", "no")}


def animations_enabled():
    return _ENABLED["value"]


def set_animations_enabled(enabled):
    """Globally enable or disable animations (disabled: jump to the end)."""
    _ENABLED["value"] = bool(enabled)


def _interpolate(start, end, progress):
    if isinstance(start, (tuple, list)):
        values = [_interpolate(a, b, progress) for a, b in zip(start, end)]
        return type(start)(values)
    return start + (end - start) * progress


def _setter_name(name):
    return "set" + name[:1].upper() + name[1:]


class PropertyAnimation:
    """Animate ``target``'s property ``name`` (see the module docstring).

    ``name`` may also be a callable ``setter(value)``; then pass
    ``interactor=`` (and ``start_value=``) since nothing can be read from it.
    Each step requests a render unless ``request_render=False`` (for
    setters that render themselves only when needed).
    """

    STOPPED, PAUSED, RUNNING = "stopped", "paused", "running"
    FORWARD, BACKWARD = "forward", "backward"

    _running = set()            # keeps fire-and-forget animations alive

    def __init__(self, target=None, name=None, duration_ms=250,
                 easing="inOutQuad", start_value=None, end_value=None,
                 interactor=None, loop_count=1, request_render=True):
        self._target_ref = None if target is None else _ref(target)
        self._name = name
        self._duration = max(0.0, float(duration_ms))
        self._easing = None
        self.setEasingCurve(easing)
        self._start_value = start_value
        self._end_value = end_value
        self._loops = int(loop_count)
        # False when the setter requests renders itself (and may skip them,
        # e.g. while the target is hidden).
        self._request_renders = bool(request_render)
        self._direction = self.FORWARD
        self._state = self.STOPPED
        self._current_value = None
        self._current_loop = 0
        self._started_at = 0.0
        self._paused_elapsed = 0.0
        self._from = None
        interactor = interactor if interactor is not None else \
            getattr(target, "interactor", None)
        if interactor is None:
            raise ValueError("PropertyAnimation needs an interactor (pass "
                             "interactor= or animate a widget)")
        self._interactor_ref = weakref.ref(interactor)
        self._timer = Timer(interactor, FRAME_MS)
        self._timer.timeout.connect(self._tick)
        self.valueChanged = Signal()
        self.finished = Signal()
        self.stateChanged = Signal()
        if target is not None and hasattr(target, "destroyed"):
            target.destroyed.connect(lambda *_: self.stop())

    # -- configuration --------------------------------------------------------------
    def targetObject(self):
        return None if self._target_ref is None else self._target_ref()

    def propertyName(self):
        return self._name if isinstance(self._name, str) else None

    def duration(self):
        return self._duration

    def setDuration(self, duration_ms):
        self._duration = max(0.0, float(duration_ms))

    def easingCurve(self):
        return self._easing

    def setEasingCurve(self, easing):
        if callable(easing):
            self._easing = easing
        elif easing in EASINGS:
            self._easing = EASINGS[easing]
        else:
            raise ValueError(f"unknown easing {easing!r}; "
                             f"use one of {sorted(EASINGS)} or a callable")

    def startValue(self):
        return self._start_value

    def setStartValue(self, value):
        self._start_value = value

    def endValue(self):
        return self._end_value

    def setEndValue(self, value):
        self._end_value = value

    def loopCount(self):
        return self._loops

    def setLoopCount(self, count):
        """Number of loops; ``-1`` runs until stopped."""
        self._loops = int(count)

    def currentLoop(self):
        return self._current_loop

    def direction(self):
        return self._direction

    def setDirection(self, direction):
        if direction not in (self.FORWARD, self.BACKWARD):
            raise ValueError("direction must be 'forward' or 'backward'")
        self._direction = direction

    def state(self):
        return self._state

    def currentValue(self):
        return self._current_value

    # -- property access ------------------------------------------------------------------
    def _read(self):
        target = self.targetObject()
        if target is None or not isinstance(self._name, str):
            return None
        value = getattr(target, self._name, None)
        return value() if callable(value) else value

    def _write(self, value):
        self._current_value = value
        if callable(self._name):
            self._name(value)
        else:
            target = self.targetObject()
            if target is None:
                self.stop()
                return
            setter = getattr(target, _setter_name(self._name), None)
            if callable(setter):
                setter(value)
            else:
                setattr(target, self._name, value)
        self.valueChanged.emit(value)
        if self._request_renders:
            self._request_render()

    def _request_render(self):
        target = self.targetObject()
        request = getattr(target, "requestRender", None)
        if callable(request):
            request()
            return
        interactor = self._interactor_ref()
        if interactor is None:
            return
        from .core import RenderScheduler

        window = interactor.GetRenderWindow()
        if window is not None:
            RenderScheduler.for_window(window, interactor).request()

    # -- control --------------------------------------------------------------------------
    def _now(self):
        clock = VirtualClock.for_interactor(self._interactor_ref())
        return clock.now() if clock is not None else time.monotonic() * 1000.0

    def _set_state(self, state):
        if state != self._state:
            old, self._state = self._state, state
            self.stateChanged.emit(state, old)

    def start(self):
        """Start (or restart) from the start value (current value if unset)."""
        if self._end_value is None:
            raise ValueError("set an end value before starting")
        self._timer.stop()
        start = self._start_value
        if start is None:
            start = self._read()
        if start is None:
            raise ValueError(f"cannot read {self._name!r}; set a start value")
        self._from = start
        self._current_loop = 0
        if not animations_enabled() or self._duration <= 0:
            self._write(self._end_value if self._direction == self.FORWARD
                        else start)
            self._set_state(self.STOPPED)
            self.finished.emit()
            return
        PropertyAnimation._running.add(self)
        self._started_at = self._now()
        self._set_state(self.RUNNING)
        self._write(self._value_at(0.0))
        self._timer.start()

    def pause(self):
        if self._state == self.RUNNING:
            self._timer.stop()
            self._paused_elapsed = self._now() - self._started_at
            self._set_state(self.PAUSED)

    def resume(self):
        if self._state == self.PAUSED:
            self._started_at = self._now() - self._paused_elapsed
            self._set_state(self.RUNNING)
            self._timer.start()

    def stop(self):
        """Stop where it is (no ``finished``, as in Qt)."""
        self._timer.stop()
        PropertyAnimation._running.discard(self)
        self._set_state(self.STOPPED)

    def _value_at(self, progress):
        if self._direction == self.BACKWARD:
            progress = 1.0 - progress
        return _interpolate(self._from, self._end_value,
                            self._easing(max(0.0, min(1.0, progress))))

    def _tick(self):
        if self._state != self.RUNNING:
            return
        elapsed = self._now() - self._started_at
        loops_done = int(elapsed // self._duration)
        if self._loops >= 0 and loops_done >= self._loops:
            self._timer.stop()
            self._current_loop = max(0, self._loops - 1)
            self._write(self._value_at(1.0))
            PropertyAnimation._running.discard(self)
            self._set_state(self.STOPPED)
            self.finished.emit()
            return
        self._current_loop = loops_done
        self._write(self._value_at((elapsed % self._duration)
                                   / self._duration))


def _ref(target):
    try:
        return weakref.ref(target)
    except TypeError:            # not weak-referenceable: hold it strongly
        return lambda: target


def animate(target, name, end_value, duration_ms=150, easing="outCubic",
            **options):
    """Start and return a :class:`PropertyAnimation` to ``end_value``."""
    animation = PropertyAnimation(target, name, duration_ms=duration_ms,
                                  easing=easing, end_value=end_value,
                                  **options)
    animation.start()
    return animation
