"""Standard controls built as native widgets (``docs/QT_PARITY_PROPOSAL.md`` §9).

Every control here receives input through the ``WidgetMixin`` event
handlers (delivered by the :class:`~multipanel.router.EventRouter`), draws
with plain 2D actors on the UI layer, takes its colours from the renderer's
theme tokens, and provides size hints for layouts::

    from multipanel.standard import CheckBox, ComboBox, Label, Menu

    wireframe = CheckBox(renderer, interactor, "Wireframe")
    wireframe.toggled.connect(set_wireframe)

    material = ComboBox(renderer, interactor)
    material.addItems(["Air", "Lead", "Water"])
    material.currentTextChanged.connect(set_material)

    menu = Menu(renderer, interactor)
    menu.addAction(copy_action)
    menu.addSeparator()
    menu.addAction("Delete", delete_selection)
    menu.popup(at=(x, y))
"""
from __future__ import annotations

import weakref

import vtk

from ._widget_support import (
    font_scale,
    UI_Z_PANEL_CONTROL,
    apply_ui_font,
    rounded_rect_polydata,
    ui_layer,
    ui_scale,
)
from .actions import Action, ActionGroup
from .core import Signal, SizePolicy, WidgetMixin
from .overlay import Popup
from .style import Style
from .ui_theme import LIGHT, vtk_tokens
from .vtk_compat import add_actor_2d, remove_actor_2d

__all__ = [
    "MenuBar",
    "MessageBox",
    "StatusBar",
    "ButtonGroup",
    "CheckBox",
    "ComboBox",
    "Label",
    "Menu",
    "MenuItem",
    "NativeWidget",
    "ProgressBar",
    "PushButton",
    "RadioButton",
]

_DEFAULT_TOKENS = vtk_tokens(LIGHT)


def _rgba(color, alpha=1.0):
    return tuple(int(round(255 * channel)) for channel in color[:3]) + (
        int(round(255 * alpha)),)


def _merge(polydatas):
    append = vtk.vtkAppendPolyData()
    for polydata in polydatas:
        append.AddInputData(polydata)
    append.Update()
    output = vtk.vtkPolyData()
    output.DeepCopy(append.GetOutput())
    return output


def _polyline(points, rgba):
    """Open polyline (check marks, chevrons) coloured per point.

    vtkPolyDataMapper2D draws only the first segment of line cells that
    carry cell colours (VTK 9.5), so lines use point colours and the overlay
    actor that draws them maps point data.
    """
    vtk_points = vtk.vtkPoints()
    ids = [vtk_points.InsertNextPoint(x, y, 0.0) for x, y in points]
    cells = vtk.vtkCellArray()
    colors = vtk.vtkUnsignedCharArray()
    colors.SetNumberOfComponents(4)
    for _ in ids:
        colors.InsertNextTuple4(*rgba)
    for start, end in zip(ids, ids[1:]):
        segment = vtk.vtkLine()
        segment.GetPointIds().SetId(0, start)
        segment.GetPointIds().SetId(1, end)
        cells.InsertNextCell(segment)
    polydata = vtk.vtkPolyData()
    polydata.SetPoints(vtk_points)
    polydata.SetLines(cells)
    polydata.GetPointData().SetScalars(colors)
    return polydata


def _triangle(points, rgba):
    vtk_points = vtk.vtkPoints()
    polygon = vtk.vtkPolygon()
    for x, y in points:
        polygon.GetPointIds().InsertNextId(vtk_points.InsertNextPoint(x, y, 0.0))
    cells = vtk.vtkCellArray()
    cells.InsertNextCell(polygon)
    colors = vtk.vtkUnsignedCharArray()
    colors.SetNumberOfComponents(4)
    colors.InsertNextTuple4(*rgba)
    polydata = vtk.vtkPolyData()
    polydata.SetPoints(vtk_points)
    polydata.SetPolys(cells)
    polydata.GetCellData().SetScalars(colors)
    return polydata


def _shape_actor(point_colors=False):
    mapper = vtk.vtkPolyDataMapper2D()
    mapper.SetColorModeToDirectScalars()
    if point_colors:
        mapper.SetScalarModeToUsePointData()
    else:
        mapper.SetScalarModeToUseCellData()
    actor = vtk.vtkActor2D()
    actor.SetMapper(mapper)
    actor.IsUI = True
    actor.PickableOff()
    return actor


