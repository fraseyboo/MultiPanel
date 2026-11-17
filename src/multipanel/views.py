"""List, tree and table views of an item model (``QT_PARITY_PROPOSAL`` §13, W9).

The views show a :class:`~multipanel.models.ItemModel` and draw only the
rows that are visible, so a model with 10k rows costs what 20 do::

    model = ListModel(["Air", "Lead", "Water"])
    view = ListView(renderer, interactor, model=model)
    view.setGeometry("20px", "20px", "220px", "300px")
    view.clicked.connect(lambda index: print(index.data()))

    tree = TreeView(renderer, interactor,
                    model=TreeModel.from_hierarchy(scene_root))
    table = TableView(renderer, interactor,
                      model=TableModel(rows, headers=("Cell", "Material")))

Rows are clipped exactly to the view (they live on a
:class:`~multipanel.layers.LinkedRenderer`, as in a
:class:`~multipanel.scrollarea.ScrollArea`) and scroll smoothly with the
wheel. Each view has a :class:`~multipanel.models.SelectionModel`: Ctrl
toggles and Shift selects a range in ``"extended"`` mode. Checkable items
draw a check box, and ``"decoration"`` may be an RGB swatch or an icon
name from ``icons/png_icons``. ``"toolTip"`` shows on hover.

Model changes mark the view dirty; the rows are re-synced once, before the
next frame, and only text and icon actors whose content changed are
touched (:meth:`ItemView.doItemsLayout` syncs immediately).
"""
from __future__ import annotations

import math
import os
from functools import partial

import vtk

from ._widget_support import (
    font_scale,
    UI_Z_PANEL_CONTROL,
    apply_ui_font,
    rounded_rect_polydata,
    ui_layer,
    ui_scale,
)
from .core import Signal, SizePolicy, WidgetMixin
from .events import CTRL, SHIFT
from .layers import LinkedRenderer
from .models import (
    CHECK_STATE, CHECKED, DECORATION, DISPLAY, PARTIALLY_CHECKED, TOOLTIP,
    UNCHECKED, ItemModel, ListModel, ModelIndex, SelectionModel,
)
from .resources import ICON_ROOT
from .scrollarea import ScrollBar
from .standard import _DEFAULT_TOKENS, _merge, _polyline, _rgba, _shape_actor
from .style import Style, _outline
from .units import px
from .vtk_compat import add_actor_2d, remove_actor_2d

__all__ = ["ItemView", "ListView", "TableView", "TreeView"]

ELLIPSIS = "…"


# ---------------------------------------------------------------------------------------
# Text measurement and icons


class _Measure:
    """Cached text widths for eliding (one per font size)."""

    LIMIT = 4096

    def __init__(self):
        self._property = vtk.vtkTextProperty()
        apply_ui_font(self._property)
        self._mono = vtk.vtkTextProperty()
        self._mono.SetFontFamilyToCourier()
        self._cache = {}

    def width(self, text, size, dpi, bold=False, monospace=False):
        key = (text, size, dpi, bold, monospace)
        width = self._cache.get(key)
        if width is None:
            if len(self._cache) > self.LIMIT:
                self._cache.clear()
            if not text:
                width = 0.0
            else:
                prop = self._mono if monospace else self._property
                prop.SetFontSize(size)
                prop.SetBold(bool(bold))
                box = [0, 0, 0, 0]
                vtk.vtkTextRenderer.GetInstance().GetBoundingBox(
                    prop, text, box, dpi)
                width = float(box[1] - box[0] + 1)
            self._cache[key] = width
        return width

    def elide(self, text, available, size, dpi, bold=False):
        """``text`` cut to ``available`` display px with an ellipsis."""
        if available <= 0 or not text:
            return ""
        if self.width(text, size, dpi, bold) <= available:
            return text
        low, high = 0, len(text)
        while low < high:
            middle = (low + high + 1) // 2
            if self.width(text[:middle].rstrip() + ELLIPSIS, size, dpi,
                          bold) <= available:
                low = middle
            else:
                high = middle - 1
        if low == 0:
            return ELLIPSIS if self.width(ELLIPSIS, size, dpi,
                                          bold) <= available else ""
        return text[:low].rstrip() + ELLIPSIS


_MEASURE = None


def _measure():
    global _MEASURE
    if _MEASURE is None:
        _MEASURE = _Measure()
    return _MEASURE


_ICONS = {}


def _icon_image(name, size, tint=None):
    """RGBA image of icon ``name`` (a png_icons name or a path), ``size`` px.

    Single-colour icons (black or grey line art) are recoloured to
    ``tint`` so they stay visible in dark themes; colour icons are kept.
    """
    key = (name, size, tint)
    image = _ICONS.get(key)
    if image is not None:
        return image
    path = name if os.path.isabs(str(name)) else os.path.join(
        ICON_ROOT, "png_icons", f"{name}.png")
    if not os.path.exists(path):
        _ICONS[key] = False
        return False
    reader = vtk.vtkPNGReader()
    reader.SetFileName(path)
    resize = vtk.vtkImageResize()
    resize.SetInputConnection(reader.GetOutputPort())
    resize.SetOutputDimensions(int(size), int(size), 1)
    resize.Update()
    image = vtk.vtkImageData()
    image.DeepCopy(resize.GetOutput())
    if tint is not None:
        _tint_if_monochrome(image, tint)
    _ICONS[key] = image
    return image


def _tint_if_monochrome(image, tint):
    from vtkmodules.util.numpy_support import vtk_to_numpy

    scalars = image.GetPointData().GetScalars()
    if scalars is None or scalars.GetNumberOfComponents() != 4:
        return
    pixels = vtk_to_numpy(scalars)            # a view: edits write through
    opaque = pixels[pixels[:, 3] > 32, :3].astype(int)
    if len(opaque) == 0:
        return
    spread = (opaque.max(axis=1) - opaque.min(axis=1)).max()
    if spread > 24:                           # has colour: leave it alone
        return
    pixels[:, :3] = [int(round(255 * c)) for c in tint[:3]]
    scalars.Modified()


# ---------------------------------------------------------------------------------------
# Actor cells


def _quad(x, y, width, height, rgba):
    """Plain filled rectangle (cheaper than a rounded one)."""
    points = vtk.vtkPoints()
    polygon = vtk.vtkPolygon()
    for px_, py_ in ((x, y), (x + width, y), (x + width, y + height),
                     (x, y + height)):
        polygon.GetPointIds().InsertNextId(points.InsertNextPoint(px_, py_, 0))
    cells = vtk.vtkCellArray()
    cells.InsertNextCell(polygon)
    colors = vtk.vtkUnsignedCharArray()
    colors.SetNumberOfComponents(4)
    colors.InsertNextTuple4(*rgba)
    polydata = vtk.vtkPolyData()
    polydata.SetPoints(points)
    polydata.SetPolys(cells)
    polydata.GetCellData().SetScalars(colors)
    return polydata


