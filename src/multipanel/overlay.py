"""Popups drawn above all other UI (``docs/QT_PARITY_PROPOSAL.md`` §7).

::

    from multipanel.overlay import Popup

    menu = Popup(renderer, interactor)
    menu.setLayout(column_of_items)
    menu.popup(anchor=button, placement="below")   # flips when out of room
    menu.closed.connect(on_closed)

While any popup is open the :class:`OverlayLayer` filters input through the
interactor's :class:`~multipanel.router.EventRouter`:

* a press outside every open popup closes them all and is consumed, so it
  does not also click whatever lies underneath (as Qt popups behave);
* a press inside a popup closes the popups opened above it (sub-menus);
* while a *modal* popup is open, pointer input outside it is blocked and an
  outside press does not dismiss it;
* Escape closes the topmost popup.

With no popup open the filter is removed again, so the router keeps its
zero-cost path for hosts that only use legacy widgets.

Popups draw on the window's popup layer (:func:`multipanel.layers.popup_layer`),
above every panel and scroll viewport: build their content with
``popup.renderer``. Native widgets created on another renderer are moved
onto the popup layer when the popup is shown.

Popups consume pointer input inside their rectangle. Their content should be
native widgets (those overriding the ``WidgetMixin`` event handlers); legacy
widgets react through their own VTK observers, which run after the router
and therefore never see presses on a popup.
"""
from __future__ import annotations

import logging
import weakref

import vtk

from ._widget_support import (
    _ui_render_props,
    rounded_rect_polydata,
    ui_layer,
    ui_scale,
)
from .vtk_compat import add_actor_2d, remove_actor_2d
from .containers import Frame
from .core import Signal
from .events import KeyEvent, MouseEvent

logger = logging.getLogger(__name__)

__all__ = ["OverlayLayer", "Popup", "UI_Z_POPUP"]

UI_Z_POPUP = 1000

_COMPOSITE_PARTS = ("panel_background", "background_widget",
                    "value_text_widget", "left_button", "right_button",
                    "prepended_text_widget", "draggable_area_widget",
                    "scroll_box", "_background")


def raise_widget(widget, layer):
    """Move ``widget``'s props (and known composite parts) to the front."""
    seen = set()

    def visit(item):
        if item is None or id(item) in seen:
            return
        seen.add(id(item))
        for prop in _ui_render_props(item):
            if layer.HasViewProp(prop):
                layer.RemoveViewProp(prop)
                layer.AddViewProp(prop)
        for name in _COMPOSITE_PARTS:
            visit(getattr(item, name, None))

    visit(widget)


class OverlayLayer:
    """The stack of open popups for one renderer."""

    _instances = weakref.WeakKeyDictionary()

    def __init__(self, renderer, interactor):
        self._renderer_ref = weakref.ref(renderer)
        self._interactor_ref = weakref.ref(interactor)
        self._stack = []            # open popups, bottom to top
        self._filtering = False

    @classmethod
    def for_renderer(cls, renderer, interactor):
        """The popup stack for ``renderer``'s window (one per popup layer)."""
        from .layers import popup_layer

        renderer = popup_layer(renderer)
        layer = cls._instances.get(renderer)
        if layer is None:
            layer = cls(renderer, interactor)
            cls._instances[renderer] = layer
        return layer

    # -- stack ---------------------------------------------------------------
    def popups(self):
        return tuple(self._stack)

    def topmost(self):
        return self._stack[-1] if self._stack else None

    def _router(self):
        from .router import EventRouter

        return EventRouter.install(self._interactor_ref())

    def open(self, popup):
        if popup in self._stack:
            self._stack.remove(popup)
        self._stack.append(popup)
        if not self._filtering:
            self._router().installEventFilter(self)
            self._filtering = True

    def remove(self, popup):
        if popup in self._stack:
            self._stack.remove(popup)
        if not self._stack and self._filtering:
            self._router().removeEventFilter(self)
            self._filtering = False

    def close_above(self, popup):
        """Close the popups opened after ``popup`` (its sub-popups)."""
        while self._stack and self._stack[-1] is not popup:
            self._stack[-1].dismiss()

    def close_all(self):
        while self._stack:
            self._stack[-1].dismiss()

    def raise_all(self):
        layer = ui_layer(self._renderer_ref())
        for popup in self._stack:
            popup.raise_(layer)

    # -- input -------------------------------------------------------------
    def _owner(self, widget):
        """The open popup whose widget tree contains ``widget``, or None."""
        while widget is not None:
            if widget in self._stack:
                return widget
            parent_of = getattr(widget, "parentWidget", None)
            widget = parent_of() if callable(parent_of) else None
        return None

    def _modal(self):
        return next((popup for popup in reversed(self._stack)
                     if popup.isModal()), None)

    def eventFilter(self, target, event):
        kind = event.type()
        if isinstance(event, KeyEvent):
            if kind == KeyEvent.PRESS and event.key().lower() in (
                    "escape", "esc") and self._stack and \
                    self._stack[-1].tookFocus():
                # Popups shown without focus (completion lists) leave
                # Escape to the widget that kept it.
                self._stack[-1].dismiss()
                return True
            return False
        owner = self._owner(target)
        modal = self._modal()
        if kind in (MouseEvent.PRESS, MouseEvent.DOUBLE_CLICK, "ContextMenu"):
            if owner is not None:
                self.close_above(owner)
                return False
            if modal is not None:
                return True          # modal: outside presses do nothing
            consume = any(popup.consumesOutsideClick() for popup in self._stack)
            self.close_all()
            return consume
        if modal is not None and owner is None:
            return True              # block hover/wheel/release outside
        return False


