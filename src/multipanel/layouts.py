"""Qt-style layouts for MultiPanel widgets (``docs/QT_PARITY_PROPOSAL.md`` §6).

::

    from multipanel.layouts import FormLayout, HBoxLayout, VBoxLayout
    from multipanel.units import frac, px

    form = FormLayout()
    form.addRow("Density", density_spin)
    form.addRow("Material", material_field)

    buttons = HBoxLayout(spacing=6)
    buttons.addWidget(apply_button)
    buttons.addStretch()
    buttons.addWidget(close_button)

    column = VBoxLayout(margins=(8, 8, 8, 8))
    column.addLayout(form)
    column.addWidget(slider, stretch=1)
    column.addLayout(buttons)
    panel.setLayout(column)

Layouts compute in logical pixels (display px / ``ui_scale()``).  Margins,
spacing and spacer sizes accept numbers (px), ``px()``/``frac()`` lengths or
strings such as ``"8px"`` and ``"2%"``; fractions are resolved against the
viewport at every layout pass, so they follow window resizes.

Vertical layouts and grid rows run top to bottom, although VTK's y axis
points up.  A layout installed on a widget with ``setLayout`` relayouts once
per frame after anything invalidates it: a child's ``updateGeometry()`` or
visibility change, the host's geometry change, or a window resize.
"""
from __future__ import annotations

import contextlib
import functools
import weakref

from .core import QWIDGETSIZE_MAX, SizePolicy, WidgetMixin
from .units import Length, parse_length, to_px

__all__ = [
    "BoxLayout",
    "FormLayout",
    "GridLayout",
    "HBoxLayout",
    "Layout",
    "SpacerItem",
    "VBoxLayout",
    "WidgetItem",
    "layout_pass",
]

GROW, EXPAND, SHRINK, IGNORE = (SizePolicy.GROW, SizePolicy.EXPAND,
                                SizePolicy.SHRINK, SizePolicy.IGNORE)
_EPS = 1e-6

_ALIGN_TOKENS = {
    "left": (0, "start"), "right": (0, "end"), "hcenter": (0, "center"),
    "bottom": (1, "start"), "top": (1, "end"), "vcenter": (1, "center"),
}


def parse_alignment(alignment):
    """Return ``(horizontal, vertical)`` of ``None|"start"|"center"|"end"``.

    Accepts ``None``, ``"center"`` or combinations such as ``"left|vcenter"``
    and ``"top right"``.  Start is left/bottom in VTK's coordinates.
    """
    if alignment is None:
        return (None, None)
    if isinstance(alignment, tuple):
        return alignment
    result = [None, None]
    for token in str(alignment).replace("|", " ").replace(",", " ").split():
        token = token.lower()
        if token == "center":
            result = ["center", "center"]
            continue
        if token not in _ALIGN_TOKENS:
            raise ValueError(f"unknown alignment {token!r}")
        axis, value = _ALIGN_TOKENS[token]
        result[axis] = value
    return tuple(result)


# -- per-pass hint cache -------------------------------------------------------------
#
# One layout pass asks each item for its hints many times (every spec()
# along both axes, every aggregate of a parent). Within a pass nothing that
# a hint depends on changes, so hints are cached for the pass and dropped
# at its end: no hint is ever reused across passes, so widgets that change
# their text without updateGeometry() (the legacy controls) still get
# measured afresh on the next pass.

_PASS = {"depth": 0, "memo": None}


@contextlib.contextmanager
def layout_pass():
    """Cache size hints until the outermost ``layout_pass`` ends."""
    if _PASS["depth"] == 0:
        _PASS["memo"] = {}
    _PASS["depth"] += 1
    try:
        yield
    finally:
        _PASS["depth"] -= 1
        if _PASS["depth"] == 0:
            _PASS["memo"] = None


def _memoized(method):
    name = method.__name__

    @functools.wraps(method)
    def wrapper(self):
        memo = _PASS["memo"]
        if memo is None:
            with layout_pass():
                return wrapper(self)
        key = (id(self), name)
        value = memo.get(key)
        if value is None:
            value = memo[key] = method(self)
        return value

    return wrapper