class NativeWidget(WidgetMixin):
    """Base for the standard controls: geometry, visibility, state, drawing.

    Subclasses implement :meth:`paint` (shapes in viewport pixels plus the
    text actor) and :meth:`sizeHint`. ``GetEnabled``/``SetVisibility`` are
    the container protocol (shown or not, as for other widgets);
    ``isEnabled``/``setEnabled`` mean availability (greyed out).
    """

    FOCUS_POLICY = "NoFocus"
    FONT_SIZE = 12

    def __init__(self, renderer, interactor, parent=None, object_name=None,
                 ui_z_order=UI_Z_PANEL_CONTROL):
        self.renderer = renderer
        self.interactor = interactor
        self.ui_z_order = int(ui_z_order)
        self._bounds = (0.0, 0.0, 0.0, 0.0)
        self._shown = True
        self._available = True
        self._hovered = False
        self._pressed = False
        self.initWidget(object_name or type(self).__name__.lower(), parent)
        self.registerFocus(interactor, self.FOCUS_POLICY)
        self.actor = _shape_actor()
        self.overlay_actor = _shape_actor(point_colors=True)   # lines
        self.overlay_actor.GetProperty().SetLineWidth(2.0 * ui_scale())
        self.text_actor = vtk.vtkTextActor()
        self.text_actor.IsUI = True
        self.text_actor.PickableOff()
        text_property = self.text_actor.GetTextProperty()
        apply_ui_font(text_property)
        text_property.SetFontSize(self.fontSize())
        text_property.SetVerticalJustificationToCentered()
        self._text_x_align = "left"
        layer = ui_layer(renderer)
        for prop in (self.actor, self.overlay_actor, self.text_actor):
            prop.SetVisibility(False)
            add_actor_2d(layer, prop)
        self.registerWithRouter(interactor)
        window = interactor.GetRenderWindow()
        self.ownObserver(window, "WindowResizeEvent",
                         lambda *_: self.refresh())

    # -- appearance helpers -----------------------------------------------------
    def fontSize(self):
        return max(8, int(round(self.FONT_SIZE * font_scale())))

    def tokens(self):
        theme = getattr(self.renderer, "theme", None)
        tokens = getattr(theme, "tokens", None)
        return tokens if tokens else _DEFAULT_TOKENS

    def style(self):
        """The renderer's :class:`~multipanel.style.Style`."""
        return Style.for_renderer(self.renderer)

    def color(self, role, part, *extra_states):
        """Colour for ``role``/``part`` in this widget's current state."""
        states = self.styleState() | frozenset(extra_states)
        return self.style().color(role, part, states, widget=self)

    def measureText(self, text):
        """Rendered ``(width, height)`` of ``text`` in logical px."""
        box = [0, 0, 0, 0]
        window = self.interactor.GetRenderWindow()
        vtk.vtkTextRenderer.GetInstance().GetBoundingBox(
            self.text_actor.GetTextProperty(), text or "Hg", box,
            max(1, window.GetDPI()))
        scale = ui_scale()
        width = (box[1] - box[0] + 1) if text else 0
        return width / scale, (box[3] - box[2] + 1) / scale

    def px(self, value):
        """Logical px to display px."""
        return value * ui_scale()

    def rect(self):
        """Viewport-pixel rectangle ``(x, y, w, h)`` of the widget."""
        width, height = self.viewportExtent()
        x0, x1, y0, y1 = self._bounds
        return (x0 * width, y0 * height, (x1 - x0) * width, (y1 - y0) * height)

    # -- container protocol --------------------------------------------------------
    def GetBounds(self):
        return self._bounds

    def SetBounds(self, x0, x1, y0, y1):
        self._bounds = (float(x0), float(x1), float(y0), float(y1))
        self.refresh()

    def GetVisibility(self):
        return self._shown

    def SetVisibility(self, visible):
        visible = bool(visible)
        if visible == self._shown:
            return
        self._shown = visible
        if not visible:
            self._hovered = self._pressed = False
        self.refresh()

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
        if enabled == self._available:
            return
        self._available = enabled
        self.enabledChanged.emit(enabled)
        self.refresh()

    # -- drawing -----------------------------------------------------------------------
    def refresh(self):
        x, y, width, height = self.rect()
        drawable = self._shown and width > 0 and height > 0
        for prop in (self.actor, self.overlay_actor, self.text_actor):
            prop.SetVisibility(False)
        if drawable:
            shapes, overlay = self.paint(x, y, width, height, self.tokens())
            for prop, polydatas in ((self.actor, shapes),
                                    (self.overlay_actor, overlay)):
                if polydatas:
                    prop.GetMapper().SetInputData(_merge(polydatas))
                    prop.SetVisibility(True)
            if self.text_actor.GetInput():
                self.text_actor.SetVisibility(True)
        self.updateStyleState()
        self.requestRender()

    def paint(self, x, y, width, height, tokens):
        """Return ``(shapes, overlay_lines)`` polydata lists; place text."""
        return [], []

    def placeText(self, text, x, y_centre, color, align="left"):
        text_property = self.text_actor.GetTextProperty()
        text_property.SetFontSize(self.fontSize())
        text_property.SetColor(*color[:3])
        if align == "center":
            text_property.SetJustificationToCentered()
        elif align == "right":
            text_property.SetJustificationToRight()
        else:
            text_property.SetJustificationToLeft()
        self.text_actor.SetInput(text or "")
        self.text_actor.GetPositionCoordinate().SetCoordinateSystemToViewport()
        self.text_actor.SetPosition(x, y_centre)

    def textColor(self, tokens=None):
        return self.color("text", "text")

    def focusInEvent(self, reason="other"):
        super().focusInEvent(reason)
        self.refresh()

    def focusOutEvent(self, reason="other"):
        super().focusOutEvent(reason)
        self.refresh()

    # -- hover --------------------------------------------------------------------
    def enterEvent(self, event):
        self._hovered = True
        self.refresh()

    def leaveEvent(self, event):
        self._hovered = False
        self.refresh()

    def close(self):
        layer = ui_layer(self.renderer)
        for prop in (self.actor, self.overlay_actor, self.text_actor):
            remove_actor_2d(layer, prop)
        return super().close()


class Label(NativeWidget):
    """Non-interactive text (``QLabel``)."""

    def __init__(self, renderer, interactor, text="", parent=None,
                 alignment="left", muted=False, bold=False, object_name=None):
        self._text = str(text)
        self._alignment = alignment
        self._muted = bool(muted)
        super().__init__(renderer, interactor, parent, object_name or "label")
        if bold:
            apply_ui_font(self.text_actor.GetTextProperty(), bold=True)
        self.refresh()

    def text(self):
        return self._text

    def setText(self, text):
        text = str(text)
        if text != self._text:
            self._text = text
            self.updateGeometry()
            self.refresh()

    def setAlignment(self, alignment):
        self._alignment = alignment
        self.refresh()

    def defaultSizePolicy(self):
        return SizePolicy(SizePolicy.Preferred, SizePolicy.Fixed)

    def sizeHint(self):
        width, height = self.measureText(self._text)
        return (width + 4.0, height + 6.0)

    def minimumSizeHint(self):
        return self.sizeHint()

    def paint(self, x, y, width, height, tokens):
        color = tokens["muted"] if self._muted else self.textColor(tokens)
        if self._alignment == "center":
            self.placeText(self._text, x + width / 2, y + height / 2, color,
                           "center")
        elif self._alignment == "right":
            self.placeText(self._text, x + width - self.px(2), y + height / 2,
                           color, "right")
        else:
            self.placeText(self._text, x + self.px(2), y + height / 2, color)
        return [], []


class _Clickable(NativeWidget):
    """Press/release/click semantics shared by buttons and toggles."""

    FOCUS_POLICY = "StrongFocus"

    def _init_click(self):
        self.pressed = Signal(self)
        self.released = Signal(self)
        self.clicked = Signal(self)

    def mousePressEvent(self, event):
        if event.button() != "left":
            event.ignore()
            return
        event.accept()
        if self._available:
            self._pressed = True
            self.pressed.emit()
            self.refresh()

    def mouseReleaseEvent(self, event):
        event.accept()
        if not self._pressed:
            return
        self._pressed = False
        self.released.emit()
        x, y = event.globalPos()
        if self.hitTest(x, y):
            self.click()
        else:
            self.refresh()

    def mouseDoubleClickEvent(self, event):
        self.mousePressEvent(event)

    def click(self):
        """Activate as if clicked (also used by Space/Enter via focus)."""
        if not self._available:
            return
        self._activate()
        self.clicked.emit()
        self.refresh()

    def _activate(self):
        pass


