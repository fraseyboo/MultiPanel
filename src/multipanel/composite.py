"""Composite versions of the controls that subclass VTK widgets (W5 §9.1).

The classes here have the constructor and public API of their namesakes in
:mod:`multipanel.controls`/:mod:`multipanel.containers`, but are drawn with
context items and actors of their own instead of subclassing a
``vtk*Widget``, so their bounds are the drawn bounds and they take part in
event routing like the other composite widgets. :attr:`native` is ``None``
on these and the instance itself on the legacy classes.

Use them directly, or make every later import of ``controls``/
``containers`` (and the library's own containers) use them with
:func:`multipanel.backend.set_widget_backend`.
"""
from __future__ import annotations

import logging
import os

import numpy as np
import vtk

from ._widget_support import (ICON_ROOT, UI_Z_PANEL_BACKGROUND,
                              UI_Z_PANEL_CONTROL, colormap_utils,
                              theme_role_for_color, ui_layer)
from .controls import VectorPanelBackground, _SliderAPI
from .core import Signal, SizePolicy, WidgetMixin
from .standard import _Clickable
from .vtk_compat import add_actor_2d, remove_actor_2d

logger = logging.getLogger(__name__)


class UnsupportedVtkMethod(AttributeError, NotImplementedError):
    """A VTK method a composite does not provide (an ``AttributeError``, so
    ``getattr(obj, name, default)`` and ``hasattr`` still work)."""


def _event_name(event):
    """``"StateChangedEvent"`` for the name or the ``vtkCommand`` id."""
    if isinstance(event, int):
        return vtk.vtkCommand.GetStringFromEventId(event)
    return str(event)


class VtkEvents:
    """``AddObserver``/``RemoveObserver``/``InvokeEvent`` for composites
    that stand in for VTK widgets: callbacks get ``(widget, event_name)``,
    higher priorities first."""

    def _vtk_observers(self):
        observers = self.__dict__.get("_vtk_event_observers")
        if observers is None:
            observers = self.__dict__["_vtk_event_observers"] = {}
        return observers

    def AddObserver(self, event, callback, priority=0.0):
        observers = self._vtk_observers()
        tag = self.__dict__.get("_vtk_next_tag", 1)
        self.__dict__["_vtk_next_tag"] = tag + 1
        observers[tag] = (_event_name(event), callback, float(priority))
        return tag

    def RemoveObserver(self, tag):
        self._vtk_observers().pop(tag, None)

    def RemoveObservers(self, event):
        name = _event_name(event)
        observers = self._vtk_observers()
        for tag in [t for t, (n, _c, _p) in observers.items() if n == name]:
            del observers[tag]

    def HasObserver(self, event):
        name = _event_name(event)
        return any(n == name for n, _c, _p in self._vtk_observers().values())

    def InvokeEvent(self, event, call_data=None):
        name = _event_name(event)
        ordered = sorted(((p, tag, c) for tag, (n, c, p) in
                          self._vtk_observers().items() if n == name),
                         key=lambda item: (-item[0], item[1]))
        for _priority, _tag, callback in ordered:
            callback(self, name)
        return 0