def distribute(specs, available):
    """Share ``available`` logical px between items along one axis.

    ``specs`` are ``(minimum, hint, maximum, policy, stretch)`` tuples.
    Items with a stretch factor share the total space of the stretched
    items by weight (Qt semantics); any remaining spare space goes to
    expanding items, then to any item that may grow, equally; a deficit is
    taken from shrinkable items in proportion to their slack.  Returns the
    sizes; they sum to less than ``available`` only when nothing can grow,
    and to more only when minimum sizes cannot fit.
    """
    sizes = []
    for minimum, hint, maximum, policy, _stretch in specs:
        preferred = minimum if policy & IGNORE else hint
        sizes.append(min(max(preferred, minimum), maximum))
    total = sum(sizes)
    if available >= total - _EPS:
        extra = available - total
        growable = [index for index, spec in enumerate(specs)
                    if spec[3] & GROW and spec[2] > sizes[index] + _EPS]
        stretched = [index for index in growable if specs[index][4] > 0]
        expanding = [index for index in growable if specs[index][3] & EXPAND]
        if stretched:
            # As in Qt, stretch factors divide the *total* space of the
            # stretched items, not only the spare space: hints that exceed
            # their share are kept, maximum sizes cap, the rest share by weight.
            extra = _stretch_fill(sizes, specs, stretched, extra)
            growable = [index for index in growable if index not in stretched
                        and specs[index][2] > sizes[index] + _EPS]
            expanding = [index for index in growable
                         if specs[index][3] & EXPAND]
            weights = {index: 1.0 for index in (expanding or growable)}
        elif expanding:
            weights = {index: 1.0 for index in expanding}
        else:
            weights = {index: 1.0 for index in growable}
        while extra > _EPS and weights:
            total_weight = sum(weights.values())
            given = 0.0
            for index, weight in list(weights.items()):
                share = extra * weight / total_weight
                room = specs[index][2] - sizes[index]
                step = min(share, room)
                sizes[index] += step
                given += step
                if room - step <= _EPS:
                    del weights[index]
            extra -= given
            if given <= _EPS:
                break
        return sizes
    deficit = total - available
    shrinkable = {index: sizes[index] - spec[0]
                  for index, spec in enumerate(specs)
                  if spec[3] & SHRINK and sizes[index] - spec[0] > _EPS}
    while deficit > _EPS and shrinkable:
        total_slack = sum(shrinkable.values())
        taken = 0.0
        for index, slack in list(shrinkable.items()):
            step = min(slack, deficit * slack / total_slack)
            sizes[index] -= step
            taken += step
            shrinkable[index] = slack - step
            if shrinkable[index] <= _EPS:
                del shrinkable[index]
        deficit -= taken
        if taken <= _EPS:
            break
    return sizes


def _stretch_fill(sizes, specs, indices, extra):
    """Water-fill stretched items in place; return the unused space."""
    pool = extra + sum(sizes[index] for index in indices)
    active = list(indices)
    fixed = {}
    while active:
        total_weight = sum(float(specs[index][4]) for index in active)
        unit = pool / total_weight
        settled = False
        for index in list(active):
            target = unit * float(specs[index][4])
            maximum = specs[index][2]
            if target < sizes[index] - _EPS:
                fixed[index] = sizes[index]      # hint exceeds its share
            elif target > maximum + _EPS:
                fixed[index] = maximum
            else:
                continue
            pool -= fixed[index]
            active.remove(index)
            settled = True
        if not settled:
            for index in active:
                fixed[index] = unit * float(specs[index][4])
            pool = 0.0
            break
    for index, value in fixed.items():
        sizes[index] = value
    return max(0.0, pool)


def _place(cell_start, cell_size, size, alignment):
    if alignment == "end":
        return cell_start + cell_size - size
    if alignment == "start":
        return cell_start
    return cell_start + (cell_size - size) / 2.0


class _Item:
    """Common protocol for everything a layout arranges."""

    alignment = (None, None)
    stretch = 0

    def isEmpty(self):
        return False

    def sizeHint(self):
        return (0.0, 0.0)

    def minimumSize(self):
        return (0.0, 0.0)

    def maximumSize(self):
        return (QWIDGETSIZE_MAX, QWIDGETSIZE_MAX)

    def policy(self, axis):
        return SizePolicy.Preferred

    def policyStretch(self, axis):
        return 0

    def spec(self, axis):
        """``(minimum, hint, maximum, policy, stretch)`` along ``axis``."""
        return (self.minimumSize()[axis], self.sizeHint()[axis],
                self.maximumSize()[axis], self.policy(axis),
                self.stretch or self.policyStretch(axis))

    def setGeometry(self, rect):
        pass

    def _fit(self, rect):
        """Size and position within ``rect`` honouring max size/alignment."""
        out = []
        hint = self.sizeHint()
        maximum = self.maximumSize()
        for axis in (0, 1):
            start, extent = rect[axis], rect[axis + 2]
            align = self.alignment[axis]
            if align is not None and not self.policy(axis) & EXPAND:
                size = min(extent, hint[axis])
            else:
                size = extent
            size = max(0.0, min(size, maximum[axis]))
            out.append((_place(start, extent, size, align or "center"), size))
        return (out[0][0], out[1][0], out[0][1], out[1][1])


