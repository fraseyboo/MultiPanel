"""Frame-rate and render-cost profiler for the VTK scene and its 2D UI.

Attach to a render window to measure every ``Render()``:

* frame time (start -> end of each render) and frames per second;
* how many renders happen per second, including while the scene is idle --
  ideally zero when nothing changes, so a non-zero idle rate exposes
  unnecessary renders;
* time spent in the Python ``Paint`` callbacks of the 2D UI widgets, per
  widget type, via the :func:`profiled_paint` decorator.

Usage::

    from LIBS.render_profiler import RenderProfiler
    profiler = RenderProfiler.attach(render_window, renderer)   # F3 toggles
    profiler.set_overlay_visible(True)
    print(profiler.report())

The overlay text is refreshed from the end-of-render callback and never
requests a render itself, so enabling it does not change what it measures.
Set ``MULTIPANEL_RENDER_PROFILER=1`` to show it at start-up.
"""
from __future__ import annotations

import collections
import functools
import os
import time

import vtk

_active = None          # the profiler instance collecting paint timings


def profiled_paint(name):
    """Decorate a 2D painter's ``Paint`` so its cost is attributed to *name*.

    Costs one global lookup when no profiler is attached.
    """
    def decorate(paint):
        @functools.wraps(paint)
        def wrapper(*args, **kwargs):
            profiler = _active
            if profiler is None or not profiler.collecting:
                return paint(*args, **kwargs)
            start = time.perf_counter()
            try:
                return paint(*args, **kwargs)
            finally:
                profiler._record_paint(name, time.perf_counter() - start)
        return wrapper
    return decorate