class PanelBackgroundWidget(VectorPanelBackground):
    """A rounded rectangle behind other elements, in place of the
    ``vtkBorderWidget`` of :class:`multipanel.containers.PanelBackgroundWidget`.

    ``panel_bounds`` (``xmin, xmax, ymin, ymax``, viewport fractions) grow
    by ``buffer`` on each side; ``radius`` is the corner strength of
    ``vtkBorderRepresentation`` (a fraction of half the shorter side). A
    highlighted background is drawn opaque in ``highlight_color``. With
    ``grabbable`` the panel can be dragged (``InteractionEvent``), as a
    :class:`~multipanel.controls.VectorPanelBackground` is.
    """

    native = None

    def __init__(self, renderer, interactor, panel_bounds, buffer=0.01,
                 panel_color=(1.0, 1.0, 1.0), highlight_color=(0.8, 0.8, 1),
                 border_color=(0, 0, 0), opacity=0.9,
                 name="background_rectangle", radius=0.1, border_width=4,
                 grabbable=False, place_factor=0.01, callback=None,
                 ui_z_order=UI_Z_PANEL_BACKGROUND):
        bounds = np.asarray(panel_bounds, dtype=float).copy()
        bounds[[0, 2]] -= buffer
        bounds[[1, 3]] += buffer
        self.buffer = buffer
        self.radius = float(radius)
        self.grabbable = bool(grabbable)
        self.place_factor = place_factor
        self._base_opacity = float(opacity)
        super().__init__(
            renderer, interactor, bounds=tuple(bounds),
            panel_color=panel_color, border_color=border_color,
            highlight_color=highlight_color, opacity=opacity,
            border_width=border_width, corner_radius=0.0,
            movable=self.grabbable, resizable=False, name=name,
            ui_z_order=ui_z_order)
        # The legacy class themes white/black defaults too.
        if tuple(panel_color[:3]) == (1.0, 1.0, 1.0) and \
                self._panel_theme_role is None:
            self._panel_theme_role = "panel_background_color"
        if tuple(border_color[:3]) == (0.0, 0.0, 0.0) and \
                self._border_theme_role is None:
            self._border_theme_role = "border_color"
        if self._highlight_theme_role is None:
            self._highlight_theme_role = theme_role_for_color(
                renderer, highlight_color, "accent_faint", "accent_soft")
        if callback is not None:
            self.AddObserver("InteractionEvent", callback)

    # -- the legacy attributes --------------------------------------------------------------
    @property
    def panel_bounds(self):
        return self.normalized_bounds

    @property
    def width(self):
        return self.normalized_bounds[1] - self.normalized_bounds[0]

    @property
    def height(self):
        return self.normalized_bounds[3] - self.normalized_bounds[2]

    @property
    def rep(self):
        return self

    def SetPanelBounds(self, xmin, xmax, ymin, ymax):
        self.SetBounds(xmin, xmax, ymin, ymax)

    # -- drawing ----------------------------------------------------------------------------
    def initialise_polydata(self, x, y, width, height, corner_radius=0.0,
                            resolution=6):
        radius = self.radius * min(width, height) / 2.0
        fill, border = super().initialise_polydata(
            x, y, width, height,
            corner_radius=radius if radius > 1.0 else 0.0,
            resolution=resolution)
        if self.border_width <= 0:            # no outline at all
            colors = border.GetCellData().GetScalars()
            for i in range(colors.GetNumberOfTuples()):
                colors.SetComponent(i, 3, 0)
        return fill, border

    def Highlight(self, state=True):
        """Draw in ``highlight_color``, opaque (the legacy behaviour)."""
        self.opacity = 1.0 if state else self._base_opacity
        super().Highlight(bool(state))

    def SetOpacity(self, opacity):
        self._base_opacity = float(opacity)
        if not self.highlighted:
            self.opacity = self._base_opacity
            self.Modified()

    def SetPolygonColor(self, *color):
        """``rep.SetPolygonColor`` of the legacy representation."""
        color = color[0] if len(color) == 1 else color
        self.panel_color = tuple(colormap_utils.color_to_RGB(color))
        self.Modified()

    def SetBorderColor(self, *color):
        color = color[0] if len(color) == 1 else color
        self.border_color = tuple(colormap_utils.color_to_RGB(color))
        self.Modified()

    def __repr__(self):
        return (f"composite.PanelBackgroundWidget(name={self.name}, "
                f"bounds={self.normalized_bounds}, visible={self.visible})")


def _png_icon(name, strict):
    path = os.path.join(ICON_ROOT, "png_icons", f"{name}.png")
    if os.path.exists(path):
        return path
    if strict:
        raise AssertionError(f"Icon path ({path}) does not exist")
    logger.warning("Icon path (%s) does not exist; using the question "
                   "mark icon.", path)
    return os.path.join(ICON_ROOT, "png_icons", "question-sign.png")


class _ButtonRepresentation:
    """The parts of ``vtkTexturedButtonRepresentation2D`` hosts use."""

    def __init__(self, button):
        self._button = button
        self._object_name = ""

    def GetState(self):
        return self._button.state()

    def SetState(self, state):
        self._button._set_state(int(state))

    def GetNumberOfStates(self):
        return len(self._button._textures)

    def GetVisibility(self):
        return self._button.GetVisibility()

    def SetVisibility(self, visible):
        self._button.SetVisibility(visible)

    VisibilityOn = lambda self: self.SetVisibility(True)       # noqa: E731
    VisibilityOff = lambda self: self.SetVisibility(False)     # noqa: E731

    def GetObjectName(self):
        return self._object_name

    def SetObjectName(self, name):
        self._object_name = str(name)

    def PlaceWidget(self, bounds):
        x0, x1, y0, y1 = (float(v) for v in tuple(bounds)[:4])
        self._button.SetPixelPosition(x0, y0, x1 - x0, y1 - y0)

    def Modified(self):
        self._button.refresh()