class WidgetItem(_Item):
    """A widget managed by a layout."""

    def __init__(self, widget, stretch=0, alignment=None):
        self.widget = widget
        self.stretch = int(stretch)
        self.alignment = parse_alignment(alignment)
        # A form label's buddy is its row's field: the label is hidden (and
        # takes no space) whenever the field is.
        self.buddy = None

    # The widget's own hints, measured once per pass (minimumSize,
    # maximumSize and sizeHint all need them).
    @_memoized
    def _widget_hint(self):
        return self.widget.sizeHint()

    @_memoized
    def _widget_minimum_hint(self):
        return self.widget.minimumSizeHint()

    def _policy_object(self):
        return self.widget.sizePolicy()

    def effectivelyHidden(self):
        """Hidden explicitly, or a label whose field is hidden."""
        if self.widget.isClosed() or self.widget.isHidden():
            return True
        return self.buddy is not None and self.buddy.isEmpty()

    def isEmpty(self):
        if self.widget.isClosed():
            return True
        if self.buddy is not None and self.buddy.isEmpty():
            return True
        # Explicit hide() only: a widget hidden along with its panel or an
        # inactive dock tab must keep its place in the layout.
        if not self.widget.isHidden():
            return False
        return not self._policy_object().retainSizeWhenHidden

    def policy(self, axis):
        return self._policy_object().policy(axis)

    def policyStretch(self, axis):
        return self._policy_object().stretch(axis)

    def _explicit(self, name):
        return getattr(self.widget, name, None)

    @_memoized
    def minimumSize(self):
        explicit = self._explicit("_ui_minimum_size")
        explicit_size = self.widget.minimumSize()
        hint = self._widget_hint()
        min_hint = self._widget_minimum_hint()
        result = []
        for axis in (0, 1):
            policy = self.policy(axis)
            if explicit is not None and explicit_size[axis] > 0:
                value = explicit_size[axis]
            elif policy & IGNORE:
                value = 0.0
            elif policy & SHRINK:
                value = min_hint[axis]
            else:
                value = max(hint[axis], min_hint[axis])
            result.append(float(value))
        return tuple(result)

    @_memoized
    def maximumSize(self):
        explicit = self.widget.maximumSize()
        hint = self._widget_hint()
        minimum = self.minimumSize()
        result = []
        for axis in (0, 1):
            value = explicit[axis]
            if not self.policy(axis) & GROW:
                value = min(value, max(hint[axis], minimum[axis]))
            result.append(max(minimum[axis], value))
        return tuple(result)

    @_memoized
    def sizeHint(self):
        hint = self._widget_hint()
        minimum = self.minimumSize()
        maximum_explicit = self.widget.maximumSize()
        return tuple(min(max(hint[axis], minimum[axis]),
                         max(minimum[axis], maximum_explicit[axis]))
                     for axis in (0, 1))

    def setGeometry(self, rect):
        from .units import px

        x, y, width, height = self._fit(rect)
        self.widget.setGeometry(px(x), px(y), px(width), px(height))


class SpacerItem(_Item):
    """Blank space; ``addStretch`` and ``addSpacing`` create these."""

    def __init__(self, width=0, height=0, horizontal=SizePolicy.Minimum,
                 vertical=SizePolicy.Minimum, stretch=0, layout=None):
        self._size = (parse_length(width, "px"), parse_length(height, "px"))
        self._policies = (int(horizontal), int(vertical))
        self.stretch = int(stretch)
        self._layout_ref = None if layout is None else weakref.ref(layout)

    def _resolved(self):
        layout = None if self._layout_ref is None else self._layout_ref()
        extent = layout._extent() if layout is not None else (1.0, 1.0)
        return tuple(to_px(self._size[axis], extent[axis]) for axis in (0, 1))

    def sizeHint(self):
        return self._resolved()

    def minimumSize(self):
        size = self._resolved()
        return tuple(0.0 if self._policies[axis] & SHRINK else size[axis]
                     for axis in (0, 1))

    def maximumSize(self):
        size = self._resolved()
        return tuple(QWIDGETSIZE_MAX if self._policies[axis] & GROW
                     else size[axis] for axis in (0, 1))

    def policy(self, axis):
        return self._policies[axis]