class _TextCell:
    """One recycled text actor; ``show`` touches VTK only on change."""

    __slots__ = ("actor", "key")

    def __init__(self, renderer):
        self.actor = vtk.vtkTextActor()
        self.actor.IsUI = True
        self.actor.PickableOff()
        text_property = self.actor.GetTextProperty()
        apply_ui_font(text_property)
        text_property.SetVerticalJustificationToCentered()
        self.actor.SetVisibility(False)
        self.key = None
        add_actor_2d(renderer, self.actor)

    def show(self, text, x, y, color, size, align="left", bold=False):
        key = (text, round(x, 1), round(y, 1), tuple(color[:3]), size, align,
               bold)
        if key == self.key:
            return False
        self.key = key
        text_property = self.actor.GetTextProperty()
        text_property.SetFontSize(size)
        text_property.SetColor(*color[:3])
        text_property.SetBold(bool(bold))
        if align == "right":
            text_property.SetJustificationToRight()
        elif align == "center":
            text_property.SetJustificationToCentered()
        else:
            text_property.SetJustificationToLeft()
        self.actor.SetInput(text)
        self.actor.SetPosition(x, y)
        self.actor.SetVisibility(bool(text))
        return True

    def hide(self):
        if self.key is None:
            return False
        self.key = None
        self.actor.SetVisibility(False)
        return True

    def remove(self, renderer):
        remove_actor_2d(renderer, self.actor)


class _IconCell:
    """One recycled image actor for a ``"decoration"`` icon."""

    __slots__ = ("actor", "mapper", "key")

    def __init__(self, renderer):
        self.mapper = vtk.vtkImageMapper()
        self.mapper.SetColorWindow(255.0)
        self.mapper.SetColorLevel(127.5)
        self.actor = vtk.vtkActor2D()
        self.actor.SetMapper(self.mapper)
        self.actor.IsUI = True
        self.actor.PickableOff()
        self.actor.SetVisibility(False)
        self.key = None
        add_actor_2d(renderer, self.actor)

    def show(self, name, x, y, size, tint=None):
        key = (name, round(x, 1), round(y, 1), size, tint)
        if key == self.key:
            return False
        image = _icon_image(name, size, tint)
        self.key = key
        if not image:
            self.actor.SetVisibility(False)
            return True
        self.mapper.SetInputData(image)
        self.actor.SetPosition(x, y)
        self.actor.SetVisibility(True)
        return True

    def hide(self):
        if self.key is None:
            return False
        self.key = None
        self.actor.SetVisibility(False)
        return True

    def remove(self, renderer):
        remove_actor_2d(renderer, self.actor)


class _RowTip:
    """Adapter that lets the shared tooltip overlay show a row's tooltip."""

    enabled = True

    def __init__(self, view, key, text):
        self.view = view
        self.key = key
        self.hover_text = text
        self.pixel_bounds = (0, 0, 0, 0)
        self.actor = self

    def GetVisibility(self):
        return self.view.isVisible()

    def _update_pixel_bounds(self):
        bounds = self.view._row_display_rect(self.key)
        if bounds is not None:
            self.pixel_bounds = bounds

    def _point_in_bounds(self, x, y):
        hit = self.view._row_at_point(x, y)
        if hit is None:
            return False
        return self.view._key(hit[1]) == self.key


# ---------------------------------------------------------------------------------------
# Views