class ButtonWidget(VtkEvents, _Clickable):
    """An icon button with one PNG per state, in place of the
    ``vtkButtonWidget`` of :class:`multipanel.controls.ButtonWidget`.

    ``icon_name`` is one icon (two states drawn alike) or a list (one per
    state) from ``icons/png_icons``; a click moves to the next state and
    calls ``callback(widget, "StateChangedEvent")``, as the native widget
    does. ``SetPosition`` takes viewport fractions, ``SetPixelPosition`` and
    ``SetSize`` display pixels (the native conventions).
    """

    native = None

    def __init__(self, renderer, interactor, icon_name, callback,
                 initial_state=0, widget_bounds=(0.8, 0.9, 0.5, 0.6),
                 name=None, verbose=False, show_bounds=False,
                 ui_z_order=UI_Z_PANEL_CONTROL):
        names = [icon_name, icon_name] if isinstance(icon_name, str) \
            else list(icon_name)
        self.icon_name = icon_name
        self.callback = callback
        self.widget_bounds = widget_bounds
        self.name = name
        self.verbose = verbose
        self.show_bounds = show_bounds
        self.object_name = name if name is not None else \
            f"buttons/{names[0]}_button"
        self._state = 1 if initial_state else 0
        self.initial_state = self._state
        self._textures = []
        for index, icon in enumerate(names):
            reader = vtk.vtkPNGReader()
            reader.SetFileName(_png_icon(icon, strict=isinstance(icon_name,
                                                                  str)))
            reader.Update()
            texture = vtk.vtkTexture()
            texture.SetInputData(reader.GetOutput())
            texture.InterpolateOn()
            self._textures.append(texture)
        self._representation = _ButtonRepresentation(self)
        self._representation.SetObjectName(self.object_name)
        super().__init__(renderer, interactor, object_name=self.object_name,
                         ui_z_order=ui_z_order)
        self._init_click()
        self.toggled = Signal(self)
        self._last_signal_state = self._state
        self.icon_actor = self._make_icon_actor()
        add_actor_2d(ui_layer(renderer), self.icon_actor)
        width, height = interactor.GetRenderWindow().GetSize()[:2]
        if not width or not height:
            logger.warning("Window size is zero, defaulting to (800, 600)")
            width, height = 800, 600
        x0, x1, y0, y1 = widget_bounds
        self.Bounds = np.array([x0 * width, x1 * width, y0 * height,
                                y1 * height, 0.0, 0.0])
        if callback is not None:
            self.AddObserver("StateChangedEvent", callback)
        if not hasattr(renderer, "widgets"):
            renderer.widgets = {}
        renderer.widgets[self.object_name] = self
        self._sync_bounds()

    # -- drawing ----------------------------------------------------------------------------
    def _make_icon_actor(self):
        points = vtk.vtkPoints()
        points.SetNumberOfPoints(4)
        tcoords = vtk.vtkFloatArray()
        tcoords.SetNumberOfComponents(2)
        for u, v in ((0, 0), (1, 0), (1, 1), (0, 1)):
            tcoords.InsertNextTuple2(u, v)
        quad = vtk.vtkCellArray()
        quad.InsertNextCell(4, (0, 1, 2, 3))
        self._quad = vtk.vtkPolyData()
        self._quad.SetPoints(points)
        self._quad.SetPolys(quad)
        self._quad.GetPointData().SetTCoords(tcoords)
        mapper = vtk.vtkPolyDataMapper2D()
        mapper.SetInputData(self._quad)
        mapper.ScalarVisibilityOff()
        actor = vtk.vtkTexturedActor2D()
        actor.SetMapper(mapper)
        actor.IsUI = True
        actor.PickableOff()
        actor.SetVisibility(False)
        return actor

    def paint(self, x, y, width, height, tokens):
        points = self._quad.GetPoints()
        for index, (px, py) in enumerate(((x, y), (x + width, y),
                                          (x + width, y + height),
                                          (x, y + height))):
            points.SetPoint(index, px, py, 0.0)
        points.Modified()
        self._quad.Modified()
        self.icon_actor.SetTexture(self._textures[self._state])
        return [], []

    def refresh(self):
        super().refresh()
        icon = getattr(self, "icon_actor", None)
        if icon is not None:
            _x, _y, width, height = self.rect()
            icon.SetVisibility(bool(self._shown and width > 0 and height > 0))

    def rect(self):
        bounds = getattr(self, "Bounds", None)
        if bounds is None:
            return (0.0, 0.0, 0.0, 0.0)
        return (bounds[0], bounds[2], bounds[1] - bounds[0],
                bounds[3] - bounds[2])

    # -- geometry (the native conventions) --------------------------------------------------
    def _window_size(self):
        width, height = self.interactor.GetRenderWindow().GetSize()[:2]
        return max(1, width), max(1, height)

    def _sync_bounds(self):
        width, height = self._window_size()
        b = self.Bounds
        self._bounds = (b[0] / width, b[1] / width, b[2] / height,
                        b[3] / height)
        self.refresh()

    def SetPosition(self, x, y):
        """Move the lower-left corner to viewport fractions ``x, y``."""
        width, height = self._window_size()
        b = self.Bounds
        size = (b[1] - b[0], b[3] - b[2])
        self.SetPixelPosition(x * width, y * height, *size)

    def SetPixelPosition(self, x, y, width, height):
        self.Bounds[:4] = (x, x + width, y, y + height)
        self._sync_bounds()

    def SetSize(self, width, height):
        """Size in display pixels."""
        self.Bounds[1] = self.Bounds[0] + width
        self.Bounds[3] = self.Bounds[2] + height
        self._sync_bounds()

    def SetBounds(self, x0, x1, y0, y1):
        width, height = self._window_size()
        self.SetPixelPosition(x0 * width, y0 * height, (x1 - x0) * width,
                              (y1 - y0) * height)

    def defaultSizePolicy(self):
        return SizePolicy(SizePolicy.Fixed, SizePolicy.Fixed)

    def sizeHint(self):
        return (32.0, 32.0)

    def minimumSizeHint(self):
        return (20.0, 20.0)

    # -- state ------------------------------------------------------------------------------
    def GetRepresentation(self):
        return self._representation

    def On(self):
        self.SetVisibility(True)

    def Off(self):
        self.SetVisibility(False)

    def state(self):
        return self._state

    def _set_state(self, state):
        count = max(1, len(self._textures))
        self._state = int(state) % count
        self.refresh()

    def setState(self, state):
        old = self._state
        self._set_state(state)
        if old != self._state:
            self._last_signal_state = self._state
            self.toggled.emit(self.isChecked())

    def isChecked(self):
        return bool(self._state)

    def setChecked(self, checked):
        self.setState(1 if checked else 0)

    def toggle(self):
        self.setState((self._state + 1) % max(1, len(self._textures)))

    def click(self):
        """Next state, then the native signals and ``StateChangedEvent``."""
        if not self._available:
            return
        self.pressed.emit()
        self._next_state()
        self.released.emit()

    def _next_state(self):
        self._set_state(self._state + 1)
        self.InvokeEvent("StateChangedEvent")
        checked = self.isChecked()
        self.clicked.emit(checked)
        if self._state != self._last_signal_state:
            self._last_signal_state = self._state
            self.toggled.emit(checked)

    def mousePressEvent(self, event):
        if event.button() == "left" and self._available:
            self.setFocus(reason="mouse")
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        event.accept()
        if not self._pressed:
            return
        self._pressed = False
        self.released.emit()
        x, y = event.globalPos()
        if self.hitTest(x, y) and self._available:
            self._next_state()

    def saveState(self):
        state = super().saveState()
        state["state"] = self.state()
        return state

    def restoreState(self, state):
        if "state" in state:
            self.setState(state["state"])
        return super().restoreState({
            key: state[key] for key in (
                "objectName", "enabled", "visible", "toolTip", "statusTip")
            if key in state})

    def Modified(self):
        self.refresh()

    def close(self):
        remove_actor_2d(ui_layer(self.renderer), self.icon_actor)
        return super().close()

    def Delete(self):
        self.Off()
        self.close()