class PushButton(_Clickable):
    """A text push button (``QPushButton``); can be bound to an Action."""

    def __init__(self, renderer, interactor, text="", parent=None,
                 action=None, default=False, object_name=None):
        self._text = str(text)
        self._default = bool(default)
        self._action = None
        super().__init__(renderer, interactor, parent,
                         object_name or "push_button")
        self._init_click()
        if action is not None:
            self.setAction(action)
        self.refresh()

    def text(self):
        return self._text

    def setText(self, text):
        self._text = str(text)
        self.updateGeometry()
        self.refresh()

    def setAction(self, action):
        self._action = action
        action.changed.connect(self._sync_action, unique=True)
        self._sync_action()

    def action(self):
        return self._action

    def _sync_action(self):
        action = self._action
        self._text = action.text()
        self.setToolTip(action.toolTip())
        self._available = action.isEnabled()
        self.updateGeometry()
        self.refresh()

    def _activate(self):
        if self._action is not None:
            self._action.trigger()

    def defaultSizePolicy(self):
        return SizePolicy(SizePolicy.Minimum, SizePolicy.Fixed)

    def sizeHint(self):
        width, height = self.measureText(self._text)
        return (max(64.0, width + 24.0), height + 12.0)

    def minimumSizeHint(self):
        width, height = self.measureText(self._text)
        return (width + 12.0, height + 8.0)

    def styleState(self):
        states = super().styleState()
        return states | {"default"} if self._default else states

    def paint(self, x, y, width, height, tokens):
        radius = self.px(5)
        shapes = [
            rounded_rect_polydata(x, y, width, height, [radius] * 4,
                                  _rgba(self.color("button", "border"))),
            rounded_rect_polydata(x + 1, y + 1, width - 2, height - 2,
                                  [radius - 1] * 4,
                                  _rgba(self.color("button", "background"))),
        ]
        text = self.color("button", "text")
        self.placeText(self._text, x + width / 2, y + height / 2, text,
                       "center")
        return shapes, []


class CheckBox(_Clickable):
    """A check box with a text label (``QCheckBox``, optionally tristate)."""

    UNCHECKED, PARTIAL, CHECKED = 0, 1, 2
    BOX_PX = 14

    def __init__(self, renderer, interactor, text="", parent=None,
                 checked=False, tristate=False, object_name=None):
        self._text = str(text)
        self._state = self.CHECKED if checked else self.UNCHECKED
        self._tristate = bool(tristate)
        super().__init__(renderer, interactor, parent,
                         object_name or "check_box")
        self._init_click()
        self.toggled = Signal(self)
        self.stateChanged = Signal(self)
        self.refresh()

    def text(self):
        return self._text

    def setText(self, text):
        self._text = str(text)
        self.updateGeometry()
        self.refresh()

    def isChecked(self):
        return self._state == self.CHECKED

    def setChecked(self, checked):
        self.setCheckState(self.CHECKED if checked else self.UNCHECKED)

    def checkState(self):
        return self._state

    def setCheckState(self, state):
        state = int(state)
        if state == self.PARTIAL and not self._tristate:
            state = self.CHECKED
        if state == self._state:
            return
        was_checked = self.isChecked()
        self._state = state
        self.stateChanged.emit(state)
        if was_checked != self.isChecked():
            self.toggled.emit(self.isChecked())
        self.refresh()

    def isTristate(self):
        return self._tristate

    def setTristate(self, tristate=True):
        self._tristate = bool(tristate)

    def toggle(self):
        self.setChecked(not self.isChecked())

    def _activate(self):
        if self._tristate:
            self.setCheckState((self._state + 1) % 3)
        else:
            self.toggle()

    def saveState(self):
        state = super().saveState()
        state["checkState"] = self._state
        return state

    def restoreState(self, state):
        if "checkState" in state:
            with self.signalBlocker():
                self.setCheckState(state["checkState"])
        return super().restoreState(
            {key: value for key, value in state.items()
             if key != "checkState"})

    def defaultSizePolicy(self):
        return SizePolicy(SizePolicy.Preferred, SizePolicy.Fixed)

    def sizeHint(self):
        width, height = self.measureText(self._text)
        gap = 6.0 if self._text else 0.0
        return (self.BOX_PX + gap + width + 2.0,
                max(self.BOX_PX + 4.0, height + 6.0))

    def minimumSizeHint(self):
        return self.sizeHint()

    def _indicator(self, x, y, size, tokens, filled):
        radius = self.px(3)
        extra = ("checked",) if filled else ()
        border = self.color("indicator", "border", *extra)
        fill = self.color("indicator", "background", *extra)
        return [rounded_rect_polydata(x, y, size, size, [radius] * 4,
                                      _rgba(border)),
                rounded_rect_polydata(x + 1, y + 1, size - 2, size - 2,
                                      [radius - 1] * 4, _rgba(fill))]

    def paint(self, x, y, width, height, tokens):
        size = self.px(self.BOX_PX)
        box_x, box_y = x, y + (height - size) / 2
        filled = self._state != self.UNCHECKED
        shapes = self._indicator(box_x, box_y, size, tokens, filled)
        overlay = []
        mark = _rgba(self.color("indicator", "mark"))
        if self._state == self.CHECKED:
            overlay.append(_polyline(
                [(box_x + size * 0.24, box_y + size * 0.52),
                 (box_x + size * 0.43, box_y + size * 0.30),
                 (box_x + size * 0.78, box_y + size * 0.72)], mark))
        elif self._state == self.PARTIAL:
            overlay.append(_polyline(
                [(box_x + size * 0.26, box_y + size * 0.5),
                 (box_x + size * 0.74, box_y + size * 0.5)], mark))
        self.placeText(self._text, box_x + size + self.px(6), y + height / 2,
                       self.textColor(tokens))
        return shapes, overlay


class ButtonGroup:
    """Groups check boxes/radio buttons; exclusive by default."""

    def __init__(self, exclusive=True):
        self._buttons = []
        self._ids = {}
        self._exclusive = bool(exclusive)
        self.buttonClicked = Signal()
        self.idClicked = Signal()
        self.buttonToggled = Signal()
        self.idToggled = Signal()

    def addButton(self, button, button_id=-1):
        if button in self._buttons:
            return
        if button_id == -1:
            button_id = -2 - len(self._buttons)       # Qt's automatic ids
        self._buttons.append(button)
        self._ids[id(button)] = button_id
        button._group_ref = weakref.ref(self)
        button.clicked.connect(lambda current=button: self._clicked(current))
        button.toggled.connect(
            lambda checked, current=button: self._toggled(current, checked))
        if self._exclusive and button.isChecked():
            for other in self._buttons:
                if other is not button and other.isChecked():
                    other.setChecked(False)

    def removeButton(self, button):
        if button in self._buttons:
            self._buttons.remove(button)
            self._ids.pop(id(button), None)
            button._group_ref = None

    def buttons(self):
        return tuple(self._buttons)

    def id(self, button):
        return self._ids.get(id(button), -1)

    def button(self, button_id):
        return next((button for button in self._buttons
                     if self._ids.get(id(button)) == button_id), None)

    def checkedButton(self):
        return next((button for button in self._buttons
                     if button.isChecked()), None)

    def checkedId(self):
        button = self.checkedButton()
        return -1 if button is None else self.id(button)

    def exclusive(self):
        return self._exclusive

    def setExclusive(self, exclusive):
        self._exclusive = bool(exclusive)

    def _clicked(self, button):
        self.buttonClicked.emit(button)
        self.idClicked.emit(self.id(button))

    def _toggled(self, button, checked):
        if checked and self._exclusive:
            for other in self._buttons:
                if other is not button and other.isChecked():
                    other.setChecked(False)
        self.buttonToggled.emit(button, checked)
        self.idToggled.emit(self.id(button), checked)