class Popup(Frame):
    """A transient, topmost container: menus, dropdown lists, tooltips.

    Hidden until :meth:`popup` is called. ``dismiss()`` (or Escape, or an
    outside click) hides it again and emits ``closed``.
    """

    GAP_PX = 4
    MARGIN_PX = 4
    FADE_IN_MS = 90          # 0 disables; see also set_animations_enabled

    def __init__(self, renderer, interactor, modal=False, background=True,
                 panel_color=None, opacity=1.0, object_name="popup",
                 ui_z_order=UI_Z_POPUP):
        from .layers import popup_layer

        # ``at`` points are given in the caller's renderer; the popup itself
        # draws on the window's popup layer, above every panel and viewport.
        self._source_renderer_ref = weakref.ref(renderer)
        renderer = popup_layer(renderer)
        super().__init__(renderer, interactor, background=background,
                         panel_color=panel_color, opacity=opacity,
                         object_name=object_name, ui_z_order=ui_z_order)
        self.aboutToShow = Signal(self)
        self.aboutToHide = Signal(self)
        self.closed = Signal(self)
        self._modal = bool(modal)
        self._consume_outside = True
        self._open = False
        self._anchor_ref = None
        self._scrim = False
        self._scrim_actor = None
        self._opacity = 1.0
        self._base_opacity = {}
        self._fade = None
        self.registerFocus(interactor, "StrongFocus")
        self.setContentsMargins(4, 4, 4, 4)
        self.SetVisibility(False)

    # -- configuration -------------------------------------------------------
    def isModal(self):
        return self._modal

    def setModal(self, modal):
        self._modal = bool(modal)

    def consumesOutsideClick(self):
        return self._consume_outside

    def setConsumesOutsideClick(self, consume):
        self._consume_outside = bool(consume)

    def isOpen(self):
        return self._open

    def tookFocus(self):
        """False when shown with ``popup(take_focus=False)``."""
        return getattr(self, "_took_focus", True)

    def hasScrim(self):
        return self._scrim

    def setScrim(self, scrim, opacity=0.35):
        """Dim the rest of the UI behind this popup while it is open."""
        self._scrim = bool(scrim)
        self._scrim_opacity = float(opacity)

    def _show_scrim(self, layer):
        if not self._scrim:
            return
        if self._scrim_actor is None:
            mapper = vtk.vtkPolyDataMapper2D()
            mapper.SetColorModeToDirectScalars()
            mapper.SetScalarModeToUseCellData()
            self._scrim_actor = vtk.vtkActor2D()
            self._scrim_actor.SetMapper(mapper)
            self._scrim_actor.IsUI = True
            self._scrim_actor.PickableOff()
            add_actor_2d(layer, self._scrim_actor)
        width, height = self.viewportExtent()
        alpha = int(round(255 * getattr(self, "_scrim_opacity", 0.35)))
        self._scrim_actor.GetMapper().SetInputData(rounded_rect_polydata(
            0, 0, width, height, [0, 0, 0, 0], (0, 0, 0, alpha)))
        self._scrim_actor.SetVisibility(True)
        layer.RemoveViewProp(self._scrim_actor)
        layer.AddViewProp(self._scrim_actor)

    def anchor(self):
        return None if self._anchor_ref is None else self._anchor_ref()

    def layer(self):
        return OverlayLayer.for_renderer(self.renderer, self.interactor)

    # -- placement -----------------------------------------------------------
    @staticmethod
    def _display_origin(item):
        """Display-px origin of a widget's (or renderer's) viewport."""
        from .units import viewport_origin

        source = item.viewportSource() if hasattr(item, "viewportSource") \
            else ui_layer(item)
        return viewport_origin(source)

    def _viewport_px(self):
        width, height = self.viewportExtent()
        scale = ui_scale()
        return width / scale, height / scale

    def place(self, size, at=None, anchor=None, placement="below"):
        """Return the ``(x, y, w, h)`` logical-px rectangle for the popup.

        ``anchor`` is a widget, ``at`` a logical-px point (top-left corner of
        the popup). The preferred ``placement`` (below, above, right, left)
        flips to the opposite side when there is no room, then the rectangle
        is clamped inside the viewport.
        """
        width, height = size
        view_w, view_h = self._viewport_px()
        gap, margin = self.GAP_PX, self.MARGIN_PX
        scale = ui_scale()
        ox, oy = self._display_origin(self)
        if anchor is not None:
            dx, dy, dw, dh = anchor.geometry("display")
            ax, ay = (dx - ox) / scale, (dy - oy) / scale
            aw, ah = dw / scale, dh / scale
            candidates = {
                "below": (ax, ay - gap - height),
                "above": (ax, ay + ah + gap),
                "right": (ax + aw + gap, ay + ah - height),
                "left": (ax - gap - width, ay + ah - height),
            }
            opposite = {"below": "above", "above": "below",
                        "right": "left", "left": "right"}

            def fits(point):
                return (margin <= point[0] <= view_w - width - margin and
                        margin <= point[1] <= view_h - height - margin)

            x, y = candidates[placement]
            flipped = candidates[opposite[placement]]
            if not fits((x, y)) and fits(flipped):
                x, y = flipped
        elif at is not None:
            source = self._source_renderer_ref()
            if source is not None and source is not self.renderer:
                sx, sy = self._display_origin(source)
                at = (at[0] + (sx - ox) / scale, at[1] + (sy - oy) / scale)
            x, y = at[0], at[1] - height
            if y < margin:
                y = at[1]                       # open upwards instead
            if x + width > view_w - margin:
                x = at[0] - width               # open leftwards instead
        else:
            x, y = (view_w - width) / 2.0, (view_h - height) / 2.0
        x = min(max(margin, x), max(margin, view_w - width - margin))
        y = min(max(margin, y), max(margin, view_h - height - margin))
        return (x, y, width, height)

    def popup(self, at=None, anchor=None, placement="below", size=None,
              take_focus=True):
        """Show the popup next to ``anchor`` or at ``at`` (logical px).

        ``take_focus=False`` leaves keyboard focus where it is (a completer
        list under a field that is still being typed into).
        """
        from .units import px

        self._adopt_content()
        if size is None:
            size = self.sizeHint()
        self.aboutToShow.emit()
        x, y, width, height = self.place(size, at=at, anchor=anchor,
                                         placement=placement)
        self.setGeometry(px(x), px(y), px(width), px(height))
        layout = self.contentLayout()
        if layout is not None:
            layout.activate()
        self._anchor_ref = None if anchor is None else weakref.ref(anchor)
        self.SetVisibility(True)
        self._open = True
        self.registerWithRouter()
        self.layer().open(self)
        self.raise_()
        self._fade_in()
        self._took_focus = bool(take_focus)
        if take_focus:
            self.setFocus(reason="popup")
        self.requestRender()
        return self

    # -- opacity / fade ---------------------------------------------------------
    def _content_props(self):
        props, seen = [], set()

        def visit(item):
            if item is None or id(item) in seen:
                return
            seen.add(id(item))
            props.extend(_ui_render_props(item))
            for name in _COMPOSITE_PARTS:
                visit(getattr(item, name, None))

        visit(self._background)
        layout = self.contentLayout()
        for widget in (layout.widgets() if layout is not None else
                       self.children()):
            visit(widget)
        if self._scrim_actor is not None:
            props.append(self._scrim_actor)
        return props

    def windowOpacity(self):
        return self._opacity

    def setWindowOpacity(self, opacity):
        """Scale the opacity of everything the popup draws (0..1)."""
        self._opacity = max(0.0, min(1.0, float(opacity)))
        for prop in self._content_props():
            if isinstance(prop, vtk.vtkTextActor):
                target = prop.GetTextProperty()
            else:
                getter = getattr(prop, "GetProperty", None)
                target = getter() if callable(getter) else None
            if target is None or not hasattr(target, "SetOpacity"):
                continue
            key = target.GetAddressAsString("vtkObject")
            base = self._base_opacity.setdefault(key, target.GetOpacity())
            target.SetOpacity(base * self._opacity)
        if self._opacity >= 1.0:
            self._base_opacity.clear()
        self.requestRender()

    def _stop_fade(self):
        if self._fade is not None:
            self._fade.stop()
            self._fade = None
        if self._opacity < 1.0:
            self.setWindowOpacity(1.0)

    def _fade_in(self):
        from .animation import PropertyAnimation, animations_enabled

        self._stop_fade()
        if self.FADE_IN_MS <= 0 or not animations_enabled():
            return
        self.setWindowOpacity(0.0)
        self._fade = PropertyAnimation(
            self, "windowOpacity", duration_ms=self.FADE_IN_MS,
            easing="outCubic", start_value=0.0, end_value=1.0)
        self._fade.finished.connect(lambda: setattr(self, "_fade", None))
        self._fade.start()

    def _adopt_content(self):
        """Move native content made on another renderer onto this layer."""
        layout = self.contentLayout()
        widgets = layout.widgets() if layout is not None else self.children()
        target = self.renderer
        for widget in widgets:
            renderer = getattr(widget, "renderer", None)
            if renderer is None or renderer is target:
                continue
            from .standard import NativeWidget

            if not isinstance(widget, NativeWidget):
                logger.warning(
                    "%s in popup %r was made on another renderer and may "
                    "draw beneath the popup; create it with popup.renderer",
                    type(widget).__name__, self.objectName())
                continue
            source = ui_layer(renderer)
            for prop in _ui_render_props(widget):
                if source.HasViewProp(prop):
                    remove_actor_2d(source, prop)
                add_actor_2d(target, prop)
            widget.renderer = target
            widget.refresh()

    def raise_(self, layer=None):
        """Draw this popup and its content in front of all other UI."""
        layer = layer or ui_layer(self.renderer)
        if self._open:
            self._show_scrim(layer)
        raise_widget(self._background, layer)
        layout = self.contentLayout()
        for widget in (layout.widgets() if layout is not None else
                       self.children()):
            raise_widget(widget, layer)
        self.requestRender()

    def dismiss(self):
        """Hide the popup (and any opened above it) and emit ``closed``."""
        if not self._open:
            return False
        layer = self.layer()
        layer.close_above(self)
        self.aboutToHide.emit()
        self._open = False
        self._stop_fade()
        self.SetVisibility(False)
        if self._scrim_actor is not None:
            self._scrim_actor.SetVisibility(False)
        layer.remove(self)
        if self.hasFocus():
            self.clearFocus(reason="popup")
        self.closed.emit()
        self.requestRender()
        return True

    def cancel(self):
        """Escape while the popup has focus (FocusManager.cancelFocused)."""
        self.dismiss()

    # -- input: popups are opaque to the scene and to widgets beneath -------
    def mousePressEvent(self, event):
        event.accept()

    def mouseReleaseEvent(self, event):
        event.accept()

    def mouseDoubleClickEvent(self, event):
        event.accept()

    def mouseMoveEvent(self, event):
        event.accept()

    def wheelEvent(self, event):
        event.accept()

    def contextMenuEvent(self, event):
        event.accept()

    def close(self):
        if self._open:
            self.dismiss()
        if self._scrim_actor is not None:
            remove_actor_2d(ui_layer(self.renderer), self._scrim_actor)
            self._scrim_actor = None
        return super().close()