# -- SliderWidget -----------------------------------------------------------------------------
def _parameter(name, default, rebuild=True):
    """``Get<name>``/``Set<name>`` for a representation parameter."""
    attribute = "_" + name

    def getter(self):
        return getattr(self, attribute, default)

    def setter(self, value):
        value = type(default)(value)
        if getattr(self, attribute, default) != value:
            setattr(self, attribute, value)
            if rebuild:
                self.Modified()

    return getter, setter


def _in_quad(quad, x, y):
    """``(x, y)`` inside (or on) the convex quadrilateral ``quad``."""
    sign = 0
    for (ax, ay), (bx, by) in zip(quad, np.roll(quad, -1, axis=0)):
        cross = (bx - ax) * (y - ay) - (by - ay) * (x - ax)
        if abs(cross) < 1e-9:
            continue
        current = 1 if cross > 0 else -1
        if sign and current != sign:
            return False
        sign = current
    return bool(sign) or False


class SliderRepresentation:
    """A stand-in for ``vtkSliderRepresentation2D``: the same parameters,
    properties, point coordinates, geometry and picking, drawn with plain
    2D actors on the UI layer.

    The geometry follows VTK 9.5's ``BuildRepresentation``: the slider is
    laid out along x in units of the renderer's width, then rotated to the
    angle from point 1 to point 2 and scaled by the renderer's size; so
    lengths along a vertical slider are in units of the width, and widths
    across it in units of the height (the hosts rely on this).
    """

    OUTSIDE, TUBE, LEFT_CAP, RIGHT_CAP, SLIDER = 0, 1, 2, 3, 4

    GetSliderLength, SetSliderLength = _parameter("SliderLength", 0.01)
    GetSliderWidth, SetSliderWidth = _parameter("SliderWidth", 0.02)
    GetEndCapLength, SetEndCapLength = _parameter("EndCapLength", 0.005)
    GetEndCapWidth, SetEndCapWidth = _parameter("EndCapWidth", 0.05)
    GetTubeWidth, SetTubeWidth = _parameter("TubeWidth", 0.01)
    GetTitleHeight, SetTitleHeight = _parameter("TitleHeight", 0.030)
    GetLabelHeight, SetLabelHeight = _parameter("LabelHeight", 0.025)
    GetShowSliderLabel, SetShowSliderLabel = _parameter("ShowSliderLabel", 1)
    GetLabelFormat, SetLabelFormat = _parameter("LabelFormat", "%0.3g")

    def ShowSliderLabelOn(self):
        self.SetShowSliderLabel(1)

    def ShowSliderLabelOff(self):
        self.SetShowSliderLabel(0)

    def __getattr__(self, name):
        # Anything else of vtkSliderRepresentation2D: say what to use.
        if name.startswith(("Get", "Set")) or name.endswith(("On", "Off")):
            raise UnsupportedVtkMethod(
                f"SliderRepresentation.{name} is not provided by the "
                "composite slider; use the SliderWidget API or "
                "multipanel.legacy.SliderWidget")
        raise AttributeError(name)

    def __init__(self):
        self._minimum, self._maximum, self._value = 0.0, 1.0, 0.0
        self._picked_t = 0.0
        self._state = self.OUTSIDE
        self._title = ""
        self._object_name = ""
        self._visibility = True
        self._renderer = None
        self._widget = None
        self._key = None
        self._quads = {}
        self.X = 0.5
        self.Point1Coordinate = vtk.vtkCoordinate()
        self.Point1Coordinate.SetCoordinateSystemToWorld()
        self.Point1Coordinate.SetValue(-1.0, 0.0, 0.0)
        self.Point2Coordinate = vtk.vtkCoordinate()
        self.Point2Coordinate.SetCoordinateSystemToWorld()
        self.Point2Coordinate.SetValue(1.0, 0.0, 0.0)
        self.SliderProperty = vtk.vtkProperty2D()
        self.SliderProperty.SetColor(1, 1, 1)
        self.TubeProperty = vtk.vtkProperty2D()
        self.TubeProperty.SetColor(1, 1, 1)
        self.CapProperty = vtk.vtkProperty2D()
        self.CapProperty.SetColor(1, 1, 1)
        self.SelectedProperty = vtk.vtkProperty2D()
        self.SelectedProperty.SetColor(1.0, 0.4118, 0.7059)
        self.LabelProperty = self._text_property()
        self.TitleProperty = self._text_property()
        self._shapes = {}
        for part, prop in (("tube", self.TubeProperty),
                           ("slider", self.SliderProperty),
                           ("cap", self.CapProperty)):
            polydata = vtk.vtkPolyData()
            mapper = vtk.vtkPolyDataMapper2D()
            mapper.SetInputData(polydata)
            actor = vtk.vtkActor2D()
            actor.SetMapper(mapper)
            actor.SetProperty(prop)
            actor.IsUI = True
            actor.PickableOff()
            self._shapes[part] = (actor, polydata)
        self.LabelMapper, self.LabelActor = self._text_actor(
            self.LabelProperty)
        self.TitleMapper, self.TitleActor = self._text_actor(
            self.TitleProperty)

    @staticmethod
    def _text_property():
        prop = vtk.vtkTextProperty()
        prop.SetBold(1)
        prop.SetShadow(1)
        prop.SetFontFamilyToArial()
        prop.SetJustificationToCentered()
        prop.SetVerticalJustificationToCentered()
        return prop

    @staticmethod
    def _text_actor(prop):
        mapper = vtk.vtkTextMapper()
        mapper.SetInput("")
        mapper.SetTextProperty(prop)
        actor = vtk.vtkActor2D()
        actor.SetMapper(mapper)
        actor.IsUI = True
        actor.PickableOff()
        return mapper, actor

    def actors(self):
        """Back to front, as VTK renders them."""
        return [self._shapes["tube"][0], self._shapes["slider"][0],
                self._shapes["cap"][0], self.LabelActor, self.TitleActor]

    def GetActors2D(self, collection):
        for actor in self.actors():
            collection.AddItem(actor)

    # -- values -----------------------------------------------------------------------------
    def _changed(self):
        self.Modified()

    def GetMinimumValue(self):
        return self._minimum

    def GetMaximumValue(self):
        return self._maximum

    def GetValue(self):
        return self._value

    def GetCurrentT(self):
        return (self._value - self._minimum) / (self._maximum - self._minimum)

    def SetMinimumValue(self, value):
        value = float(value)
        if value == self._minimum:
            return
        if value >= self._maximum:
            self._maximum = value + 1
        self._minimum = value
        self._value = min(max(self._value, self._minimum), self._maximum)
        self._changed()

    def SetMaximumValue(self, value):
        value = float(value)
        if value == self._maximum:
            return
        if value <= self._minimum:
            self._minimum = value - 1
        self._maximum = value
        self._value = min(max(self._value, self._minimum), self._maximum)
        self._changed()

    def SetValue(self, value):
        value = float(value)
        if value == self._value:
            return
        self._value = min(max(value, self._minimum), self._maximum)
        self._changed()

    def GetPickedT(self):
        return self._picked_t

    def GetInteractionState(self):
        return self._state

    def SetTitleText(self, text):
        self._title = "" if text is None else str(text)
        self.Modified()

    def GetTitleText(self):
        return self._title

    def GetPoint1Coordinate(self):
        return self.Point1Coordinate

    def GetPoint2Coordinate(self):
        return self.Point2Coordinate

    def GetSliderProperty(self):
        return self.SliderProperty

    def GetTubeProperty(self):
        return self.TubeProperty

    def GetCapProperty(self):
        return self.CapProperty

    def GetSelectedProperty(self):
        return self.SelectedProperty

    def GetLabelProperty(self):
        return self.LabelProperty

    def GetTitleProperty(self):
        return self.TitleProperty

    def SetObjectName(self, name):
        self._object_name = str(name)

    def GetObjectName(self):
        return self._object_name

    def GetBounds(self):
        return None

    def SetRenderer(self, renderer):
        self._renderer = renderer

    def GetRenderer(self):
        return self._renderer

    def GetVisibility(self):
        return self._visibility

    def SetVisibility(self, visible):
        self._visibility = bool(visible)
        self.Modified()

    def VisibilityOn(self):
        self.SetVisibility(True)

    def VisibilityOff(self):
        self.SetVisibility(False)

    def Highlight(self, highlight):
        self._shapes["slider"][0].SetProperty(
            self.SelectedProperty if highlight else self.SliderProperty)

    def Modified(self):
        self._key = None
        widget = self._widget
        if widget is not None:
            widget._representation_changed()

    # -- geometry (VTK's BuildRepresentation) -----------------------------------------------
    def _endpoints(self):
        renderer = self._renderer
        p1 = self.Point1Coordinate.GetComputedDisplayValue(renderer)
        p2 = self.Point2Coordinate.GetComputedDisplayValue(renderer)
        return (float(p1[0]), float(p1[1])), (float(p2[0]), float(p2[1]))

    def BuildRepresentation(self, force=False):
        """Place the shapes and text; returns False before the renderer
        has a size."""
        renderer = self._renderer
        if renderer is None:
            return False
        size = renderer.GetSize()
        if not size[0] or not size[1]:
            return False
        p1, p2 = self._endpoints()
        key = (p1, p2, tuple(size), self._value, self._minimum,
               self._maximum, self.GetSliderLength(), self.GetSliderWidth(),
               self.GetEndCapLength(), self.GetEndCapWidth(),
               self.GetTubeWidth(), self.GetTitleHeight(),
               self.GetLabelHeight(), self.GetShowSliderLabel(),
               self.GetLabelFormat(), self._title,
               self.TitleProperty.GetMTime(), self.LabelProperty.GetMTime())
        if not force and key == self._key:
            return True
        sx, sy = float(size[0]), float(size[1])
        t = self.GetCurrentT()
        dx, dy = p2[0] - p1[0], p2[1] - p1[1]
        length = float(np.hypot(dx, dy)) or 1.0
        X = self.X = 0.5 * (length / sx)
        theta = float(np.arctan2(dy, dx))
        cap_l, slider_l = self.GetEndCapLength(), self.GetSliderLength()
        x = [-X, -X + cap_l]
        x.append(x[1] + t * (2.0 * X - 2.0 * cap_l - slider_l))
        x += [x[2] + slider_l, X - cap_l, X]
        cap_w, slider_w = self.GetEndCapWidth(), self.GetSliderWidth()
        tube_w = self.GetTubeWidth()
        y = [-0.5 * cap_w, -0.5 * slider_w, -0.5 * tube_w, 0.5 * tube_w,
             0.5 * slider_w, 0.5 * cap_w]
        canonical = {
            "cap0": [(x[0], y[0]), (x[1], y[0]), (x[1], y[5]), (x[0], y[5])],
            "tube": [(x[1], y[2]), (x[4], y[2]), (x[4], y[3]), (x[1], y[3])],
            "slider": [(x[2], y[1]), (x[3], y[1]), (x[3], y[4]),
                       (x[2], y[4])],
            "cap1": [(x[4], y[0]), (x[5], y[0]), (x[5], y[5]), (x[4], y[5])],
        }
        cos, sin = np.cos(theta), np.sin(theta)
        tx, ty = (int(p1[0]) + int(p2[0])) / 2.0, (int(p1[1]) + int(p2[1])) / 2.0

        def place(points):
            points = np.asarray(points, dtype=float)
            u, v = points[:, 0], points[:, 1]
            return np.column_stack((tx + (u * cos - v * sin) * sx,
                                    ty + (u * sin + v * cos) * sy))

        self._quads = {name: place(points)
                       for name, points in canonical.items()}
        for part, names in (("tube", ("tube",)), ("slider", ("slider",)),
                            ("cap", ("cap0", "cap1"))):
            self._shapes[part][1].ShallowCopy(
                self._polygons([self._quads[n] for n in names]))
        max_y = max(slider_w, tube_w, cap_w)
        show_label = bool(self.GetShowSliderLabel())
        self.LabelActor.SetVisibility(show_label and self._visibility)
        if show_label:
            fmt = self.GetLabelFormat()
            try:
                text = fmt % self._value if fmt else ""
            except (TypeError, ValueError):
                text = str(self._value)
            self.LabelMapper.SetInput(text)
            self.LabelProperty.SetFontSize(int(self.GetLabelHeight() * sy))
            w, h = self._text_size(self.LabelMapper)
            radius = max_y / 2.0 + h / sy * cos + w / sx * sin
            self.LabelActor.SetPosition(*place([((x[2] + x[3]) / 2.0,
                                                 radius)])[0])
        self.TitleMapper.SetInput(self._title)
        self.TitleProperty.SetFontSize(int(self.GetTitleHeight() * sy))
        w, h = self._text_size(self.TitleMapper)
        radius = max_y / 2.0 + h / sy * cos + w / sx * sin
        self.TitleActor.SetPosition(*place([(0.0, -radius)])[0])
        self._key = key
        return True

    def _text_size(self, mapper):
        size = [0, 0]
        if mapper.GetInput():
            mapper.GetSize(self._renderer, size)
        return float(size[0]), float(size[1])

    @staticmethod
    def _polygons(quads):
        points = vtk.vtkPoints()
        cells = vtk.vtkCellArray()
        for quad in quads:
            ids = [points.InsertNextPoint(px, py, 0.0) for px, py in quad]
            cells.InsertNextCell(len(ids), ids)
        polydata = vtk.vtkPolyData()
        polydata.SetPoints(points)
        polydata.SetPolys(cells)
        return polydata

    # -- picking (VTK's StartWidgetInteraction / ComputePickPosition) -----------------------
    def _local(self, event_pos):
        origin = self._renderer.GetOrigin() if self._renderer else (0, 0)
        return float(event_pos[0]) - origin[0], float(event_pos[1]) - origin[1]

    def ComputeInteractionState(self, event_pos):
        """The part under ``event_pos`` (display px), without side effects."""
        if not self._quads and not self.BuildRepresentation():
            return self.OUTSIDE
        x, y = self._local(event_pos)
        for state, name in ((self.SLIDER, "slider"), (self.TUBE, "tube"),
                            (self.LEFT_CAP, "cap0"),
                            (self.RIGHT_CAP, "cap1")):
            if _in_quad(self._quads[name], x, y):
                return state
        return self.OUTSIDE

    def StartWidgetInteraction(self, event_pos):
        self.BuildRepresentation()
        state = self.ComputeInteractionState(event_pos)
        self._state = state
        if state == self.TUBE:
            self.ComputePickPosition(event_pos)
        elif state == self.LEFT_CAP:
            self._picked_t = 0.0
        elif state == self.RIGHT_CAP:
            self._picked_t = 1.0
        return state

    def ComputePickPosition(self, event_pos):
        tube = self._quads["tube"]
        start = (tube[0] + tube[3]) / 2.0
        end = (tube[1] + tube[2]) / 2.0
        axis = end - start
        span = float(axis @ axis)
        point = np.asarray(self._local(event_pos))
        t = 0.0 if span == 0 else float((point - start) @ axis / span)
        X, cap_l = self.X, self.GetEndCapLength()
        travel = 2.0 * X - 2.0 * cap_l - self.GetSliderLength()
        scale = (2.0 * X - 2.0 * cap_l) / travel if travel else 1.0
        t = 0.5 + (t - 0.5) * scale
        self._picked_t = min(1.0, max(0.0, t))
        return self._picked_t

    def WidgetInteraction(self, event_pos):
        t = self.ComputePickPosition(event_pos)
        self.SetValue(self._minimum + t * (self._maximum - self._minimum))
        self.BuildRepresentation()