class RadioButton(CheckBox):
    """A radio button (``QRadioButton``).

    Radio buttons with the same parent widget are mutually exclusive unless
    placed in a :class:`ButtonGroup` (or ``setAutoExclusive(False)``).
    Clicking a checked radio button leaves it checked.
    """

    def __init__(self, renderer, interactor, text="", parent=None,
                 checked=False, object_name=None):
        self._auto_exclusive = True
        self._group_ref = None
        super().__init__(renderer, interactor, text, parent, checked,
                         object_name=object_name or "radio_button")
        self.toggled.connect(self._exclude_siblings)

    def autoExclusive(self):
        return self._auto_exclusive

    def setAutoExclusive(self, exclusive):
        self._auto_exclusive = bool(exclusive)

    def group(self):
        return None if self._group_ref is None else self._group_ref()

    def _activate(self):
        group = self.group()
        exclusive = (group.exclusive() if group is not None
                     else self._auto_exclusive)
        if exclusive and self.isChecked():
            return
        self.toggle()

    def _exclude_siblings(self, checked):
        if not checked or self.group() is not None or not self._auto_exclusive:
            return
        parent = self.parentWidget()
        if parent is None:
            return
        for sibling in parent.children():
            if (sibling is not self and isinstance(sibling, RadioButton)
                    and sibling.group() is None and sibling.autoExclusive()
                    and sibling.isChecked()):
                sibling.setChecked(False)

    def _indicator(self, x, y, size, tokens, filled):
        border = self.color("indicator", "border")
        fill = self.style().color("indicator", "background",
                                  self.styleState() - {"checked"}, widget=self)
        return [rounded_rect_polydata(x, y, size, size, [size / 2] * 4,
                                      _rgba(border)),
                rounded_rect_polydata(x + 1.5, y + 1.5, size - 3, size - 3,
                                      [size / 2] * 4, _rgba(fill))]

    def paint(self, x, y, width, height, tokens):
        size = self.px(self.BOX_PX)
        box_x, box_y = x, y + (height - size) / 2
        shapes = self._indicator(box_x, box_y, size, tokens, self.isChecked())
        if self.isChecked():
            dot = size * 0.5
            color = self.color("indicator", "fill")
            shapes.append(rounded_rect_polydata(
                box_x + (size - dot) / 2, box_y + (size - dot) / 2, dot, dot,
                [dot / 2] * 4, _rgba(color)))
        self.placeText(self._text, box_x + size + self.px(6), y + height / 2,
                       self.textColor(tokens))
        return shapes, []


class ProgressBar(NativeWidget):
    """A progress bar (``QProgressBar``); ``setRange(0, 0)`` means busy."""

    def __init__(self, renderer, interactor, parent=None, minimum=0,
                 maximum=100, value=0, text_visible=True, object_name=None):
        self._minimum = minimum
        self._maximum = maximum
        self._value = value
        self._format = "%p%"
        self._text_visible = bool(text_visible)
        self._busy_phase = 0.0
        self._busy_animation = None
        super().__init__(renderer, interactor, parent,
                         object_name or "progress_bar")
        self.valueChanged = Signal(self)
        self._sync_busy()
        self.refresh()

    def minimum(self):
        return self._minimum

    def maximum(self):
        return self._maximum

    def setRange(self, minimum, maximum):
        self._minimum, self._maximum = minimum, max(minimum, maximum)
        self._value = min(max(self._value, self._minimum), self._maximum)
        self._sync_busy()
        self.refresh()

    def value(self):
        return self._value

    def setValue(self, value):
        value = min(max(value, self._minimum), self._maximum)
        if value != self._value:
            self._value = value
            self.valueChanged.emit(value)
            self.refresh()

    def reset(self):
        self.setValue(self._minimum)

    def setFormat(self, text):
        self._format = str(text)
        self.refresh()

    def setTextVisible(self, visible):
        self._text_visible = bool(visible)
        self.refresh()

    def isBusy(self):
        return self._minimum == self._maximum == 0

    def text(self):
        if self.isBusy():
            return ""
        span = self._maximum - self._minimum
        percent = 0 if span == 0 else round(
            100.0 * (self._value - self._minimum) / span)
        return (self._format.replace("%p", str(percent))
                .replace("%v", str(self._value))
                .replace("%m", str(self._maximum)))

    BUSY_CYCLE_MS = 1400

    def _sync_busy(self):
        from .animation import PropertyAnimation, animations_enabled

        if self.isBusy() and self._busy_animation is None:
            if not animations_enabled():
                self._busy_phase = 0.5          # a still chunk mid-bar
                return
            animation = PropertyAnimation(
                self, "busyPhase", duration_ms=self.BUSY_CYCLE_MS,
                easing="inOutSine", start_value=0.0, end_value=1.0,
                loop_count=-1, request_render=False)
            self._busy_animation = animation
            animation.start()
        elif not self.isBusy() and self._busy_animation is not None:
            self._busy_animation.stop()
            self._busy_animation = None

    def busyPhase(self):
        return self._busy_phase

    def setBusyPhase(self, phase):
        self._busy_phase = float(phase) % 1.0
        if self._shown:
            self.refresh()

    def close(self):
        if self._busy_animation is not None:
            self._busy_animation.stop()
            self._busy_animation = None
        return super().close()

    def defaultSizePolicy(self):
        return SizePolicy(SizePolicy.Expanding, SizePolicy.Fixed)

    def sizeHint(self):
        return (160.0, 18.0 if self._text_visible else 8.0)

    def minimumSizeHint(self):
        return (48.0, 18.0 if self._text_visible else 8.0)

    def paint(self, x, y, width, height, tokens):
        bar_height = self.px(8)
        bar_y = y + (height - bar_height) / 2
        radius = bar_height / 2
        text = self.text() if self._text_visible else ""
        # Text sits to the right of the bar (as in Qt's Fusion style).
        text_width = self.px(self.measureText("100%")[0] + 8) if text else 0.0
        width = max(bar_height, width - text_width)
        shapes = [rounded_rect_polydata(x, bar_y, width, bar_height,
                                        [radius] * 4,
                                        _rgba(self.color("progress",
                                                         "background")))]
        fill = self.color("progress", "fill")
        if self.isBusy():
            chunk = width * 0.25
            start = x + (width + chunk) * self._busy_phase - chunk
            left, right = max(x, start), min(x + width, start + chunk)
            if right > left:
                shapes.append(rounded_rect_polydata(
                    left, bar_y, right - left, bar_height, [radius] * 4,
                    _rgba(fill)))
        else:
            span = self._maximum - self._minimum
            fraction = 0.0 if span == 0 else (
                (self._value - self._minimum) / span)
            if fraction > 0:
                shapes.append(rounded_rect_polydata(
                    x, bar_y, max(bar_height, width * fraction), bar_height,
                    [radius] * 4, _rgba(fill)))
        self.placeText(text, x + width + text_width, y + height / 2,
                       self.textColor(tokens), "right")
        return shapes, []


