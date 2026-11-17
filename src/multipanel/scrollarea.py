"""Scroll areas and scroll bars (``docs/QT_PARITY_PROPOSAL.md`` §6.2, W2).

A :class:`ScrollArea` shows a content widget taller than itself through a
viewport that clips exactly: the content lives on the area's own
:class:`~multipanel.layers.LinkedRenderer`, whose viewport is the area's
rectangle. Build the content on :meth:`ScrollArea.contentRenderer`::

    area = ScrollArea(renderer, interactor)
    content = Frame(area.contentRenderer(), interactor)
    column = VBoxLayout()
    for name in materials:
        column.addWidget(CheckBox(area.contentRenderer(), interactor, name))
    content.setLayout(column)
    area.setWidget(content)
    panel_layout.addWidget(area)

The wheel scrolls smoothly (an animation; instant with animations off),
the scroll bar can be dragged or clicked to page, and
:meth:`ScrollArea.ensureWidgetVisible` brings a child into view. Popups
opened from the content (combo box lists, menus) draw on the popup layer,
above the clipped viewport.
"""
from __future__ import annotations

from ._widget_support import ui_layer, ui_scale
from .core import Signal, SizePolicy, WidgetMixin
from .layers import LinkedRenderer
from .standard import NativeWidget, _rgba
from ._widget_support import rounded_rect_polydata
from .units import px

__all__ = ["ScrollArea", "ScrollBar"]


class ScrollBar(NativeWidget):
    """A vertical scroll bar (``QScrollBar``); values are logical px."""

    FOCUS_POLICY = "NoFocus"
    MIN_THUMB_PX = 24

    def __init__(self, renderer, interactor, parent=None, object_name=None):
        self._minimum = 0.0
        self._maximum = 0.0
        self._value = 0.0
        self._page_step = 100.0
        self._single_step = 20.0
        self._drag_offset = None
        super().__init__(renderer, interactor, parent,
                         object_name or "scroll_bar")
        self.valueChanged = Signal(self)
        self.sliderMoved = Signal(self)
        self.refresh()

    # -- range and value -----------------------------------------------------------
    def minimum(self):
        return self._minimum

    def maximum(self):
        return self._maximum

    def setRange(self, minimum, maximum):
        self._minimum = float(minimum)
        self._maximum = max(self._minimum, float(maximum))
        self.setValue(self._value)
        self.refresh()

    def pageStep(self):
        return self._page_step

    def setPageStep(self, step):
        self._page_step = max(1.0, float(step))
        self.refresh()

    def singleStep(self):
        return self._single_step

    def setSingleStep(self, step):
        self._single_step = max(1.0, float(step))

    def value(self):
        return self._value

    def setValue(self, value):
        value = min(max(float(value), self._minimum), self._maximum)
        if value != self._value:
            self._value = value
            self.valueChanged.emit(value)
            self.refresh()

    # -- geometry ------------------------------------------------------------------------
    def defaultSizePolicy(self):
        return SizePolicy(SizePolicy.Fixed, SizePolicy.Expanding)

    def sizeHint(self):
        return (10.0, 60.0)

    def minimumSizeHint(self):
        return (10.0, 30.0)

    def _thumb(self, y, height):
        """``(top, length)`` of the thumb in display px."""
        span = self._maximum - self._minimum
        length = height if span <= 0 else max(
            min(height, self.px(self.MIN_THUMB_PX)),
            height * self._page_step / (span + self._page_step))
        progress = 0.0 if span <= 0 else (self._value - self._minimum) / span
        top = y + height - progress * (height - length)
        return top, length

    def paint(self, x, y, width, height, tokens):
        if self._maximum <= self._minimum:
            return [], []
        inset = self.px(2)
        bar_w = max(2.0, width - 2 * inset)
        top, length = self._thumb(y + inset, height - 2 * inset)
        track = self.color("scrollbar", "background")
        handle = self.color("scrollbar", "handle",
                            *(("pressed",) if self._drag_offset is not None
                              else ()))
        radius = bar_w / 2
        return [rounded_rect_polydata(x + inset, y + inset, bar_w,
                                      height - 2 * inset, [radius] * 4,
                                      _rgba(track)),
                rounded_rect_polydata(x + inset, top - length, bar_w, length,
                                      [radius] * 4, _rgba(handle))], []

    def _value_for_top(self, top, y, height):
        span = self._maximum - self._minimum
        _top, length = self._thumb(y, height)
        travel = height - length
        if span <= 0 or travel <= 0:
            return self._minimum
        progress = (y + height - top) / travel
        return self._minimum + min(1.0, max(0.0, progress)) * span

    # -- input -------------------------------------------------------------------------------
    def mousePressEvent(self, event):
        if event.button() != "left" or self._maximum <= self._minimum:
            event.ignore()
            return
        event.accept()
        x, y, width, height = self.rect()
        _gx, gy = event.globalPos()
        oy = self.geometry("display")[1] - y
        pointer = gy - oy
        top, length = self._thumb(y, height)
        if top - length <= pointer <= top:
            self._drag_offset = top - pointer
            self.refresh()
        else:          # page towards the pointer, as Qt does
            step = self._page_step if pointer < top - length else \
                -self._page_step
            self.setValue(self._value + step)

    def mouseMoveEvent(self, event):
        if self._drag_offset is None:
            event.ignore()
            return
        event.accept()
        x, y, width, height = self.rect()
        oy = self.geometry("display")[1] - y
        pointer = event.globalPos()[1] - oy
        value = self._value_for_top(pointer + self._drag_offset, y, height)
        if value != self._value:
            self.setValue(value)
            self.sliderMoved.emit(value)

    def mouseReleaseEvent(self, event):
        if self._drag_offset is None:
            event.ignore()
            return
        event.accept()
        self._drag_offset = None
        self.refresh()

    def wheelEvent(self, event):
        event.ignore()                    # the scroll area handles the wheel