class _SliderSurface(WidgetMixin):
    """The ``vtkSliderWidget`` surface of the composite slider: below
    ``_SliderAPI`` in the MRO, which extends some of these methods."""

    START, SLIDING, ANIMATING = 0, 1, 2

    def _init_surface(self):
        self._vtk_enabled = False
        self._process_events = True
        self._interactor = None
        self._current_renderer = None
        self._default_renderer = None
        self._representation = None
        self._priority = 0.0
        self._widget_state = self.START
        self._animation_mode = "jump"
        self._vtk_object_name = ""

    # -- the vtkAbstractWidget surface ------------------------------------------------------
    def SetInteractor(self, interactor):
        self._interactor = interactor

    def GetInteractor(self):
        return self._interactor

    def SetCurrentRenderer(self, renderer):
        self._current_renderer = renderer
        if self._representation is not None:
            self._representation.SetRenderer(renderer)

    def GetCurrentRenderer(self):
        return self._current_renderer

    def SetDefaultRenderer(self, renderer):
        self._default_renderer = renderer

    def GetDefaultRenderer(self):
        return self._default_renderer

    def SetRepresentation(self, rep):
        if rep is self._representation:
            return
        layer = ui_layer(self.renderer)
        if self._representation is not None:
            for actor in self._representation.actors():
                remove_actor_2d(layer, actor)
            self._representation._widget = None
        self._representation = rep
        if rep is not None:
            rep._widget = self
            rep.SetRenderer(self._current_renderer or layer)
            for actor in rep.actors():
                actor.SetVisibility(False)
                add_actor_2d(layer, actor)
            self._representation_changed()

    def GetRepresentation(self):
        return self._representation

    def SetAnimationModeToJump(self):
        self._animation_mode = "jump"

    def SetAnimationModeToOff(self):
        self._animation_mode = "off"

    def SetPriority(self, priority):
        self._priority = float(priority)

    def GetPriority(self):
        return self._priority

    def SetObjectName(self, name):
        self._vtk_object_name = str(name)

    def GetObjectName(self):
        return self._vtk_object_name

    def SetProcessEvents(self, process):
        self._process_events = bool(process)

    def GetProcessEvents(self):
        return int(self._process_events)

    def GetEnabled(self):
        return int(self._vtk_enabled)

    def GetVisibility(self):
        return bool(self._vtk_enabled)

    def SetVisibility(self, visible):
        self.SetEnabled(bool(visible))

    def _set_vtk_enabled(self, enabled):
        enabled = bool(enabled)
        if enabled == self._vtk_enabled:
            return
        self._vtk_enabled = enabled
        if not enabled and self._widget_state != self.START:
            self._widget_state = self.START
            self._representation.Highlight(0)
        self._representation_changed()

    # _SliderAPI's EnabledOn/EnabledOff/SetEnabled call these through super().
    def EnabledOn(self):
        self._set_vtk_enabled(True)

    def EnabledOff(self):
        self._set_vtk_enabled(False)

    def SetEnabled(self, enabled):
        self._set_vtk_enabled(enabled)

    def On(self):
        self.EnabledOn()

    def Off(self):
        self.EnabledOff()

    def Render(self):
        self.requestRender()

    def Modified(self):
        self._representation_changed()

    # -- drawing ----------------------------------------------------------------------------
    def _representation_changed(self):
        rep = self._representation
        if rep is None:
            return
        shown = self._vtk_enabled and rep.GetVisibility()
        if shown:
            shown = rep.BuildRepresentation(force=True)
        for actor in rep.actors():
            actor.SetVisibility(bool(shown))
        if shown and not rep.GetShowSliderLabel():
            rep.LabelActor.SetVisibility(False)
        self.requestRender()

    def _before_render(self, *_):
        rep = self._representation
        if rep is not None and self._vtk_enabled and rep.GetVisibility():
            if rep._key is None:
                self._representation_changed()
            else:
                rep.BuildRepresentation()

    # -- input ------------------------------------------------------------------------------
    def hitTest(self, x, y):
        rep = self._representation
        if (rep is None or not self._vtk_enabled or not self._process_events
                or not rep.GetVisibility()):
            return False
        return rep.ComputeInteractionState((x, y)) != rep.OUTSIDE

    def mousePressEvent(self, event):
        rep = self._representation
        if event.button() != "left" or not self._process_events:
            event.ignore()
            return
        state = rep.StartWidgetInteraction(event.globalPos())
        if state == rep.OUTSIDE:
            event.ignore()
            return
        event.accept()
        self._widget_state = (self.SLIDING if state == rep.SLIDER
                              else self.ANIMATING)
        rep.Highlight(1)
        self.InvokeEvent("StartInteractionEvent")
        self.requestRender()

    def mouseMoveEvent(self, event):
        if self._widget_state != self.SLIDING:
            event.ignore()
            return
        event.accept()
        self._representation.WidgetInteraction(event.globalPos())
        self.InvokeEvent("InteractionEvent")
        self._representation_changed()

    def mouseReleaseEvent(self, event):
        if self._widget_state == self.START:
            event.ignore()
            return
        event.accept()
        rep = self._representation
        if (self._widget_state == self.ANIMATING
                and self._animation_mode == "jump"):
            state = rep.GetInteractionState()
            low, high = rep.GetMinimumValue(), rep.GetMaximumValue()
            if state == rep.TUBE:
                rep.SetValue(low + rep.GetPickedT() * (high - low))
            elif state == rep.LEFT_CAP:
                rep.SetValue(low)
            elif state == rep.RIGHT_CAP:
                rep.SetValue(high)
            if state != rep.SLIDER:
                rep.BuildRepresentation()
                self.InvokeEvent("InteractionEvent")
        rep.Highlight(0)
        self._widget_state = self.START
        self.InvokeEvent("EndInteractionEvent")
        self._representation_changed()

    def mouseDoubleClickEvent(self, event):
        self.mousePressEvent(event)

    # -- teardown ---------------------------------------------------------------------------
    def close(self):
        self.SetRepresentation(None)
        return super().close()

    def Delete(self):
        self.EnabledOff()
        self.close()


class SliderWidget(VtkEvents, _SliderAPI, _SliderSurface):
    """A slider drawn and picked like ``vtkSliderWidget`` (the geometry,
    parts and jump-to-click of VTK's 2D representation), in place of
    :class:`multipanel.controls.SliderWidget`.

    The constructor and API are the native class's (they share
    ``_SliderAPI``); ``rep`` is a :class:`SliderRepresentation`. Input
    comes through the router: pressing the thumb drags it, pressing the
    track or an end cap jumps there on release (VTK's ``Jump`` mode).
    """

    native = None

    def __init__(self, renderer, interactor, *args, **kwargs):
        self._init_surface()
        self._init_slider(SliderRepresentation(), renderer, interactor,
                          *args, **kwargs)
        self.registerWithRouter(interactor)
        self.ownObserver(ui_layer(renderer), "StartEvent",
                         self._before_render, 20.0)


__all__ = ["ButtonWidget", "PanelBackgroundWidget", "SliderRepresentation",
           "SliderWidget", "UnsupportedVtkMethod", "VtkEvents"]