class MenuItem(_Clickable):
    """One row of a :class:`Menu`: an action, a separator or a sub-menu."""

    FOCUS_POLICY = "NoFocus"
    ROW_PX = 24
    SEPARATOR_PX = 9

    def __init__(self, menu, action=None, submenu=None, separator=False):
        self._menu_ref = weakref.ref(menu)
        self.menu_action = action
        self.submenu = submenu
        self.separator = bool(separator)
        self._active = False
        super().__init__(menu.renderer, menu.interactor, menu,
                         object_name="menu_item", ui_z_order=menu.ui_z_order)
        self._init_click()
        if action is not None:
            action.changed.connect(self._sync, unique=True)
        self._sync()

    def menu(self):
        return self._menu_ref()

    def _sync(self):
        action = self.menu_action
        if action is not None:
            self._available = action.isEnabled()
            self.setVisible(action.isVisible())
        self.updateGeometry()
        self.refresh()

    def text(self):
        if self.submenu is not None:
            return self.submenu.title()
        return self.menu_action.text() if self.menu_action is not None else ""

    def isSelectable(self):
        return not self.separator and self._available and self.isVisible()

    def setActive(self, active):
        active = bool(active)
        if active != self._active:
            self._active = active
            self.refresh()

    def enterEvent(self, event):
        super().enterEvent(event)
        menu = self.menu()
        if menu is not None and self.isSelectable():
            menu._set_active(self, open_submenu=True)

    def _activate(self):
        menu = self.menu()
        if menu is not None and not self.separator:
            menu._activate_item(self)

    def defaultSizePolicy(self):
        return SizePolicy(SizePolicy.Expanding, SizePolicy.Fixed)

    def _shortcut_text(self):
        action = self.menu_action
        shortcut = action.shortcut() if action is not None else None
        return shortcut.toString() if shortcut is not None else ""

    def sizeHint(self):
        if self.separator:
            return (40.0, float(self.SEPARATOR_PX))
        width, _height = self.measureText(self.text())
        extra = self.measureText(self._shortcut_text())[0]
        return (22.0 + width + (24.0 + extra if extra else 0.0) + 22.0,
                float(self.ROW_PX))

    def minimumSizeHint(self):
        return self.sizeHint()

    def paint(self, x, y, width, height, tokens):
        if self.separator:
            self.text_actor.SetInput("")
            line_y = y + height / 2
            return [rounded_rect_polydata(x + self.px(6), line_y, width
                                          - self.px(12), max(1.0, self.px(1)),
                                          [0, 0, 0, 0],
                                          _rgba(tokens["border"]))], []
        shapes = []
        highlight = self.color("menu_item", "background",
                               *(("active",) if self._active else ()))
        if highlight is not None:
            shapes.append(rounded_rect_polydata(
                x + self.px(2), y, width - self.px(4), height, [self.px(4)] * 4,
                _rgba(highlight)))
        overlay = []
        action = self.menu_action
        mark = _rgba(self.color("menu_item", "mark"))
        if action is not None and action.isChecked():
            size = self.px(10)
            mx, my = x + self.px(6), y + (height - size) / 2
            overlay.append(_polyline(
                [(mx, my + size * 0.5), (mx + size * 0.35, my + size * 0.15),
                 (mx + size, my + size * 0.85)], mark))
        if self.submenu is not None:
            size = self.px(4)
            cx, cy = x + width - self.px(10), y + height / 2
            overlay.append(_polyline(
                [(cx - size / 2, cy + size), (cx + size / 2, cy),
                 (cx - size / 2, cy - size)], mark))
        text = self.text()
        shortcut = self._shortcut_text()
        if shortcut:
            text = f"{text}"
        self.placeText(text, x + self.px(22), y + height / 2,
                       self.textColor(tokens))
        if shortcut:
            # Second text drawn by a dedicated actor keeps alignment simple.
            self._shortcut_actor().SetInput(shortcut)
            self._shortcut_actor().SetPosition(x + width - self.px(10),
                                               y + height / 2)
            self._shortcut_actor().GetTextProperty().SetColor(
                *tokens["muted"])
            self._shortcut_actor().SetVisibility(True)
        return shapes, overlay

    def _shortcut_actor(self):
        actor = getattr(self, "_shortcut_text_actor", None)
        if actor is None:
            actor = vtk.vtkTextActor()
            actor.IsUI = True
            actor.PickableOff()
            text_property = actor.GetTextProperty()
            apply_ui_font(text_property)
            text_property.SetFontSize(self.fontSize())
            text_property.SetJustificationToRight()
            text_property.SetVerticalJustificationToCentered()
            actor.GetPositionCoordinate().SetCoordinateSystemToViewport()
            add_actor_2d(ui_layer(self.renderer), actor)
            self._shortcut_text_actor = actor
            self.overlay_track_actor = actor        # raised with the item
        return actor

    def refresh(self):
        actor = getattr(self, "_shortcut_text_actor", None)
        if actor is not None:
            actor.SetVisibility(False)
        super().refresh()

    def close(self):
        actor = getattr(self, "_shortcut_text_actor", None)
        if actor is not None:
            remove_actor_2d(ui_layer(self.renderer), actor)
        return super().close()