class Layout(_Item):
    """Base class: margins, spacing, ownership and invalidation."""

    def __init__(self, margins=None, spacing=6):
        self._items = []
        self._parent_widget_ref = None
        self._parent_layout_ref = None
        self._scheduled = False
        self._dirty = True
        self._resize_tag = None
        self._geometry = None
        self._applying = False
        self.stretch = 0
        self.alignment = (None, None)
        self.passes = 0                  # completed layout passes (diagnostic)
        self._spacing = parse_length(spacing, "px")
        self._margins = tuple(parse_length(value, "px") for value in (
            margins if margins is not None else (0, 0, 0, 0)))

    # -- configuration ------------------------------------------------------------
    def setContentsMargins(self, left, top, right, bottom):
        self._margins = tuple(parse_length(value, "px")
                              for value in (left, top, right, bottom))
        self.invalidate()

    def contentsMargins(self):
        extent = self._extent()
        return tuple(to_px(value, extent[index % 2])
                     for index, value in enumerate(self._margins))

    def spacing(self):
        return to_px(self._spacing, self._extent()[self._spacing_axis()])

    def setSpacing(self, spacing):
        self._spacing = parse_length(spacing, "px")
        self.invalidate()

    def _spacing_axis(self):
        return 0

    # -- ownership ---------------------------------------------------------------------
    def parentWidget(self):
        """The widget whose geometry this layout (or its ancestor) manages."""
        layout = self
        while layout is not None:
            ref = layout._parent_widget_ref
            if ref is not None:
                return ref()
            parent = layout._parent_layout_ref
            layout = parent() if parent is not None else None
        return None

    def _extent(self):
        widget = self.parentWidget()
        if widget is None:
            return (1.0, 1.0)
        try:
            return widget.viewportExtent()
        except RuntimeError:
            return (1.0, 1.0)

    def _attach(self, widget):
        self._parent_widget_ref = weakref.ref(widget)
        widget.geometryChanged.connect(self._on_host_geometry, unique=True)
        self._watch_window(widget)
        self._adopt_children()
        self.invalidate()

    def _detach(self):
        widget = self.parentWidget()
        if widget is not None:
            try:
                widget.geometryChanged.disconnect(self._on_host_geometry)
            except ValueError:
                pass
            if self._resize_tag is not None:
                subject, tag = self._resize_tag
                widget.observerRegistry().remove(subject, tag)
        self._resize_tag = None
        self._parent_widget_ref = None

    def _watch_window(self, widget):
        interactor = getattr(widget, "interactor", None)
        if interactor is None and hasattr(widget, "GetInteractor"):
            interactor = widget.GetInteractor()
        if interactor is None:
            return
        window = interactor.GetRenderWindow()
        tag = widget.ownObserver(
            window, "WindowResizeEvent", lambda *_: self.invalidate())
        self._resize_tag = (window, tag)

    def _on_host_geometry(self, *_args):
        if self._applying:
            return
        widget = self.parentWidget()
        if (not self._dirty and widget is not None and self._geometry is not None
                and widget.contentsRect() == self._geometry):
            return
        self.invalidate()

    def _adopt_children(self):
        widget = self.parentWidget()
        for item in self._items:
            if isinstance(item, WidgetItem):
                if widget is not None and item.widget is not widget:
                    item.widget.setParent(widget)
            elif isinstance(item, Layout):
                item._adopt_children()

    def _add_item(self, item, index=None):
        if isinstance(item, WidgetItem):
            widget = item.widget
            if not isinstance(widget, WidgetMixin):
                raise TypeError("layouts manage WidgetMixin widgets")
            existing = getattr(widget, "_ui_parent_layout", None)
            owner = existing() if existing is not None else None
            if owner is not None and owner is not self:
                owner.removeWidget(widget)
            widget._ui_parent_layout = weakref.ref(self)
            widget.visibilityChanged.connect(self._child_changed, unique=True)
            parent = self.parentWidget()
            if parent is not None:
                widget.setParent(parent)
        elif isinstance(item, Layout):
            if item.parentWidget() is not None and item._parent_widget_ref:
                raise ValueError("layout already installed on a widget")
            item._parent_layout_ref = weakref.ref(self)
            item._adopt_children()
        if index is None:
            self._items.append(item)
        else:
            self._items.insert(int(index), item)
        self.invalidate()
        return item

    def _child_changed(self, *_args):
        self.invalidate()

    def removeWidget(self, widget):
        for item in list(self._items):
            if isinstance(item, WidgetItem) and item.widget is widget:
                self._items.remove(item)
                widget._ui_parent_layout = None
                try:
                    widget.visibilityChanged.disconnect(self._child_changed)
                except ValueError:
                    pass
                self.invalidate()
                return True
            if isinstance(item, Layout) and item.removeWidget(widget):
                return True
        return False

    def count(self):
        return len(self._items)

    def itemAt(self, index):
        return self._items[index] if 0 <= index < len(self._items) else None

    def indexOf(self, widget):
        for index, item in enumerate(self._items):
            if isinstance(item, WidgetItem) and item.widget is widget:
                return index
        return -1

    def widgetItems(self):
        """All WidgetItems in this layout and nested layouts."""
        found = []
        for item in self._items:
            if isinstance(item, WidgetItem):
                found.append(item)
            elif isinstance(item, Layout):
                found.extend(item.widgetItems())
        return found

    def widgets(self):
        """All widgets managed by this layout and nested layouts."""
        found = []
        for item in self._items:
            if isinstance(item, WidgetItem):
                found.append(item.widget)
            elif isinstance(item, Layout):
                found.extend(item.widgets())
        return found

    # -- invalidation ----------------------------------------------------------------
    def invalidate(self):
        """Mark dirty and schedule one relayout before the next render."""
        self._dirty = True
        parent_ref = getattr(self, "_parent_layout_ref", None)
        parent = parent_ref() if parent_ref is not None else None
        if parent is not None:
            parent.invalidate()
            return
        widget = self.parentWidget()
        if widget is None or self._scheduled:
            return
        scheduler = widget.renderScheduler()
        if scheduler is None:
            self.activate()
            return
        self._scheduled = True
        scheduler.defer(self.activate)

    def isDirty(self):
        return self._dirty

    def activate(self):
        """Lay out now into the host widget's contents rectangle.

        A host that must resize itself first (a panel that grows with its
        content, or one stacked in a dock) implements
        ``layoutRequestEvent(layout)``, as Qt widgets handle
        ``QEvent::LayoutRequest``, and calls ``setGeometry`` itself.
        """
        self._scheduled = False
        widget = self.parentWidget()
        if widget is None or self._parent_layout_ref is not None:
            return False
        handler = getattr(widget, "layoutRequestEvent", None)
        if callable(handler):
            self._applying = True
            try:
                handler(self)
            finally:
                self._applying = False
            return True
        rect = widget.contentsRect()
        if rect is None:
            return False
        self._applying = True
        try:
            self.setGeometry(rect)
        finally:
            self._applying = False
        return True

    def geometry(self):
        return self._geometry

    def setGeometry(self, rect):
        self._geometry = tuple(float(value) for value in rect)
        left, top, right, bottom = self.contentsMargins()
        x, y, width, height = self._geometry
        inner = (x + left, y + bottom, max(0.0, width - left - right),
                 max(0.0, height - top - bottom))
        with layout_pass():
            self._do_layout(inner)
        self._dirty = False
        self.passes += 1

    def _do_layout(self, rect):
        raise NotImplementedError

    # -- as an item ----------------------------------------------------------------------
    def isEmpty(self):
        return all(item.isEmpty() for item in self._items)

    def _margin_totals(self):
        left, top, right, bottom = self.contentsMargins()
        return (left + right, top + bottom)

    def policy(self, axis):
        policies = [item.policy(axis) for item in self._items
                    if not item.isEmpty()]
        if any(policy & EXPAND for policy in policies):
            return SizePolicy.Expanding
        return SizePolicy.Preferred


