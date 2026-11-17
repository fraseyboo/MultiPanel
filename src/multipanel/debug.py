"""Widget inspector and hierarchy dump (``docs/QT_PARITY_PROPOSAL.md`` §14, W10).

::

    from multipanel.debug import Inspector, dump_tree

    inspector = Inspector(interactor)     # Ctrl+Alt+I toggles it
    print(dump_tree(interactor))          # the widget hierarchy as text

While the inspector is on, the widget under the pointer is outlined (its
parent more faintly) and a box beside the pointer shows its class,
``objectName``, geometry in logical px, size hints, size policy, style
state and z-order. It only observes: clicks and keys still reach the UI.
"""
from __future__ import annotations

import vtk

from ._widget_support import apply_ui_font, font_scale, ui_layer, ui_scale
from .core import RenderScheduler, WidgetMixin
from .router import EventRouter
from .style import _outline
from .vtk_compat import add_actor_2d, remove_actor_2d

__all__ = ["Inspector", "describe", "dump_tree"]

HIGHLIGHT = (1.0, 0.25, 0.6)          # magenta: unlike any theme colour
PARENT = (0.55, 0.55, 0.6)


# ---------------------------------------------------------------------------------------
# Describing widgets


def _call(widget, name, *args):
    method = getattr(widget, name, None)
    if not callable(method):
        return None
    try:
        return method(*args)
    except Exception:            # inspecting must never break the UI
        return None


def _fmt(values):
    if values is None:
        return "-"
    return "(" + ", ".join(f"{v:g}" for v in values) + ")"


def _policy(widget):
    policy = _call(widget, "sizePolicy")
    if policy is None:
        return None
    names = {}
    for name in ("Fixed", "Minimum", "Maximum", "Preferred", "Expanding",
                 "MinimumExpanding", "Ignored"):
        value = getattr(type(policy), name, None)
        if value is not None:
            names.setdefault(value, name)
    horizontal = getattr(policy, "horizontal", None)
    vertical = getattr(policy, "vertical", None)
    if horizontal is None or vertical is None:
        return None
    return f"{names.get(horizontal, horizontal)}/{names.get(vertical, vertical)}"


def _name(widget):
    name = _call(widget, "objectName")
    return f"{type(widget).__name__} {name!r}" if name else \
        type(widget).__name__


def describe(widget):
    """One block of text describing ``widget`` (what the inspector shows)."""
    lines = [_name(widget)]
    geometry = _call(widget, "geometry", "px")
    lines.append(f"geometry {_fmt(geometry)} px")
    hint, minimum = _call(widget, "sizeHint"), _call(widget, "minimumSizeHint")
    if hint is not None:
        lines.append(f"sizeHint {_fmt(hint)}  min {_fmt(minimum)}")
    policy = _policy(widget)
    if policy:
        lines.append(f"policy {policy}")
    states = _call(widget, "styleState")
    if states:
        lines.append("state " + ", ".join(sorted(states)))
    z_order = _call(widget, "uiZOrder")
    flags = []
    if z_order is not None:
        flags.append(f"z {z_order}")
    if _call(widget, "isVisible") is False:
        flags.append("hidden")
    if isinstance(widget, WidgetMixin) and not widget.isEventNative():
        flags.append("legacy input")
    if flags:
        lines.append("  ".join(flags))
    tip = _call(widget, "toolTip")
    if tip:
        lines.append(f"toolTip {tip!r}")
    return "\n".join(lines)


def _children(widget):
    children = _call(widget, "children")
    return list(children) if children else []


def dump_tree(interactor, stream=None):
    """The widget hierarchy of ``interactor`` as indented text.

    Top-level widgets come in the router's stacking order (topmost
    first). Also written to ``stream`` when given.
    """
    router = EventRouter.install(interactor)
    lines = []

    def visit(widget, depth, seen):
        if id(widget) in seen:
            return
        seen.add(id(widget))
        geometry = _call(widget, "geometry", "px")
        hidden = "" if _call(widget, "isVisible") is not False else " hidden"
        lines.append(f"{'  ' * depth}{_name(widget)} {_fmt(geometry)}{hidden}")
        for child in _children(widget):
            visit(child, depth + 1, seen)

    # The router knows the widgets that take input; their containers
    # (frames, splitters) need not be registered, so start from the
    # topmost ancestor of each.
    roots, root_ids = [], set()
    for widget in router._stacking(router._candidates()):
        root = widget
        parent = _call(root, "parentWidget")
        while parent is not None:
            root = parent
            parent = _call(root, "parentWidget")
        if id(root) not in root_ids:
            root_ids.add(id(root))
            roots.append(root)
    seen = set()
    for top in roots:
        visit(top, 0, seen)
    text = "\n".join(lines)
    if stream is not None:
        stream.write(text + "\n")
    return text


# ---------------------------------------------------------------------------------------
# The inspector overlay