class Menu(Popup):
    """A popup menu of actions (``QMenu``).

    ``addAction`` accepts an :class:`~multipanel.actions.Action` or a text
    plus optional slot; ``addSeparator`` and ``addMenu`` add structure.
    Keyboard: Up/Down move, Return/Space activate, Right opens a sub-menu,
    Left or Escape closes. Triggering an item closes the whole menu chain
    and emits ``triggered(action)`` on every menu in it.
    """

    def __init__(self, renderer, interactor, title="", parent_menu=None):
        from .layouts import VBoxLayout

        super().__init__(renderer, interactor, object_name="menu")
        self._title = str(title)
        self._parent_menu_ref = (None if parent_menu is None
                                 else weakref.ref(parent_menu))
        self._items = []
        self._active = None
        self.triggered = Signal(self)
        self.hovered = Signal(self)
        self.setContentsMargins(4, 4, 4, 4)
        self._column = VBoxLayout(spacing=0)
        self.setLayout(self._column)

    # -- building ----------------------------------------------------------------
    def title(self):
        return self._title

    def setTitle(self, title):
        self._title = str(title)

    def addAction(self, action, slot=None):
        if not isinstance(action, Action):
            action = Action(str(action))
        if slot is not None:
            action.triggered.connect(lambda _checked=False: slot())
        self._add(MenuItem(self, action=action))
        return action

    def addSeparator(self):
        self._add(MenuItem(self, separator=True))

    def addMenu(self, title):
        submenu = Menu(self.renderer, self.interactor, title,
                       parent_menu=self)
        self._add(MenuItem(self, submenu=submenu))
        submenu.triggered.connect(self.triggered.emit)
        return submenu

    def _add(self, item):
        self._items.append(item)
        self._column.addWidget(item)

    def actions(self):
        return [item.menu_action for item in self._items
                if item.menu_action is not None]

    def items(self):
        return tuple(self._items)

    def clear(self):
        for item in self._items:
            self._column.removeWidget(item)
            item.close()
        self._items = []
        self._active = None

    def parentMenu(self):
        return None if self._parent_menu_ref is None else \
            self._parent_menu_ref()

    def rootMenu(self):
        menu = self
        while menu.parentMenu() is not None:
            menu = menu.parentMenu()
        return menu

    # -- showing ------------------------------------------------------------------
    def popup(self, at=None, anchor=None, placement="below", size=None,
              take_focus=True):
        for item in self._items:
            item._sync()
        self._set_active(None)
        return super().popup(at=at, anchor=anchor, placement=placement,
                             size=size, take_focus=take_focus)

    # -- activation ----------------------------------------------------------------
    def _selectable(self):
        return [item for item in self._items if item.isSelectable()]

    def activeItem(self):
        return self._active

    def _set_active(self, item, open_submenu=False):
        if self._active is not None and self._active is not item:
            self._active.setActive(False)
            if self._active.submenu is not None and \
                    self._active.submenu.isOpen():
                self._active.submenu.dismiss()
        self._active = item
        if item is None:
            return
        item.setActive(True)
        if item.menu_action is not None:
            item.menu_action.hover()
            self.hovered.emit(item.menu_action)
        if open_submenu and item.submenu is not None and \
                not item.submenu.isOpen():
            item.submenu.popup(anchor=item, placement="right")

    def _activate_item(self, item):
        if item.submenu is not None:
            if not item.submenu.isOpen():
                self._set_active(item)
                item.submenu.popup(anchor=item, placement="right")
            return
        action = item.menu_action
        if action is None or not action.isEnabled():
            return
        root = self.rootMenu()
        root.dismiss()
        action.trigger()
        self.triggered.emit(action)

    def _move(self, step):
        items = self._selectable()
        if not items:
            return
        if self._active not in items:
            target = items[0] if step > 0 else items[-1]
        else:
            target = items[(items.index(self._active) + step) % len(items)]
        self._set_active(target)

    def keyPressEvent(self, event):
        key = event.key().lower()
        if key == "down":
            self._move(1)
        elif key == "up":
            self._move(-1)
        elif key in ("return", "kp_enter", "space"):
            if self._active is not None:
                self._activate_item(self._active)
        elif key == "right":
            item = self._active
            if item is not None and item.submenu is not None:
                item.submenu.popup(anchor=item, placement="right")
                item.submenu._move(1)
        elif key == "left" and self.parentMenu() is not None:
            self.dismiss()
            self.parentMenu().setFocus(reason="popup")
        else:
            event.ignore()
            return
        event.accept()

    def dismiss(self):
        if self._active is not None:
            self._active.setActive(False)
            self._active = None
        return super().dismiss()


class ComboBox(_Clickable):
    """A drop-down list (``QComboBox``); the list is a :class:`Menu`.

    Up/Down change the current item while the combo box has focus; a click,
    or Space/Enter after keyboard focus, opens the list.
    """

    def __init__(self, renderer, interactor, parent=None, object_name=None):
        self._items = []          # (text, data)
        self._current = -1
        self._menu = None
        self._model = None        # optional ItemModel (setModel)
        self._model_column = 0
        self._model_keys = []
        super().__init__(renderer, interactor, parent,
                         object_name or "combo_box")
        self._init_click()
        self.currentIndexChanged = Signal(self)
        self.currentTextChanged = Signal(self)
        self.activated = Signal(self)
        self.textActivated = Signal(self)
        self.refresh()

    # -- model ------------------------------------------------------------------
    def model(self):
        """The :class:`~multipanel.models.ItemModel` shown, or None."""
        return self._model

    def setModel(self, model, column=0):
        """Show column ``column`` of an item model (``None``: own items).

        Items follow the model's changes; ``addItem`` and friends edit a
        :class:`~multipanel.models.ListModel` and are refused for other
        models. ``itemData`` is the model's ``"user"`` role.
        """
        if self._model is not None:
            for signal in self._model_signals():
                signal.disconnect(self._sync_from_model)
        self._model = model
        self._model_column = int(column)
        self._model_keys = []
        if model is None:
            return
        for signal in self._model_signals():
            signal.connect(self._sync_from_model)
        self._current = -1
        self._sync_from_model()

    def _model_signals(self):
        model = self._model
        return (model.dataChanged, model.rowsInserted, model.rowsRemoved,
                model.modelReset)

    def _sync_from_model(self, *_args):
        model = self._model
        current_key = self._model_keys[self._current] \
            if 0 <= self._current < len(self._model_keys) else None
        items, keys = [], []
        for row in range(model.rowCount()):
            index = model.index(row, self._model_column)
            text = index.data("display")
            items.append(("" if text is None else str(text),
                          index.data("user")))
            keys.append(model.persistentKey(model.index(row, 0)))
        old_text = self.currentText()
        self._items, self._model_keys = items, keys
        current = keys.index(current_key) if current_key in keys and \
            model.hasStableKeys() else min(self._current, len(items) - 1)
        if current < 0 and items:
            current = 0
        changed = current != self._current
        self._current = current
        if changed:
            self.currentIndexChanged.emit(current)
        if changed or self.currentText() != old_text:
            self.currentTextChanged.emit(self.currentText())
        self.updateGeometry()
        self.refresh()

    def _edit_model(self):
        """The ListModel to edit, None without a model, else TypeError."""
        if self._model is None:
            return None
        from .models import ListModel

        if not isinstance(self._model, ListModel):
            raise TypeError("edit the combo box's model directly")
        return self._model

    # -- items --------------------------------------------------------------------
    def addItem(self, text, data=None):
        model = self._edit_model()
        if model is not None:
            model.append({"display": str(text), "user": data})
            return
        self._items.append((str(text), data))
        if self._current < 0:
            self.setCurrentIndex(0)
        self.updateGeometry()
        self.refresh()

    def addItems(self, texts):
        for text in texts:
            self.addItem(text)

    def insertItem(self, index, text, data=None):
        model = self._edit_model()
        if model is not None:
            model.insert(index, {"display": str(text), "user": data})
            return
        self._items.insert(int(index), (str(text), data))
        if self._current >= index:
            self._current += 1
        elif self._current < 0:
            self.setCurrentIndex(0)
        self.updateGeometry()
        self.refresh()

    def removeItem(self, index):
        if not 0 <= index < len(self._items):
            return
        model = self._edit_model()
        if model is not None:
            model.removeRow(index)
            return
        del self._items[index]
        if not self._items:
            self.setCurrentIndex(-1)
        elif index < self._current or self._current >= len(self._items):
            self.setCurrentIndex(max(0, self._current - 1))
        else:
            self.refresh()
        self.updateGeometry()

    def clear(self):
        model = self._edit_model()
        if model is not None:
            model.clear()
            return
        self._items = []
        self.setCurrentIndex(-1)
        self.updateGeometry()

    def count(self):
        return len(self._items)

    def itemText(self, index):
        return self._items[index][0] if 0 <= index < len(self._items) else ""

    def itemData(self, index):
        return self._items[index][1] if 0 <= index < len(self._items) else None

    def findText(self, text):
        return next((index for index, (item, _data) in enumerate(self._items)
                     if item == text), -1)

    def findData(self, data):
        return next((index for index, (_text, item) in enumerate(self._items)
                     if item == data), -1)

    def currentIndex(self):
        return self._current

    def setCurrentIndex(self, index):
        index = int(index)
        if not -1 <= index < len(self._items):
            raise IndexError(f"combo box index {index} out of range")
        if index == self._current:
            return
        self._current = index
        self.currentIndexChanged.emit(index)
        self.currentTextChanged.emit(self.currentText())
        self.refresh()

    def currentText(self):
        return self.itemText(self._current)

    def setCurrentText(self, text):
        index = self.findText(text)
        if index >= 0:
            self.setCurrentIndex(index)

    def currentData(self):
        return self.itemData(self._current)

    # -- popup ------------------------------------------------------------------
    def isPopupVisible(self):
        return self._menu is not None and self._menu.isOpen()

    def showPopup(self):
        if not self._items or not self._available:
            return
        menu = Menu(self.renderer, self.interactor)
        group = ActionGroup()
        for index, (text, _data) in enumerate(self._items):
            action = Action(text, checkable=True, checked=index == self._current,
                            data=index)
            group.addAction(action)
            menu.addAction(action)
        menu.triggered.connect(self._chosen)
        menu.closed.connect(self._menu_closed)
        self._menu = menu
        width = max(self.geometry("px")[2], menu.sizeHint()[0])
        menu.popup(anchor=self, placement="below",
                   size=(width, menu.sizeHint()[1]))
        if 0 <= self._current < len(menu.items()):
            menu._set_active(menu.items()[self._current])
        self.refresh()

    def hidePopup(self):
        if self._menu is not None:
            self._menu.dismiss()

    def _chosen(self, action):
        index = action.data()
        self.setCurrentIndex(index)
        self.activated.emit(index)
        self.textActivated.emit(self.itemText(index))

    def _menu_closed(self):
        menu, self._menu = self._menu, None
        if menu is not None:
            self._release_menu(menu)
        self.refresh()

    def _release_menu(self, menu):
        """Release the list after the current event finishes."""
        scheduler = self.renderScheduler()
        if scheduler is None:
            menu.close()
        else:
            scheduler.defer(menu.close)

    def _activate(self):
        if self.isPopupVisible():
            self.hidePopup()
        else:
            self.showPopup()

    def keyPressEvent(self, event):
        key = event.key().lower()
        if key in ("down", "up") and self._items and not self.isPopupVisible():
            step = 1 if key == "down" else -1
            index = min(max(0, self._current + step), len(self._items) - 1)
            if index != self._current:
                self.setCurrentIndex(index)
                self.activated.emit(index)
                self.textActivated.emit(self.itemText(index))
            event.accept()
            return
        event.ignore()

    # -- appearance ----------------------------------------------------------------
    def defaultSizePolicy(self):
        return SizePolicy(SizePolicy.Expanding, SizePolicy.Fixed)

    def sizeHint(self):
        widest = max((self.measureText(text)[0] for text, _ in self._items),
                     default=40.0)
        _width, height = self.measureText("Hg")
        return (widest + 36.0, height + 12.0)

    def minimumSizeHint(self):
        _width, height = self.measureText("Hg")
        return (60.0, height + 10.0)

    def paint(self, x, y, width, height, tokens):
        radius = self.px(5)
        extra = ("open",) if self.isPopupVisible() else ()
        border = self.color("field", "border", *extra)
        fill = self.color("field", "background", *extra)
        shapes = [rounded_rect_polydata(x, y, width, height, [radius] * 4,
                                        _rgba(border)),
                  rounded_rect_polydata(x + 1, y + 1, width - 2, height - 2,
                                        [radius - 1] * 4, _rgba(fill))]
        size = self.px(4)
        cx, cy = x + width - self.px(12), y + height / 2
        overlay = [_polyline([(cx - size, cy + size / 2), (cx, cy - size / 2),
                              (cx + size, cy + size / 2)],
                             _rgba(self.textColor(tokens)))]
        self.placeText(self.currentText(), x + self.px(8), y + height / 2,
                       self.textColor(tokens))
        return shapes, overlay


