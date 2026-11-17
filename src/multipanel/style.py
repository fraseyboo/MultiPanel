"""State-based colours and the keyboard focus ring (§11 of the proposal).

Widgets ask the renderer's :class:`Style` for colours by *role* (``button``,
``field``, ``indicator``, ``menu_item``, ``progress``, ``scrollbar``,
``text``), *part* (``background``, ``border``, ``text``, ``mark``, ``fill``,
``handle``) and their current
*states* (``hover``, ``pressed``, ``focus``, ``disabled``, ``checked``,
``default``, ``active``, ``open``) instead of picking theme tokens
themselves, so every control reacts to state the same way. Hosts can
override a colour for one widget or for everything::

    style = Style.for_renderer(renderer)
    style.setOverride("#place_button", "button", "background", (0.8, 0.2, 0.2))
    style.setOverride("*", "field", "border", (0.5, 0.5, 0.5), states={"focus"})

The :class:`FocusRing` outlines the focused widget only after keyboard
navigation (Tab/Shift-Tab), never after a mouse click or while a text field
is editing; it follows the widget through layout changes and hides with it.
"""
from __future__ import annotations

import weakref

import vtk

from ._widget_support import rounded_rect_polydata, ui_layer, ui_scale
from .ui_theme import LIGHT, vtk_tokens
from .vtk_compat import add_actor_2d

__all__ = ["FocusRing", "Style", "update_focus_ring"]

_DEFAULTS = vtk_tokens(LIGHT)


class Style:
    """Colour rules for one renderer (see the module docstring)."""

    _instances = weakref.WeakKeyDictionary()

    def __init__(self, renderer):
        self._renderer_ref = weakref.ref(renderer)
        self._overrides = []      # (selector, role, part, states, color)

    @classmethod
    def for_renderer(cls, renderer):
        """The style of ``renderer`` (shared with its scroll viewports and
        popup layer)."""
        from .layers import ui_root

        renderer = ui_root(renderer)
        style = cls._instances.get(renderer)
        if style is None:
            style = cls(renderer)
            cls._instances[renderer] = style
        return style

    def tokens(self):
        renderer = self._renderer_ref()
        theme = getattr(renderer, "theme", None)
        tokens = getattr(theme, "tokens", None)
        return tokens if tokens else _DEFAULTS

    # -- overrides ------------------------------------------------------------------
    def setOverride(self, selector, role, part, color, states=None):
        """Override a colour: ``selector`` is ``"*"`` or ``"#objectName"``.

        With ``states``, the override applies only while all of them hold.
        Later overrides win.
        """
        if selector != "*" and not selector.startswith("#"):
            raise ValueError("selector must be '*' or '#objectName'")
        self._overrides.append((selector, role, part,
                                frozenset(states or ()), tuple(color)))

    def clearOverrides(self):
        self._overrides.clear()

    def _override(self, role, part, states, widget):
        name = widget.objectName() if widget is not None else None
        for selector, o_role, o_part, o_states, color in reversed(
                self._overrides):
            if o_role != role or o_part != part or not o_states <= states:
                continue
            if selector == "*" or (name and selector == f"#{name}"):
                return color
        return None

    # -- rules ------------------------------------------------------------------------
    def color(self, role, part, states=(), widget=None):
        states = frozenset(states)
        override = self._override(role, part, states, widget)
        if override is not None:
            return override
        t = self.tokens()
        disabled = "disabled" in states
        if part == "text":
            if disabled:
                return t["disabled"]
            if role == "button" and "default" in states and \
                    "pressed" not in states:
                return t.get("accent_text", t["panel"])
            if role == "muted":
                return t["muted"]
            return t["text"]
        if role == "button":
            if part == "border":
                return t["accent"] if "default" in states and not disabled \
                    else t["border"]
            if disabled:
                return t["button"]
            if "pressed" in states:
                return t["accent_soft"]
            if "default" in states:
                return t["accent"]
            if "hover" in states or "checked" in states:
                return t["button_hover"]
            return t["button"]
        if role == "field":
            if part == "border":
                if not disabled and ({"focus", "open"} & states):
                    return t["accent"]
                return t["input_border"]
            return t["row_hover"] if "hover" in states and not disabled \
                else t["input"]
        if role == "indicator":
            checked = "checked" in states
            if part == "border":
                return t["accent"] if checked and not disabled \
                    else t["input_border"]
            if part == "mark":
                return t.get("accent_text", t["panel"])
            if checked:
                return t["disabled"] if disabled else t["accent"]
            return t["row_hover"] if "hover" in states else t["input"]
        if role == "menu_item":
            if part == "background":
                return t["accent_soft"] if "active" in states and \
                    not disabled else None
            if part == "mark":
                return t["disabled"] if disabled else t["text"]
        if role == "item":               # rows of item views
            if part == "background":
                if "selected" in states:
                    return t["accent_soft"] if "focus" in states \
                        else t["button_hover"]
                return t["row_hover"] if "hover" in states else None
            if part == "header":
                return t["title"]
            if part == "branch":
                return t["muted"]
        if role == "progress":
            if part == "background":
                return t["border"]
            return t["disabled"] if disabled else t["accent"]
        if role == "scrollbar":
            if part == "background":
                return t["row_hover"]
            return t["muted"] if {"hover", "pressed"} & states else \
                t["input_border"]
        if role == "focus":
            return t["accent"]
        if part == "background":
            return t["panel"]
        return t["border"]