class RenderProfiler:
    """Measure render frequency and cost for one render window."""

    WINDOW_SECONDS = 2.0     # rolling window for the overlay statistics
    OVERLAY_HZ = 4.0

    def __init__(self, render_window, renderer=None):
        self.render_window = render_window
        self.renderer = renderer
        self.collecting = True
        self._frame_start = None
        self._frames = collections.deque()      # (end_time, duration)
        self._frame_paint = collections.Counter()
        self._frame_paint_calls = collections.Counter()
        self._paint_totals = collections.Counter()
        self._paint_calls = collections.Counter()
        self._window_paint = collections.deque()  # (end_time, {name: secs}, {name: calls})
        self.total_frames = 0
        self.total_render_seconds = 0.0
        self._last_overlay = 0.0
        self.overlay = None
        self._observers = [
            render_window.AddObserver("StartEvent", self._on_start, 10000.0),
            render_window.AddObserver("EndEvent", self._on_end, -10000.0),
        ]

    # ---- attaching -----------------------------------------------------
    @classmethod
    def attach(cls, render_window, renderer=None, interactor=None,
               toggle_key="F3"):
        """Create the profiler, make it the active one and bind *toggle_key*."""
        global _active
        profiler = cls(render_window, renderer)
        _active = profiler
        render_window.render_profiler = profiler
        interactor = interactor or render_window.GetInteractor()
        if interactor is not None and toggle_key:
            def on_key(caller, _event):
                if caller.GetKeySym() == toggle_key:
                    profiler.set_overlay_visible(not profiler.overlay_visible)
                    render_window.Render()
            interactor.AddObserver("KeyPressEvent", on_key, 50.0)
        if renderer is not None and os.environ.get(
                "MULTIPANEL_RENDER_PROFILER", "").strip().lower() in {"1", "true", "yes", "on"}:
            profiler.set_overlay_visible(True)
        return profiler

    def detach(self):
        global _active
        for tag in self._observers:
            self.render_window.RemoveObserver(tag)
        self._observers = []
        if _active is self:
            _active = None
        if self.overlay is not None and self.renderer is not None:
            self.renderer.RemoveActor2D(self.overlay)

    # ---- collection ----------------------------------------------------
    def _record_paint(self, name, seconds):
        self._frame_paint[name] += seconds
        self._frame_paint_calls[name] += 1

    def _on_start(self, *_args):
        self._frame_start = time.perf_counter()
        self._frame_paint = collections.Counter()
        self._frame_paint_calls = collections.Counter()

    def _on_end(self, *_args):
        if self._frame_start is None:
            return
        now = time.perf_counter()
        duration = now - self._frame_start
        self._frame_start = None
        self.total_frames += 1
        self.total_render_seconds += duration
        self._frames.append((now, duration))
        self._window_paint.append(
            (now, self._frame_paint, self._frame_paint_calls))
        self._paint_totals.update(self._frame_paint)
        self._paint_calls.update(self._frame_paint_calls)
        cutoff = now - self.WINDOW_SECONDS
        while self._frames and self._frames[0][0] < cutoff:
            self._frames.popleft()
        while self._window_paint and self._window_paint[0][0] < cutoff:
            self._window_paint.popleft()
        if (self.overlay is not None and self.overlay.GetVisibility() and
                now - self._last_overlay >= 1.0 / self.OVERLAY_HZ):
            self._last_overlay = now
            # Shown on the next render; setting text does not render.
            self.overlay.SetInput(self.summary_text())

    # ---- statistics ----------------------------------------------------
    def window_stats(self):
        """Statistics over the last ``WINDOW_SECONDS`` of renders."""
        now = time.perf_counter()
        frames = [d for t, d in self._frames if t >= now - self.WINDOW_SECONDS]
        paint = collections.Counter()
        calls = collections.Counter()
        for t, seconds, count in self._window_paint:
            if t >= now - self.WINDOW_SECONDS:
                paint.update(seconds)
                calls.update(count)
        n = len(frames)
        span = self.WINDOW_SECONDS
        return {
            "renders_per_second": n / span,
            "frames": n,
            "mean_ms": 1000.0 * sum(frames) / n if n else 0.0,
            "max_ms": 1000.0 * max(frames) if n else 0.0,
            "paint_ms_per_frame": {k: 1000.0 * v / n for k, v in paint.items()} if n else {},
            "paint_calls_per_frame": {k: v / n for k, v in calls.items()} if n else {},
        }

    def summary_text(self):
        s = self.window_stats()
        achievable = 1000.0 / s["mean_ms"] if s["mean_ms"] else 0.0
        lines = [
            f"renders/s {s['renders_per_second']:5.1f}   "
            f"frame {s['mean_ms']:5.1f} ms (max {s['max_ms']:5.1f})   "
            f"~{achievable:4.0f} fps possible",
        ]
        paint = s["paint_ms_per_frame"]
        if paint:
            total = sum(paint.values())
            lines.append(f"2D UI paint {total:5.1f} ms/frame "
                         f"({100.0 * total / s['mean_ms']:3.0f}% of frame)"
                         if s["mean_ms"] else "")
            for name, ms in sorted(paint.items(), key=lambda kv: -kv[1])[:5]:
                calls = s["paint_calls_per_frame"].get(name, 0)
                lines.append(f"  {name:<24s}{ms:6.2f} ms  x{calls:4.0f}")
        return "\n".join(lines)

    def report(self):
        """Totals since attaching, as plain text."""
        frames = max(self.total_frames, 1)
        lines = [f"frames: {self.total_frames}   mean frame: "
                 f"{1000.0 * self.total_render_seconds / frames:.2f} ms"]
        paint_total = sum(self._paint_totals.values())
        lines.append(f"2D UI paint: {1000.0 * paint_total / frames:.2f} ms/frame")
        for name, secs in sorted(self._paint_totals.items(), key=lambda kv: -kv[1]):
            lines.append(f"  {name:<24s}{1000.0 * secs / frames:7.3f} ms/frame  "
                         f"{self._paint_calls[name] / frames:6.1f} calls/frame")
        return "\n".join(lines)

    def reset(self):
        self._frames.clear()
        self._window_paint.clear()
        self._paint_totals.clear()
        self._paint_calls.clear()
        self.total_frames = 0
        self.total_render_seconds = 0.0

    # ---- overlay -------------------------------------------------------
    @property
    def overlay_visible(self):
        return self.overlay is not None and bool(self.overlay.GetVisibility())

    def set_overlay_visible(self, visible):
        if self.renderer is None:
            return
        if self.overlay is None:
            text = vtk.vtkTextActor()
            text.IsUI = True
            text.PickableOff()
            prop = text.GetTextProperty()
            prop.SetFontFamilyToCourier()
            prop.SetFontSize(13)
            prop.SetColor(0.2, 1.0, 0.4)
            prop.SetBackgroundColor(0.0, 0.0, 0.0)
            prop.SetBackgroundOpacity(0.6)
            # Bottom centre, above the progress bar and clear of the side
            # panes and the viewport controls.
            prop.SetVerticalJustificationToBottom()
            prop.SetJustificationToCentered()
            text.GetPositionCoordinate().SetCoordinateSystemToNormalizedViewport()
            text.SetPosition(0.5, 0.08)
            text.SetInput("profiling…")
            self.renderer.AddActor2D(text)
            self.overlay = text
        self.overlay.SetVisibility(bool(visible))