class MessageBox(Popup):
    """A modal message with buttons (``QMessageBox``), centred and dimmed.

    VTK has no nested event loop, so ``exec()`` is not offered: connect to
    ``finished(button_text)`` instead. Enter presses the default button;
    Escape (or a close) reports the escape button.
    """

    def __init__(self, renderer, interactor, title="", text="",
                 buttons=("OK",), default=None, escape=None, scrim=True):
        from .layouts import HBoxLayout, VBoxLayout

        super().__init__(renderer, interactor, modal=True,
                         object_name="message_box")
        self.setScrim(scrim)
        self.finished = Signal(self)
        self._buttons = {}
        self._result = None
        names = [str(name) for name in buttons]
        self._default = default if default in names else names[0]
        if escape in names:
            self._escape = escape
        else:
            self._escape = next((name for name in names if name.lower() in
                                 ("cancel", "no", "close")), names[-1])
        self.setContentsMargins(16, 14, 16, 12)
        column = VBoxLayout(spacing=10)
        renderer = self.renderer            # the popup layer
        self._title = Label(renderer, interactor, title, bold=True)
        self._text = Label(renderer, interactor, text)
        if title:
            column.addWidget(self._title)
        column.addWidget(self._text)
        row = HBoxLayout(spacing=8)
        row.addStretch()
        for name in names:
            button = PushButton(renderer, interactor, name,
                                default=name == self._default)
            button.clicked.connect(lambda current=name: self.done(current))
            self._buttons[name] = button
            row.addWidget(button)
        column.addSpacing(4)
        column.addLayout(row)
        self.setLayout(column)

    @classmethod
    def information(cls, renderer, interactor, title, text, buttons=("OK",)):
        return cls(renderer, interactor, title, text, buttons).show_box()

    @classmethod
    def warning(cls, renderer, interactor, title, text, buttons=("OK",)):
        return cls(renderer, interactor, title, text, buttons).show_box()

    @classmethod
    def question(cls, renderer, interactor, title, text,
                 buttons=("Yes", "No"), default="Yes"):
        return cls(renderer, interactor, title, text, buttons,
                   default=default).show_box()

    def button(self, name):
        return self._buttons.get(name)

    def defaultButton(self):
        return self._default

    def result(self):
        return self._result

    def show_box(self):
        """Open centred in the viewport; returns ``self``."""
        self._result = None
        self.popup()
        return self

    def done(self, name):
        if not self.isOpen():
            return
        self._result = name
        super().dismiss()
        self.finished.emit(name)

    def dismiss(self):
        """Closing without a choice reports the escape button."""
        if self.isOpen():
            self.done(self._escape)
            return True
        return False

    def keyPressEvent(self, event):
        if event.key().lower() in ("return", "kp_enter"):
            self.done(self._default)
            event.accept()
            return
        event.ignore()