def _outline(x, y, width, height, radius, rgba):
    """Closed rounded-rectangle outline as line segments with point colours.

    (vtkPolyDataMapper2D draws only the first segment of line cells that
    carry cell colours, so colours are per point.)
    """
    fill = rounded_rect_polydata(x, y, width, height, [radius] * 4, rgba)
    source = fill.GetPoints()
    count = source.GetNumberOfPoints()
    points = vtk.vtkPoints()
    points.DeepCopy(source)
    lines = vtk.vtkCellArray()
    colors = vtk.vtkUnsignedCharArray()
    colors.SetNumberOfComponents(4)
    for index in range(count):
        colors.InsertNextTuple4(*rgba)
        segment = vtk.vtkLine()
        segment.GetPointIds().SetId(0, index)
        segment.GetPointIds().SetId(1, (index + 1) % count)
        lines.InsertNextCell(segment)
    polydata = vtk.vtkPolyData()
    polydata.SetPoints(points)
    polydata.SetLines(lines)
    polydata.GetPointData().SetScalars(colors)
    return polydata


class FocusRing:
    """Keyboard-focus outline for one interactor (installed on first Tab)."""

    KEYBOARD_REASONS = ("tab", "backtab")
    _instances = weakref.WeakKeyDictionary()

    def __init__(self, interactor):
        self._interactor_ref = weakref.ref(interactor)
        self._widget_ref = None
        self._actor = None
        self._layer_ref = None
        self._render_tag = None
        self._window_ref = None
        self._key = None
        self._raise = True

    @classmethod
    def for_interactor(cls, interactor):
        ring = cls._instances.get(interactor)
        if ring is None:
            ring = cls(interactor)
            cls._instances[interactor] = ring
        return ring

    def target(self):
        return None if self._widget_ref is None else self._widget_ref()

    def on_focus_changed(self, widget, reason):
        keyboard = reason in self.KEYBOARD_REASONS
        target = widget if widget is not None and keyboard else None
        if target is not self.target():
            self._widget_ref = None if target is None else weakref.ref(target)
            self._key = None
            self._raise = True
        if target is not None:
            self._watch_renders()
        self.update()
        self._request_render()

    def _request_render(self):
        interactor = self._interactor_ref()
        if interactor is None:
            return
        from .core import RenderScheduler

        get_window = getattr(interactor, "GetRenderWindow", None)
        window = get_window() if callable(get_window) else None
        if window is not None:
            RenderScheduler.for_window(window, interactor).request()

    def _watch_renders(self):
        if self._render_tag is not None:
            return
        interactor = self._interactor_ref()
        get_window = getattr(interactor, "GetRenderWindow", None)
        window = get_window() if callable(get_window) else None
        if window is None:
            return
        # Follow layout passes and resizes: refresh just before each frame.
        self._window_ref = weakref.ref(window)
        self._render_tag = window.AddObserver("StartEvent",
                                              lambda *_: self.update(), 100.0)

    def _ensure_actor(self, renderer):
        layer = ui_layer(renderer)
        if self._actor is None or self._layer_ref is None or \
                self._layer_ref() is not layer:
            if self._actor is not None and self._layer_ref is not None and \
                    self._layer_ref() is not None:
                self._layer_ref().RemoveViewProp(self._actor)
            mapper = vtk.vtkPolyDataMapper2D()
            mapper.SetColorModeToDirectScalars()
            mapper.SetScalarModeToUsePointData()
            self._actor = vtk.vtkActor2D()
            self._actor.SetMapper(mapper)
            self._actor.IsUI = True
            self._actor.PickableOff()
            self._actor.GetProperty().SetLineWidth(2.0 * ui_scale())
            add_actor_2d(layer, self._actor)
            self._layer_ref = weakref.ref(layer)
            self._key = None
        return self._actor

    def isVisible(self):
        return self._actor is not None and bool(self._actor.GetVisibility())

    def _hide(self):
        if self._actor is not None and self._actor.GetVisibility():
            self._actor.SetVisibility(False)

    def update(self):
        widget = self.target()
        show = (widget is not None and not widget.isClosed()
                and getattr(widget, "renderer", None) is not None
                and callable(getattr(widget, "geometry", None)))
        if show:
            visible = getattr(widget, "isVisible", None)
            switched_on = getattr(widget, "GetEnabled", None)   # VTK widgets
            show = ((not callable(visible) or visible())
                    and (not callable(switched_on) or bool(switched_on()))
                    and not getattr(widget, "editing", False))
        geometry = None
        if show:
            try:
                geometry = widget.geometry("display")
            except (RuntimeError, TypeError, ValueError, AttributeError):
                geometry = None
            show = geometry is not None and geometry[2] > 0 and geometry[3] > 0
        if not show:
            self._hide()
            return
        renderer = widget.renderer
        actor = self._ensure_actor(renderer)
        layer = ui_layer(renderer)
        origin = tuple(layer.GetOrigin())
        color = tuple(Style.for_renderer(renderer).color("focus", "border"))
        key = (tuple(geometry), origin, color, ui_scale())
        if key != self._key:
            self._key = key
            x, y, width, height = geometry
            gap = 2.0 * ui_scale()
            rgba = tuple(int(round(255 * c)) for c in color[:3]) + (255,)
            actor.GetMapper().SetInputData(_outline(
                x - origin[0] - gap, y - origin[1] - gap, width + 2 * gap,
                height + 2 * gap, 5.0 * ui_scale(), rgba))
            actor.GetProperty().SetLineWidth(2.0 * ui_scale())
        if self._raise:
            # Keep the ring above the widget it outlines.
            self._raise = False
            layer.RemoveViewProp(actor)
            layer.AddViewProp(actor)
        if not actor.GetVisibility():
            actor.SetVisibility(True)


def update_focus_ring(manager, widget, reason):
    """Called by :class:`~multipanel.core.FocusManager` on focus changes.

    The ring is created on the first keyboard focus change only, so
    mouse-only applications never pay for it.
    """
    interactor = manager._interactor_ref()
    if interactor is None:
        return
    ring = FocusRing._instances.get(interactor)
    if ring is None:
        if widget is None or reason not in FocusRing.KEYBOARD_REASONS:
            return
        ring = FocusRing.for_interactor(interactor)
    ring.on_focus_changed(widget, reason)
