"""Keeping the UI in step with the window's display (size and DPI).

Two problems seen with VTK's Cocoa windows on mixed-DPI setups (a 1x
monitor and a 2x Retina panel, VTK 9.5):

* Moving a window to another display changes ``GetSize()`` (device
  pixels) and ``GetDPI()`` (72 to 144 and back) but often sends no
  ``WindowResizeEvent``/``ConfigureEvent``: layouts keep the old geometry
  while text, sized from the DPI, changes size. A manual resize "fixed"
  it.
* A window asked for larger than its screen is shrunk by macOS, but
  ``GetSize()`` keeps the requested size, so the first layout is made for
  a taller window and the top is cut off.

:class:`DisplayWatcher` compares the size and DPI at the start of every
render and, when they changed without a resize event, sends one (on the
next event-loop turn, then renders again): everything re-lays out as after
a manual resize. It also keeps the library's display density
(:func:`~multipanel._widget_support.device_scale`, window DPI / 72: 2 on a
Retina display) current, before anyone lays out, so logical-pixel sizes
keep their physical size from one display to another, as text (sized by
VTK from the DPI) does. :meth:`EventRouter.install
<multipanel.router.EventRouter.install>` installs one per window.
:func:`fit_window_to_screen` shrinks a requested size to the screen before
the window is first shown.
"""
from __future__ import annotations

import logging

from .core import Signal

logger = logging.getLogger(__name__)

# Room for the menu bar, title bar and a dock (points, at 72 DPI).
SCREEN_MARGIN_PT = (40, 120)


def fit_window_to_screen(render_window, margin=SCREEN_MARGIN_PT):
    """Shrink the window's requested size to fit its screen (minus
    ``margin`` points for the menu bar, title bar and dock); returns the
    size set. Call before the window is first rendered."""
    width, height = (int(v) for v in render_window.GetSize())
    screen_w, screen_h = (int(v) for v in render_window.GetScreenSize())
    if screen_w <= 0 or screen_h <= 0:
        return width, height
    scale = max(1.0, (render_window.GetDPI() or 72) / 72.0)
    fit_w = min(width, int(screen_w - margin[0] * scale))
    fit_h = min(height, int(screen_h - margin[1] * scale))
    fit_w, fit_h = max(200, fit_w), max(200, fit_h)
    if (fit_w, fit_h) != (width, height):
        logger.debug("window %sx%s fitted to screen %sx%s: %sx%s", width,
                     height, screen_w, screen_h, fit_w, fit_h)
        render_window.SetSize(fit_w, fit_h)
    return fit_w, fit_h


class DisplayWatcher:
    """Turns unannounced size/DPI changes into resize events.

    ``changed(size, dpi)`` is emitted after the resize events were sent.
    """

    _instances = {}

    def __init__(self, render_window, interactor=None):
        self.render_window = render_window
        self.interactor = interactor
        self.changed = Signal()
        self._known = self._state()
        self._pending = None
        self._sending = False
        self._apply_density()
        self._tags = [
            (render_window, render_window.AddObserver(
                "StartEvent", self._on_render, 100.0)),
            # Before anyone lays out for a real resize: the new density.
            (render_window, render_window.AddObserver(
                "WindowResizeEvent", self._apply_density, 1000.0)),
            # After everyone else has handled a real resize, remember it.
            (render_window, render_window.AddObserver(
                "WindowResizeEvent", self._on_resize, -100.0)),
        ]
        if interactor is not None:
            self._tags.append((interactor, interactor.AddObserver(
                "ConfigureEvent", self._apply_density, 1000.0)))
            self._tags.append((interactor, interactor.AddObserver(
                "ConfigureEvent", self._on_resize, -100.0)))

    @classmethod
    def install(cls, render_window, interactor=None):
        """The watcher of ``render_window``, created if needed."""
        watcher = cls._instances.get(render_window)
        if watcher is None:
            watcher = cls(render_window, interactor)
            cls._instances[render_window] = watcher
        return watcher

    @classmethod
    def uninstall(cls, render_window):
        watcher = cls._instances.pop(render_window, None)
        if watcher is not None:
            watcher.close()
        # The density follows the most recently watched window left (1 if
        # none), not the one just closed (e.g. between tests).
        if cls._instances:
            list(cls._instances.values())[-1]._apply_density()
        else:
            from ._widget_support import set_device_scale
            set_device_scale(1.0)

    def close(self):
        for obj, tag in self._tags:
            obj.RemoveObserver(tag)
        self._tags = []

    def _apply_density(self, *_):
        from ._widget_support import device_scale, set_device_scale

        density = max(1.0, (self.render_window.GetDPI() or 72) / 72.0)
        if density != device_scale():
            logger.debug("display density %s", density)
            set_device_scale(density)

    def _state(self):
        window = self.render_window
        return tuple(int(v) for v in window.GetSize()), window.GetDPI()

    def _on_resize(self, *_):
        if not self._sending:
            self._known = self._state()

    def _on_render(self, *_):
        state = self._state()
        if state == self._known or state == self._pending:
            return
        # Not during the render: re-layout on the next event-loop turn.
        self._pending = state
        from .core import RenderScheduler

        scheduler = RenderScheduler.for_window(self.render_window,
                                               self.interactor)
        scheduler.defer(self.sync)
        scheduler.request()

    def sync(self):
        """Send resize events if the size or DPI changed unannounced;
        returns True if it did."""
        self._pending = None
        state = self._state()
        if state == self._known:
            return False
        logger.debug("display changed: %s -> %s", self._known, state)
        self._known = state
        self._apply_density()
        self._sending = True
        try:
            self.render_window.InvokeEvent("WindowResizeEvent")
            if self.interactor is not None:
                self.interactor.InvokeEvent("ConfigureEvent")
        finally:
            self._sending = False
        self.changed.emit(*state)
        return True