class StatusBar(NativeWidget):
    """One line of status text (``QStatusBar``).

    ``showMessage(text, timeout_ms)`` shows a temporary message; while the
    pointer rests on a widget with a status tip, that tip is shown instead,
    as in Qt.
    """

    def __init__(self, renderer, interactor, parent=None, object_name=None):
        from .router import EventRouter

        self._message = ""
        self._tip = ""
        self._timer = None
        super().__init__(renderer, interactor, parent,
                         object_name or "status_bar")
        self.messageChanged = Signal(self)
        EventRouter.install(interactor).hoverChanged.connect(self._hovered_widget)
        self.refresh()

    def currentMessage(self):
        return self._tip or self._message

    def showMessage(self, text, timeout_ms=0):
        from .timer import Timer

        self._message = str(text)
        if self._timer is not None:
            self._timer.stop()
            self._timer = None
        if timeout_ms:
            self._timer = Timer.singleShot(self.interactor, timeout_ms,
                                           self.clearMessage)
        self.messageChanged.emit(self.currentMessage())
        self.refresh()

    def clearMessage(self):
        if self._timer is not None:
            self._timer.stop()
            self._timer = None
        self._message = ""
        self.messageChanged.emit(self.currentMessage())
        self.refresh()

    def _hovered_widget(self, widget):
        tip = ""
        while widget is not None and not tip:
            getter = getattr(widget, "statusTip", None)
            tip = getter() if callable(getter) else ""
            parent_of = getattr(widget, "parentWidget", None)
            widget = parent_of() if callable(parent_of) else None
        if tip != self._tip:
            self._tip = tip
            self.messageChanged.emit(self.currentMessage())
            self.refresh()

    def defaultSizePolicy(self):
        return SizePolicy(SizePolicy.Expanding, SizePolicy.Fixed)

    def sizeHint(self):
        return (200.0, self.measureText("Hg")[1] + 8.0)

    def paint(self, x, y, width, height, tokens):
        shapes = [rounded_rect_polydata(x, y, width, height, [0, 0, 0, 0],
                                        _rgba(tokens["title"])),
                  rounded_rect_polydata(x, y + height - 1, width, 1,
                                        [0, 0, 0, 0], _rgba(tokens["border"]))]
        self.placeText(self.currentMessage(), x + self.px(8), y + height / 2,
                       tokens["muted"])
        return shapes, []

    def close(self):
        from .router import EventRouter

        router = EventRouter.for_interactor(self.interactor)
        if router is not None:
            try:
                router.hoverChanged.disconnect(self._hovered_widget)
            except ValueError:
                pass
        if self._timer is not None:
            self._timer.stop()
        return super().close()


class _MenuTitle(_Clickable):
    """One title in a :class:`MenuBar`."""

    FOCUS_POLICY = "NoFocus"

    def __init__(self, bar, menu):
        self._bar_ref = weakref.ref(bar)
        self.menu = menu
        super().__init__(bar.renderer, bar.interactor, bar,
                         object_name="menu_title")
        self._init_click()
        self.refresh()

    def text(self):
        return self.menu.title()

    def mousePressEvent(self, event):
        event.accept()
        bar = self._bar_ref()
        if bar is not None and event.button() == "left":
            bar._title_pressed(self)

    def mouseReleaseEvent(self, event):
        event.accept()

    def enterEvent(self, event):
        super().enterEvent(event)
        bar = self._bar_ref()
        if bar is not None:
            bar._title_hovered(self)

    def defaultSizePolicy(self):
        return SizePolicy(SizePolicy.Fixed, SizePolicy.Fixed)

    def sizeHint(self):
        width, height = self.measureText(self.text())
        return (width + 20.0, height + 10.0)

    def paint(self, x, y, width, height, tokens):
        shapes = []
        if self.menu.isOpen() or self._hovered:
            fill = tokens["accent_soft"] if self.menu.isOpen() else \
                tokens["row_hover"]
            shapes.append(rounded_rect_polydata(
                x, y + self.px(2), width, height - self.px(4),
                [self.px(4)] * 4, _rgba(fill)))
        self.placeText(self.text(), x + width / 2, y + height / 2,
                       self.textColor(tokens), "center")
        return shapes, []


class MenuBar(WidgetMixin):
    """A horizontal strip of menus (``QMenuBar``).

    Click a title to open its menu (again to close it); while a menu is
    open, hovering another title switches to it. Place it like any widget
    (``setGeometry``, or in a layout).
    """

    def __init__(self, renderer, interactor, parent=None):
        from .containers import Frame
        from .layouts import HBoxLayout

        self.renderer = renderer
        self.interactor = interactor
        self.initWidget("menu_bar", parent)
        self._frame = Frame(renderer, interactor, background=True,
                            object_name="menu_bar_background")
        self._frame.setParent(self)
        self._frame.setContentsMargins(4, 0, 4, 0)
        self._row = HBoxLayout(spacing=2)
        self._row.addStretch()
        self._frame.setLayout(self._row)
        self._titles = []
        self._just_closed = None

    # geometry is the frame's
    def GetBounds(self):
        return self._frame.GetBounds()

    def SetBounds(self, x0, x1, y0, y1):
        self._frame.SetBounds(x0, x1, y0, y1)

    def GetVisibility(self):
        return self._frame.GetVisibility()

    def SetVisibility(self, visible):
        self._frame.SetVisibility(visible)

    def sizeHint(self):
        return self._frame.sizeHint()

    def defaultSizePolicy(self):
        return SizePolicy(SizePolicy.Expanding, SizePolicy.Fixed)

    def addMenu(self, title):
        menu = Menu(self.renderer, self.interactor, title)
        title_widget = _MenuTitle(self, menu)
        self._titles.append(title_widget)
        self._row.insertWidget(len(self._titles) - 1, title_widget)
        menu.closed.connect(lambda current=title_widget:
                            self._menu_closed(current))
        return menu

    def menus(self):
        return [title.menu for title in self._titles]

    def openMenu(self):
        return next((title.menu for title in self._titles
                     if title.menu.isOpen()), None)

    def _open(self, title):
        current = self.openMenu()
        if current is title.menu:
            return
        if current is not None:
            current.dismiss()
        title.menu.popup(anchor=title, placement="below")
        title.refresh()

    def _title_pressed(self, title):
        # An outside press closes an open menu before reaching the title;
        # pressing the open menu's own title should leave it closed.
        if self._just_closed is title.menu:
            self._just_closed = None
            return
        if title.menu.isOpen():
            title.menu.dismiss()
        else:
            self._open(title)

    def _title_hovered(self, title):
        current = self.openMenu()
        if current is not None and current is not title.menu:
            self._open(title)

    def _menu_closed(self, title):
        self._just_closed = title.menu
        title.refresh()
        scheduler = self.renderScheduler()
        if scheduler is not None:
            scheduler.defer(self._forget_closed)

    def _forget_closed(self):
        self._just_closed = None