class ScrollArea(WidgetMixin):
    """A clipped, scrollable viewport onto one content widget (``QScrollArea``)."""

    BAR_PX = 10
    WHEEL_STEP_PX = 60
    SCROLL_MS = 140

    def __init__(self, renderer, interactor, parent=None,
                 object_name="scroll_area", geometry=None, ui_z_order=15):
        self.renderer = renderer
        self.interactor = interactor
        self.ui_z_order = int(ui_z_order)
        self._bounds = (0.0, 0.0, 0.0, 0.0)
        self._shown = True
        self._widget = None
        self._resizable = True
        self._target = 0.0
        self._animation = None
        self._applying = False
        self.parent_pane = None
        self.initWidget(object_name, parent)
        layer = ui_layer(renderer)
        self._content = LinkedRenderer().link(layer)
        self._content._ui_clips_children = True
        self._content.SetLayer(layer.GetLayer())
        self._content.SetViewport(0.0, 0.0, 0.0, 0.0)
        window = interactor.GetRenderWindow()
        window.AddRenderer(self._content)
        self._bar = ScrollBar(renderer, interactor, parent=self,
                              object_name=f"{object_name}/bar")
        self._bar.ui_z_order = self.ui_z_order + 1
        self._bar.valueChanged.connect(self._on_bar_value)
        self.registerWithRouter(interactor)
        self.ownObserver(window, "WindowResizeEvent",
                         lambda *_: self._relayout())
        if geometry is not None:
            self.setGeometry(*geometry)

    # -- content ---------------------------------------------------------------------------
    def contentRenderer(self):
        """The (clipped) renderer to build the content widgets on."""
        return self._content

    def widget(self):
        return self._widget

    def setWidget(self, widget):
        if getattr(widget, "renderer", None) is not self._content:
            raise ValueError("create the scroll area's content on "
                             "area.contentRenderer()")
        if self._widget is not None and self._widget is not widget:
            self._widget.parent_pane = None
        self._widget = widget
        widget.setParent(self)
        # Frames ask their parent_pane to re-lay them out when their content
        # changes size (Frame.layoutRequestEvent).
        widget.parent_pane = self
        self._relayout()

    def takeWidget(self):
        widget, self._widget = self._widget, None
        if widget is not None:
            widget.parent_pane = None
        self._relayout()
        return widget

    def widgetResizable(self):
        return self._resizable

    def setWidgetResizable(self, resizable):
        """True (default): the content fills the width and at least the height."""
        self._resizable = bool(resizable)
        self._relayout()

    def verticalScrollBar(self):
        return self._bar

    def layout(self, render=False):
        """Re-fit the content (called by content frames that changed size)."""
        self._relayout()

    # -- container protocol ----------------------------------------------------------------
    def GetBounds(self):
        return self._bounds

    def SetBounds(self, x0, x1, y0, y1):
        self._bounds = (float(x0), float(x1), float(y0), float(y1))
        self._relayout()

    def GetVisibility(self):
        return self._shown

    def SetVisibility(self, visible):
        visible = bool(visible)
        if visible == self._shown:
            return
        self._shown = visible
        self._relayout()

    def GetEnabled(self):
        return self._shown

    def SetEnabled(self, enabled):
        self.SetVisibility(enabled)

    def isVisible(self):
        return self._shown

    def defaultSizePolicy(self):
        return SizePolicy(SizePolicy.Expanding, SizePolicy.Expanding)

    def sizeHint(self):
        content = self._content_hint()
        return (content[0] + self.BAR_PX, min(content[1], 240.0))

    def minimumSizeHint(self):
        return (self.BAR_PX + 40.0, 40.0)

    def _content_hint(self):
        if self._widget is None:
            return (0.0, 0.0)
        return tuple(float(v) for v in self._widget.sizeHint())

    # -- layout -----------------------------------------------------------------------------
    def _viewport_rect(self):
        """Viewport ``(x, y, w, h)`` in display px and whether the bar shows."""
        x, y, width, height = self.geometry("display")
        scale = ui_scale()
        content_h = self._content_hint()[1] * scale
        bar = content_h > height + 0.5
        if bar:
            width = max(0.0, width - self.BAR_PX * scale)
        return (x, y, width, height), bar

    def _relayout(self):
        if self._applying:
            return
        self._applying = True
        try:
            self._apply_layout()
        finally:
            self._applying = False
        self.requestRender()

    def _apply_layout(self):
        window = self.interactor.GetRenderWindow()
        win_w, win_h = (max(1, v) for v in window.GetSize())
        (vx, vy, vw, vh), bar = self._viewport_rect()
        shown = self._shown and vw > 0 and vh > 0
        self._content.SetDraw(bool(shown))
        if not shown:
            self._content.SetViewport(0.0, 0.0, 0.0, 0.0)
        else:
            self._content.SetViewport(vx / win_w, vy / win_h,
                                      (vx + vw) / win_w, (vy + vh) / win_h)
        scale = ui_scale()
        view_w, view_h = vw / scale, vh / scale
        content_w, content_h = self._content_hint()
        if self._resizable:
            content_w, content_h = view_w, max(view_h, content_h)
        maximum = max(0.0, content_h - view_h)
        self._bar.setPageStep(max(1.0, view_h))
        self._bar.setSingleStep(self.WHEEL_STEP_PX / 3.0)
        self._bar.setRange(0.0, maximum)
        self._target = min(max(self._target, 0.0), maximum)
        ax, ay, aw, ah = self.geometry("px")
        self._bar.setGeometry(px(ax + aw - self.BAR_PX), px(ay),
                              px(self.BAR_PX), px(ah))
        self._bar.SetVisibility(self._shown and bar)
        if self._widget is not None:
            if hasattr(self._widget, "SetVisibility"):
                self._widget.SetVisibility(shown)
            if shown:
                self._place_content(view_h, content_w, content_h)

    def _place_content(self, view_h, content_w, content_h):
        offset = self._bar.value()
        self._widget.setGeometry(px(0), px(view_h - content_h + offset),
                                 px(content_w), px(content_h))

    def _on_bar_value(self, value):
        if self._animation is None or self._animation.state() != "running":
            self._target = value
        if self._widget is None or self._applying:
            return
        (_vx, _vy, _vw, vh), _bar = self._viewport_rect()
        scale = ui_scale()
        content_w, content_h = self._content_hint()
        view_w = _vw / scale
        if self._resizable:
            content_w, content_h = view_w, max(vh / scale, content_h)
        self._place_content(vh / scale, content_w, content_h)
        self.requestRender()

    # -- scrolling ---------------------------------------------------------------------------
    def scrollValue(self):
        return self._bar.value()

    def setScrollValue(self, value):
        self._bar.setValue(value)

    def scrollTo(self, value, animated=True):
        """Scroll so ``value`` logical px of content are above the viewport."""
        from .animation import PropertyAnimation, animations_enabled

        value = min(max(float(value), self._bar.minimum()), self._bar.maximum())
        self._target = value
        if self._animation is not None:
            self._animation.stop()
            self._animation = None
        if not animated or not animations_enabled() or \
                value == self._bar.value():
            self._bar.setValue(value)
            return
        self._animation = PropertyAnimation(
            self, "scrollValue", duration_ms=self.SCROLL_MS,
            easing="outCubic", end_value=value)
        self._animation.start()

    def ensureWidgetVisible(self, child, margin=10):
        """Scroll the least amount that shows ``child`` (a content widget)."""
        if self._widget is None:
            return
        scale = ui_scale()
        cx, cy, cw, ch = child.geometry("display")
        _x, top_y, _w, content_h = self._widget.geometry("display")
        (_vx, _vy, _vw, vh), _bar = self._viewport_rect()
        # Distance of the child's top/bottom below the content's top edge.
        child_top = (top_y + content_h - (cy + ch)) / scale
        child_bottom = child_top + ch / scale
        view = vh / scale
        value = self._target
        if child_top - margin < value:
            value = child_top - margin
        elif child_bottom + margin > value + view:
            value = child_bottom + margin - view
        self.scrollTo(value)

    def wheelEvent(self, event):
        if self._bar.maximum() <= self._bar.minimum():
            event.ignore()
            return
        event.accept()
        self.scrollTo(self._target - event.delta() * self.WHEEL_STEP_PX)

    def mousePressEvent(self, event):
        event.ignore()

    def close(self):
        if self._animation is not None:
            self._animation.stop()
        window = self.interactor.GetRenderWindow()
        if window is not None:
            window.RemoveRenderer(self._content)
        return super().close()