class Inspector:
    """Outline and describe the widget under the pointer (Ctrl+Alt+I)."""

    MARGIN = 12

    def __init__(self, interactor, renderer=None, shortcut="Ctrl+Alt+I",
                 enabled=False):
        from .actions import Shortcut

        self.interactor = interactor
        self._router = EventRouter.install(interactor)
        if renderer is None:
            renderer = interactor.GetRenderWindow().GetRenderers()\
                .GetFirstRenderer()
        self.renderer = renderer
        self._enabled = False
        self._target = None
        self._layer = None
        self._outline_actor = None
        self._text_actor = None
        self._observers = [interactor.AddObserver(
            "MouseMoveEvent", self._on_move, 2.0)]
        self._shortcut = None
        if shortcut:
            self._shortcut = Shortcut(shortcut, interactor)
            self._shortcut.activated.connect(self.toggle)
        if enabled:
            self.setEnabled(True)

    # -- state --------------------------------------------------------------------------
    def isEnabled(self):
        return self._enabled

    def setEnabled(self, enabled):
        enabled = bool(enabled)
        if enabled == self._enabled:
            return
        self._enabled = enabled
        if enabled:
            self._ensure_actors()
            self.inspectAt(*self.interactor.GetEventPosition())
        else:
            self._target = None
            self._hide()

    def toggle(self):
        self.setEnabled(not self._enabled)

    def inspected(self):
        """The widget currently outlined, or None."""
        return self._target

    # -- drawing --------------------------------------------------------------------------
    def _ensure_actors(self):
        from .layers import popup_layer

        layer = popup_layer(ui_layer(self.renderer))
        if self._layer is layer and self._outline_actor is not None:
            return
        self._remove_actors()
        self._layer = layer
        mapper = vtk.vtkPolyDataMapper2D()
        mapper.SetColorModeToDirectScalars()
        mapper.SetScalarModeToUsePointData()
        self._outline_actor = vtk.vtkActor2D()
        self._outline_actor.SetMapper(mapper)
        self._outline_actor.GetProperty().SetLineWidth(2.0)
        self._text_actor = vtk.vtkTextActor()
        text = self._text_actor.GetTextProperty()
        apply_ui_font(text)
        text.SetFontSize(max(9, int(round(11 * font_scale()))))
        text.SetColor(1.0, 1.0, 1.0)
        text.SetBackgroundColor(0.1, 0.1, 0.12)
        text.SetBackgroundOpacity(0.92)
        text.SetFrame(True)
        text.SetFrameColor(*HIGHLIGHT)
        text.SetJustificationToLeft()
        text.SetVerticalJustificationToBottom()
        for actor in (self._outline_actor, self._text_actor):
            actor.IsUI = True
            actor.PickableOff()
            actor.SetVisibility(False)
            add_actor_2d(layer, actor)

    def _remove_actors(self):
        if self._layer is not None:
            for actor in (self._outline_actor, self._text_actor):
                if actor is not None:
                    remove_actor_2d(self._layer, actor)
        self._outline_actor = self._text_actor = self._layer = None

    def _hide(self):
        for actor in (self._outline_actor, self._text_actor):
            if actor is not None:
                actor.SetVisibility(False)
        self._render()

    def _render(self):
        window = self.interactor.GetRenderWindow()
        if window is not None:
            RenderScheduler.for_window(window, self.interactor).request()

    def _on_move(self, caller=None, _event=None):
        if self._enabled:
            self.inspectAt(*self.interactor.GetEventPosition())

    def inspectAt(self, x, y):
        """Outline the widget at display point ``(x, y)``; returns it."""
        chain = self._router.hitChain(x, y)
        target = chain[0] if chain else None
        self._target = target
        if target is None:
            self._hide()
            return None
        self._ensure_actors()
        outlines = []
        for widget, color in ((chain[1] if len(chain) > 1 else None, PARENT),
                              (target, HIGHLIGHT)):
            rect = _call(widget, "geometry", "display") if widget else None
            if rect is None or rect[2] <= 0 or rect[3] <= 0:
                continue
            ox, oy = self._layer_origin()
            rgba = tuple(int(255 * c) for c in color) + (255,)
            outlines.append(_outline(rect[0] - ox, rect[1] - oy, rect[2],
                                     rect[3], 0.0, rgba))
        if outlines:
            append = vtk.vtkAppendPolyData()
            for polydata in outlines:
                append.AddInputData(polydata)
            append.Update()
            data = vtk.vtkPolyData()
            data.DeepCopy(append.GetOutput())
            self._outline_actor.GetMapper().SetInputData(data)
            self._outline_actor.SetVisibility(True)
        else:
            self._outline_actor.SetVisibility(False)
        self._place_text(describe(target), x, y)
        self._render()
        return target

    def _layer_origin(self):
        window = self.interactor.GetRenderWindow()
        width, height = window.GetSize()[:2]
        viewport = self._layer.GetViewport()
        return viewport[0] * width, viewport[1] * height

    def _place_text(self, text, x, y):
        # A space either side of each line pads the framed background.
        text = "\n".join(f" {line} " for line in text.splitlines())
        actor = self._text_actor
        actor.SetInput(text)
        box = [0, 0, 0, 0]
        window = self.interactor.GetRenderWindow()
        vtk.vtkTextRenderer.GetInstance().GetBoundingBox(
            actor.GetTextProperty(), text, box, max(1, window.GetDPI()))
        text_w, text_h = box[1] - box[0] + 1, box[3] - box[2] + 1
        width, height = window.GetSize()[:2]
        margin = self.MARGIN * ui_scale()
        tx = x + margin if x + margin + text_w < width else x - margin - text_w
        ty = y + margin if y + margin + text_h < height else y - margin - text_h
        ox, oy = self._layer_origin()
        actor.SetPosition(max(0.0, tx) - ox, max(0.0, ty) - oy)
        actor.SetVisibility(True)

    # -- teardown ------------------------------------------------------------------------
    def close(self):
        for observer in self._observers:
            self.interactor.RemoveObserver(observer)
        self._observers = []
        if self._shortcut is not None:
            self._shortcut.release()
            self._shortcut = None
        self._remove_actors()
        self._enabled = False
