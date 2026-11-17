"""Splitters: children side by side with draggable handles (W2, ``QSplitter``).

::

    split = Splitter(renderer, interactor, "horizontal")
    split.addWidget(scene_tree)
    split.addWidget(properties)
    split.setSizes([220, 380])            # logical px
    split.setStretchFactor(1, 1)          # the second one takes resizes
    split.splitterMoved.connect(remember_sizes)
    panel_layout.addWidget(split, stretch=1)

Dragging a handle moves the two widgets beside it. A widget can be
dragged closed (to zero) past half its minimum size unless
``setChildrenCollapsible(False)`` or ``setCollapsible(i, False)``. When the
splitter is resized the extra space goes to widgets by stretch factor, or
in proportion to their sizes when no factor is set, as in Qt.
"""
from __future__ import annotations

import vtk

from ._widget_support import rounded_rect_polydata
from .core import Signal, SizePolicy, WidgetMixin
from .standard import NativeWidget, _rgba
from .units import px

__all__ = ["Splitter", "SplitterHandle"]


class SplitterHandle(NativeWidget):
    """The draggable bar between two widgets of a :class:`Splitter`."""

    FOCUS_POLICY = "NoFocus"

    def __init__(self, splitter, index):
        self._splitter = splitter
        self.index = index
        self._drag = None             # (start pointer, start sizes)
        super().__init__(splitter.renderer, splitter.interactor,
                         parent=splitter,
                         object_name=f"{splitter.objectName()}/handle{index}",
                         ui_z_order=splitter.ui_z_order + 1)
        self.setCursor(vtk.VTK_CURSOR_SIZEWE if splitter.isHorizontal()
                       else vtk.VTK_CURSOR_SIZENS)

    def paint(self, x, y, width, height, tokens):
        active = self._hovered or self._drag is not None
        color = tokens["accent"] if active else tokens["border"]
        thickness = self.px(2 if active else 1)
        if self._splitter.isHorizontal():
            grip = (x + (width - thickness) / 2, y + self.px(4), thickness,
                    max(0.0, height - self.px(8)))
        else:
            grip = (x + self.px(4), y + (height - thickness) / 2,
                    max(0.0, width - self.px(8)), thickness)
        return [rounded_rect_polydata(*grip, [thickness / 2] * 4,
                                      _rgba(color))], []

    def mousePressEvent(self, event):
        if event.button() != "left":
            event.ignore()
            return
        event.accept()
        self._drag = (self._axis_value(event), self._splitter.sizes())
        self.refresh()

    def mouseMoveEvent(self, event):
        if self._drag is None:
            event.ignore()
            return
        event.accept()
        start, sizes = self._drag
        delta = (self._axis_value(event) - start) / self._splitter._scale()
        if not self._splitter.isHorizontal():
            delta = -delta              # display y grows upwards
        self._splitter._drag_handle(self.index, sizes, delta)

    def mouseReleaseEvent(self, event):
        if self._drag is None:
            event.ignore()
            return
        event.accept()
        self._drag = None
        self.refresh()

    def _axis_value(self, event):
        x, y = event.globalPos()
        return x if self._splitter.isHorizontal() else y