class BoxLayout(Layout):
    """Lines items up horizontally (``"horizontal"``) or vertically."""

    def __init__(self, direction="vertical", margins=None, spacing=6):
        if direction not in ("horizontal", "vertical"):
            raise ValueError("direction must be 'horizontal' or 'vertical'")
        self._axis = 0 if direction == "horizontal" else 1
        super().__init__(margins, spacing)

    def direction(self):
        return "horizontal" if self._axis == 0 else "vertical"

    def _spacing_axis(self):
        return self._axis

    # -- building ----------------------------------------------------------------------
    def addWidget(self, widget, stretch=0, alignment=None):
        self._add_item(WidgetItem(widget, stretch, alignment))
        return widget

    def insertWidget(self, index, widget, stretch=0, alignment=None):
        self._add_item(WidgetItem(widget, stretch, alignment), index)
        return widget

    def addLayout(self, layout, stretch=0):
        layout.stretch = int(stretch)
        self._add_item(layout)
        return layout

    def addSpacing(self, size):
        """Fixed space along the layout direction."""
        main = parse_length(size, "px")
        if self._axis == 0:
            item = SpacerItem(main, 0, SizePolicy.Fixed, SizePolicy.Minimum,
                              layout=self)
        else:
            item = SpacerItem(0, main, SizePolicy.Minimum, SizePolicy.Fixed,
                              layout=self)
        return self._add_item(item)

    def addStretch(self, stretch=1):
        """Expanding space that takes ``stretch`` shares of spare room."""
        if self._axis == 0:
            item = SpacerItem(0, 0, SizePolicy.Expanding, SizePolicy.Minimum,
                              stretch=stretch, layout=self)
        else:
            item = SpacerItem(0, 0, SizePolicy.Minimum, SizePolicy.Expanding,
                              stretch=stretch, layout=self)
        return self._add_item(item)

    def addSpacerItem(self, item):
        item._layout_ref = weakref.ref(self)
        return self._add_item(item)

    def setStretch(self, index, stretch):
        self._items[index].stretch = int(stretch)
        self.invalidate()

    def stretchAt(self, index):
        return self._items[index].stretch

    # -- sizes ---------------------------------------------------------------------------
    def _visible(self):
        return [item for item in self._items if not item.isEmpty()]

    def _combine(self, values_main, values_cross, axis_total, cross_total,
                 gaps):
        main = sum(values_main) + gaps
        cross = max(values_cross, default=0.0)
        if self._axis == 0:
            return (main + axis_total, cross + cross_total)
        return (cross + cross_total, main + axis_total)

    def _aggregate(self, getter):
        items = self._visible()
        gaps = self.spacing() * max(0, len(items) - 1)
        margin_w, margin_h = self._margin_totals()
        axis_total = margin_w if self._axis == 0 else margin_h
        cross_total = margin_h if self._axis == 0 else margin_w
        main = [getter(item)[self._axis] for item in items]
        cross = [getter(item)[1 - self._axis] for item in items]
        return self._combine(main, cross, axis_total, cross_total, gaps)

    @_memoized
    def sizeHint(self):
        return self._aggregate(lambda item: item.sizeHint())

    @_memoized
    def minimumSize(self):
        return self._aggregate(lambda item: item.minimumSize())

    @_memoized
    def maximumSize(self):
        items = self._visible()
        if not items:
            return (QWIDGETSIZE_MAX, QWIDGETSIZE_MAX)
        margin_w, margin_h = self._margin_totals()
        gaps = self.spacing() * max(0, len(items) - 1)
        main = min(QWIDGETSIZE_MAX, sum(item.maximumSize()[self._axis]
                                        for item in items) + gaps)
        cross = QWIDGETSIZE_MAX
        if all(not item.policy(1 - self._axis) & GROW for item in items):
            cross = max(item.maximumSize()[1 - self._axis] for item in items)
        if self._axis == 0:
            return (min(QWIDGETSIZE_MAX, main + margin_w),
                    min(QWIDGETSIZE_MAX, cross + margin_h))
        return (min(QWIDGETSIZE_MAX, cross + margin_w),
                min(QWIDGETSIZE_MAX, main + margin_h))

    # -- geometry ------------------------------------------------------------------------
    def _do_layout(self, rect):
        items = self._visible()
        if not items:
            return
        x, y, width, height = rect
        spacing = self.spacing()
        main_extent = width if self._axis == 0 else height
        available = max(0.0, main_extent - spacing * (len(items) - 1))
        sizes = distribute([item.spec(self._axis) for item in items],
                           available)
        if self._axis == 0:
            cursor = x
            for item, size in zip(items, sizes):
                item.setGeometry((cursor, y, size, height))
                cursor += size + spacing
        else:
            cursor = y + height                 # top edge; rows run downward
            for item, size in zip(items, sizes):
                item.setGeometry((x, cursor - size, width, size))
                cursor -= size + spacing