class ItemView(WidgetMixin):
    """Base of :class:`ListView`, :class:`TreeView` and :class:`TableView`.

    Sizes are logical px: ``ROW_PX`` per row, ``HEADER_PX`` for the
    header. Signals: ``pressed``, ``clicked``, ``doubleClicked`` and
    ``activated`` (double click or Enter) with the row's index;
    ``currentChanged(current, previous)`` and ``selectionChanged``.
    """

    FOCUS_POLICY = "StrongFocus"
    FONT_SIZE = 12
    ROW_PX = 24
    HEADER_PX = 24
    BAR_PX = 10
    PAD_PX = 6
    INDENT_PX = 16
    CHECK_PX = 14
    ICON_PX = 16
    MIN_COLUMN_PX = 24
    WHEEL_STEP_PX = 60
    SCROLL_MS = 140

    def __init__(self, renderer, interactor, parent=None, model=None,
                 object_name=None, ui_z_order=UI_Z_PANEL_CONTROL,
                 selection_mode="extended"):
        self.renderer = renderer
        self.interactor = interactor
        self.ui_z_order = int(ui_z_order)
        self._bounds = (0.0, 0.0, 0.0, 0.0)
        self._shown = True
        self._available = True
        self._model = None
        self._selection = None
        self._selection_mode = selection_mode
        self._dirty = True
        self._header_visible = False
        self._column_widths = {}
        self._stretch_last = True
        self._hover_key = None
        self._press = None              # (key, column, display row)
        self._header_drag = None        # (column, start x, start width)
        self._target = 0.0
        self._animation = None
        self._slots = []                # per visible row: {column: cells}
        self._header_cells = []
        self._shape_key = None
        self._frame_key = None
        self._tip = None
        self._geometry_cache = None
        self.actor_updates = 0          # text/icon actor changes (for tests)
        self.initWidget(object_name or type(self).__name__.lower(), parent)
        self.registerFocus(interactor, self.FOCUS_POLICY)

        layer = ui_layer(renderer)
        self._frame_actor = _shape_actor()
        self._header_lines = _shape_actor(point_colors=True)
        for prop in (self._frame_actor, self._header_lines):
            prop.SetVisibility(False)
            add_actor_2d(layer, prop)

        self._content = LinkedRenderer().link(layer)
        self._content.SetLayer(layer.GetLayer())
        self._content.SetViewport(0.0, 0.0, 0.0, 0.0)
        self._content.SetDraw(False)
        window = interactor.GetRenderWindow()
        window.AddRenderer(self._content)
        self._rows_actor = _shape_actor()
        self._rows_lines = _shape_actor(point_colors=True)
        self._rows_lines.GetProperty().SetLineWidth(1.5 * ui_scale())
        for prop in (self._rows_actor, self._rows_lines):
            prop.SetVisibility(False)
            add_actor_2d(self._content, prop)

        self._bar = ScrollBar(renderer, interactor, parent=self,
                              object_name=f"{self.objectName()}/bar")
        self._bar.ui_z_order = self.ui_z_order + 1
        self._bar.valueChanged.connect(self._on_bar_value)

        self.pressed = Signal(self)
        self.clicked = Signal(self)
        self.doubleClicked = Signal(self)
        self.activated = Signal(self)
        self.currentChanged = Signal(self)
        self.selectionChanged = Signal(self)

        self.registerWithRouter(interactor)
        self.ownObserver(window, "WindowResizeEvent",
                         lambda *_: self._invalidate())
        self.ownObserver(window, "StartEvent", self._before_render)
        self.setModel(model if model is not None else ListModel())

    # -- model ------------------------------------------------------------------------
    def model(self):
        return self._model

    def setModel(self, model):
        """Show ``model`` (an :class:`ItemModel`, or a list for a ListModel)."""
        if not isinstance(model, ItemModel):
            model = ListModel(list(model))
        if self._model is not None:
            for signal, slot in self._model_connections():
                signal.disconnect(slot)
        if self._selection is not None:
            self._selection.setModel(None)
        self._model = model
        for signal, slot in self._model_connections():
            signal.connect(slot)
        selection = SelectionModel(model, self._selection_mode)
        self.setSelectionModel(selection)
        self._model_changed()
        self._invalidate()

    def _model_connections(self):
        model = self._model
        return ((model.dataChanged, self._on_data_changed),
                (model.headerDataChanged, self._on_header_changed),
                (model.rowsInserted, self._on_rows_inserted),
                (model.rowsRemoved, self._on_rows_removed),
                (model.modelReset, self._on_model_reset))

    def selectionModel(self):
        return self._selection

    def setSelectionModel(self, selection):
        if self._selection is not None:
            self._selection.selectionChanged.disconnect(self._on_selection)
            self._selection.currentChanged.disconnect(self._on_current)
        self._selection = selection
        selection.selectionChanged.connect(self._on_selection)
        selection.currentChanged.connect(self._on_current)
        self._invalidate()

    def selectionMode(self):
        return self._selection.selectionMode()

    def setSelectionMode(self, mode):
        self._selection_mode = mode
        self._selection.setSelectionMode(mode)

    def currentIndex(self):
        return self._selection.currentIndex()

    def setCurrentIndex(self, index):
        """Make ``index`` current and selected, scrolling it into view."""
        self._selection.setCurrentIndex(index, "clearAndSelect")
        self._selection.setAnchor(index)
        self.scrollTo(index)

    def selectedIndexes(self):
        return self._selection.selectedRows()

    def selectAll(self):
        if self._selection.selectionMode() in ("multi", "extended"):
            self._selection.select(
                [self._index_at(row) for row in range(self._row_count())],
                "select")

    def clearSelection(self):
        self._selection.clearSelection()

    def _on_selection(self, selected, deselected):
        self._invalidate()
        self.selectionChanged.emit(selected, deselected)

    def _on_current(self, current, previous):
        self._invalidate()
        self.currentChanged.emit(current, previous)

    def _on_data_changed(self, top_left, bottom_right, roles):
        self._invalidate()

    def _on_header_changed(self, *_args):
        self._invalidate()

    def _on_rows_inserted(self, parent, first, last):
        self._structure_changed()

    def _on_rows_removed(self, parent, first, last):
        self._structure_changed()

    def _on_model_reset(self):
        self._model_changed()
        self._structure_changed()

    def _model_changed(self):
        """Hook: the whole model was replaced or reset."""

    def _structure_changed(self):
        self._invalidate()

    # -- rows (overridden by the tree) ---------------------------------------------------------
    def _row_count(self):
        return self._model.rowCount()

    def _index_at(self, row):
        return self._model.index(row, 0)

    def _depth_at(self, row):
        return 0

    def _display_row(self, index):
        """Display row of ``index`` (column ignored) or -1."""
        if index is None or not index.isValid() or index.parent().isValid():
            return -1
        return index.row()

    def _key(self, index):
        if index is None or not index.isValid():
            return None
        if index.column() != 0:
            index = index.sibling(index.row(), 0)
        return self._model.persistentKey(index)

    def _columns(self):
        """Model columns shown, left to right."""
        return list(range(self._model.columnCount()))

    def _branch_indent(self, row):
        """Logical px before the first column's content (tree indent)."""
        return 0.0

    # -- geometry ---------------------------------------------------------------------------
    def GetBounds(self):
        return self._bounds

    def SetBounds(self, x0, x1, y0, y1):
        self._bounds = (float(x0), float(x1), float(y0), float(y1))
        self._invalidate()

    def GetVisibility(self):
        return self._shown

    def SetVisibility(self, visible):
        visible = bool(visible)
        if visible == self._shown:
            return
        self._shown = visible
        if not visible:
            self._set_hover(None)
        self.doItemsLayout()

    def GetEnabled(self):
        return self._shown

    def SetEnabled(self, enabled):
        self.SetVisibility(enabled)

    def isVisible(self):
        return self._shown

    def isEnabled(self):
        return self._available

    def setEnabled(self, enabled):
        enabled = bool(enabled)
        if enabled != self._available:
            self._available = enabled
            self.enabledChanged.emit(enabled)
            self._invalidate()

    def defaultSizePolicy(self):
        return SizePolicy(SizePolicy.Expanding, SizePolicy.Expanding)

    def sizeHint(self):
        rows = min(max(self._row_count(), 3), 10)
        header = self.HEADER_PX if self._header_visible else 0
        return (200.0, rows * self.ROW_PX + header + 2)

    def minimumSizeHint(self):
        return (60.0, self.ROW_PX * 2 + 2)

    def rect(self):
        """Viewport-pixel rectangle of the view on its own renderer."""
        width, height = self.viewportExtent()
        x0, x1, y0, y1 = self._bounds
        return (x0 * width, y0 * height, (x1 - x0) * width, (y1 - y0) * height)

    def isHeaderHidden(self):
        return not self._header_visible

    def setHeaderHidden(self, hidden):
        self._header_visible = not hidden
        self._invalidate()

    def rowHeight(self):
        return self.ROW_PX

    def _geometry(self):
        """Layout in display px (window coords) and viewport px."""
        scale = ui_scale()
        x, y, width, height = self.rect()
        dx, dy = self.geometry("display")[:2] if width > 0 else (x, y)
        header = self.HEADER_PX * scale if self._header_visible else 0.0
        inner_h = max(0.0, height - 2 - header)
        content_h = self._row_count() * self.ROW_PX
        bar = content_h * scale > inner_h + 0.5
        bar_w = self.BAR_PX * scale if bar else 0.0
        rows_w = max(0.0, width - 2 - bar_w)
        return {
            "scale": scale, "rect": (x, y, width, height),
            "origin": (dx - x, dy - y),          # viewport -> display
            "header": (x + 1, y + height - 1 - header, rows_w, header),
            "rows": (x + 1, y + 1, rows_w, inner_h),
            "bar": bar, "content_h": content_h,
            "view_h": inner_h / scale if scale else 0.0,
        }

    def _column_spans(self, rows_width):
        """``[(column, x, width), ...]`` in display px from the rows' left."""
        scale = ui_scale()
        columns = self._columns()
        # Columns without a set width share what the others leave (there
        # is no horizontal scrolling, so the defaults must fit).
        fixed = sum(self._column_widths.get(c, 0.0) for c in columns) * scale
        free = [c for c in columns if c not in self._column_widths]
        share = max(self.MIN_COLUMN_PX * scale,
                    (rows_width - fixed) / len(free)) if free else 0.0
        spans, x = [], 0.0
        for position, column in enumerate(columns):
            width = self._column_widths.get(column)
            width = share if width is None else width * scale
            if position == len(columns) - 1 and self._stretch_last:
                width = max(width, rows_width - x)
            spans.append((column, x, width))
            x += width
        return spans

    def columnWidth(self, column):
        geometry = self._geometry()
        for col, _x, width in self._column_spans(geometry["rows"][2]):
            if col == column:
                return width / geometry["scale"]
        return 0.0

    def setColumnWidth(self, column, width):
        """Width of ``column`` in logical px (the last one stretches)."""
        self._column_widths[column] = max(float(self.MIN_COLUMN_PX),
                                          float(width))
        self._invalidate()

    def setStretchLastSection(self, stretch):
        self._stretch_last = bool(stretch)
        self._invalidate()

    def resizeColumnToContents(self, column):
        """Fit ``column`` to its widest visible cell and its header."""
        scale = ui_scale()
        size = self._font_size()
        dpi = self._dpi()
        widest = _measure().width(
            str(self._model.headerData(column) or ""), size, dpi, bold=True)
        first, last = self._visible_range()
        for row in range(first, last + 1):
            index = self._index_at(row)
            cell = index.sibling(index.row(), column)
            extra = self._cell_lead(row, column, cell) * scale
            widest = max(widest, extra + _measure().width(
                str(cell.data(DISPLAY) or ""), size, dpi))
        self.setColumnWidth(column, widest / scale + 2 * self.PAD_PX)

    # -- scrolling ---------------------------------------------------------------------------
    def verticalScrollBar(self):
        return self._bar

    def scrollValue(self):
        return self._bar.value()

    def setScrollValue(self, value):
        self._update_range()
        self._bar.setValue(value)

    def _update_range(self):
        geometry = self._geometry()
        maximum = max(0.0, geometry["content_h"] - geometry["view_h"])
        page = max(1.0, geometry["view_h"])
        if (page, maximum) != (self._bar.pageStep(), self._bar.maximum()):
            self._bar.setPageStep(page)
            self._bar.setSingleStep(self.ROW_PX)
            self._bar.setRange(0.0, maximum)
        self._target = min(max(self._target, 0.0), maximum)
        return geometry

    def _on_bar_value(self, value):
        if self._animation is None or self._animation.state() != "running":
            self._target = value
        self._invalidate()

    def _scroll_to_value(self, value, animated=True):
        from .animation import PropertyAnimation, animations_enabled

        self._update_range()
        value = min(max(float(value), 0.0), self._bar.maximum())
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

    def scrollTo(self, index, animated=False):
        """Scroll the least amount that shows ``index``'s row."""
        row = self._display_row(index)
        if row < 0:
            return
        geometry = self._update_range()
        top, bottom = row * self.ROW_PX, (row + 1) * self.ROW_PX
        value = self._target
        if top < value:
            value = top
        elif bottom > value + geometry["view_h"]:
            value = bottom - geometry["view_h"]
        if value != self._target:
            self._scroll_to_value(value, animated)

    def scrollToTop(self):
        self._scroll_to_value(0.0, animated=False)

    def scrollToBottom(self):
        self._scroll_to_value(float("inf"), animated=False)

    def _visible_range(self):
        """First and last display rows at least partly visible."""
        count = self._row_count()
        if count == 0:
            return 0, -1
        geometry = self._geometry()
        scroll = self._bar.value()
        first = max(0, int(scroll // self.ROW_PX))
        last = min(count - 1, int(math.ceil(
            (scroll + geometry["view_h"]) / self.ROW_PX)) - 1)
        return first, max(first - 1, last)

    # -- hit testing ------------------------------------------------------------------------------
    def _row_at_point(self, x, y):
        """``(display row, index, column, local x in display px)`` or None."""
        geometry = self._geometry()
        rx, ry, rw, rh = geometry["rows"]
        ox, oy = geometry["origin"]
        left, bottom = rx + ox, ry + oy
        if not (left <= x <= left + rw and bottom <= y <= bottom + rh):
            return None
        scale = geometry["scale"]
        from_top = (bottom + rh - y) / scale + self._bar.value()
        row = int(from_top // self.ROW_PX)
        if not 0 <= row < self._row_count():
            return None
        local = x - left
        column = None
        for col, cx, cw in self._column_spans(rw):
            if cx <= local < cx + cw:
                column = col
                break
        index = self._index_at(row)
        return row, index, column, local

    def indexAt(self, x, y):
        """The index under display point ``(x, y)`` (invalid if none)."""
        hit = self._row_at_point(x, y)
        if hit is None:
            return ModelIndex()
        row, index, column, _local = hit
        if column is None:
            return index
        return index.sibling(index.row(), column)

    def _row_display_rect(self, key):
        """Display-pixel ``(x0, x1, y0, y1)`` of the row with ``key``."""
        index = self._model.indexForKey(key)
        row = self._display_row(index)
        if row < 0:
            return None
        geometry = self._geometry()
        rx, ry, rw, rh = geometry["rows"]
        ox, oy = geometry["origin"]
        scale = geometry["scale"]
        top = ry + oy + rh - (row * self.ROW_PX - self._bar.value()) * scale
        return (rx + ox, rx + ox + rw, top - self.ROW_PX * scale, top)

    def _rows_rect_display(self):
        geometry = self._geometry()
        rx, ry, rw, rh = geometry["rows"]
        ox, oy = geometry["origin"]
        return rx + ox, ry + oy, rw, rh

    # -- input ---------------------------------------------------------------------------------
    def _header_hit(self, event):
        if not self._header_visible:
            return None
        geometry = self._geometry()
        hx, hy, hw, hh = geometry["header"]
        ox, oy = geometry["origin"]
        x, y = event.globalPos()
        if not (hx + ox <= x <= hx + ox + hw and hy + oy <= y <= hy + oy + hh):
            return None
        return x - (hx + ox)

    def _resize_edge(self, local_x):
        """Column whose right edge is under ``local_x`` (header), or None."""
        grip = 4 * ui_scale()
        spans = self._column_spans(self._geometry()["rows"][2])
        for position, (column, cx, cw) in enumerate(spans):
            last = position == len(spans) - 1
            if not last and abs(local_x - (cx + cw)) <= grip:
                return column, cw
        return None

    def mousePressEvent(self, event):
        if event.button() != "left" or not self._available:
            event.ignore()
            return
        event.accept()
        self.setFocus(reason="mouse")
        header_x = self._header_hit(event)
        if header_x is not None:
            edge = self._resize_edge(header_x)
            if edge is not None:
                self._header_drag = (edge[0], event.globalPos()[0],
                                     edge[1] / ui_scale())
            return
        hit = self._row_at_point(*event.globalPos())
        if hit is None:
            if self._selection.selectionMode() in ("single", "extended") \
                    and not ({CTRL, SHIFT} & event.modifiers()):
                self._selection.clearSelection()
            return
        row, index, column, local = hit
        if self._press_decoration(row, index, column, local):
            self._press = None
            return
        self._press = (self._key(index), column, row)
        self._select_by_click(row, index, event.modifiers())
        self.pressed.emit(self._cell(index, column))

    def _cell(self, index, column):
        if column is None or column == index.column():
            return index
        return index.sibling(index.row(), column)

    def _press_decoration(self, row, index, column, local):
        """Handle a press on a branch chevron or check box; True if handled."""
        if column is None:
            return False
        cell = self._cell(index, column)
        box = self._check_box_span(row, column, cell)
        if box is not None and box[0] <= local <= box[1]:
            self._toggle_check(cell)
            return True
        return False

    def _toggle_check(self, cell):
        flags = cell.flags()
        if "checkable" not in flags or "enabled" not in flags:
            return
        state = cell.data(CHECK_STATE)
        self._model.setData(cell, UNCHECKED if state == CHECKED else CHECKED,
                            CHECK_STATE)

    def _select_by_click(self, row, index, modifiers):
        selection = self._selection
        mode = selection.selectionMode()
        ctrl, shift = CTRL in modifiers, SHIFT in modifiers
        if mode == "none":
            selection.setCurrentIndex(index)
        elif mode == "single":
            selection.setCurrentIndex(index, "clearAndSelect")
        elif mode == "multi":
            selection.setCurrentIndex(index, "toggle")
        elif shift and self._display_row(selection.anchorIndex()) >= 0:
            anchor = self._display_row(selection.anchorIndex())
            span = [self._index_at(r) for r in
                    range(min(anchor, row), max(anchor, row) + 1)]
            selection.setCurrentIndex(index)
            selection.select(span, "select" if ctrl else "clearAndSelect")
            return
        elif ctrl:
            selection.setCurrentIndex(index, "toggle")
        else:
            selection.setCurrentIndex(index, "clearAndSelect")
        selection.setAnchor(index)

    def mouseMoveEvent(self, event):
        if self._header_drag is not None:
            event.accept()
            column, start, width = self._header_drag
            delta = (event.globalPos()[0] - start) / ui_scale()
            self.setColumnWidth(column, width + delta)
            return
        hit = self._row_at_point(*event.globalPos())
        self._set_hover(None if hit is None else self._key(hit[1]),
                        None if hit is None else hit[1])
        if self._press is not None and hit is not None and \
                self._selection.selectionMode() == "extended" and \
                hit[0] != self._press[2]:
            # Drag-select from the anchor, as Qt's extended mode does.
            event.accept()
            row, index = hit[0], hit[1]
            anchor = self._display_row(self._selection.anchorIndex())
            if anchor >= 0:
                span = [self._index_at(r) for r in
                        range(min(anchor, row), max(anchor, row) + 1)]
                self._selection.setCurrentIndex(index)
                self._selection.select(span, "clearAndSelect")
            return
        event.ignore()

    def mouseReleaseEvent(self, event):
        if self._header_drag is not None:
            event.accept()
            self._header_drag = None
            return
        press, self._press = self._press, None
        if event.button() != "left" or press is None:
            event.ignore()
            return
        event.accept()
        hit = self._row_at_point(*event.globalPos())
        if hit is not None and self._key(hit[1]) == press[0]:
            self.clicked.emit(self._cell(hit[1], hit[2]))

    def mouseDoubleClickEvent(self, event):
        if event.button() != "left":
            event.ignore()
            return
        hit = self._row_at_point(*event.globalPos())
        if hit is None:
            self.mousePressEvent(event)
            return
        event.accept()
        row, index, column, local = hit
        if self._press_decoration(row, index, column, local):
            return
        cell = self._cell(index, column)
        self.doubleClicked.emit(cell)
        self._double_clicked(index)
        self.activated.emit(cell)

    def _double_clicked(self, index):
        """Hook (the tree toggles branches)."""

    def leaveEvent(self, event):
        self._set_hover(None)

    def wheelEvent(self, event):
        self._update_range()
        if self._bar.maximum() <= 0:
            event.ignore()
            return
        event.accept()
        self._scroll_to_value(self._target - event.delta() * self.WHEEL_STEP_PX)

    def _set_hover(self, key, index=None):
        if key == self._hover_key:
            return
        self._hover_key = key
        self._invalidate()
        self._update_tip(key, index)

    def _update_tip(self, key, index):
        try:
            from .controls import get_hover_text_overlay
        except ImportError:                       # pragma: no cover
            return
        overlay = get_hover_text_overlay(self.renderer, self.interactor)
        if self._tip is not None:
            overlay.unregister(self._tip)
            self._tip = None
        text = index.data(TOOLTIP) if index is not None else None
        if key is not None and text:
            self._tip = _RowTip(self, key, str(text))
            overlay.register(self._tip)

    def keyPressEvent(self, event):
        key = event.key().lower()
        count = self._row_count()
        if count == 0 or not self._available:
            event.ignore()
            return
        current = self._display_row(self.currentIndex())
        page = max(1, int(self._geometry()["view_h"] // self.ROW_PX) - 1)
        target = None
        if key == "down":
            target = 0 if current < 0 else min(count - 1, current + 1)
        elif key == "up":
            target = 0 if current < 0 else max(0, current - 1)
        elif key == "home":
            target = 0
        elif key == "end":
            target = count - 1
        elif key == "next":
            target = min(count - 1, max(current, 0) + page)
        elif key == "prior":
            target = max(0, current - page)
        elif key in ("return", "kp_enter"):
            if current >= 0:
                self.activated.emit(self.currentIndex())
            event.accept()
            return
        elif key == "space":
            index = self.currentIndex()
            if index.isValid():
                if "checkable" in index.flags():
                    self._toggle_check(index)
                elif CTRL in event.modifiers():
                    self._selection.select(index, "toggle")
                else:
                    self._selection.select(index, "select")
            event.accept()
            return
        elif key == "a" and CTRL in event.modifiers():
            self.selectAll()
            event.accept()
            return
        elif self._tree_key(key, current):
            event.accept()
            return
        if target is None:
            event.ignore()
            return
        event.accept()
        self._move_current(target, event.modifiers())

    def _tree_key(self, key, current):
        return False

    def _move_current(self, row, modifiers):
        index = self._index_at(row)
        selection = self._selection
        mode = selection.selectionMode()
        if mode == "extended" and SHIFT in modifiers and \
                self._display_row(selection.anchorIndex()) >= 0:
            anchor = self._display_row(selection.anchorIndex())
            span = [self._index_at(r) for r in
                    range(min(anchor, row), max(anchor, row) + 1)]
            selection.setCurrentIndex(index)
            selection.select(span, "clearAndSelect")
        elif CTRL in modifiers and mode in ("multi", "extended"):
            selection.setCurrentIndex(index)
        elif mode in ("single", "extended"):
            selection.setCurrentIndex(index, "clearAndSelect")
            selection.setAnchor(index)
        else:
            selection.setCurrentIndex(index)
            selection.setAnchor(index)
        self.scrollTo(index, animated=True)

    def focusInEvent(self, reason="other"):
        super().focusInEvent(reason)
        self._invalidate()

    def focusOutEvent(self, reason="other"):
        super().focusOutEvent(reason)
        self._invalidate()

    # -- drawing ---------------------------------------------------------------------------------
    def tokens(self):
        theme = getattr(self.renderer, "theme", None)
        tokens = getattr(theme, "tokens", None)
        return tokens if tokens else _DEFAULT_TOKENS

    def style(self):
        return Style.for_renderer(self.renderer)

    def _color(self, role, part, states=()):
        states = set(states)
        if not self._available:
            states.add("disabled")
        return self.style().color(role, part, states, widget=self)

    def _font_size(self):
        return max(8, int(round(self.FONT_SIZE * font_scale())))

    def _dpi(self):
        return max(1, self.interactor.GetRenderWindow().GetDPI())

    def _invalidate(self):
        self._dirty = True
        self.requestRender()

    def _before_render(self, *_args):
        if self._dirty:
            self.doItemsLayout()

    def doItemsLayout(self):
        """Sync every actor with the model now (normally before a frame)."""
        self._dirty = False
        x, y, width, height = self.rect()
        shown = self._shown and width > 2 and height > 2
        if not shown:
            self._hide_all()
            self.requestRender()
            return
        geometry = self._update_range()
        scale = geometry["scale"]
        # The scroll bar.
        ax, ay, aw, ah = self.geometry("px")
        header_px = self.HEADER_PX if self._header_visible else 0
        self._bar.setGeometry(px(ax + aw - 1 - self.BAR_PX), px(ay + 1),
                              px(self.BAR_PX), px(max(0.0, ah - 2 - header_px)))
        self._bar.SetVisibility(geometry["bar"])
        # The clipped rows viewport.
        window = self.interactor.GetRenderWindow()
        win_w, win_h = (max(1, v) for v in window.GetSize())
        rx, ry, rw, rh = geometry["rows"]
        ox, oy = geometry["origin"]
        self._content.SetDraw(rw > 0 and rh > 0)
        self._content.SetViewport((rx + ox) / win_w, (ry + oy) / win_h,
                                  (rx + ox + rw) / win_w,
                                  (ry + oy + rh) / win_h)
        self._paint_frame(geometry)
        self._paint_header(geometry)
        self._paint_rows(geometry, rw, rh, scale)
        self.requestRender()

    def _hide_all(self):
        self._content.SetDraw(False)
        self._content.SetViewport(0.0, 0.0, 0.0, 0.0)
        self._bar.SetVisibility(False)
        for prop in (self._frame_actor, self._header_lines, self._rows_actor,
                     self._rows_lines):
            prop.SetVisibility(False)
        self._frame_key = self._shape_key = None
        for slot in self._slots:
            for cell in slot.values():
                self.actor_updates += bool(cell.hide())
        for cell in self._header_cells:
            cell.hide()

    def _paint_frame(self, geometry):
        x, y, width, height = geometry["rect"]
        border = self._color("field", "border",
                             ("focus",) if self.hasFocus() else ())
        fill = self._color("field", "background")
        header = geometry["header"]
        key = (geometry["rect"], border, fill, header,
               self._color("item", "header") if self._header_visible else None)
        if key == self._frame_key:
            return
        self._frame_key = key
        radius = 4 * geometry["scale"]
        shapes = [rounded_rect_polydata(x, y, width, height, [radius] * 4,
                                        _rgba(border)),
                  rounded_rect_polydata(x + 1, y + 1, width - 2, height - 2,
                                        [radius - 1] * 4, _rgba(fill))]
        if self._header_visible and header[3] > 0:
            hx, hy, hw, hh = header
            shapes.append(rounded_rect_polydata(
                hx, hy, width - 2, hh, [0, 0, radius - 1, radius - 1],
                _rgba(self._color("item", "header"))))
            shapes.append(rounded_rect_polydata(
                hx, hy, width - 2, 1, [0] * 4, _rgba(self.tokens()["border"])))
        self._frame_actor.GetMapper().SetInputData(_merge(shapes))
        self._frame_actor.SetVisibility(True)

    def _paint_header(self, geometry):
        layer = ui_layer(self.renderer)
        if not self._header_visible or geometry["header"][3] <= 0:
            for cell in self._header_cells:
                cell.hide()
            self._header_lines.SetVisibility(False)
            return
        hx, hy, hw, hh = geometry["header"]
        size, dpi = self._font_size(), self._dpi()
        pad = self.PAD_PX * geometry["scale"]
        spans = self._column_spans(hw)
        lines = []
        text_color = self._color("muted", "text")
        for position, (column, cx, cw) in enumerate(spans):
            while len(self._header_cells) <= position:
                self._header_cells.append(_TextCell(layer))
            label = str(self._model.headerData(column) or "")
            visible_w = min(cw, hw - cx)
            text = _measure().elide(label, visible_w - 2 * pad, size, dpi,
                                    bold=True)
            self._header_cells[position].show(
                text, hx + cx + pad, hy + hh / 2, text_color, size, bold=True)
            edge = hx + cx + cw
            if position < len(spans) - 1 and edge < hx + hw:
                lines.append(_polyline([(edge, hy + 4), (edge, hy + hh - 4)],
                                       _rgba(self.tokens()["border"])))
        for cell in self._header_cells[len(spans):]:
            cell.hide()
        if lines:
            self._header_lines.GetMapper().SetInputData(_merge(lines))
            self._header_lines.SetVisibility(True)
        else:
            self._header_lines.SetVisibility(False)

    # Per-row layout helpers ------------------------------------------------------------------
    def _check_state(self, cell):
        flags = cell.flags()
        state = cell.data(CHECK_STATE)
        if state is None and "checkable" not in flags:
            return None
        return state or UNCHECKED

    def _cell_lead(self, row, column, cell):
        """Logical px from the cell's left edge to its text."""
        lead = self.PAD_PX
        if column == self._columns()[0]:
            lead += self._branch_indent(row)
        if self._check_state(cell) is not None:
            lead += self.CHECK_PX + self.PAD_PX
        if cell.data(DECORATION) is not None:
            lead += self.ICON_PX + self.PAD_PX
        return lead

    def _check_box_span(self, row, column, cell):
        """Local display-x span of the cell's check box, or None."""
        if self._check_state(cell) is None:
            return None
        scale = ui_scale()
        spans = self._column_spans(self._geometry()["rows"][2])
        for col, cx, _cw in spans:
            if col == column:
                lead = self.PAD_PX + (self._branch_indent(row)
                                      if column == self._columns()[0] else 0)
                start = cx + lead * scale
                return start, start + self.CHECK_PX * scale
        return None

    def _row_states(self, index):
        states = set()
        key = self._key(index)
        if self._selection.isSelected(index):
            states.add("selected")
        if key is not None and key == self._hover_key:
            states.add("hover")
        if self.hasFocus():
            states.add("focus")
        return states

    SHAPE_BLOCK = 8          # rows; shapes are built a block beyond the view

    def _paint_rows(self, geometry, rows_w, rows_h, scale):
        first, last = self._visible_range()
        count = self._row_count()
        # Shapes (backgrounds, check boxes, chevrons) are drawn unscrolled
        # for whole blocks of rows around the visible ones and the actors
        # moved by the scroll offset, so scrolling rebuilds them only when
        # it crosses a block boundary. The clipped viewport hides the rest.
        block = self.SHAPE_BLOCK
        shape_first = max(0, (first // block - 1) * block)
        shape_last = min(count - 1, (last // block + 2) * block - 1)
        row_h = self.ROW_PX * scale
        scroll = self._bar.value() * scale
        size, dpi = self._font_size(), self._dpi()
        pad = self.PAD_PX * scale
        spans = self._column_spans(rows_w)
        shapes, lines, shape_key = [], [], []
        text_color = self._color("text", "text")
        disabled_color = self.tokens()["disabled"]
        current_key = self._key(self.currentIndex())
        icon_size = int(round(self.ICON_PX * scale))
        used = 0
        for row in range(shape_first, shape_last + 1):
            visible = first <= row <= last
            index = self._index_at(row)
            fixed_top = rows_h - row * row_h
            fixed_bottom, fixed_centre = fixed_top - row_h, fixed_top - row_h / 2
            centre = fixed_centre + scroll
            states = self._row_states(index)
            background = self._color("item", "background", states)
            if background is not None:
                shape_key.append(("bg", row, background))
                shapes.append(partial(_quad, 0, fixed_bottom, rows_w, row_h,
                                      _rgba(background)))
            if self.hasFocus() and current_key is not None and \
                    self._key(index) == current_key:
                accent = self._color("focus", "border")
                shape_key.append(("current", row, accent))
                lines.append(partial(_outline, 1, fixed_bottom + 1, rows_w - 2,
                                     row_h - 2, 2 * scale, _rgba(accent)))
            slot = shown_cells = None
            if visible:
                while len(self._slots) <= used:
                    self._slots.append({})
                slot = self._slots[used]
                used += 1
                shown_cells = set()
            for position, (column, cx, cw) in enumerate(spans):
                cell = index if column == index.column() else \
                    index.sibling(index.row(), column)
                flags = cell.flags()
                color = text_color if "enabled" in flags and self._available \
                    else disabled_color
                x = cx + pad
                right = min(cx + cw, rows_w) - pad
                if position == 0:
                    indent = self._branch_indent(row) * scale
                    self._paint_branch(row, index, cx + pad + indent,
                                       fixed_centre, scale, lines, shape_key)
                    x += indent
                state = self._check_state(cell)
                if state is not None:
                    self._paint_check(x, fixed_centre, state, flags, scale,
                                      shapes, lines, shape_key, row, column)
                    x += (self.CHECK_PX + self.PAD_PX) * scale
                decoration = cell.data(DECORATION)
                if decoration is not None:
                    if isinstance(decoration, str):
                        if visible:
                            icon = slot.get(("icon", column))
                            if icon is None:
                                icon = slot[("icon", column)] = \
                                    _IconCell(self._content)
                            self.actor_updates += bool(icon.show(
                                decoration, x, centre - icon_size / 2,
                                icon_size, tuple(color)))
                            shown_cells.add(("icon", column))
                    else:
                        swatch = tuple(decoration[:3])
                        shape_key.append(("swatch", row, column, swatch))
                        shapes.append(partial(
                            rounded_rect_polydata, x,
                            fixed_centre - icon_size / 2, icon_size,
                            icon_size, [3 * scale] * 4, _rgba(swatch)))
                    x += (self.ICON_PX + self.PAD_PX) * scale
                if not visible:
                    continue
                text = cell.data(DISPLAY)
                text = "" if text is None else str(text)
                text_cell = slot.get(("text", column))
                if text_cell is None:
                    text_cell = slot[("text", column)] = \
                        _TextCell(self._content)
                shown = _measure().elide(text, right - x, size, dpi)
                self.actor_updates += bool(text_cell.show(shown, x, centre,
                                                          color, size))
                shown_cells.add(("text", column))
            if visible:
                for name, cell in slot.items():
                    if name not in shown_cells:
                        self.actor_updates += bool(cell.hide())
        for slot in self._slots[used:]:
            for cell in slot.values():
                self.actor_updates += bool(cell.hide())
        for prop in (self._rows_actor, self._rows_lines):
            prop.SetPosition(0.0, scroll)
        key = (tuple(shape_key), rows_w, rows_h)
        if key != self._shape_key:
            self._shape_key = key
            for prop, data in ((self._rows_actor, shapes),
                               (self._rows_lines, lines)):
                if data:
                    prop.GetMapper().SetInputData(
                        _merge([build() for build in data]))
                    prop.SetVisibility(True)
                else:
                    prop.SetVisibility(False)

    def _paint_branch(self, row, index, x, centre, scale, lines, shape_key):
        """Hook: the tree draws its chevrons."""

    def _paint_check(self, x, centre, state, flags, scale, shapes, lines,
                     shape_key, row, column):
        size = self.CHECK_PX * scale
        states = set()
        if state in (CHECKED, PARTIALLY_CHECKED):
            states.add("checked")
        if "enabled" not in flags or not self._available:
            states.add("disabled")
        style = self.style()
        border = style.color("indicator", "border", states, widget=self)
        fill = style.color("indicator", "background", states, widget=self)
        mark = style.color("indicator", "mark", states, widget=self)
        bottom = centre - size / 2
        radius = 3 * scale
        shape_key.append(("check", row, column, state, border, fill))
        shapes.append(partial(rounded_rect_polydata, x, bottom, size, size,
                                            [radius] * 4, _rgba(border)))
        shapes.append(partial(rounded_rect_polydata, x + 1, bottom + 1, size - 2,
                                            size - 2, [radius - 1] * 4,
                                            _rgba(fill)))
        if state == CHECKED:
            lines.append(partial(_polyline, [(x + size * 0.25, centre),
                                    (x + size * 0.43, centre - size * 0.2),
                                    (x + size * 0.76, centre + size * 0.2)],
                                   _rgba(mark)))
        elif state == PARTIALLY_CHECKED:
            lines.append(partial(_polyline, [(x + size * 0.28, centre),
                                    (x + size * 0.72, centre)], _rgba(mark)))

    # -- teardown ---------------------------------------------------------------------------------
    def close(self):
        if self._animation is not None:
            self._animation.stop()
        if self._tip is not None:
            self._update_tip(None, None)
        if self._model is not None:
            for signal, slot in self._model_connections():
                try:
                    signal.disconnect(slot)
                except ValueError:
                    pass
        layer = ui_layer(self.renderer)
        for prop in (self._frame_actor, self._header_lines):
            remove_actor_2d(layer, prop)
        for cell in self._header_cells:
            cell.remove(layer)
        for slot in self._slots:
            for cell in slot.values():
                cell.remove(self._content)
        self._slots = []
        window = self.interactor.GetRenderWindow()
        if window is not None:
            window.RemoveRenderer(self._content)
        self._bar.close()
        return super().close()


class ListView(ItemView):
    """One column of a model as a list (``QListView``)."""

    def __init__(self, renderer, interactor, parent=None, model=None,
                 object_name=None, **options):
        self._model_column = 0
        super().__init__(renderer, interactor, parent, model, object_name,
                         **options)

    def modelColumn(self):
        return self._model_column

    def setModelColumn(self, column):
        self._model_column = int(column)
        self._invalidate()

    def _columns(self):
        return [self._model_column]


class TableView(ItemView):
    """Rows and columns with a resizable header (``QTableView``).

    Drag a header edge to resize a column; the last column stretches to
    fill the view (``setStretchLastSection(False)`` to turn that off).
    """

    def __init__(self, renderer, interactor, parent=None, model=None,
                 object_name=None, **options):
        super().__init__(renderer, interactor, parent, model, object_name,
                         **options)
        self._header_visible = True


class TreeView(ItemView):
    """A tree with expandable branches (``QTreeView``).

    Click a chevron or double-click a branch to expand or collapse it;
    Right/Left do the same from the keyboard. Collapsing keeps the
    selection (hidden rows stay selected); the current row moves to the
    collapsed branch if it was inside it. A header is shown when the model
    has more than one column.
    """

    def __init__(self, renderer, interactor, parent=None, model=None,
                 object_name=None, **options):
        self._expanded = set()
        self._flat = None               # [(index, depth, has_children)]
        self._flat_rows = {}
        super().__init__(renderer, interactor, parent, model, object_name,
                         **options)
        self.expanded = Signal(self)
        self.collapsed = Signal(self)

    # -- model hooks ----------------------------------------------------------------------------
    def _model_changed(self):
        self._expanded = set()
        self._flat = None
        self._apply_default_expansion(None)
        self._header_visible = self._model.columnCount() > 1

    def _apply_default_expansion(self, parent):
        model = self._model
        for row in range(model.rowCount(parent)):
            index = model.index(row, 0, parent)
            node = index.internalPointer()
            if getattr(node, "expanded_by_default", False):
                self._expanded.add(self._key(index))
            self._apply_default_expansion(index)

    def _on_rows_inserted(self, parent, first, last):
        if not self._model.hasStableKeys():
            self._expanded.clear()
        for row in range(first, last + 1):
            index = self._model.index(row, 0, parent)
            node = index.internalPointer()
            if getattr(node, "expanded_by_default", False):
                self._expanded.add(self._key(index))
            self._apply_default_expansion(index)
        self._structure_changed()

    def _on_rows_removed(self, parent, first, last):
        if not self._model.hasStableKeys():
            self._expanded.clear()
        else:
            self._expanded = {key for key in self._expanded
                              if self._model.indexForKey(key).isValid()}
        self._structure_changed()

    def _structure_changed(self):
        self._flat = None
        self._invalidate()

    # -- flattening ----------------------------------------------------------------------------
    def _ensure_flat(self):
        if self._flat is not None:
            return self._flat
        flat, rows = [], {}
        model = self._model

        def visit(parent, depth):
            for row in range(model.rowCount(parent)):
                index = model.index(row, 0, parent)
                children = model.hasChildren(index)
                rows[self._key(index)] = len(flat)
                flat.append((index, depth, children))
                if children and self._key(index) in self._expanded:
                    visit(index, depth + 1)

        visit(None, 0)
        self._flat, self._flat_rows = flat, rows
        return flat

    def _row_count(self):
        return len(self._ensure_flat())

    def _index_at(self, row):
        flat = self._ensure_flat()
        return flat[row][0] if 0 <= row < len(flat) else ModelIndex()

    def _depth_at(self, row):
        flat = self._ensure_flat()
        return flat[row][1] if 0 <= row < len(flat) else 0

    def _display_row(self, index):
        self._ensure_flat()
        key = self._key(index)
        return self._flat_rows.get(key, -1) if key is not None else -1

    def _branch_indent(self, row):
        # Every level, top level included, reserves room for a chevron.
        return (self._depth_at(row) + 1) * self.INDENT_PX

    # -- expansion --------------------------------------------------------------------------------
    def isExpanded(self, index):
        return self._key(index) in self._expanded

    def setExpanded(self, index, expanded):
        if expanded:
            self.expand(index)
        else:
            self.collapse(index)

    def expand(self, index):
        key = self._key(index)
        if key is None or key in self._expanded or \
                not self._model.hasChildren(index.sibling(index.row(), 0)):
            return
        self._expanded.add(key)
        self._structure_changed()
        self.expanded.emit(index)

    def collapse(self, index):
        key = self._key(index)
        if key is None or key not in self._expanded:
            return
        current = self.currentIndex()
        self._expanded.discard(key)
        self._structure_changed()
        if current.isValid() and self._display_row(current) < 0:
            # The current row was hidden inside the branch.
            self._selection.setCurrentIndex(index.sibling(index.row(), 0))
        self.collapsed.emit(index)

    def toggleExpanded(self, index):
        if self.isExpanded(index):
            self.collapse(index)
        else:
            self.expand(index)

    def expandAll(self):
        model = self._model

        def visit(parent):
            for row in range(model.rowCount(parent)):
                index = model.index(row, 0, parent)
                if model.hasChildren(index):
                    self._expanded.add(self._key(index))
                    visit(index)

        visit(None)
        self._structure_changed()

    def collapseAll(self):
        self._expanded.clear()
        self._structure_changed()
        current = self.currentIndex()
        if current.isValid() and self._display_row(current) < 0:
            top = current
            while top.parent().isValid():
                top = top.parent()
            self._selection.setCurrentIndex(top)

    def scrollTo(self, index, animated=False):
        # Reveal the row first, as QTreeView.scrollTo does.
        parent = index.parent() if index is not None and index.isValid() \
            else ModelIndex()
        changed = False
        while parent.isValid():
            key = self._key(parent)
            if key not in self._expanded:
                self._expanded.add(key)
                changed = True
            parent = parent.parent()
        if changed:
            self._structure_changed()
        super().scrollTo(index, animated)

    # -- painting and input ---------------------------------------------------------------------
    def _chevron_span(self, row):
        """Local display-x span of the row's chevron."""
        scale = ui_scale()
        start = (self.PAD_PX + self._depth_at(row) * self.INDENT_PX) * scale
        return start, start + self.INDENT_PX * scale

    def _paint_branch(self, row, index, x, centre, scale, lines, shape_key):
        flat = self._ensure_flat()
        if not flat[row][2]:
            return
        expanded = self._key(index) in self._expanded
        color = self._color("item", "branch")
        shape_key.append(("branch", row, expanded, color))
        cx = x - self.INDENT_PX * scale / 2
        size = 3.5 * scale
        if expanded:
            points = [(cx - size, centre + size / 2), (cx, centre - size / 2),
                      (cx + size, centre + size / 2)]
        else:
            points = [(cx - size / 2, centre + size), (cx + size / 2, centre),
                      (cx - size / 2, centre - size)]
        lines.append(partial(_polyline, points, _rgba(color)))

    def _press_decoration(self, row, index, column, local):
        if column == self._columns()[0] and self._ensure_flat()[row][2]:
            start, end = self._chevron_span(row)
            if start <= local <= end:
                self.toggleExpanded(index)
                return True
        return super()._press_decoration(row, index, column, local)

    def _double_clicked(self, index):
        if self._model.hasChildren(index):
            self.toggleExpanded(index)

    def _tree_key(self, key, current):
        if current < 0:
            return False
        index = self._index_at(current)
        if key == "right":
            if self._model.hasChildren(index):
                if not self.isExpanded(index):
                    self.expand(index)
                else:
                    self._move_current(current + 1, frozenset())
            return True
        if key == "left":
            if self.isExpanded(index):
                self.collapse(index)
            elif index.parent().isValid():
                row = self._display_row(index.parent())
                if row >= 0:
                    self._move_current(row, frozenset())
            return True
        return False