class Splitter(WidgetMixin):
    """Lays out widgets in a row or column with draggable handles."""

    HANDLE_PX = 6

    def __init__(self, renderer, interactor, orientation="horizontal",
                 parent=None, object_name="splitter", ui_z_order=15):
        if orientation not in ("horizontal", "vertical"):
            raise ValueError("orientation must be 'horizontal' or 'vertical'")
        self.renderer = renderer
        self.interactor = interactor
        self.ui_z_order = int(ui_z_order)
        self._orientation = orientation
        self._bounds = (0.0, 0.0, 0.0, 0.0)
        self._shown = True
        self._widgets = []
        self._handles = []
        self._sizes = None            # logical px per widget, once known
        self._requested = None        # setSizes() before the first layout
        self._stretch = {}
        self._collapsible = {}
        self._children_collapsible = True
        self._handle_px = float(self.HANDLE_PX)
        self._applying = False
        self.parent_pane = None
        self.initWidget(object_name, parent)
        self.splitterMoved = Signal(self)          # (position, handle index)
        self.registerWithRouter(interactor)

    # -- children ----------------------------------------------------------------------
    def orientation(self):
        return self._orientation

    def isHorizontal(self):
        return self._orientation == "horizontal"

    def count(self):
        return len(self._widgets)

    def widget(self, index):
        return self._widgets[index] if 0 <= index < len(self._widgets) \
            else None

    def indexOf(self, widget):
        return next((i for i, w in enumerate(self._widgets) if w is widget),
                    -1)

    def addWidget(self, widget):
        self.insertWidget(len(self._widgets), widget)

    def insertWidget(self, index, widget):
        if self.indexOf(widget) >= 0:
            self._widgets.remove(widget)
        index = max(0, min(int(index), len(self._widgets)))
        self._widgets.insert(index, widget)
        widget.setParent(self)
        widget.parent_pane = self
        if self._sizes is not None:
            self._sizes.insert(index, self._hint(widget))
        self._sync_handles()
        self._relayout()

    def takeWidget(self, index):
        """Remove and return the widget at ``index`` (it is not closed)."""
        widget = self.widget(index)
        if widget is None:
            return None
        del self._widgets[index]
        if self._sizes is not None:
            del self._sizes[index]
        widget.parent_pane = None
        self._sync_handles()
        self._relayout()
        return widget

    def handle(self, index):
        """The handle before widget ``index`` (``index >= 1``)."""
        return self._handles[index - 1] if 1 <= index <= len(self._handles) \
            else None

    def _sync_handles(self):
        while len(self._handles) < max(0, len(self._widgets) - 1):
            self._handles.append(SplitterHandle(self, len(self._handles) + 1))
        while len(self._handles) > max(0, len(self._widgets) - 1):
            self._handles.pop().close()

    # -- options ------------------------------------------------------------------------
    def handleWidth(self):
        return self._handle_px

    def setHandleWidth(self, width):
        self._handle_px = max(1.0, float(width))
        self._relayout()

    def setStretchFactor(self, index, stretch):
        self._stretch[index] = max(0, int(stretch))

    def childrenCollapsible(self):
        return self._children_collapsible

    def setChildrenCollapsible(self, collapsible):
        self._children_collapsible = bool(collapsible)

    def isCollapsible(self, index):
        return self._collapsible.get(index, self._children_collapsible)

    def setCollapsible(self, index, collapsible):
        self._collapsible[index] = bool(collapsible)

    # -- sizes ----------------------------------------------------------------------------
    def _axis(self):
        return 0 if self.isHorizontal() else 1

    def _scale(self):
        from ._widget_support import ui_scale

        return ui_scale()

    def _hint(self, widget):
        return float(widget.sizeHint()[self._axis()])

    def _minimum(self, widget):
        explicit = widget.minimumSize()[self._axis()]
        if explicit:
            return float(explicit)
        return float(widget.minimumSizeHint()[self._axis()])

    def _available(self):
        if not self._widgets:
            return 0.0
        extent = self.geometry("px")[2 + self._axis()]
        return max(0.0, extent - self._handle_px * (len(self._widgets) - 1))

    def sizes(self):
        """Current sizes in logical px (0 for collapsed widgets)."""
        if self._sizes is None:
            available = self._available()
            if self._requested is not None:
                sizes = self._proportional(self._requested, available)
            else:
                sizes = self._initial_sizes(available)
            if available <= 0:              # not laid out yet: do not keep
                return list(sizes)
            self._sizes, self._requested = sizes, None
        return list(self._sizes)

    def setSizes(self, sizes):
        """Set sizes in logical px, scaled in proportion to fit (as Qt).

        Sizes set before the splitter has a size are kept as a request
        and resolved when it is first laid out.
        """
        sizes = [max(0.0, float(v)) for v in sizes][:len(self._widgets)]
        sizes += [self._hint(w) for w in self._widgets[len(sizes):]]
        available = self._available()
        if available <= 0:
            self._sizes, self._requested = None, sizes
        else:
            self._sizes = self._proportional(sizes, available)
        self._relayout()

    def _proportional(self, sizes, available):
        total = sum(sizes)
        if available <= 0 or total <= 0:
            return list(sizes)
        out = [s * available / total for s in sizes]
        out = [max(s, self._minimum(w)) if s > 0 else 0.0
               for s, w in zip(out, self._widgets)]
        return self._fit(out, available)

    def _initial_sizes(self, available):
        return self._fit([self._hint(w) for w in self._widgets], available)

    def _fit(self, sizes, available):
        """Scale ``sizes`` to ``available``: by stretch factor, else in
        proportion, keeping minimums (collapsed widgets stay closed)."""
        if not sizes or available <= 0:
            return list(sizes)
        total = sum(sizes)
        delta = available - total
        if abs(delta) < 1e-6:
            return list(sizes)
        weights = [self._stretch.get(i, 0) if sizes[i] > 0 else 0
                   for i in range(len(sizes))]
        if not any(weights) or delta < 0:
            weights = [s for s in sizes]
        if not any(weights):
            weights = [1.0] * len(sizes)
        out = list(sizes)
        # Hand out the change, re-distributing what minimums refuse.
        for _round in range(len(out) + 1):
            weight_sum = sum(weights)
            if abs(delta) < 1e-6 or weight_sum <= 0:
                break
            remainder = 0.0
            for i, weight in enumerate(weights):
                if weight <= 0:
                    continue
                share = delta * weight / weight_sum
                target = out[i] + share
                floor = self._minimum(self._widgets[i]) if out[i] > 0 else 0.0
                if target < floor:
                    remainder += target - floor
                    target = floor
                    weights[i] = 0
                out[i] = target
            delta = remainder
        return out

    def _drag_handle(self, index, start_sizes, delta):
        """Move handle ``index`` by ``delta`` logical px from ``start_sizes``."""
        before, after = index - 1, index
        sizes = list(start_sizes)
        pair = sizes[before] + sizes[after]
        first = min(max(sizes[before] + delta, 0.0), pair)
        first = self._settle(before, first, pair - first, pair)
        sizes[before], sizes[after] = first, pair - first
        if sizes != self.sizes():
            self._sizes = sizes
            self._relayout()
            self.splitterMoved.emit(self.handlePosition(index), index)

    def _settle(self, before, first, second, pair):
        """Apply minimums and collapsing to a dragged pair."""
        lo = self._minimum(self._widgets[before])
        hi_min = self._minimum(self._widgets[before + 1])
        if first < lo:
            first = 0.0 if self.isCollapsible(before) and first < lo / 2 \
                else min(lo, pair)
        second = pair - first
        if second < hi_min:
            second = 0.0 if self.isCollapsible(before + 1) and \
                second < hi_min / 2 else min(hi_min, pair)
            first = pair - second
        return first

    def handlePosition(self, index):
        """Logical px from the splitter's start to handle ``index``."""
        sizes = self.sizes()
        return sum(sizes[:index]) + self._handle_px * (index - 1)

    def moveSplitter(self, position, index):
        """Put handle ``index`` at ``position`` logical px (``QSplitter``)."""
        self._drag_handle(index, self.sizes(),
                          position - self.handlePosition(index))

    # -- container protocol ------------------------------------------------------------------
    def GetBounds(self):
        return self._bounds

    def SetBounds(self, x0, x1, y0, y1):
        old = self._bounds
        self._bounds = (float(x0), float(x1), float(y0), float(y1))
        if self._sizes is not None and old != self._bounds:
            self._sizes = self._fit(self._sizes, self._available())
        self._relayout()

    def GetVisibility(self):
        return self._shown

    def SetVisibility(self, visible):
        visible = bool(visible)
        if visible != self._shown:
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

    def _combine(self, getter):
        axis = self._axis()
        values = [getter(w) for w in self._widgets]
        if not values:
            return (0.0, 0.0)
        along = sum(v[axis] for v in values) + \
            self._handle_px * (len(values) - 1)
        across = max(v[1 - axis] for v in values)
        return (along, across) if axis == 0 else (across, along)

    def sizeHint(self):
        return self._combine(lambda w: w.sizeHint())

    def minimumSizeHint(self):
        axis = self._axis()

        def minimum(widget):
            size = list(widget.minimumSizeHint())
            size[axis] = self._minimum(widget)
            return size

        return self._combine(minimum)

    def layout(self, render=False):
        """Re-place the children (called by children that changed size)."""
        self._relayout()

    def saveState(self):
        state = super().saveState()
        state["sizes"] = self.sizes()
        return state

    def restoreState(self, state):
        super().restoreState(state)
        if isinstance(state, dict) and "sizes" in state:
            self.setSizes(state["sizes"])

    # -- layout ---------------------------------------------------------------------------------
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
        x, y, width, height = self.geometry("px")
        if width <= 0 or height <= 0 or not self._widgets:
            for handle in self._handles:
                handle.SetVisibility(False)
            return
        sizes = self.sizes()
        horizontal = self.isHorizontal()
        position = x if horizontal else y + height       # top for columns
        for i, widget in enumerate(self._widgets):
            size = sizes[i]
            shown = self._shown and size > 0
            if horizontal:
                rect = (position, y, size, height)
                position += size
            else:
                position -= size
                rect = (x, position, width, size)
            if size > 0:
                widget.setGeometry(*(px(v) for v in rect))
            if hasattr(widget, "SetVisibility"):
                widget.SetVisibility(shown)
            if i < len(self._handles):
                handle = self._handles[i]
                if horizontal:
                    handle.setGeometry(px(position), px(y),
                                       px(self._handle_px), px(height))
                    position += self._handle_px
                else:
                    position -= self._handle_px
                    handle.setGeometry(px(x), px(position), px(width),
                                       px(self._handle_px))
                handle.SetVisibility(self._shown)

    def close(self):
        for handle in self._handles:
            handle.close()
        self._handles = []
        return super().close()