class HBoxLayout(BoxLayout):
    def __init__(self, margins=None, spacing=6):
        super().__init__("horizontal", margins, spacing)


class VBoxLayout(BoxLayout):
    def __init__(self, margins=None, spacing=6):
        super().__init__("vertical", margins, spacing)


class _GridCell:
    __slots__ = ("item", "row", "column", "row_span", "column_span")

    def __init__(self, item, row, column, row_span, column_span):
        self.item = item
        self.row = row
        self.column = column
        self.row_span = row_span
        self.column_span = column_span

    def start(self, axis):
        return self.column if axis == 0 else self.row

    def span(self, axis):
        return self.column_span if axis == 0 else self.row_span


class GridLayout(Layout):
    """Rows and columns; row 0 is at the top."""

    def __init__(self, margins=None, spacing=6):
        self._cells = []
        self._stretch = ({}, {})            # column, row
        self._minimum = ({}, {})
        self._spacings = [None, None]       # horizontal, vertical
        super().__init__(margins, spacing)

    # -- building ----------------------------------------------------------------------
    def addWidget(self, widget, row, column, rowSpan=1, columnSpan=1,
                  alignment=None):
        item = WidgetItem(widget, 0, alignment)
        self._cells.append(_GridCell(item, int(row), int(column),
                                     max(1, int(rowSpan)),
                                     max(1, int(columnSpan))))
        self._add_item(item)
        return widget

    def addLayout(self, layout, row, column, rowSpan=1, columnSpan=1):
        self._cells.append(_GridCell(layout, int(row), int(column),
                                     max(1, int(rowSpan)),
                                     max(1, int(columnSpan))))
        self._add_item(layout)
        return layout

    def removeWidget(self, widget):
        self._cells = [cell for cell in self._cells
                       if not (isinstance(cell.item, WidgetItem)
                               and cell.item.widget is widget)]
        return super().removeWidget(widget)

    def setColumnStretch(self, column, stretch):
        self._stretch[0][int(column)] = int(stretch)
        self.invalidate()

    def setRowStretch(self, row, stretch):
        self._stretch[1][int(row)] = int(stretch)
        self.invalidate()

    def setColumnMinimumWidth(self, column, width):
        self._minimum[0][int(column)] = parse_length(width, "px")
        self.invalidate()

    def setRowMinimumHeight(self, row, height):
        self._minimum[1][int(row)] = parse_length(height, "px")
        self.invalidate()

    def setHorizontalSpacing(self, spacing):
        self._spacings[0] = parse_length(spacing, "px")
        self.invalidate()

    def setVerticalSpacing(self, spacing):
        self._spacings[1] = parse_length(spacing, "px")
        self.invalidate()

    def axisSpacing(self, axis):
        value = self._spacings[axis]
        if value is None:
            value = self._spacing
        return to_px(value, self._extent()[axis])

    def rowCount(self):
        return max((cell.row + cell.row_span for cell in self._cells),
                   default=0)

    def columnCount(self):
        return max((cell.column + cell.column_span for cell in self._cells),
                   default=0)

    def itemAtPosition(self, row, column):
        for cell in self._cells:
            if (cell.row <= row < cell.row + cell.row_span
                    and cell.column <= column < cell.column + cell.column_span):
                return cell.item
        return None

    # -- track computation ---------------------------------------------------------------
    def _tracks(self, axis):
        """Per-track ``[minimum, hint, maximum, policy, stretch, used]``."""
        count = self.columnCount() if axis == 0 else self.rowCount()
        extent = self._extent()[axis]
        tracks = []
        for index in range(count):
            minimum = to_px(self._minimum[axis].get(index, Length(0, "px")),
                            extent)
            tracks.append([minimum, minimum, 0.0, 0,
                           self._stretch[axis].get(index, 0), False])
        cells = [cell for cell in self._cells if not cell.item.isEmpty()]
        for cell in cells:
            if cell.span(axis) != 1:
                continue
            track = tracks[cell.start(axis)]
            item_min, item_hint, item_max, policy, stretch = cell.item.spec(axis)
            track[0] = max(track[0], item_min)
            track[1] = max(track[1], item_hint)
            track[2] = max(track[2], item_max)
            track[3] |= policy
            if not self._stretch[axis].get(cell.start(axis)):
                track[4] = max(track[4], stretch)
            track[5] = True
        spacing = self.axisSpacing(axis)
        for cell in cells:
            span = cell.span(axis)
            if span == 1:
                continue
            covered = tracks[cell.start(axis):cell.start(axis) + span]
            item_min, item_hint, _item_max, policy, _stretch = cell.item.spec(axis)
            gaps = spacing * (span - 1)
            for position, needed in ((0, item_min), (1, item_hint)):
                have = sum(track[position] for track in covered) + gaps
                if needed > have:
                    covered[-1][position] += needed - have
            for track in covered:
                track[3] |= policy
                track[5] = True
        for index, track in enumerate(tracks):
            track[1] = max(track[1], track[0])
            if not track[5]:
                track[2] = track[0]
            elif track[3] & GROW or self._stretch[axis].get(index, 0) > 0:
                # As in Qt, an explicitly stretched track grows even when its
                # items cannot; they are then aligned within it.
                track[2] = QWIDGETSIZE_MAX
                track[3] |= GROW
            else:
                track[2] = max(track[1], min(track[2], track[1]))
        return tracks

    def _used(self, tracks):
        return [track for track in tracks if track[5] or track[0] > 0]

    def _aggregate(self, position):
        result = []
        margins = self._margin_totals()
        for axis in (0, 1):
            tracks = self._used(self._tracks(axis))
            gaps = self.axisSpacing(axis) * max(0, len(tracks) - 1)
            total = sum(track[position] for track in tracks) + gaps
            result.append(min(QWIDGETSIZE_MAX, total + margins[axis]))
        return tuple(result)

    @_memoized
    def sizeHint(self):
        return self._aggregate(1)

    @_memoized
    def minimumSize(self):
        return self._aggregate(0)

    @_memoized
    def maximumSize(self):
        return self._aggregate(2)

    def _do_layout(self, rect):
        x, y, width, height = rect
        starts, sizes = [], []
        for axis, origin, extent in ((0, x, width), (1, y, height)):
            tracks = self._tracks(axis)
            used = [index for index, track in enumerate(tracks)
                    if track[5] or track[0] > 0]
            spacing = self.axisSpacing(axis)
            available = max(0.0, extent - spacing * max(0, len(used) - 1))
            shares = distribute([tuple(tracks[index][:5]) for index in used],
                                available)
            size = [0.0] * len(tracks)
            for index, share in zip(used, shares):
                size[index] = share
            start = [0.0] * len(tracks)
            if axis == 0:
                cursor = origin
                for index in range(len(tracks)):
                    start[index] = cursor
                    if index in used:
                        cursor += size[index] + spacing
            else:
                cursor = origin + extent          # rows run top to bottom
                for index in range(len(tracks)):
                    start[index] = cursor - size[index]
                    if index in used:
                        cursor -= size[index] + spacing
            starts.append(start)
            sizes.append(size)
        spacing = (self.axisSpacing(0), self.axisSpacing(1))
        for cell in self._cells:
            if cell.item.isEmpty():
                continue
            c0, c1 = cell.column, cell.column + cell.column_span - 1
            r0, r1 = cell.row, cell.row + cell.row_span - 1
            left = starts[0][c0]
            right = starts[0][c1] + sizes[0][c1]
            top = starts[1][r0] + sizes[1][r0]
            bottom = starts[1][r1]
            cell.item.setGeometry((left, bottom, max(0.0, right - left),
                                   max(0.0, top - bottom)))


class FormLayout(GridLayout):
    """Two columns of label/field rows.

    ``addRow("Label", field)`` creates a ``TextWidget`` label when the layout
    is installed on a widget (the label needs its renderer); a widget may be
    passed instead.  ``labelFactory(text, host)`` customises creation.
    """

    def __init__(self, margins=None, spacing=6, label_alignment="left|vcenter",
                 label_factory=None):
        super().__init__(margins, spacing)
        self.setColumnStretch(1, 1)
        self._label_alignment = label_alignment
        self._pending_labels = []
        self.labelFactory = label_factory or _default_label_factory

    def addRow(self, label, field=None):
        row = self.rowCount()
        if field is None:
            self._add_field(label, row, 0, 2)
            return row
        self._add_field(field, row, 1, 1)
        if isinstance(label, str):
            self._pending_labels.append((row, label))
        elif label is not None:
            GridLayout.addWidget(self, label, row, 0,
                                 alignment=self._label_alignment)
            self._link_label(row)
        self._create_pending_labels()
        return row

    def _link_label(self, row):
        label = self.itemAtPosition(row, 0)
        field = self.itemAtPosition(row, 1)
        if isinstance(label, WidgetItem) and field is not None:
            label.buddy = field

    def _add_field(self, field, row, column, span):
        if isinstance(field, Layout):
            GridLayout.addLayout(self, field, row, column, 1, span)
        else:
            GridLayout.addWidget(self, field, row, column, 1, span)

    def labelForRow(self, row):
        item = self.itemAtPosition(row, 0)
        return item.widget if isinstance(item, WidgetItem) else None

    def _create_pending_labels(self):
        host = self.parentWidget()
        if host is None or not self._pending_labels:
            return
        pending, self._pending_labels = self._pending_labels, []
        for row, text in pending:
            label = self.labelFactory(text, host)
            GridLayout.addWidget(self, label, row, 0,
                                 alignment=self._label_alignment)
            self._link_label(row)

    def _adopt_children(self):
        self._create_pending_labels()
        super()._adopt_children()


def _default_label_factory(text, host):
    from .controls import TextWidget

    return TextWidget(host.renderer, host.interactor, text=text,
                      editable=False, scale_text_to_widget=False,
                      text_color=getattr(host, "text_color", (0, 0, 0)),
                      horizontal_alignment="left")
