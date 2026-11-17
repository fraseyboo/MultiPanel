"""General-purpose VTK controls and their implementations."""

import logging
import weakref

from ._widget_support import *

logger = logging.getLogger(__name__)

def _display_to_logical(value):
    """Display pixels to logical pixels (see multipanel.units)."""
    return float(value) / ui_scale()


def _measure_text_px(widget, text, font_size, bold=None):
    """Rendered ``(width, height)`` in display px of ``text`` at ``font_size``."""
    prop = vtk.vtkTextProperty()
    prop.ShallowCopy(widget.text_actor.GetTextProperty())
    prop.SetFontSize(max(1, int(font_size)))
    if bold is not None:
        prop.SetBold(bool(bold))
    window = widget.interactor.GetRenderWindow()
    box = [0, 0, 0, 0]
    vtk.vtkTextRenderer.GetInstance().GetBoundingBox(
        prop, text or " ", box, max(1, window.GetDPI()))
    height = text_line_height(widget.interactor, font_size, bool(prop.GetBold()))
    return (max(1, box[1] - box[0] + 1),
            max(box[3] - box[2] + 1, height * max(1, window.GetSize()[1])))


class _SliderAPI:

    """
    Creates and configures a slider widget for use in a VTK rendering environment.

    Parameters:
        renderer (vtkRenderer): The VTK renderer to which the slider widget will be
        added.
        interactor (vtkRenderWindowInteractor): The interactor to handle user input for
        the slider.
        min_value (int, optional): The minimum value of the slider. Defaults to 0.
        max_value (int, optional): The maximum value of the slider. Defaults to 10.
        initial_value (int, optional): The initial value of the slider. Defaults to 5.
        title (str, optional): The title text displayed on the slider. Defaults to
        "Locator Level".
        callback (callable, optional): A function to be called when the slider value
        changes.Defaults to `trajan.graph.generate_box_representation_Callback`.
        position (tuple, optional): The (x, y) position of the slider in display or
        normalized display coordinates. Defaults to (40, 120).
        bar_length (int, optional): The length of the slider bar. Defaults to 200.
        use_relative_position (bool, optional): If True, the position is interpreted as
        normalized display coordinates. If False, it is interpretedas display
        coordinates. Defaults to False.
    Returns:
        vtkSliderWidget: The configured slider widget.
    Notes:
        - The slider widget is added to the `widgets` attribute of the renderer for
        tracking.
        - The slider's appearance (e.g., colors) is pre-configured but can be customized
        further.
        - The slider widget is enabled and given a high priority to ensure it receives
        interaction events.
    """


    def _init_slider(self,
        rep,
        renderer,
        interactor,
        min_value=0,
        max_value=10,
        initial_value=5,
        enabled=True,
        title="Slider Value",
        callback=None,
        position=(40, 120),
        bar_length=200,
        use_relative_position=False,
        slider_thickness=0.1,
        slider_bar_fraction=0.1,
        object_name=None,
        show_value=True,
        label_placement="above",
        orientation='horizontal',
        ui_z_order=UI_Z_SCROLL_ROWS,
        register_draw_order=True):

        """Set the slider up on ``rep`` (a ``vtkSliderRepresentation2D`` or
        the composite's stand-in)."""
        self.renderer = renderer
        self.interactor = interactor
        self.initWidget(object_name)
        self.valueChanged = Signal(self)
        self.sliderPressed = Signal(self)
        self.sliderMoved = Signal(self)
        self.sliderReleased = Signal(self)
        self._orientation = str(orientation).lower()
        self._single_step = 1.0
        self._tracking = True
        self._legacy_callback = callback
        self._last_committed_value = float(initial_value)
        self._last_moved_value = float(initial_value)
        self._use_relative_position = bool(use_relative_position)
        self._bar_position = tuple(float(value) for value in position[:2])
        self._bar_length = float(bar_length)
        self.registerFocus(interactor, policy="StrongFocus")

        self.SetInteractor(interactor)
        self.SetCurrentRenderer(ui_layer(renderer))
        self.SetDefaultRenderer(ui_layer(renderer))
        self.bar_length = bar_length

        if callback is None:
            warnings.warn("No callback provided for slider")



        # build a slide bar
        slide_rep = rep

        self.rep = slide_rep

        if title is not None:
            if object_name is None:
                object_name = f"sliders/{title}_slider"
            slide_rep.SetTitleText(title)
        else:
            if object_name is None:
                random_name = np.random.randint(0, 1000000)
                object_name = f"sliders/slider_{random_name}"


        slide_rep.SetObjectName(object_name)

        slide_rep.SetMinimumValue(min_value)
        slide_rep.SetMaximumValue(max_value)
        slide_rep.SetValue(initial_value)


        slide_rep.CurrentValue = initial_value

        # slider_height = slider_height_fraction * bar_length

        slide_rep.GetSliderProperty().SetColor(colormap_utils.color_to_RGB("alizarin_crimson"))
        slide_rep.GetTitleProperty().SetColor(colormap_utils.color_to_RGB("black"))
        slide_rep.GetLabelProperty().SetColor(colormap_utils.color_to_RGB("black"))
        slide_rep.GetSelectedProperty().SetColor(colormap_utils.color_to_RGB("green"))
        slide_rep.GetTubeProperty().SetColor(colormap_utils.color_to_RGB("black"))
        slide_rep.GetCapProperty().SetColor(colormap_utils.color_to_RGB("black"))
        slide_rep.SetTubeWidth(0.1 * slider_thickness)
        slide_rep.SetEndCapWidth(0.1 * slider_thickness)
        slide_rep.SetSliderWidth(0.11 * slider_thickness)


        if orientation == 'vertical':


            # slideBar.SetSliderLength(self.bar_length * slider_bar_fraction)
            # slideBar.SetTitleHeight(0)
            # slideBar.SetLabelHeight(0)
            # slideBar.SetShowSliderLabel(0)



            slide_rep.SetSliderLength(slider_bar_fraction)

            logger.debug("Slider length: %s", slide_rep.GetSliderLength())

            slide_rep.Modified()



        elif orientation == 'horizontal':
            slide_rep.SetSliderLength(0.1 * slider_thickness)
            slide_rep.SetTitleHeight(0.2 * slider_thickness)
            slide_rep.SetLabelHeight(0.2 * slider_thickness)

        slide_rep.GetBounds()

        self._set_slider_endpoints(
            self._bar_position, self._bar_length, self._orientation,
            relative=self._use_relative_position)


        # if orientation == 'vertical':


        #     if use_relative_position:


        #         slideBar.GetPoint1Coordinate().SetCoordinateSystemToNormalizedDisplay()
        #         slideBar.GetPoint1Coordinate().SetValue(position[0], position[1])

        #         slideBar.GetPoint2Coordinate().SetCoordinateSystemToNormalizedDisplay()
        #         slideBar.GetPoint2Coordinate().SetValue(position[0] , position[1])

        #     else:

        #         window_size = interactor.GetRenderWindow().GetSize()


        #         slideBar.GetPoint1Coordinate().SetCoordinateSystemToDisplay()
        #         slideBar.GetPoint1Coordinate().SetValue(position[0], position[1])

        #         slideBar.GetPoint2Coordinate().SetCoordinateSystemToDisplay()
        #         slideBar.GetPoint2Coordinate().SetValue(position[0], position[1] - bar_length)

        # elif orientation == 'horizontal':


        #     if use_relative_position:
        #         slideBar.GetPoint1Coordinate().SetCoordinateSystemToNormalizedDisplay()
        #         slideBar.GetPoint1Coordinate().SetValue(position[0], position[1])

        #         slideBar.GetPoint2Coordinate().SetCoordinateSystemToNormalizedDisplay()
        #         slideBar.GetPoint2Coordinate().SetValue(position[0] + bar_length, position[1])

        #     else:
        #         slideBar.GetPoint1Coordinate().SetCoordinateSystemToDisplay()
        #         slideBar.GetPoint1Coordinate().SetValue(position[0], position[1])

        #         slideBar.GetPoint2Coordinate().SetCoordinateSystemToDisplay()
        #         slideBar.GetPoint2Coordinate().SetValue(position[0] + bar_length, position[1])

        # if label_placement == "above":
        #     slideBar.GetLabelProperty().SetVerticalJustificationToTop()
        # elif label_placement == "below":
        #     slideBar.GetLabelProperty().SetVerticalJustificationToBottom()

        slide_rep.GetLabelProperty().ShadowOff()
        slide_rep.GetTitleProperty().ShadowOff()
        apply_ui_font(slide_rep.GetLabelProperty())
        apply_ui_font(slide_rep.GetTitleProperty())

        if not show_value:
            slide_rep.SetLabelFormat("")

        self.SetInteractor(interactor)
        self.SetRepresentation(slide_rep)
        self.SetAnimationModeToJump()


        if enabled:
            self.EnabledOn()
        else:
            self.EnabledOff()
        self.renderer = renderer
        self.SetPriority(1)  # Set a high priority to ensure it's the first widget to receive events


        self.ownObserver(self, "InteractionEvent", self._on_slider_moved)
        self.ownObserver(self, "StartInteractionEvent", self._on_slider_pressed)
        self.ownObserver(self, "EndInteractionEvent", self._on_slider_released)

        self.SetObjectName(object_name)
        self.ui_z_order = int(ui_z_order)
        if register_draw_order:
            register_ui_drawable(renderer, self, ui_z_order, object_name)

        if not hasattr(renderer, "widgets"):
            renderer.widgets = {}
        renderer.widgets.update({object_name: self})

    def _set_slider_endpoints(self, position, length, orientation, relative=True):
        point1 = self.rep.GetPoint1Coordinate()
        point2 = self.rep.GetPoint2Coordinate()
        if relative:
            point1.SetCoordinateSystemToNormalizedDisplay()
            point2.SetCoordinateSystemToNormalizedDisplay()
        else:
            point1.SetCoordinateSystemToDisplay()
            point2.SetCoordinateSystemToDisplay()
        x, y = position
        point1.SetValue(x, y)
        if orientation == "horizontal":
            point2.SetValue(x + length, y)
        elif orientation == "vertical":
            point2.SetValue(x, y - length)
        else:
            raise ValueError("orientation must be horizontal or vertical")
        self.rep.Modified()

    def _invoke_legacy_callback(self, event):
        if self._legacy_callback is not None:
            self._legacy_callback(self, event)

    def _on_slider_pressed(self, _caller=None, event="StartInteractionEvent"):
        self.setFocus(reason="mouse")
        self.grabMouse()
        self._last_committed_value = self.value()
        self._last_moved_value = self.value()
        self.sliderPressed.emit()

    def _on_slider_moved(self, _caller=None, event="InteractionEvent"):
        value = self.value()
        if math.isclose(value, self._last_moved_value,
                        rel_tol=0.0, abs_tol=1e-12):
            return
        self._last_moved_value = value
        self.sliderMoved.emit(value)
        if self._tracking:
            self._last_committed_value = value
            self.valueChanged.emit(value)
            self._invoke_legacy_callback(event)

    def _on_slider_released(self, _caller=None, event="EndInteractionEvent"):
        value = self.value()
        if (not self._tracking and
                not math.isclose(value, self._last_committed_value,
                                 rel_tol=0.0, abs_tol=1e-12)):
            self._last_committed_value = value
            self.valueChanged.emit(value)
            self._invoke_legacy_callback(event)
        self.releaseMouse()
        self.sliderReleased.emit()

    def value(self):
        return float(self.rep.GetValue())

    def setValue(self, value):
        value = min(self.maximum(), max(self.minimum(), float(value)))
        if math.isclose(value, self.value(), rel_tol=0.0, abs_tol=1e-12):
            return
        self.rep.SetValue(value)
        self.rep.CurrentValue = value
        self.rep.Modified()
        self._last_committed_value = value
        self.valueChanged.emit(value)

    def minimum(self):
        return float(self.rep.GetMinimumValue())

    def maximum(self):
        return float(self.rep.GetMaximumValue())

    def setMinimum(self, value):
        self.setRange(value, self.maximum())

    def setMaximum(self, value):
        self.setRange(self.minimum(), value)

    def setRange(self, minimum, maximum):
        minimum, maximum = float(minimum), float(maximum)
        if minimum > maximum:
            raise ValueError("minimum cannot exceed maximum")
        before = self.value()
        self.rep.SetMinimumValue(minimum)
        self.rep.SetMaximumValue(maximum)
        value = self.value()          # the representation clamped it
        if not math.isclose(value, before, rel_tol=0.0, abs_tol=1e-12):
            self.rep.CurrentValue = value
            self._last_committed_value = value
            self.valueChanged.emit(value)        # as Qt does

    def singleStep(self):
        return self._single_step

    def setSingleStep(self, step):
        step = float(step)
        if step <= 0:
            raise ValueError("single step must be greater than zero")
        self._single_step = step

    def orientation(self):
        return self._orientation

    def setOrientation(self, orientation):
        orientation = str(orientation).lower()
        if orientation not in {"horizontal", "vertical"}:
            raise ValueError("orientation must be horizontal or vertical")
        if orientation == self._orientation:
            return
        point1 = self.rep.GetPoint1Coordinate().GetValue()
        point2 = self.rep.GetPoint2Coordinate().GetValue()
        midpoint = ((point1[0] + point2[0]) * 0.5,
                    (point1[1] + point2[1]) * 0.5)
        length = math.hypot(point2[0] - point1[0], point2[1] - point1[1])
        self._orientation = orientation
        if orientation == "horizontal":
            start = (midpoint[0] - length * 0.5, midpoint[1])
        else:
            start = (midpoint[0], midpoint[1] + length * 0.5)
        self._bar_position = start
        self._bar_length = length
        self._set_slider_endpoints(
            start, length, orientation, relative=self._use_relative_position)
        if getattr(self, "flat_style", False):
            self._update_flat(force=True)

    def isTracking(self):
        return self._tracking

    def setTracking(self, tracking):
        self._tracking = bool(tracking)

    def _applyTheme(self):
        self.rep.GetTitleProperty().SetColor(
            *theme_value(self.renderer, 'text_color', (0.0, 0.0, 0.0)))
        self.rep.GetLabelProperty().SetColor(
            *theme_value(self.renderer, 'muted_text_color', (0.0, 0.0, 0.0)))
        if getattr(self, 'flat_style', False):
            self._flat_colors.update({
                'track': theme_value(
                    self.renderer, 'border_color', (0.75, 0.77, 0.8)),
                'thumb': theme_value(
                    self.renderer, 'muted_text_color', (0.4, 0.42, 0.45)),
                'active': theme_value(
                    self.renderer, 'text_color', (0.1, 0.1, 0.1)),
            })
            self.overlay_track_actor.GetProperty().SetColor(
                *self._flat_colors['track'])
            self._update_flat(force=True)
        self.rep.Modified()

    def saveState(self):
        state = super().saveState()
        state.update({
            'value': self.value(),
            'minimum': self.minimum(),
            'maximum': self.maximum(),
            'singleStep': self.singleStep(),
            'orientation': self.orientation(),
            'tracking': self.isTracking(),
        })
        return state

    def restoreState(self, state):
        if 'minimum' in state or 'maximum' in state:
            self.setRange(state.get('minimum', self.minimum()),
                          state.get('maximum', self.maximum()))
        if 'singleStep' in state:
            self.setSingleStep(state['singleStep'])
        if 'orientation' in state:
            self.setOrientation(state['orientation'])
        if 'tracking' in state:
            self.setTracking(state['tracking'])
        if 'value' in state:
            self.setValue(state['value'])
        return super().restoreState({
            key: state[key] for key in (
                'objectName', 'enabled', 'visible', 'toolTip', 'statusTip')
            if key in state})

    def _overlay_actors(self):
        return [actor for actor in (getattr(self, "overlay_track_actor", None),
                                    getattr(self, "overlay_actor", None))
                if actor is not None]

    def EnabledOn(self):
        """Enable the native interaction and any decorative overlay."""
        super().EnabledOn()
        for overlay in self._overlay_actors():
            overlay.SetVisibility(True)
        if getattr(self, "flat_style", False):
            self._update_flat(force=True)

    def EnabledOff(self):
        """Disable the native interaction and any decorative overlay."""
        super().EnabledOff()
        for overlay in self._overlay_actors():
            overlay.SetVisibility(False)

    def SetEnabled(self, enabled):
        super().SetEnabled(bool(enabled))
        for overlay in self._overlay_actors():
            overlay.SetVisibility(bool(enabled))
        if enabled and getattr(self, "flat_style", False):
            self._update_flat(force=True)

    # ---- flat style (matches the scrollbars) ----------------------------
    FLAT_TRACK_PX = 4
    FLAT_THUMB_PX = (20, 12)        # width, height
    FLAT_HIT_PX = 18                # grab height for the thumb and track

    def apply_flat_style(self):
        """Draw a thin rounded track and a rounded thumb (as the
        scrollbars do) instead of VTK's tube, end caps and square slider.

        The native parts stay as invisible hit targets; the overlay follows
        the value, layout and window size on every render."""
        if getattr(self, "flat_style", False):
            return
        self.flat_style = True
        self.available = True
        renderer = self.renderer
        rep = self.rep
        rep.SetEndCapLength(0.0)
        rep.SetEndCapWidth(0.0)
        for prop in (rep.GetTubeProperty(), rep.GetCapProperty(),
                     rep.GetSliderProperty(), rep.GetSelectedProperty()):
            prop.SetOpacity(0.0)
        self._flat_colors = {
            "track": theme_value(renderer, "border_color", (0.75, 0.77, 0.8)),
            "thumb": theme_value(renderer, "muted_text_color", (0.4, 0.42, 0.45)),
            "active": theme_value(renderer, "text_color", (0.1, 0.1, 0.1)),
        }
        for text_property, key in ((rep.GetTitleProperty(), "text_color"),
                                   (rep.GetLabelProperty(), "muted_text_color")):
            text_property.SetColor(*theme_value(renderer, key, (0.0, 0.0, 0.0)))
            apply_ui_font(text_property, bold=False, italic=False)
            text_property.ShadowOff()
        layer = ui_layer(renderer)
        actors = []
        for key in ("track", "thumb"):
            polydata = vtk.vtkPolyData()
            mapper = vtk.vtkPolyDataMapper2D()
            mapper.SetInputData(polydata)
            actor = vtk.vtkActor2D()
            actor.SetMapper(mapper)
            actor.GetProperty().SetColor(*self._flat_colors[key])
            actor.PickableOff()
            actor.IsUI = True
            actor._polydata = polydata
            actor.SetVisibility(bool(self.GetEnabled()))
            layer.AddActor(actor)
            actors.append(actor)
        self.overlay_track_actor, self.overlay_actor = actors
        self._flat_key = None
        # Interaction and the start of every UI render (layout and window
        # changes); unchanged geometry is skipped cheaply.
        self.ownObserver(self, "InteractionEvent",
                         lambda *_: self._update_flat(), 10.0)
        self._dragging = False

        def set_dragging(state):
            self._dragging = state
            self._update_flat(force=True)
        self.ownObserver(self, "StartInteractionEvent",
                         lambda *_: set_dragging(True), 10.0)
        self.ownObserver(self, "EndInteractionEvent",
                         lambda *_: set_dragging(False), 10.0)
        self.ownObserver(
            layer, "StartEvent", lambda *_: self._update_flat(), 10.0)
        enforce_ui_draw_order(renderer, [self])

    def SetAvailable(self, available):
        """Mute and lock the slider while keeping it visible."""
        self.available = bool(available)
        self.SetProcessEvents(self.available)
        opacity = 1.0 if self.available else 0.35
        rep = self.rep
        for text_property in (rep.GetTitleProperty(), rep.GetLabelProperty()):
            text_property.SetOpacity(opacity)
        if getattr(self, "flat_style", False):
            for actor in self._overlay_actors():
                actor.GetProperty().SetOpacity(opacity)
        else:
            for prop in (rep.GetSliderProperty(), rep.GetSelectedProperty(),
                         rep.GetTubeProperty(), rep.GetCapProperty()):
                prop.SetOpacity(opacity)
        rep.Modified()

    def _update_flat(self, force=False):
        if not getattr(self, "flat_style", False):
            return
        rep = self.rep
        window = self.GetInteractor().GetRenderWindow() if self.GetInteractor() else None
        if window is None:
            return
        width, height = (max(1, v) for v in window.GetSize())
        scale = ui_scale()
        thumb_w, thumb_h = (v * scale for v in self.FLAT_THUMB_PX)
        # Native hit targets sized to the drawn thumb (and a grabbable track).
        hit = self.FLAT_HIT_PX * scale
        if rep.GetEndCapWidth() != 0.0 or rep.GetEndCapLength() != 0.0:
            rep.SetEndCapLength(0.0)    # layouts reset these
            rep.SetEndCapWidth(0.0)
        vertical = self._orientation == "vertical"
        slider_length = thumb_h / height if vertical else thumb_w / width
        cross_span = width if vertical else height
        for getter, setter, value in (
                (rep.GetSliderLength, rep.SetSliderLength, slider_length),
                (rep.GetSliderWidth, rep.SetSliderWidth, hit / cross_span),
                (rep.GetTubeWidth, rep.SetTubeWidth, hit / cross_span)):
            if abs(getter() - value) > 1e-9:
                setter(value)
        renderer = self.GetCurrentRenderer() or ui_layer(self.renderer)
        p1 = rep.GetPoint1Coordinate().GetComputedDisplayValue(renderer)
        p2 = rep.GetPoint2Coordinate().GetComputedDisplayValue(renderer)
        value_range = rep.GetMaximumValue() - rep.GetMinimumValue()
        t = (0.0 if value_range == 0 else
             (rep.GetValue() - rep.GetMinimumValue()) / value_range)
        t = min(1.0, max(0.0, t))
        dragging = getattr(self, "_dragging", False)
        key = (tuple(round(value, 2) for value in p1),
               tuple(round(value, 2) for value in p2), round(t, 5),
               width, height, scale, dragging, self._orientation)
        if not force and key == self._flat_key:
            return
        self._flat_key = key
        track, thumb = self.overlay_track_actor, self.overlay_actor
        track_size = self.FLAT_TRACK_PX * scale
        if vertical:
            x = float(p1[0])
            y1, y2 = sorted((float(p1[1]), float(p2[1])))
            span = max(1.0, y2 - y1)
            centre = y1 + thumb_h / 2.0 + t * max(0.0, span - thumb_h)
            track._polydata.ShallowCopy(_pill_polydata(
                x - track_size / 2.0, x + track_size / 2.0,
                y1, y2, track_size / 2.0))
            thumb._polydata.ShallowCopy(_pill_polydata(
                x - thumb_w / 2.0, x + thumb_w / 2.0,
                centre - thumb_h / 2.0, centre + thumb_h / 2.0,
                thumb_w / 2.0))
        else:
            x1, x2 = sorted((float(p1[0]), float(p2[0])))
            y = float(p1[1])
            span = max(1.0, x2 - x1)
            centre = x1 + thumb_w / 2.0 + t * max(0.0, span - thumb_w)
            track._polydata.ShallowCopy(_pill_polydata(
                x1, x2, y - track_size / 2.0, y + track_size / 2.0,
                track_size / 2.0))
            thumb._polydata.ShallowCopy(_pill_polydata(
                centre - thumb_w / 2.0, centre + thumb_w / 2.0,
                y - thumb_h / 2.0, y + thumb_h / 2.0,
                thumb_h / 2.0))
        thumb.GetProperty().SetColor(
            *self._flat_colors["active" if dragging else "thumb"])
        track._polydata.Modified()
        thumb._polydata.Modified()

    def update_position(self, caller, event, position_1, position_2, orientation):
        """
        Updates the position of the slider widget.
        Args:
            position (tuple): A tuple containing the new (x, y) position for the slider.
        """
        slideBar = self.GetRepresentation()

        logger.debug("Updating slider position to %s %s (%s)",
                     position_1, position_2, orientation)

        if orientation == 0:
            bar_width = position_2[0]
            bar_height = position_2[1]
            slideBar.GetPoint1Coordinate().SetValue(position_1[0], position_1[1] + (bar_height/2))
            slideBar.GetPoint2Coordinate().SetValue(position_1[0] + bar_width, position_1[1] + (bar_height/2))
        elif orientation == 1:
            bar_width = position_2[0]
            bar_height = position_2[1]
            slideBar.GetPoint1Coordinate().SetValue(position_1[0] + (bar_width/2), position_1[1])
            slideBar.GetPoint2Coordinate().SetValue(position_1[0] + (bar_width/2), position_1[1] + bar_height)

        slideBar.Modified()
        self.Modified()

    def GetBounds(self):
        """Bounds ``(x0, x1, y0, y1)`` as fractions of the render window."""
        stored = getattr(self, "_ui_bounds", None)
        if stored is not None:
            return stored
        panel = getattr(self, "panel_bounds", None)
        if panel is not None:
            return tuple(float(value) for value in panel[:4])
        rep = self.GetRepresentation()
        window = self.interactor.GetRenderWindow()
        width, height = (max(1, value) for value in window.GetSize()[:2])
        points = []
        for coordinate in (rep.GetPoint1Coordinate(), rep.GetPoint2Coordinate()):
            x, y = coordinate.GetComputedDisplayValue(self.renderer)[:2]
            points.append((x / width, y / height))
        (ax, ay), (bx, by) = points
        length = max(abs(bx - ax), abs(by - ay))
        cross = rep.GetSliderWidth() / 0.8 * length
        if self._orientation == "horizontal":
            middle = (ay + by) / 2.0
            return (min(ax, bx), max(ax, bx), middle - cross / 2.0,
                    middle + cross / 2.0)
        middle = (ax + bx) / 2.0
        return (middle - cross / 2.0, middle + cross / 2.0,
                min(ay, by), max(ay, by))

    def SetBounds(self, x0, x1, y0, y1):
        """Lay the track along the long axis of the given bounds."""
        self._ui_bounds = (float(x0), float(x1), float(y0), float(y1))
        if self._orientation == "horizontal":
            self._set_slider_endpoints((x0, (y0 + y1) / 2.0), x1 - x0,
                                       "horizontal")
        else:
            self._set_slider_endpoints(((x0 + x1) / 2.0, y1), y1 - y0,
                                       "vertical")
        self.update_size(size=(x1 - x0, y1 - y0))
        self.Modified()

    def defaultSizePolicy(self):
        if self._orientation == "horizontal":
            return SizePolicy(SizePolicy.Expanding, SizePolicy.Fixed)
        return SizePolicy(SizePolicy.Fixed, SizePolicy.Expanding)

    def sizeHint(self):
        return (160.0, 28.0) if self._orientation == "horizontal" else (28.0, 160.0)

    def minimumSizeHint(self):
        return (48.0, 20.0) if self._orientation == "horizontal" else (20.0, 48.0)

    def update_size(self, caller=None, event=None, size=(0.1, 0.1)):
        """Fit the native slider's parts to an allotted ``(width, height)``.

        ``size`` is in window-normalized units. VTK measures the tube, end
        cap, slider and text widths as fractions of the window extent across
        the slider, and the slider/end-cap lengths as fractions of the
        extent along it, so both are derived from the cross size in pixels.
        """
        width, height = (max(0.0, float(value)) for value in size[:2])
        if width == 0.0 or height == 0.0:
            return
        window = self.interactor.GetRenderWindow()
        window_w, window_h = (max(1, value) for value in window.GetSize()[:2])
        horizontal = self._orientation == "horizontal"
        cross_span, axis_span = ((window_h, window_w) if horizontal
                                 else (window_w, window_h))
        cross_px = (height if horizontal else width) * cross_span
        rep = self.GetRepresentation()
        rep.SetTubeWidth(0.3 * cross_px / cross_span)
        rep.SetSliderWidth(0.8 * cross_px / cross_span)
        rep.SetEndCapWidth(0.7 * cross_px / cross_span)
        rep.SetTitleHeight(0.45 * cross_px / cross_span)
        rep.SetLabelHeight(0.45 * cross_px / cross_span)
        rep.SetSliderLength(0.5 * cross_px / axis_span)
        rep.SetEndCapLength(0.12 * cross_px / axis_span)
        rep.Modified()
        self.Modified()
        if getattr(self, "flat_style", False):
            self._update_flat(force=True)


class SliderWidget(_SliderAPI, vtk.vtkSliderWidget, WidgetMixin):
    __doc__ = _SliderAPI.__doc__

    def __init__(self, renderer, interactor, *args, **kwargs):
        """Initialize the instance (see the class docstring)."""
        super().__init__()
        self._init_slider(vtk.vtkSliderRepresentation2D(), renderer,
                          interactor, *args, **kwargs)

    @property
    def native(self):
        """This widget (``None`` on the composite SliderWidget)."""
        return self


def camera_view_callback(widget, event):
    """
    Callback function to handle camera view changes in a renderer.
    This function is triggered by a widget event and updates the active camera
    in the renderer based on the widget's state. It also ensures that the
    compass widget (if present) is updated with the new camera orientation.
    Args:
        widget: The widget triggering the callback. It is expected to have
                methods like `GetRepresentation` and `GetCurrentRenderer`.
        event: The event that triggered the callback.
    Behavior:
        - Retrieves the current state of the widget to determine the desired camera.
        - Sets the active camera in the renderer based on the widget's state:
            - State 0: Uses the "main camera".
            - State 1: Attempts to use the "drone camera". If it doesn't exist,
              and the renderer has camera orientations, a new drone camera is added.
              Otherwise, defaults to the "main camera".
        - Updates the compass widget (if available) to reflect the new camera's
            orientation.
        - Triggers a render update for the current renderer.
    """

    value = widget.GetRepresentation().GetState()

    ren = widget.GetCurrentRenderer()

    cameras = ren.cameras

    if value == 0:
        active_camera = cameras["main camera"]
    elif value == 1:
        active_camera = cameras.get("drone camera")
        if active_camera is None:
            if hasattr(ren, "camera_orientations"):
                logger.warning("Could not find existing drone camera, adding drone camera")

                drone_camera = _vtk_utils().add_camera(
                    initial_position=ren.camera_orientations["camera_positions"][0],
                    initial_rotation=ren.camera_orientations["camera_rotations_matrix"][
                        0
                    ],
                )
                ren.cameras["drone camera"] = drone_camera
                active_camera = drone_camera

            else:
                logger.debug("No camera orientations found in renderer.")
                logger.debug("Using main camera instead.")
                active_camera = cameras["main camera"]

    ren.SetActiveCamera(active_camera)

    compass_widget = ren.widgets.get("compass_widget")

    if compass_widget is not None:
        camera = ren.GetActiveCamera()
        _attach_camera_orientation_observer(compass_widget, camera)

    widget.GetCurrentRenderer().Render()


def graph_representation_state_callback(widget, event):
    """
    Callback function to handle changes in the graph representation state.
    This function is triggered by an event and updates the graph representation
    state based on the widget's current state. It maps the widget's state to a
    corresponding graph representation and updates the `representation` attribute
    of the graph object in the renderer, if available.
    Args:
        widget: The widget object that triggered the callback. It is expected to
                have methods `GetRepresentation()` and `GetCurrentRenderer()`.
        event: The event object associated with the callback. It is not used
               directly in this function.
    Behavior:
        - Retrieves the current state of the widget's representation.
        - Maps the state to one of the predefined graph representations:
          'voxel', 'unweighted', or 'weighted'.
        - Checks if the renderer associated with the widget has a `graph` object.
        - If the `graph` object has a `representation` attribute, updates it
          with the mapped representation and prints a confirmation message.
        - If the `representation` attribute or `graph` object is not found,
          prints an appropriate message.
    Returns:
        None
    """

    value = widget.GetRepresentation().GetState()

    renderer = widget.GetCurrentRenderer()

    representations = {0: "voxel", 1: "unweighted", 2: "weighted"}

    if hasattr(renderer, "graph"):
        graph = renderer.graph
        if hasattr(graph, "representation"):
            graph.representation = representations[value]
            logger.debug("%s %s", "Graph representation changed to:", graph.representation)
        else:
            logger.warning("representation not found in graph object.")
    else:
        logger.warning("Graph not found in renderer.")


def dummy_callback(widget, event):
    """
    Dummy Callback function to handle events triggered by widgets.

    This function is a placeholder and does not perform any specific action.
    It is intended to be used as a default callback for widgets that do not
    require a specific action to be performed when an event occurs.

    This function processes events for two types of widget representations:
    vtkTexturedButtonRepresentation2D and vtkSliderRepresentation2D. It retrieves
    the state or value of the widget and prints relevant information to the console.
    Args:
        widget: The widget object that triggered the event. It is expected to have
                a `GetRepresentation` method to retrieve its representation.
        event: The event object associated with the widget interaction.
    Behavior:
        - If the widget representation is of type vtkTexturedButtonRepresentation2D:
            - Retrieves the current state of the button.
            - Prints the button's name and its new state.
        - If the widget representation is of type vtkSliderRepresentation2D:
            - Retrieves the current value of the slider.
            - Prints the slider's name and its new value.
    Note:
        This function assumes that the widget's representation has methods like
        `GetState`, `GetValue`, and `GetObjectName`. It also assumes that the
        `vtk` module is imported and available in the scope where this function
        is used.
    """

    rep = widget.GetRepresentation()

    if isinstance(rep, vtk.vtkTexturedButtonRepresentation2D):
        value = widget.GetRepresentation().GetState()

        logger.debug("%s %s", "Button name:", widget.GetRepresentation().GetObjectName())
        logger.debug("%s %s", "Button state changed to:", value)

    elif isinstance(rep, vtk.vtkSliderRepresentation2D):
        value = widget.GetRepresentation().GetValue()
        logger.debug("%s %s", "Slider name:", widget.GetRepresentation().GetObjectName())
        logger.debug("%s %s", "Slider value changed to:", value)


class VectorPanelBackground(WidgetMixin):

    EDGE_NONE = 0
    EDGE_LEFT = 1
    EDGE_RIGHT = 2
    EDGE_BOTTOM = 4
    EDGE_TOP = 8

    def __init__(
        self,
        renderer,
        interactor,
        bounds=(0.2, 0.5, 0.2, 0.5),
        panel_color=(0.95, 0.95, 0.95),
        border_color=None,
        highlight_color=None,
        opacity=1,
        border_width=None,
        corner_radius=PANEL_CORNER_RADIUS,
        callback=None,
        movable=True,
        resizable=True,
        draggable=None,
        draggable_edges=None,
        minimum_width_pixels=50,
        minimum_height_pixels=50,
        visible=True,
        name="panel",
        parent=None,
        keep_aspect_ratio=False,
        ui_z_order=10,
        decorations_only=False,
    ):

        """Initialize the instance."""
        self.renderer = renderer
        self.interactor = interactor
        self.initWidget(name, parent=parent)
        self.highlightedChanged = Signal(self)

        self.normalized_bounds = list(bounds)
        self.panel_size = (bounds[1] - bounds[0], bounds[3] - bounds[2])

        self.current_bounds = (0, 0, 0, 0)

        self._panel_theme_role = theme_role_for_color(
            renderer, panel_color, 'panel_background_color', 'pane_color',
            'title_color', 'button_color', 'well_color')
        self.panel_color = panel_color
        # Thin themed hairline instead of the former 3 px black outline.
        themed = getattr(renderer, "theme", None) is not None
        self.border_color = (border_color if border_color is not None else
                             theme_value(renderer, "border_color", (0.0, 0.0, 0.0)))
        self.highlight_color = (
            highlight_color if highlight_color is not None else
            theme_value(renderer, "accent_faint", (0.8, 0.8, 1.0)))
        self._border_theme_role = theme_role_for_color(
            renderer, self.border_color, 'border_color')
        self._highlight_theme_role = theme_role_for_color(
            renderer, self.highlight_color, 'accent_faint', 'accent_soft')
        if border_width is None:
            border_width = 2 if themed else 3
        # Optional header band (normalized height from the top edge) and
        # recessed "wells" (normalized x0, x1, y0, y1) drawn inside the panel.
        self.header_height = 0.0
        self.header_color = theme_value(renderer, "title_color", None)
        self.wells = []
        self.well_color = theme_value(renderer, "well_color", None)
        # Panel-coloured strips (normalized y0, y1) painted by a decoration
        # layer above scrolled rows: the gaps around a list well.
        self.mask_strips = []
        # Optional browser-style tab: dict(x0, x1, y0, y1 normalized,
        # radius_px, color, content_side). Used by DockPane tab bars.
        self.tab_shape = None
        # Paint only the header band/wells (a layer above other widgets).
        self.decorations_only = bool(decorations_only)
        # Collapsed panels paint as one rounded bar in the header colour.
        self.collapsed_header = False
        self.fill_override = None
        self._decor_key = None
        self._decor_pds = []

        self.opacity = opacity
        self.border_width = border_width
        self.corner_radius = corner_radius

        self.callback = callback

        self.movable = bool(movable if draggable is None else draggable)
        self.draggable = self.movable
        all_edges = (self.EDGE_LEFT | self.EDGE_RIGHT |
                     self.EDGE_BOTTOM | self.EDGE_TOP)
        if draggable_edges is None:
            draggable_edges = all_edges if resizable else self.EDGE_NONE
        self.draggable_edges = int(draggable_edges)
        self.resizable = bool(resizable and self.draggable_edges)
        self.minimum_width_pixels = max(1, int(minimum_width_pixels))
        self.minimum_height_pixels = max(1, int(minimum_height_pixels))

        self.visible = visible

        self.parent = parent

        self.name = name
        self.ui_z_order = int(ui_z_order)

        self.highlighted = False


        self.keep_aspect_ratio = keep_aspect_ratio
        self.dragging = False
        self.resizing = False

        self.active_edge = self.EDGE_NONE

        self.last_mouse = None


        self._base_fill_pd = None
        self._base_border_pd = None

        self.fill_pd = None
        self.border_pd = None
        self._geometry_key = None
        self._geometry_build_count = 0

        self.actor = vtk.vtkContextActor()
        self.actor.IsUI = True
        self.actor.PickableOff()
        self.scene = self.actor.GetScene()

        self.actor.SetVisibility(bool(self.visible))
        register_ui_drawable(renderer, self, self.ui_z_order, name)
        ui_layer(renderer).AddActor(self.actor)

        self.painter = self._make_painter()

        self.scene.AddItem(self.painter)

        self._update_pixel_bounds()

        # ------------------------------------------------------------
        # Events
        # ------------------------------------------------------------


        if self.movable or self.resizable:
            self.ownObserver(
                interactor,
                "MouseMoveEvent",
                self._on_mouse_move,
                0.1,
            )

            self.ownObserver(
                interactor,
                "LeftButtonPressEvent",
                self._on_left_press,
                0.1,
            )

            self.ownObserver(
                interactor,
                "LeftButtonReleaseEvent",
                self._on_left_release,
                1.0,
            )

            self.ownObserver(
                interactor,
                "MiddleButtonPressEvent",
                self._on_middle_press,
                0.1,
            )

            # interactor.AddObserver(
            #     "MiddleButtonReleaseEvent",
            #     self._on_middle_release,
            #     0.1,
            # )


            # interactor.AddObserver(
            #     "EndInteractionEvent",
            #     self._force_stop_interaction,
            #     0.1,
            # )

        self.ownObserver(
            interactor,
            "LeaveEvent",
            self._force_stop_interaction,
            0.1,
        )

        # VTK >= 9.5 deprecates WindowResizeEvent on the interactor (it warns
        # and stops after 9.6): observe it on the render window, and
        # ConfigureEvent on the interactor for Qt-embedded resizes.
        self.ownObserver(
            interactor.GetRenderWindow(),
            "WindowResizeEvent",
            self._update_pixel_bounds,
            0.1,
        )
        self.ownObserver(
            interactor,
            "ConfigureEvent",
            self._update_pixel_bounds,
            0.1,
        )


        if not hasattr(renderer, "widgets"):
            renderer.widgets = {}

        renderer.widgets[name] = self

    # ============================================================
    # Painter
    # ============================================================

    def scale_polydata(self, x, y, width, height):

        """Execute the scale polydata operation."""
        transform = vtk.vtkTransform()
        transform.Translate(x, y, 0)
        transform.Scale(width, height, 1.0)

        transform_filter = vtk.vtkTransformPolyDataFilter()
        transform_filter.SetInputData(self._base_fill_pd)
        transform_filter.SetTransform(transform)
        transform_filter.Update()

        # self.fill_pd = transform_filter.GetOutput()

        self.fill_pd = vtk.vtkPolyData()
        self.fill_pd.DeepCopy(transform_filter.GetOutput())

        transform_filter.SetInputData(self._base_border_pd)
        transform_filter.Update()

        self.border_pd = transform_filter.GetOutput()

        self.current_bounds = (x, x + width, y, y + height)



    def set_collapsed_header(self, collapsed):
        """Paint as a single header-coloured bar while the panel is collapsed."""
        collapsed = bool(collapsed) and self.header_color is not None
        self.collapsed_header = collapsed
        self.fill_override = tuple(self.header_color) if collapsed else None
        self.Modified()

    def _decorations(self, x0, y0, width, height):
        """Cached header-band, divider and well polydata for this frame."""
        window_width, window_height = self.interactor.GetRenderWindow().GetSize()
        radius = float(self.corner_radius)
        if radius <= 1.0:
            radius *= min(max(1, window_width), max(1, window_height))
        if self.collapsed_header:
            return []      # the whole (collapsed) panel is already the bar
        band = (round(self.header_height * window_height)
                if self.header_height and self.header_color is not None else 0)
        wells = tuple(
            (round(wx0 * window_width), round(wx1 * window_width),
             round(wy0 * window_height), round(wy1 * window_height))
            for wx0, wx1, wy0, wy1 in (self.wells if self.well_color is not None else ()))
        strips = tuple((round(sy0 * window_height), round(sy1 * window_height))
                       for sy0, sy1 in self.mask_strips)
        tab = self.tab_shape
        tab_key = None
        if tab is not None:
            tab_key = (round(tab["x0"] * window_width), round(tab["x1"] * window_width),
                       round(tab["y0"] * window_height), round(tab["y1"] * window_height),
                       round(tab["radius_px"], 2), tuple(tab["color"]), tab["content_side"])
        key = (x0, y0, width, height, round(radius, 3), band, wells, strips, tab_key,
               tuple(self.header_color or ()), tuple(self.well_color or ()),
               tuple(self.border_color), float(self.opacity))
        if key == self._decor_key:
            return self._decor_pds
        pds = []
        if tab_key is not None:
            tx0, tx1, ty0, ty1, tab_radius, tab_color, tab_side = tab_key
            pds.append(tab_shape_polydata(
                tx0, tx1, ty0, ty1, tab_radius, _rgba255(tab_color), tab_side))
        inset = float(self.border_width)       # keep the border visible
        for sy0, sy1 in strips:
            bottom_edge = sy0 <= y0 + 1
            r = max(0.0, radius - inset) if bottom_edge else 0.0
            pds.append(rounded_rect_polydata(
                x0 + inset, max(sy0, y0 + inset), width - 2 * inset,
                max(0.0, sy1 - max(sy0, y0 + inset)), (r, r, 0, 0),
                _rgba255(self.panel_color, self.opacity)))
        if band > 0:
            band = min(band, height)
            top = y0 + height
            pds.append(rounded_rect_polydata(
                x0, top - band, width, band, (0, 0, radius, radius),
                _rgba255(self.header_color, self.opacity)))
            # Hairline divider under the band.
            pds.append(rounded_rect_polydata(
                x0, top - band - 1, width, 1.5, (0, 0, 0, 0),
                _rgba255(self.border_color, self.opacity)))
        well_radius = max(3.0, radius * 0.6)
        for wx0, wx1, wy0, wy1 in wells:
            pds.append(rounded_rect_polydata(
                wx0, wy0, wx1 - wx0, wy1 - wy0, (well_radius,) * 4,
                _rgba255(self.well_color, self.opacity)))
        self._decor_key, self._decor_pds = key, pds
        return pds

    def initialise_polydata(
        self,
        x,
        y,
        width,
        height,
        corner_radius=0.03,
        resolution=6,
    ):

        # if self._base_fill_pd is not None and self._base_border_pd is not None:

        #     # check if the size has changed significantly, if not, reuse existing polydata

        #     if (x, x + width, y, y + height) == self.current_bounds:
        #         # print("Bounds unchanged, reusing existing polydata for panel", self.name)
        #         return self.fill_pd, self.border_pd

        #     else:

        #         self.scale_polydata(x, y, width, height)

        #         return self.fill_pd, self.border_pd


        """Build geometry only when panel bounds or visual style changed."""

        # corners = [
        #     (x + corner_radius, y + corner_radius, np.pi, 1.5 * np.pi),
        #     (x + width - corner_radius, y + corner_radius, 1.5 * np.pi, 2 * np.pi),
        #     (x + width - corner_radius, y + height - corner_radius, 0, 0.5 * np.pi),
        #     (x + corner_radius, y + height - corner_radius, 0.5 * np.pi, np.pi),
        # ]

        # Geometry is drawn in display pixels. Building a unit rounded
        # rectangle and scaling it independently in X and Y turns circular
        # corners into ellipses, especially for a collapsed title strip.
        # Treat values <= 1 as a viewport-relative radius, convert once to
        # pixels, and clamp only when the panel is too small to contain it.
        window_width, window_height = self.interactor.GetRenderWindow().GetSize()
        radius = float(corner_radius)


        if radius <= 1.0:
            radius *= min(max(1, window_width), max(1, window_height))
        radius = min(max(0.0, radius), max(0.0, width / 2.0),
                     max(0.0, height / 2.0))

        fill_color = (self.highlight_color if self.highlighted
                      else (self.fill_override or self.panel_color))
        geometry_key = (
            int(x), int(y), int(width), int(height), round(radius, 6),
            int(resolution), tuple(fill_color), tuple(self.border_color),
            float(self.opacity), bool(self.highlighted))
        if (geometry_key == self._geometry_key and
                self.fill_pd is not None and self.border_pd is not None):
            return self.fill_pd, self.border_pd

        self._geometry_key = geometry_key
        self._geometry_build_count += 1
        points = vtk.vtkPoints()
        polygon = vtk.vtkPolygon()
        outline = vtk.vtkPolyLine()

        corners = [
            (x + radius, y + radius, np.pi, 1.5 * np.pi),
            (x + width - radius, y + radius, 1.5 * np.pi, 2 * np.pi),
            (x + width - radius, y + height - radius, 0, .5 * np.pi),
            (x + radius, y + height - radius, .5 * np.pi, np.pi),
        ]

        pid = 0

        # if radius == 0:
        #     # corners = [
        #     #     (x, y, 0, 0),
        #     #     (x + width, y, 0, 0),
        #     #     (x + width, y + height, 0, 0),
        #     #     (x, y + height, 0, 0),
        #     # ]
        #     points.InsertNextPoint(x, y, 0)
        #     points.InsertNextPoint(x + width, y, 0)
        #     points.InsertNextPoint(x + width, y + height, 0)
        #     points.InsertNextPoint(x, y + height, 0)
        #     polygon.GetPointIds().InsertNextId(0)
        #     polygon.GetPointIds().InsertNextId(1)
        #     polygon.GetPointIds().InsertNextId(2)
        #     polygon.GetPointIds().InsertNextId(3)
        #     pid = 4

        # else:

        for cx, cy, a0, a1 in corners:

            angles = np.linspace(a0, a1, resolution)

            for a in angles:

                px = cx + radius * np.cos(a)
                py = cy + radius * np.sin(a)

                points.InsertNextPoint(px, py, 0)

                polygon.GetPointIds().InsertNextId(pid)

                pid += 1

            # --------------------------------------------------------
        # CLOSE OUTLINE
        # --------------------------------------------------------

        outline.GetPointIds().SetNumberOfIds(pid + 1)

        for i in range(pid):
            outline.GetPointIds().SetId(i, i)

        outline.GetPointIds().SetId(pid, 0)

        # --------------------------------------------------------
        # Fill Polydata
        # --------------------------------------------------------

        fill_cells = vtk.vtkCellArray()
        fill_cells.InsertNextCell(polygon)

        fill_pd = vtk.vtkPolyData()

        fill_pd.SetPoints(points)
        fill_pd.SetPolys(fill_cells)

        colors = vtk.vtkUnsignedCharArray()
        colors.SetNumberOfComponents(4)

        if self.highlighted:
            c = self.highlight_color
        else:
            c = self.panel_color

        colors.InsertNextTuple4(
            int(c[0] * 255),
            int(c[1] * 255),
            int(c[2] * 255),
            int(self.opacity * 255),
        )

        fill_pd.GetCellData().SetScalars(colors)

        # --------------------------------------------------------
        # Border Polydata
        # --------------------------------------------------------

        line_cells = vtk.vtkCellArray()
        line_cells.InsertNextCell(outline)

        border_pd = vtk.vtkPolyData()

        border_pd.SetPoints(points)
        border_pd.SetLines(line_cells)

        bc = self.border_color
        border_colors = vtk.vtkUnsignedCharArray()
        border_colors.SetNumberOfComponents(4)
        border_colors.InsertNextTuple4(
            int(bc[0] * 255),
            int(bc[1] * 255),
            int(bc[2] * 255),
            int(self.opacity * 255),
        )
        border_pd.GetCellData().SetScalars(border_colors)


        self.fill_pd = fill_pd
        self.border_pd = border_pd
        self.current_bounds = (x, x + width, y, y + height)
        return self.fill_pd, self.border_pd

    def _make_painter(self):

        """Create painter."""
        panel = self

        painter = vtk.vtkPythonItem()

        class Painter:

            def Initialize(self, vtkSelf=None):

                """Execute the initialize operation."""
                return True

            @profiled_paint("VectorPanelBackground")
            def Paint(self, context2d):



                """Execute the paint operation."""
                if not panel.visible:
                    return True

                x0, x1, y0, y1 = panel.pixel_bounds

                w = x1 - x0
                h = y1 - y0

                if panel.decorations_only:
                    for decor_pd in panel._decorations(x0, y0, w, h):
                        context2d.DrawPolyData(
                            0, 0, decor_pd,
                            decor_pd.GetCellData().GetScalars(),
                            vtk.VTK_SCALAR_MODE_USE_CELL_DATA)
                    return True

                # ------------------------------------------------
                # Pen
                # ------------------------------------------------

                pen = context2d.GetPen()

                bc = panel.border_color

                pen.SetColor(
                    int(bc[0] * 255),
                    int(bc[1] * 255),
                    int(bc[2] * 255),
                    255,
                )

                pen.SetWidth(panel.border_width)

                # ------------------------------------------------
                # Brush
                # ------------------------------------------------

                brush = context2d.GetBrush()

                if panel.highlighted:
                    c = panel.highlight_color
                else:
                    c = panel.panel_color

                brush.SetColor(
                    int(c[0] * 255),
                    int(c[1] * 255),
                    int(c[2] * 255),
                    int(panel.opacity * 255),
                )

                # if panel.fill_pd is None or panel.border_pd is None:

                panel.fill_pd, panel.border_pd = panel.initialise_polydata(
                    x0,
                    y0,
                    w,
                    h,
                    corner_radius=panel.corner_radius,
                )


                context2d.DrawPolyData(
                    0,
                    0,
                    panel.fill_pd,
                    panel.fill_pd.GetCellData().GetScalars(),
                    vtk.VTK_SCALAR_MODE_USE_CELL_DATA,
                )

                for decor_pd in panel._decorations(x0, y0, w, h):
                    context2d.DrawPolyData(
                        0, 0, decor_pd,
                        decor_pd.GetCellData().GetScalars(),
                        vtk.VTK_SCALAR_MODE_USE_CELL_DATA)

                context2d.ApplyPen(pen)
                context2d.DrawPolyData(
                    0,
                    0,
                    panel.border_pd,
                    panel.border_pd.GetCellData().GetScalars(),
                    vtk.VTK_SCALAR_MODE_USE_CELL_DATA,
                )

                return True

        painter.SetPythonObject(Painter)

        return painter

    # ============================================================
    # Bounds
    # ============================================================

    def _update_pixel_bounds(self, obj=None, ev=None):

        """Update pixel bounds."""
        size = self.interactor.GetRenderWindow().GetSize()

        nx0, nx1, ny0, ny1 = self.normalized_bounds

        self.pixel_bounds = [
            int(nx0 * size[0]),
            int(nx1 * size[0]),
            int(ny0 * size[1]),
            int(ny1 * size[1]),
        ]

    def _update_normalized_bounds(self, obj=None, ev=None):

        """Update normalized bounds."""
        size = self.interactor.GetRenderWindow().GetSize()

        x0, x1, y0, y1 = self.pixel_bounds

        self.normalized_bounds = [
            x0 / size[0],
            x1 / size[0],
            y0 / size[1],
            y1 / size[1],
        ]

    # ============================================================
    # Hit Testing
    # ============================================================

    def _point_in_bounds(self, x, y):

        """Execute the point in bounds operation."""
        x0, x1, y0, y1 = self.pixel_bounds

        return x0 <= x <= x1 and y0 <= y <= y1

    def _edge_hit(self, x, y, tol=8):

        """Execute the edge hit operation."""
        x0, x1, y0, y1 = self.pixel_bounds

        edge = self.EDGE_NONE

        in_x = x0 <= x <= x1
        in_y = y0 <= y <= y1

        if abs(x - x0) < tol and in_y:
            edge |= self.EDGE_LEFT

        if abs(x - x1) < tol and in_y:
            edge |= self.EDGE_RIGHT

        if abs(y - y0) < tol and in_x:
            edge |= self.EDGE_BOTTOM

        if abs(y - y1) < tol and in_x:
            edge |= self.EDGE_TOP

        return edge & self.draggable_edges

    # ============================================================
    # Events
    # ============================================================

    def _on_left_press(self, obj, ev):


        """Handle left press."""
        if not self.visible:
            return
        if self.resizing:
            self.resizing = False
            self.active_edge = self.EDGE_NONE
            self.last_mouse = None

            return

        x, y = self.interactor.GetEventPosition()
        self._update_pixel_bounds()
        edge = self._edge_hit(x, y)

        if edge != self.EDGE_NONE and self.resizable:


            self.resizing = True
            self.active_edge = edge
            self.last_mouse = (x, y)


        return



    def _on_left_release(self, obj, ev):

        """Handle left release."""

        was_resizing = self.resizing
        self.resizing = False
        self.active_edge = self.EDGE_NONE
        self.last_mouse = None

        if was_resizing:
            self._invoke_observers("EndInteractionEvent")

        return

    def _on_middle_press(self, obj, ev):



        """Handle middle press."""
        if not self.visible:
            return
        if self.dragging:
            self.dragging = False
            self.last_mouse = None

            return

        x, y = self.interactor.GetEventPosition()

        self._update_pixel_bounds()

        if self._point_in_bounds(x, y) and self.movable:


            self.dragging = True
            self.last_mouse = (x, y)

            # obj.SetAbortFlag(1)
            return

    def _on_middle_release(self, obj, ev):

        """Handle middle release."""
        self.dragging = False
        self.active_edge = self.EDGE_NONE
        self.last_mouse = None

        return


    def _force_stop_interaction(self, obj=None, ev=None):

        """Execute the force stop interaction operation."""
        self.dragging = False
        self.resizing = False

        self.active_edge = self.EDGE_NONE

        self.last_mouse = None

    def _on_mouse_move(self, obj, ev):

        """Handle mouse move."""
        if not self.visible:
            return
        x, y = self.interactor.GetEventPosition()

        if self.last_mouse is None:
            self.last_mouse = (x, y)

        lx, ly = self.last_mouse

        dx = x - lx
        dy = y - ly

        old_x0, old_x1, old_y0, old_y1 = self.pixel_bounds

        # --------------------------------------------------------
        # Drag
        # --------------------------------------------------------

        if self.dragging:


            self.pixel_bounds = [
                old_x0 + dx,
                old_x1 + dx,
                old_y0 + dy,
                old_y1 + dy,
            ]



            self._update_normalized_bounds()

            self.Modified()
            self._invoke_observers("InteractionEvent")

            self.last_mouse = (x, y)

            if self.parent is not None:
                if hasattr(self.parent, "Modified"):
                    self.parent.Modified()
                else:
                    self.parent.update_layout()
                    # self.parent.update_positions()
            # obj.SetAbortFlag(1)

            return

        # --------------------------------------------------------
        # Resize
        # --------------------------------------------------------

        elif self.resizing:


            if self.keep_aspect_ratio:
                aspect_ratio = (old_x1 - old_x0) / (old_y1 - old_y0)


            if self.active_edge & self.EDGE_LEFT:
               new_x0 = old_x0 + dx
            else:
                new_x0 = old_x0

            if self.active_edge & self.EDGE_RIGHT:
                new_x1 = old_x1 + dx
            else:
                new_x1 = old_x1

            if self.active_edge & self.EDGE_BOTTOM:
                new_y0 = old_y0 + dy
            else:
                new_y0 = old_y0

            if self.active_edge & self.EDGE_TOP:
                new_y1 = old_y1 + dy
            else:
                new_y1 = old_y1


            if new_x1 - new_x0 < self.minimum_width_pixels:
                if ((self.active_edge & self.EDGE_LEFT) and
                        not (self.active_edge & self.EDGE_RIGHT)):
                    new_x0 = new_x1 - self.minimum_width_pixels
                else:
                    new_x1 = new_x0 + self.minimum_width_pixels
            if new_y1 - new_y0 < self.minimum_height_pixels:
                if ((self.active_edge & self.EDGE_BOTTOM) and
                        not (self.active_edge & self.EDGE_TOP)):
                    # Bottom-only scroll-box resizing treats the top as its
                    # invariant anchor. Never rebound by moving that edge.
                    new_y0 = new_y1 - self.minimum_height_pixels
                else:
                    new_y1 = new_y0 + self.minimum_height_pixels


            old_width = old_x1 - old_x0
            old_height = old_y1 - old_y0

            new_width = new_x1 - new_x0
            new_height = new_y1 - new_y0

            if self.keep_aspect_ratio:
                if new_width != old_width:
                    new_height = new_width / aspect_ratio
                elif new_height != old_height:
                    new_width = new_height * aspect_ratio



                if self.active_edge & self.EDGE_LEFT:
                    new_x0 = old_x1 - new_width

                else:
                    new_x0 = old_x0

                if self.active_edge & self.EDGE_BOTTOM:
                    new_y0 = old_y1 - new_height
                else:
                    new_y0 = old_y0


                self.pixel_bounds = [new_x0, new_x0 + new_width, new_y0, new_y0 + new_height]

            else:
                self.pixel_bounds = [new_x0, new_x1, new_y0, new_y1]

            self._update_normalized_bounds()

            self.Modified()
            self._invoke_observers("InteractionEvent")

            self.last_mouse = (x, y)


            if self.parent is not None:
                if hasattr(self.parent, "Modified"):
                    self.parent.Modified()
                else:
                    self.parent.update_layout()
                    # self.parent.update_positions()


            # obj.SetAbortFlag()

            return

        else:


            return

        # return

    # ============================================================
    # Public API
    # ============================================================

    def Modified(self):
        """Invalidate this UI item after a real state or layout change."""
        self._geometry_key = None
        if self.painter is not None:
            self.painter.Modified()
        if self.callback is not None:
            self.callback(self)

        # self.interactor.Render()

    def _applyTheme(self):
        if self._panel_theme_role is not None:
            self.panel_color = theme_value(
                self.renderer, self._panel_theme_role, self.panel_color)
        if self._border_theme_role is not None:
            self.border_color = theme_value(
                self.renderer, self._border_theme_role, self.border_color)
        if self._highlight_theme_role is not None:
            self.highlight_color = theme_value(
                self.renderer, self._highlight_theme_role,
                self.highlight_color)
        self.header_color = theme_value(
            self.renderer, 'title_color', self.header_color)
        self.well_color = theme_value(
            self.renderer, 'well_color', self.well_color)
        self._geometry_key = None
        self._decor_key = None

    def SetVisibility(self, visible):

        """Show or hide the panel; hidden panels are skipped by VTK entirely."""
        visible = bool(visible)
        if self.visible == visible:
            return
        self.visible = visible
        # Paint() already draws nothing while hidden, but leaving the
        # context actor visible still costs a Python Paint call per frame.
        self.actor.SetVisibility(visible)
        if not visible:
            self.dragging = False
            self.resizing = False
            self.last_mouse = None
        self.Modified()

    def SetEnabled(self, enabled):
        """Alias of SetVisibility for widget-style callers."""
        self.SetVisibility(bool(enabled))

    def GetEnabled(self):
        return bool(self.visible)

    def Highlight(self, state=True):

        """Execute the highlight operation."""
        if self.highlighted == bool(state):
            return
        self.highlighted = state
        self.highlightedChanged.emit(bool(state))
        self.Modified()

    def SetPosition(self, x, y):

        """Execute the set position operation."""
        w = self.normalized_bounds[1] - self.normalized_bounds[0]
        h = self.normalized_bounds[3] - self.normalized_bounds[2]

        new_bounds = [
            x,
            x + w,
            y,
            y + h,
        ]
        if np.allclose(self.normalized_bounds, new_bounds, atol=1e-12):
            return
        self.normalized_bounds = new_bounds

        self._update_pixel_bounds()

        self.Modified()

    def SetSize(self, w, h):

        """Execute the set size operation."""
        new_bounds = [self.normalized_bounds[0],
                      self.normalized_bounds[0] + w,
                      self.normalized_bounds[2],
                      self.normalized_bounds[2] + h]
        if np.allclose(self.normalized_bounds, new_bounds, atol=1e-12):
            return
        self.normalized_bounds = new_bounds

        self._update_pixel_bounds()

        self.Modified()

    def GetBounds(self):

        """Execute the get bounds operation."""
        return self.normalized_bounds

    def SetBounds(self, *bounds):
        """Execute the set bounds operation."""
        if np.allclose(self.normalized_bounds, bounds, atol=1e-12):
            return
        self.normalized_bounds = list(bounds)
        self._update_pixel_bounds()
        self.Modified()

    def AddObserver(self, event, callback):
        """Execute the add observer operation."""
        if not hasattr(self, "observers"):
            self.observers = {}
        if event not in self.observers:
            self.observers[event] = []
        self.observers[event].append(callback)

    def _invoke_observers(self, event):
        for callback in getattr(self, "observers", {}).get(event, []):
            callback(self, event)

    def GetRepresentation(self):
        """Execute the get representation operation."""
        return self

    def Delete(self):

        """Execute the delete operation."""
        self.observerRegistry().clear()
        ui_layer(self.renderer).RemoveActor(self.actor)

        del self


    def __repr__(self):

        """Return the developer-facing representation."""
        return f"VectorPanelBackground(name={self.name}, bounds={self.normalized_bounds}, visible={self.visible})"



















class ButtonWidget(vtk.vtkButtonWidget, WidgetMixin):

    """
    Adds a button widget to a VTK renderer with customizable icons and behavior.
    Parameters:
        renderer (vtk.vtkRenderer): The VTK renderer to which the button will be added.
        interactor (vtk.vtkRenderWindowInteractor): The interactor for handling user
        input.
        icon_name (str or list): The name(s) of the icon(s) to use for the button.
                                If a string, a two-state button is created using the
                                same icon.
                                If a list, a multi-state button is created with the
                                provided icons.
        callback (callable): A function to be called when the button's state changes.
        initial_state (int, optional): The initial state of the button. Defaults to 0.
        widget_bounds (tuple, optional): The normalized bounds of the button in the form
                                            (x_min, x_max, y_min, y_max). Defaults to
                                            (0.8, 0.9, 0.5, 0.6).
        name (str, optional): A custom name for the button widget. Defaults to None.
        verbose (bool, optional): If True, prints additional information during button
        creation. Defaults to False.
        show_bounds (bool, optional): If True, displays the bounds of the button.
        Defaults to False.
    Returns:
        vtk.vtkButtonWidget: The created button widget.
    Raises:
        AssertionError: If the specified icon path(s) do not exist.
    Notes:
        - The button widget uses VTK's `vtkTexturedButtonRepresentation2D` for
        rendering.
        - Icon files must be in PNG format and located in the `GUI/icons/` directory
        relative to the script.
        - The `callback` function should accept two arguments: the button widget and
        the event.
    Example:
        ```
        def on_button_click(widget, event):
            print("Button clicked!")


        button = add_button(renderer, interactor, "play", on_button_click)
        ```
    """

    @property
    def native(self):
        """This widget (``None`` on the composite ButtonWidget)."""
        return self

    def __init__(self,
                renderer,
                interactor,
                icon_name,
                callback,
                initial_state=0,
                widget_bounds=(0.8, 0.9, 0.5, 0.6),
                name=None,
                verbose=False,
                show_bounds=False):
        """Initialize the instance."""
        super().__init__()

        self.renderer = renderer
        self.interactor = interactor
        self.icon_name = icon_name
        self.callback = callback
        self.initial_state = initial_state
        self.widget_bounds = widget_bounds
        self.name = name
        self.verbose = verbose
        self.show_bounds = show_bounds
        self.initWidget(name)
        self.clicked = Signal(self)
        self.pressed = Signal(self)
        self.released = Signal(self)
        self.toggled = Signal(self)
        self._last_signal_state = int(initial_state)
        self._clicking = False
        self._state_count = (2 if isinstance(icon_name, str)
                             else len(icon_name))
        self.registerFocus(interactor, policy="StrongFocus")


        self.SetInteractor(interactor)
        self.SetRepresentation(self.create_button_representation())
        # Screen-space widgets otherwise fall back to the render window's first
        # renderer, which is incorrect in multi-viewport applications.
        self.SetCurrentRenderer(ui_layer(renderer))
        self.SetDefaultRenderer(ui_layer(renderer))
        self.GetRepresentation().SetRenderer(ui_layer(renderer))
        self.SetPriority(1)  # Set a default priority for the button widget
        if callback is not None:
            self.ownObserver(
                self, vtk.vtkCommand.StateChangedEvent, callback)
        self.ownObserver(
            self, vtk.vtkCommand.StateChangedEvent, self._emit_state_changed)
        self.ownObserver(
            self, vtk.vtkCommand.StartInteractionEvent,
            self._native_press)
        self.ownObserver(
            self, vtk.vtkCommand.EndInteractionEvent,
            self._native_release)

        self.renderer = renderer

        if not hasattr(renderer, "widgets"):
            renderer.widgets = {}
        renderer.widgets.update({self.object_name: self})

        self.On()

    def _emit_state_changed(self, *_):
        # vtkButtonWidget sends no Start/EndInteractionEvent: a mouse click
        # shows up only as this event, on release.
        if not self._clicking:
            self.setFocus(reason="mouse")
            self.pressed.emit()
            self.released.emit()
        checked = self.isChecked()
        self.clicked.emit(checked)
        if self.state() != self._last_signal_state:
            self._last_signal_state = self.state()
            self.toggled.emit(checked)

    def _native_press(self, *_):
        self.setFocus(reason="mouse")
        self.grabMouse()
        self.pressed.emit()

    def _native_release(self, *_):
        self.releaseMouse()
        self.released.emit()

    def state(self):
        return int(self.GetRepresentation().GetState())

    def setState(self, state):
        old = self.state()
        self.GetRepresentation().SetState(int(state))
        self.GetRepresentation().Modified()
        if old != self.state():
            self._last_signal_state = self.state()
            self.toggled.emit(self.isChecked())

    def isChecked(self):
        return bool(self.state())

    def setChecked(self, checked):
        self.setState(1 if checked else 0)

    def toggle(self):
        states = max(1, self._state_count)
        self.setState((self.state() + 1) % states)

    def click(self):
        self._clicking = True
        try:
            self.pressed.emit()
            self.toggle()
            self.InvokeEvent(vtk.vtkCommand.StateChangedEvent)
            self.released.emit()
        finally:
            self._clicking = False

    def saveState(self):
        state = super().saveState()
        state['state'] = self.state()
        return state

    def restoreState(self, state):
        if 'state' in state:
            self.setState(state['state'])
        return super().restoreState({
            key: state[key] for key in (
                'objectName', 'enabled', 'visible', 'toolTip', 'statusTip')
            if key in state})


    def create_button_representation(self):
        """Create button representation."""
        buttonRepresentation = vtk.vtkTexturedButtonRepresentation2D()

        if isinstance(self.icon_name, str):

            current_directory = os.path.dirname(os.path.abspath(__file__))

            icon_path = os.path.join(
                    current_directory, "icons", "png_icons", f"{self.icon_name}.png"
                )
            object_name = f"buttons/{self.icon_name}_button"

            object_name = self.name if self.name is not None else f"buttons/{self.icon_name}_button"

            assert os.path.exists(icon_path), f"Icon path ({icon_path}) does not exist"

            r1 = vtk.vtkPNGReader()
            r1.SetFileName(icon_path)
            r1.Update()

            r2 = vtk.vtkPNGReader()
            r2.SetFileName(icon_path)
            r2.Update()

            buttonRepresentation.SetNumberOfStates(2)

            buttonRepresentation.SetButtonTexture(0, r1.GetOutput())
            buttonRepresentation.SetButtonTexture(1, r2.GetOutput())

        elif isinstance(self.icon_name, list):
            current_directory = os.path.dirname(os.path.abspath(__file__))

            object_name = self.name if self.name is not None else f"buttons/{self.icon_name[0]}_button"

            buttonRepresentation.SetNumberOfStates(len(self.icon_name))

            if self.verbose:
                logger.debug(f"Adding a multistate button with {len(self.icon_name)} states")

            for i, icon_subname in enumerate(self.icon_name):
                icon_path = os.path.join(
                    current_directory, "icons", "png_icons", f"{icon_subname}.png"
                )

                assert icon_path is not None, "Icon path is None"

                # assert os.path.exists(icon_path), bcolors.FAIL + f"Icon path ({icon_path}) does not exist" + bcolors.ENDC

                if not os.path.exists(icon_path):
                    logger.warning(f"Warning: Icon path ({icon_path}) does not exist. defaulting to question mark icon.")
                    # icon_path = os.path.join(
                    #     current_directory, "icons", f"question_mark.png"
                    # )
                    icon_path = os.path.join(ICON_ROOT, "png_icons", "question-sign.png")



                reader = vtk.vtkPNGReader()
                reader.SetFileName(icon_path)
                reader.Update()

                buttonRepresentation.SetButtonTexture(i, reader.GetOutput())

        self.object_name = object_name

        if self.initial_state:
            self.initial_state = 1
        elif not self.initial_state:
            self.initial_state = 0
        if self.initial_state is None:
            self.initial_state = 0

        buttonRepresentation.SetState(self.initial_state)

        buttonRepresentation.SetObjectName(object_name)

        bds = np.zeros(6)

        window_size = self.interactor.GetRenderWindow().GetSize()

        if window_size[0] == 0 or window_size[1] == 0:
            window_size = (800, 600)
            logger.warning("Warning: Window size is zero, defaulting to (800, 600)")

        bds[0] = self.widget_bounds[0] * window_size[0]
        bds[1] = self.widget_bounds[1] * window_size[0]
        bds[2] = self.widget_bounds[2] * window_size[1]
        bds[3] = self.widget_bounds[3] * window_size[1]
        bds[4] = 0.0
        bds[5] = 0.0


        self.Bounds = bds


        buttonRepresentation.SetPlaceFactor(1)
        buttonRepresentation.PlaceWidget(bds)

        return buttonRepresentation

    def SetPosition(self, x, y):
        """
        Sets the position of the button widget.
        Args:
            x (float): The x-coordinate of the button's position in normalized
                viewport coordinates.
            y (float): The y-coordinate of the button's position in normalized
                viewport coordinates.
        """
        representation = self.GetRepresentation()
        bds = self.Bounds

        width = bds[1] - bds[0]
        height = bds[3] - bds[2]

        window_size = self.interactor.GetRenderWindow().GetSize()

        new_bds = np.zeros(6)
        new_bds[0] = x * window_size[0]
        new_bds[1] = new_bds[0] + width
        new_bds[2] = y * window_size[1]
        new_bds[3] = new_bds[2] + height
        new_bds[4] = 0.0
        new_bds[5] = 0.0


        self.Bounds = new_bds
        representation.PlaceWidget(new_bds)
        representation.Modified()
        self.Modified()

    def SetPixelPosition(self, x, y, width, height):
        """
        Sets the position of the button widget.
        Args:
            x (float): The x-coordinate of the button's position in normalized
                viewport coordinates.
            y (float): The y-coordinate of the button's position in normalized
                viewport coordinates.
        """
        representation = self.GetRepresentation()
        bds = self.Bounds

        bds[0] = x
        bds[1] = x + width
        bds[2] = y
        bds[3] = y + height
        bds[4] = 0.0
        bds[5] = 0.0

        # if self.GetRepresentation().GetVisibility():

        representation.PlaceWidget(bds)
        representation.Modified()
        self.Modified()
        # self.renderer.Render()

    def SetSize(self, width, height):
        """
        Sets the size of the button widget.
        Args:
            width (float): The width of the button in pixels.
            height (float): The height of the button in pixels.
        """
        representation = self.GetRepresentation()
        bds = self.Bounds

        bds[1] = bds[0] + width
        bds[3] = bds[2] + height


        representation.PlaceWidget(bds)
        representation.Modified()
        self.Modified()

    def GetBounds(self):
        """Bounds ``(x0, x1, y0, y1)`` as fractions of the render window."""
        width, height = self.interactor.GetRenderWindow().GetSize()[:2]
        width, height = max(1, width), max(1, height)
        bounds = self.Bounds
        return (bounds[0] / width, bounds[1] / width,
                bounds[2] / height, bounds[3] / height)

    def SetBounds(self, x0, x1, y0, y1):
        width, height = self.interactor.GetRenderWindow().GetSize()[:2]
        self.SetPixelPosition(x0 * width, y0 * height,
                              (x1 - x0) * width, (y1 - y0) * height)

    def defaultSizePolicy(self):
        return SizePolicy(SizePolicy.Fixed, SizePolicy.Fixed)

    def sizeHint(self):
        return (32.0, 32.0)

    def minimumSizeHint(self):
        return (20.0, 20.0)

    def SetVisibility(self, visible):
        """
        Sets the visibility of the button widget.
        Args:
            visible (bool): True to make the widget visible, False to hide it.
        """
        if visible:
            self.On()
            self.GetRepresentation().SetVisibility(True)
        else:
            self.Off()
            self.GetRepresentation().SetVisibility(False)


        self.Modified()


    def Delete(self):
        """
        Deletes the button widget from the renderer.
        """


        self.Off()
        self.SetInteractor(None)
        self.SetRepresentation(None)
        self.Modified()

        del self



class TextWidget(vtk.vtkTextWidget, WidgetMixin):

    """Adds a text widget to a VTK renderer.

    Parameters:
        renderer (vtkRenderer): The VTK renderer to which the text widget will be added.
        interactor (vtkRenderWindowInteractor): The interactor for handling user
            interaction with the widget.
        text (str, optional): The text to display in the widget. Defaults to
            'Hello World'.
        unique_name (str, optional): A unique name for the widget. If None, a name will
            be generated based on the text. Defaults to None.
        position (tuple, optional): The (x, y) position of the widget in normalized
            viewport coordinates. Defaults to (0.1, 0.1).
        size (tuple, optional): The (width, height) size of the widget in normalized
            viewport coordinates. Defaults to (0.2, 0.1).
        grabbable (bool, optional): Whether the widget is grabbable (interactive).
            Defaults to False.
    Returns:
        vtkTextWidget: The created text widget instance.
    """


    def __init__(
        self,
        renderer,
        interactor,
        text="Hello World",
        unique_name=None,
        position=(0.1, 0.1),
        size=(0.2, 0.1),
        fixed_text_length=None,
        grabbable=False,
        font='custom',
        # font='default',
        editable=False,
        text_color=(0,0,0),
        text_size=12,
        force_to_float=False,
        end_of_edit_callback=None,
        click_callback=None,
        clickable=False,
        claim_cell_clicks=None,
        edit_on_double_click=False,
        horizontal_alignment="left",
        prepend_text=(),
        append_text=(),
        caret_text="",
        scale_text_to_widget=True,
        fit_text_to_bounds=False,
        minimum_text_size=8,
        ui_z_order=UI_Z_SCROLL_ROWS,
        elide_to_bounds=None,
        bold=False,
        theme_role=None,
    ):


        """Initialize the instance."""
        super().__init__()


        self.renderer = renderer
        self.interactor = interactor
        self.text_color = text_color
        self._text_theme_role = (theme_role or theme_role_for_color(
            renderer, text_color, 'text_color', 'muted_text_color',
            'accent_color_rgb'))
        self.text_size = text_size
        self.editable = editable
        self.force_to_float = force_to_float
        self.end_of_edit_callback = end_of_edit_callback
        self.click_callback = click_callback
        self.clickable = bool(clickable or click_callback is not None)
        # Fixed-size fonts shrink VTK's border box to the rendered text, and
        # its edge-resize tolerance then covers most of that box, so clicks
        # rarely registered as "inside". Non-draggable text instead claims
        # presses anywhere in its assigned cell (like QLineEdit).
        self.claim_cell_clicks = (not grabbable if claim_cell_clicks is None
                                  else bool(claim_cell_clicks))
        self._cell_press_tag = None
        self.edit_on_double_click = bool(edit_on_double_click)
        self._last_click_time = 0.0
        self.horizontal_alignment = horizontal_alignment
        self.prepend_text = self._normalise_affixes(prepend_text)
        self.append_text = self._normalise_affixes(append_text)
        self.caret_text = caret_text
        self.scale_text_to_widget = bool(scale_text_to_widget)
        self.fit_text_to_bounds = bool(fit_text_to_bounds)
        # Keep one font size and shorten the *displayed* text with an
        # ellipsis when it does not fit (full text is kept for editing);
        # editable fields do by default, and show the full text on hover.
        self.elide_to_bounds = (bool(editable) if elide_to_bounds is None
                                else bool(elide_to_bounds))
        self._elide_key = None
        self._elide_value = None
        self._elided_full = None    # the full display text while shortened
        self._elide_hover = None
        self._scroll_start = 0      # first displayed character while editing
        self.maximum_text_size = int(text_size)
        self.minimum_text_size = min(
            int(minimum_text_size), self.maximum_text_size)
        self.ui_z_order = int(ui_z_order)
        self._last_text_fit_geometry = None


        if fixed_text_length is not None:
            text = self.MakeFixedLengthText(text, fixed_text_length)

        self.text = str(text)
        self.initWidget(unique_name)
        self.textChanged = Signal(self)
        self.textEdited = Signal(self)
        self.clicked = Signal(self)
        self.doubleClicked = Signal(self)
        self.editingStarted = Signal(self)
        self.editingFinished = Signal(self)
        self.returnPressed = Signal(self)
        self._read_only = not bool(editable)
        self._modified = False
        self._placeholder_text = ""
        self._validator = None
        self._max_length = 32767             # QLineEdit's default
        self._echo_mode = "normal"
        self._input_mask = None
        self._completer = None
        self._completer_menu = None
        self.registerFocus(
            interactor,
            policy="StrongFocus" if (editable or self.clickable) else "NoFocus")


        self.text_actor = vtk.vtkTextActor()
        self.text_actor.SetInput(self._compose_display_text(self.text))
        self.text_actor.GetTextProperty().SetColor(*text_color)
        apply_ui_font(self.text_actor.GetTextProperty(), bold=bold)
        if not self.scale_text_to_widget:
            self.text_actor.SetTextScaleModeToNone()
            self.text_actor.GetTextProperty().SetFontSize(int(text_size))
        self._highlighted = False
        # self.text_actor.GetTextProperty().SetFontSize(text_size)

        # Create the text representation. Used for positioning the self.text_actor
        self.text_representation = vtk.vtkTextRepresentation()
        self.text_representation.GetPositionCoordinate().SetCoordinateSystemToNormalizedViewport()
        self.text_representation.GetPosition2Coordinate().SetCoordinateSystemToNormalizedViewport()
        self.text_representation.GetPositionCoordinate().SetValue(position[0], position[1])
        self.text_representation.GetPosition2Coordinate().SetValue(size[0], size[1])
        # self.text_representation.SetPolygonColor(1, 1, 0)
        self.text_representation.GetBorderProperty().SetOpacity(0)

        self.grabbable = grabbable
        self.text_representation.SetMoving(bool(self.grabbable))
        self._locked_position = tuple(position)
        self._locked_size = tuple(size)
        # set the text to be left aligned

        self.font_dict = {'default': 0,
                          'arial': 1,
                          'courier': 2,
                          'times': 3,
                          'custom': 4}


        self.SetRepresentation(self.text_representation)
        self.text_actor.GetTextProperty().SetJustificationToLeft()
        if font is None or font.lower() == 'custom':
            apply_ui_font(self.text_actor.GetTextProperty())
        else:
            self.text_actor.GetTextProperty().SetFontFamily(self.font_dict.get(font.lower(), 0))


        self.text_actor.GetTextProperty().SetColor(*self.text_color)
        self.text_actor.GetTextProperty().Modified()
        self.text_actor.Modified()

        aspect_ratio = size[0] / size[1]
        self.aspect_ratio = aspect_ratio

        self.panel_w = size[0]
        self.panel_h = size[1]

        self.SetInteractor(interactor)
        # Explicit renderer: On() would otherwise pick the poked (scene) one.
        self.SetDefaultRenderer(ui_layer(renderer))
        self.SetCurrentRenderer(ui_layer(renderer))
        self.SetTextActor(self.text_actor)
        self._enforce_text_scale_mode()
        self._apply_text_alignment()

        if self.grabbable or self.editable or self.clickable:
            self.SetSelectable(True)
            self.SetProcessEvents(True)
        else:
            self.SetSelectable(False)
            self.SetProcessEvents(False)
        self.On()
        register_ui_drawable(
            renderer, self, self.ui_z_order,
            unique_name or f'{text}_text_widget')

        if unique_name is None:
            unique_name = f"{text}_text_widget"
            self.SetObjectName(unique_name)

        if not hasattr(renderer, "widgets"):
            renderer.widgets = {}
        renderer.widgets.update({unique_name: self})




        self.text_actor.SetInput(self._compose_display_text(self.text))

        self.editing = False
        self.orig_text = self.text
        self.caret_index = len(self.text)

        if self.editable or self.clickable:
            self.picker = vtk.vtkPropPicker()

              # Bind events
            self.ProcessEventsOn()
            self.SelectableOn()
            self.EnabledOn()
            # self.On()
            # self.AddObserver(vtk.vtkCommand.LeftButtonPressEvent, self.on_left_button_press)
            # state_str = f"TextWidget:{unique_name}"
            self.ownObserver(
                self, vtk.vtkCommand.WidgetActivateEvent,
                self.on_left_button_press)
            if self.claim_cell_clicks:
                # Above vtkAbstractWidget's default priority (0.5), so the
                # border widget never starts an edge drag for these clicks.
                self._cell_press_tag = self.ownObserver(
                    self.interactor, "LeftButtonPressEvent",
                    self._on_cell_press, 0.6)
            if not self.grabbable:
                self.ownObserver(
                    self,
                    vtk.vtkCommand.InteractionEvent,
                    self._restore_locked_geometry, 100.0)
                self.ownObserver(
                    self,
                    vtk.vtkCommand.EndInteractionEvent,
                    self._restore_locked_geometry, 100.0)
                self.text_representation.MovingOff()
            # self.interactor.AddObserver("LeftButtonPressEvent", self.on_left_button_press)
            if self.editable:
                self._key_press_observer_id = self.ownObserver(
                    self.interactor, "KeyPressEvent", self.on_key_press, 100.0)
                # Text arrives as characters (CharEvent): what the platform
                # composed (shift, Alt/Option, dead keys), consumed here so
                # no scene hotkey sees it.
                self._char_observer_id = self.ownObserver(
                    self.interactor, "CharEvent", self.on_char, 100.0)
            # self.interactor.AddObserver("RenderEvent", self.on_render_event)
            self._update_edit_display()

        if self.fit_text_to_bounds:
            self.RefitTextToBounds()
        if self.elide_to_bounds:
            self._update_edit_display()

    # def onTextClick(self, obj, event=None, string=""):



    def MakeFixedLengthText(self, text, length):

        """
        Creates a fixed-length text string by padding or truncating the input text.
        Args:
            text (str): The input text string.
            length (int): The desired fixed length of the output text string.
        Returns:
            str: The fixed-length text string.
        """
        if len(text) < length:
            # Pad the text with spaces if it's shorter than the desired length
            padded_text = text.ljust(length)
            return padded_text
        else:
            # Truncate the text if it's longer than the desired length
            truncated_text = text[:length]
            return truncated_text

    @staticmethod
    def _normalise_affixes(value):
        """Return prefix/suffix input as an immutable tuple of strings."""
        if value is None:
            return ()
        if isinstance(value, str):
            return (value,)
        return tuple(str(part) for part in value)

    ECHO_MODES = ("normal", "password", "noEcho", "passwordEchoOnEdit")
    PASSWORD_CHAR = "\u2022"

    def _echoed(self, text):
        """``text`` as the echo mode shows it (same length unless noEcho)."""
        mode = getattr(self, "_echo_mode", "normal")
        if mode == "normal" or (mode == "passwordEchoOnEdit"
                                and getattr(self, "editing", False)):
            return text
        if mode == "noEcho":
            return ""
        return self.PASSWORD_CHAR * len(text)

    def _compose_display_text(self, editable_text, caret_index=None):
        """Compose affixes and an optional inline caret for the visible actor."""
        editable_text = self._echoed(str(editable_text))
        if caret_index is not None:
            caret_index = min(int(caret_index), len(editable_text))
        if caret_index is None:
            editable_section = editable_text
        else:
            index = max(0, min(int(caret_index), len(editable_text)))
            values_before_caret = editable_text[:index]
            values_after_caret = editable_text[index:]
            editable_section = (
                values_before_caret + self.caret_text + values_after_caret)
        return ("".join(self.prepend_text) + editable_section +
                "".join(self.append_text))

    def GetEditableText(self):
        """Return only the joined values, excluding caret and display affixes."""
        return self.text

    def textValue(self):
        """Return editable text without affixes (``text`` is legacy state).

        With an input mask, blanks are left out (as ``QLineEdit.text()``);
        ``self.text`` keeps one character per mask position.
        """
        if self._input_mask is not None:
            return self._input_mask.value(self.text)
        return self.text

    def setText(self, text):
        text = self._fit_text(str(text))
        if text == self.text:
            return
        self.text = text
        self.orig_text = text
        self.caret_index = min(self.caret_index, len(text))
        self._modified = False
        self._update_edit_display()
        self.textChanged.emit(text)

    def clear(self):
        self.setText("")

    def click(self):
        self.setFocus(reason="keyboard")
        if self.click_callback is not None:
            self.click_callback(self)
        self.clicked.emit()

    def isReadOnly(self):
        return self._read_only

    def setReadOnly(self, read_only):
        if read_only and self.editing:
            self.finish_editing(commit=True)
        self._read_only = bool(read_only)
        self.editable = not self._read_only
        interactive = self.editable or self.clickable or self.grabbable
        self.SetProcessEvents(interactive)
        self.SetSelectable(interactive)
        self.setFocusPolicy("StrongFocus" if interactive else "NoFocus")

    def isModified(self):
        return self._modified

    def setModified(self, modified):
        self._modified = bool(modified)

    def placeholderText(self):
        return self._placeholder_text

    def setPlaceholderText(self, text):
        self._placeholder_text = str(text)
        self._update_edit_display()

    def validator(self):
        return self._validator

    def setValidator(self, validator):
        if validator is not None and not callable(validator):
            raise TypeError("validator must be callable or None")
        self._validator = validator

    # -- QLineEdit options (W6) ------------------------------------------------
    def _fit_text(self, text):
        if self._input_mask is not None:
            return self._input_mask.apply(text)
        return text[:self._max_length]

    def maxLength(self):
        return self._max_length

    def setMaxLength(self, length):
        """Longest text accepted (typing, pasting and setText)."""
        self._max_length = max(0, int(length))
        if self._input_mask is None and len(self.text) > self._max_length:
            self.setText(self.text[:self._max_length])
        buffer = getattr(self, "_text_buffer", None)
        if buffer is not None:
            buffer.max_length = self._max_length

    def echoMode(self):
        return self._echo_mode

    def setEchoMode(self, mode):
        """``"normal"``, ``"password"``, ``"noEcho"`` or
        ``"passwordEchoOnEdit"`` (shown while editing, masked after)."""
        if mode not in self.ECHO_MODES:
            raise ValueError(f"echo mode must be one of {self.ECHO_MODES}")
        self._echo_mode = mode
        self._update_edit_display()

    def inputMask(self):
        return "" if self._input_mask is None else self._input_mask.mask

    def setInputMask(self, mask):
        """Restrict input to a Qt-style mask (see ``text_buffer.InputMask``);
        ``""`` or ``None`` removes it."""
        from .text_buffer import InputMask

        if not mask:
            value = self.textValue()
            self._input_mask = None
            self.text = value[:self._max_length]
        else:
            value = self.textValue()
            self._input_mask = InputMask(mask)
            self.text = self._input_mask.apply(value)
        self.caret_index = min(self.caret_index, len(self.text))
        self._text_buffer = None
        self._update_edit_display()

    def hasAcceptableInput(self):
        """False while a mask's required positions are blank, or the
        validator rejects the text."""
        if self._input_mask is not None and \
                not self._input_mask.isAcceptable(self.text):
            return False
        if self._validator is not None:
            result = self._validator(self.text)
            return bool(result[0] if isinstance(result, tuple) else result)
        return True

    def insertText(self, text):
        """Insert ``text`` at the caret, replacing any selection
        (``QLineEdit.insert``). Hosts use this to deliver text composed by
        an input method; max length and the input mask apply."""
        buffer = self._edit_buffer()
        changed = buffer.insert(str(text), typing=False)
        self._apply_buffer(changed)
        if changed and not self.editing:
            self.textChanged.emit(self.text)
        return changed

    # -- completer ---------------------------------------------------------------
    def completer(self):
        return self._completer

    def setCompleter(self, completer):
        """Suggest completions while editing: a :class:`Completer`, a list
        of strings or an item model (``None`` removes it)."""
        from .completer import Completer

        self._hide_completions()
        if completer is not None and not isinstance(completer, Completer):
            completer = Completer(completer)
        self._completer = completer

    def isCompletionVisible(self):
        menu = self._completer_menu
        return menu is not None and menu.isOpen()

    def _update_completions(self):
        completer = self._completer
        if completer is None or not self.editing:
            return
        prefix = self.textValue()
        matches = completer.completions(prefix)[:completer.max_visible]
        if not matches or (len(matches) == 1 and
                           matches[0].casefold() == prefix.casefold()):
            self._hide_completions()
            return
        from .standard import Menu

        menu = self._completer_menu
        if menu is None:
            menu = self._completer_menu = Menu(self.renderer, self.interactor)
            menu.setObjectName(f"{self.objectName()}/completions")
            # A click elsewhere closes the list and still lands there.
            menu.setConsumesOutsideClick(False)
            menu.triggered.connect(self._completion_chosen)
        menu.clear()
        for text in matches:
            menu.addAction(text)
        width, height = menu.sizeHint()
        field_width = self.geometry("px")[2]
        menu.popup(anchor=self, placement="below",
                   size=(max(width, field_width), height), take_focus=False)

    def _hide_completions(self):
        menu = self._completer_menu
        if menu is not None and menu.isOpen():
            menu.dismiss()

    def _completion_chosen(self, action):
        text = action.text()
        buffer = self._edit_buffer()
        buffer.selectAll()
        changed = buffer.insert(text, typing=False)
        self._hide_completions()
        self._apply_buffer(changed, complete=False)
        if self._completer is not None:
            self._completer.activated.emit(text)

    def focusKeyIntercept(self, key):
        """FocusManager hook: Escape/Enter/Tab go to an open completion list."""
        if key in ("escape", "esc", "return", "enter", "kp_enter", "tab"):
            return self._completion_key("escape" if key == "esc" else key)
        return False

    def _completion_key(self, lower):
        """Up/Down/Return/Escape while the list is open; True if used."""
        menu = self._completer_menu
        if menu is None or not menu.isOpen():
            return False
        if lower == "down":
            menu._move(1)
            return True
        if lower == "up":
            menu._move(-1)
            return True
        if lower in ("return", "kp_enter", "enter", "tab"):
            item = menu.activeItem()
            if item is None:
                self._hide_completions()
                return lower == "tab"
            menu._activate_item(item)
            return True
        if lower == "escape":
            self._hide_completions()
            return True
        return False

    def saveState(self):
        state = super().saveState()
        state.update({
            'text': self.textValue(),
            'readOnly': self.isReadOnly(),
            'placeholderText': self.placeholderText(),
        })
        return state

    def restoreState(self, state):
        if 'text' in state:
            self.setText(state['text'])
        if 'readOnly' in state:
            self.setReadOnly(state['readOnly'])
        if 'placeholderText' in state:
            self.setPlaceholderText(state['placeholderText'])
        return super().restoreState({
            key: state[key] for key in (
                'objectName', 'enabled', 'visible', 'geometry',
                'toolTip', 'statusTip') if key in state})

    def SetPrependText(self, text):
        """Set immutable display text before the editable value."""
        self.prepend_text = self._normalise_affixes(text)
        self._update_edit_display()

    def SetAppendText(self, text):
        """Set immutable display text after the editable value."""
        self.append_text = self._normalise_affixes(text)
        self._update_edit_display()

    def _apply_text_alignment(self):
        """Keep text alignment stable when VTK rebuilds its representation."""
        text_property = self.text_actor.GetTextProperty()
        if self.horizontal_alignment == "center":
            text_property.SetJustificationToCentered()
        elif self.horizontal_alignment == "right":
            text_property.SetJustificationToRight()
        else:
            text_property.SetJustificationToLeft()
        text_property.SetVerticalJustificationToCentered()
        text_property.Modified()

    def _applyTheme(self):
        if self._text_theme_role is not None:
            self.text_color = theme_value(
                self.renderer, self._text_theme_role, self.text_color)
            self.text_actor.GetTextProperty().SetColor(*self.text_color)
        apply_ui_font(
            self.text_actor.GetTextProperty(), bold=self._highlighted)
        self._apply_text_alignment()
        self.text_actor.Modified()

    def _enforce_text_scale_mode(self):
        """Undo vtkTextRepresentation's automatic PROP scaling when fixed."""
        if not self.scale_text_to_widget:
            self.text_actor.SetTextScaleModeToNone()
            self.text_actor.GetTextProperty().SetFontSize(int(self.text_size))

    def RefitTextToBounds(self, force=False):
        """Fit a fixed-scale font after an intentional layout resize.

        This is deliberately explicit: moving a widget (including scrolling a
        row) must not cause VTK to recalculate its font metrics.
        """
        if not self.fit_text_to_bounds or self.scale_text_to_widget:
            return False

        window_width, window_height = (
            self.interactor.GetRenderWindow().GetSize())
        available_width = max(1, round(
            self._locked_size[0] * max(1, window_width) * 0.94))
        available_height = max(1, round(
            self._locked_size[1] * max(1, window_height) * 0.90))
        display_text = self.text_actor.GetInput() or " "
        fit_geometry = (
            available_width, available_height, display_text,
            self.minimum_text_size, self.maximum_text_size)
        if not force and fit_geometry == self._last_text_fit_geometry:
            return False
        self._last_text_fit_geometry = fit_geometry
        text_property = self.text_actor.GetTextProperty()
        text_renderer = vtk.vtkTextRenderer.GetInstance()
        dpi = max(1, self.interactor.GetRenderWindow().GetDPI())

        best_size = self.minimum_text_size
        low = self.minimum_text_size
        high = self.maximum_text_size
        while low <= high:
            candidate = (low + high) // 2
            text_property.SetFontSize(candidate)
            bounding_box = [0, 0, 0, 0]
            rendered = text_renderer.GetBoundingBox(
                text_property, display_text, bounding_box, dpi)
            text_width = bounding_box[1] - bounding_box[0] + 1
            text_height = bounding_box[3] - bounding_box[2] + 1
            if (rendered and text_width <= available_width and
                    text_height <= available_height):
                best_size = candidate
                low = candidate + 1
            else:
                high = candidate - 1

        changed = self.text_size != best_size
        self.text_size = best_size
        self._enforce_text_scale_mode()
        if changed:
            text_property.Modified()
            self.text_actor.Modified()
        return changed

    def SetVisibility(self, visible):
        """
        Sets the visibility of the text widget.
        Args:
            visible (bool): True to make the widget visible, False to hide it.
        """
        if visible:
            self.On()
            self._enforce_text_scale_mode()
            if self.editable or self.clickable:
                self.ProcessEventsOn()
                self.SelectableOn()
                self.EnabledOn()
                if not self.grabbable:
                    self.text_representation.MovingOff()

        else:
            if getattr(self, "editing", False):
                self.finish_editing(commit=True)
            for name in ("_caret_line", "_selection_highlight"):
                actor = getattr(self, name, None)
                if actor is not None:
                    actor.SetVisibility(False)
            self.Off()
            if self.editable or self.clickable:
                self.ProcessEventsOff()
                self.SelectableOff()
                self.EnabledOff()

    def close(self):
        if getattr(self, "editing", False):
            self.finish_editing(commit=False)
        layer = ui_layer(self.renderer)
        for name in ("_caret_line", "_selection_highlight"):
            actor = getattr(self, name, None)
            if actor is not None:
                remove_actor_2d(layer, actor)
                setattr(self, name, None)
        return super().close()

    def SetPosition(self, x, y):
        """
        Sets the position of the text widget.
        Args:
            x (float): The x-coordinate of the widget's position in normalized
                viewport coordinates.
            y (float): The y-coordinate of the widget's position in normalized
                viewport coordinates.
        """
        representation = self.GetRepresentation()
        if np.allclose(self._locked_position, (x, y), atol=1e-12):
            return
        self._locked_position = (x, y)
        representation.GetPositionCoordinate().SetValue(x, y)
        # Alignment and font metrics are invariant under translation. Avoid
        # touching the text property here; doing so causes VTK to refit
        # representation-scaled fonts while scroll rows move.
        representation.Modified()
        self._enforce_text_scale_mode()
        self.Modified()

    def GetPosition(self):
        """
        Gets the position of the text widget.
        Returns:
            tuple: A tuple containing the (x, y) position of the widget in normalized
                viewport coordinates.
        """
        representation = self.GetRepresentation()
        pos = representation.GetPositionCoordinate().GetValue()
        return (pos[0], pos[1])

    def GetBounds(self):
        """Bounds ``(x0, x1, y0, y1)`` of the box assigned to the text.

        Reported from the requested geometry: with fixed-size fonts
        vtkTextRepresentation shrinks its own box to the rendered text, but
        layouts and hit-testing need the cell the widget was given.
        """
        x, y = self._locked_position[:2]
        width, height = self._locked_size[:2]
        return (x, x + width, y, y + height)

    def SetBounds(self, x0, x1, y0, y1):
        """Place the text box at viewport-fraction bounds."""
        self.SetPosition(x0, y0)
        self.SetSize(x1 - x0, y1 - y0)

    TEXT_PADDING_PX = (6.0, 3.0)

    def defaultSizePolicy(self):
        horizontal = (SizePolicy.Expanding if self.editable
                      else SizePolicy.Preferred)
        return SizePolicy(horizontal, SizePolicy.Fixed)

    def sizeHint(self):
        """Measured text plus padding, in logical px."""
        text = self._compose_display_text(self.text)
        width, height = _measure_text_px(self, text, self.text_size)
        pad_x, pad_y = self.TEXT_PADDING_PX
        return (_display_to_logical(width) + 2 * pad_x,
                _display_to_logical(height) + 2 * pad_y)

    def minimumSizeHint(self):
        width, height = self.sizeHint()
        if self.editable or self.elide_to_bounds:
            return (min(width, 3 * height), height)
        return (width, height)

    def SetSize(self, width, height):
        """
        Sets the size of the text widget.
        Args:
            width (float): The width of the widget in normalized viewport coordinates.
            height (float): The height of the widget in normalized viewport coordinates.
        """



        representation = self.GetRepresentation()
        self._locked_size = (width, height)
        representation.GetPosition2Coordinate().SetValue(width, height)
        self._apply_text_alignment()
        representation.Modified()
        self._enforce_text_scale_mode()
        if self.elide_to_bounds:
            self._update_edit_display()   # re-fit the ellipsis to the new width
        self.Modified()

    def _restore_locked_geometry(self, caller=None, event=None):
        """Prevent editable, non-grabbable text from moving or resizing."""
        if self.grabbable:
            return
        representation = self.GetRepresentation()
        if representation is None:
            return
        representation.MovingOff()
        representation.GetPositionCoordinate().SetValue(*self._locked_position)
        representation.GetPosition2Coordinate().SetValue(*self._locked_size)
        self._apply_text_alignment()
        representation.Modified()
        self._enforce_text_scale_mode()
        self.Modified()

    def Delete(self):
        """
        Deletes the text widget from the renderer.
        """
        self.Off()
        manager = self.focusManager()
        if manager is not None:
            manager.unregister(self)
        self.observerRegistry().clear()
        observer_id = getattr(self, '_key_press_observer_id', None)
        if observer_id is not None and self.interactor is not None:
            self.interactor.RemoveObserver(observer_id)
            self._key_press_observer_id = None
        if hasattr(self.renderer, 'widgets'):
            stale_names = [name for name, widget in self.renderer.widgets.items()
                           if widget is self]
            for name in stale_names:
                del self.renderer.widgets[name]
        self.SetInteractor(None)
        self.SetTextActor(None)
        self.SetRepresentation(None)
        self.Modified()

        del self

    def Highlight(self, highlight_on=True):
        """
        Highlights or unhighlights the text widget by changing its text color.
        Args:
            highlight_on (bool): True to highlight the widget, False to unhighlight it.
        """
        self._highlighted = bool(highlight_on)
        if not self._highlighted and self.editing:
            # Selection owns the edit session.  Deselecting accepts the
            # current value just like Return or an outside click.
            self.finish_editing(commit=True)
        self.text_actor = self.GetTextActor()
        try:
            apply_ui_font(self.text_actor.GetTextProperty(), bold=self._highlighted)
        except AttributeError:
            logger.debug('actor has no text actor')
            return


        self.text_actor.Modified()
        self.Modified()



    # --------------------------------



    def on_left_button_press(self, caller, event):
        """Handle left button press."""
        x, y = self.interactor.GetEventPosition()
        # The text is drawn on the UI layer, which may be an overlay renderer
        # separate from the (possibly viewport-clipped) scene renderer.
        self.picker.Pick(x, y, 0, ui_layer(self.renderer))
        picked = self.picker.GetViewProp()
        if picked in (self.text_actor, self.text_representation):
            self._handle_click()
        else:
            # If clicked outside panel while editing, commit changes (or cancel)
            if self.editing:
                self.finish_editing(commit=True)
        return

    def _handle_click(self):
        """Focus, click/double-click signals, and start editing if due."""
        self.setFocus(reason="mouse")
        now = time.monotonic()
        is_double_click = now - self._last_click_time <= 0.35
        self._last_click_time = now
        self.click()
        if is_double_click:
            self.doubleClicked.emit()
        if not self.editing and (
                not self.edit_on_double_click or is_double_click):
            self.start_editing()

    def _on_cell_press(self, caller, _event):
        """Handle a press anywhere in the widget's cell (see __init__).

        While editing: a click places the caret (Shift extends the
        selection) and dragging selects; a double click selects a word and
        a triple click selects everything.
        """
        if not (self.editable or self.clickable) or not self.GetEnabled():
            return
        x, y = caller.GetEventPosition()
        if not self.hitTest(x, y):
            if self.editing:
                self.finish_editing(commit=True)
            return
        count = self._click_count()
        command = caller.GetCommand(self._cell_press_tag)
        if command is not None:
            command.SetAbortFlag(1)
        if self.editing:
            buffer = self._edit_buffer()
            index = self._index_at_x(x)
            if count == 2:
                buffer.selectWordAt(index)
            elif count >= 3:
                buffer.selectAll()
            else:
                buffer.move(index, select=bool(caller.GetShiftKey()))
                self._begin_drag_select()
            self._apply_buffer(False)
            return
        index = self._index_at_x(x) if self.editable else None
        self._handle_click()
        if self.editing and index is not None:
            self._edit_buffer().move(index)
            self._apply_buffer(False)
            self._begin_drag_select()

    def start_editing(self):
        """Start editing."""
        if not self.editable or self._read_only or self.editing:
            return False
        if not self.hasFocus():
            # Keep the original reason (e.g. Tab) when already focused, so
            # the keyboard focus ring returns once editing ends.
            self.setFocus(reason="editing")
        self.editing = True
        self.editingStarted.emit()
        apply_ui_font(self.text_actor.GetTextProperty(), bold=self._highlighted)
        self.orig_text = self.text
        # position panel near the display actor
        # Take self.text_actor position
        dx, dy = self.text_actor.GetPosition()  # display coordinates
        # place panel slightly below the display actor position
        self.panel_x = dx
        self.panel_y = dy #- 10 - self.panel_h
        # ensure panel within window bounds
        rw, rh = self.interactor.GetRenderWindow().GetSize()
        if self.panel_x + self.panel_w > rw - 10:
            self.panel_x = max(10, rw - 10 - self.panel_w)
        if self.panel_y < 10:
            self.panel_y = 10
        # self._update_panel_geometry()
        # set edit text actor position inside panel (left + margin)
        # self.edit_self.text_actor.SetDisplayPosition(int(self.panel_x + self.panel_margin), int(self.panel_y + self.panel_margin))
        # self._set_panel_visible(True)
        # caret at end by default
        self.caret_index = len(self.text)
        # A fresh buffer per edit session: undo history starts here.
        from .text_buffer import TextBuffer

        self._text_buffer = self._new_buffer()
        if self._input_mask is not None:
            # Start at the first blank position, as QLineEdit does.
            blank = next((i for i, ch in enumerate(self.text)
                          if self._input_mask.isEditable(i)
                          and ch == self._input_mask.blank), None)
            if blank is not None:
                self.caret_index = blank
            self._text_buffer.caret = self._text_buffer.anchor = \
                self.caret_index
        # render
        self._update_edit_display()
        self.interactor.Render()
        return True

    def cancelEditing(self):
        if not self.editing:
            return False
        self.finish_editing(commit=False)
        return True

    def focusOutEvent(self, reason="other"):
        if self.editing:
            self.finish_editing(commit=True)
        super().focusOutEvent(reason)

    def _convert_string_to_float(self, s: str):
        """Convert string to float."""
        try:
            # Attempt to convert the string to a float
            # remove any unwanted characters like letters, symbols and spaces
            s = ''.join(c for c in s if c in '0123456789.-+eE')
            value = float(s)
            return value
        except ValueError:
            logger.warning("%s %s", "Could not convert string to float:", s)
            return 0.0

    def finish_editing(self, commit=True):
        # stop editing and hide panel
        """Execute the finish editing operation."""
        self.editing = False
        self._hide_completions()
        apply_ui_font(self.text_actor.GetTextProperty(), bold=self._highlighted)
        if commit and self._input_mask is not None and \
                not self._input_mask.isAcceptable(self.text):
            commit = False          # required positions are still blank
        if commit and self._validator is not None:
            result = self._validator(self.text)
            valid = result[0] if isinstance(result, tuple) else result
            if not valid:
                commit = False
        original_text = self.orig_text
        if commit:
            if self.force_to_float:
                self.text = str(self._convert_string_to_float(self.text))
        else:
            # revert
            self.text = self.orig_text
        # self._set_panel_visible(False)
        self._update_edit_display()
        if self.end_of_edit_callback is not None:
            self.end_of_edit_callback(self, self.text)
        self._modified = False
        self.editingFinished.emit()
        if self.text != original_text:
            self.textChanged.emit(self.text)
        self.interactor.Render()

    def on_key_press(self, caller, event):
        """Edit the text: QLineEdit-style keys on a :class:`TextBuffer`.

        Shift extends the selection; Ctrl or Alt moves/deletes by word
        (VTK reports Cmd as Ctrl on macOS). Ctrl+A/C/X/V, Ctrl+Z and
        Ctrl+Y/Ctrl+Shift+Z select, use the clipboard, undo and redo; other
        Ctrl combinations are left for shortcuts. Typed text arrives
        separately, from :meth:`on_char`.
        """
        if not self.editing:
            return 1
        interactor = self.interactor
        key = interactor.GetKeySym()
        if key is None:
            return 1
        lower = key.lower()
        ctrl = bool(interactor.GetControlKey())
        shift = bool(interactor.GetShiftKey())
        alt = bool(interactor.GetAltKey())
        word = ctrl or alt
        if self._completion_key(lower):
            return 1
        buffer = self._edit_buffer()
        changed = False
        handled = True
        from . import clipboard

        masked = self._echo_mode != "normal"     # no copying passwords out
        if lower in ("return", "kp_enter", "enter"):
            self.returnPressed.emit()
            self.finish_editing(commit=True)
            return 1
        if lower == "escape":
            self.finish_editing(commit=False)
            return 1
        if lower == "backspace":
            changed = buffer.backspace(word=word)
        elif lower == "delete":
            changed = buffer.delete(word=word)
        elif lower == "left":
            buffer.left(select=shift, word=word)
        elif lower == "right":
            buffer.right(select=shift, word=word)
        elif lower == "home":
            buffer.home(select=shift)
        elif lower == "end":
            buffer.end(select=shift)
        elif ctrl and lower == "a":
            buffer.selectAll()
        elif ctrl and lower == "c":
            if buffer.hasSelection() and not masked:
                clipboard.set_text(buffer.selectedText())
        elif ctrl and lower == "x":
            if masked:
                self._apply_buffer(False)
                return 1
            cut = buffer.cut()
            if cut:
                clipboard.set_text(cut)
                changed = True
        elif ctrl and lower == "v":
            pasted = clipboard.text().replace("\r", "").replace("\n", " ")
            changed = buffer.insert(pasted, typing=False)
        elif ctrl and lower == "z" and not shift:
            changed = buffer.undo()
        elif ctrl and (lower == "y" or (lower == "z" and shift)):
            changed = buffer.redo()
        elif ctrl:
            handled = False          # e.g. Ctrl+S: leave it to shortcuts
        else:
            handled = False          # text: see on_char
        if handled:
            self._apply_buffer(changed)
        return 1

    def on_char(self, caller, event):
        """Insert the typed character while editing, and consume the event
        so the interactor style's hotkeys (w, e, q, 3...) never see it,
        with or without an EventRouter. Ctrl/Cmd combinations are
        shortcuts, not text."""
        if not self.editing:
            return
        interactor = self.interactor
        command = caller.GetCommand(self._char_observer_id) \
            if getattr(self, "_char_observer_id", None) is not None else None
        if command is not None:
            command.SetAbortFlag(1)
        if interactor.GetControlKey():
            return
        char = interactor.GetKeyCode()
        if not (isinstance(char, str) and len(char) == 1 and
                ord(char) >= 32 and char != "\x7f"):
            return
        buffer = self._edit_buffer()
        self._apply_buffer(buffer.insert(char))

    # -- text buffer, selection display and caret placement -------------------
    def _edit_buffer(self):
        from .text_buffer import TextBuffer

        buffer = getattr(self, "_text_buffer", None)
        if buffer is None:
            buffer = self._new_buffer()
            buffer.caret = buffer.anchor = self.caret_index
            self._text_buffer = buffer
        buffer.sync(self.text, self.caret_index)
        return buffer

    def _new_buffer(self):
        from .text_buffer import TextBuffer

        return TextBuffer(self.text, max_length=self._max_length,
                          mask=self._input_mask)

    def selectedText(self):
        buffer = getattr(self, "_text_buffer", None)
        return buffer.selectedText() if buffer is not None and self.editing else ""

    def hasSelectedText(self):
        return bool(self.selectedText())

    def selectAll(self):
        if self.editing:
            self._edit_buffer().selectAll()
            self._apply_buffer(False)

    def _apply_buffer(self, changed, complete=True):
        buffer = self._text_buffer
        self.text = buffer.text
        self.caret_index = buffer.caret
        if changed:
            self._modified = True
            self.textEdited.emit(self.text)
            if complete:
                self._update_completions()
        self._update_edit_display()
        self.interactor.Render()

    def _full_display_index(self, index):
        """Index in the composed (unscrolled) string of editable ``index``."""
        if getattr(self, "_echo_mode", "normal") == "noEcho":
            index = 0                     # nothing shown: the caret stays put
        offset = len("".join(self.prepend_text))
        caret_shift = (len(self.caret_text)
                       if self.editing and index > self.caret_index else 0)
        return offset + index + caret_shift

    def _display_index(self, index):
        """Index in the displayed (possibly scrolled) string of ``index``.

        Positions scrolled out of view clamp to the visible edges.
        """
        shown = len(self.text_actor.GetInput() or "")
        start = self._scroll_start if self.editing else 0
        return max(0, min(shown, self._full_display_index(index) - start))

    def _scrolls_horizontally(self):
        return bool(self.editing and not self.scale_text_to_widget)

    def _available_text_width(self):
        window_width = max(1, self.interactor.GetRenderWindow().GetSize()[0])
        return max(1, round(self._locked_size[0] * window_width * 0.94))

    def _text_width_function(self):
        text_property = self.text_actor.GetTextProperty()
        renderer = vtk.vtkTextRenderer.GetInstance()
        dpi = max(1, self.interactor.GetRenderWindow().GetDPI())

        def width(text):
            if not text:
                return 0
            box = [0, 0, 0, 0]
            renderer.GetBoundingBox(text_property, text, box, dpi)
            return box[1] - box[0] + 1
        return width

    def _scrolled(self, display):
        """Window of ``display`` that fits the field and shows the caret.

        Like ``QLineEdit``: the view moves only as far as needed to keep the
        caret visible, and slides back when text is deleted so no space is
        wasted on the right while text is hidden on the left.
        """
        if not self._scrolls_horizontally():
            self._scroll_start = 0
            return display
        width = self._text_width_function()
        available = self._available_text_width()
        if width(display) <= available:
            self._scroll_start = 0
            return display
        caret = self._full_display_index(self.caret_index)
        if self.caret_text:
            caret += len(self.caret_text)       # keep the glyph itself in view
        start = max(0, min(self._scroll_start, caret))
        while start < caret and width(display[start:caret]) > available:
            start += 1
        while start > 0 and width(display[start - 1:]) <= available:
            start -= 1
        end = len(display)
        while end > caret and width(display[start:end]) > available:
            end -= 1
        self._scroll_start = start
        return display[start:end]

    def _display_x(self, display_index):
        """Viewport x of a boundary in the displayed string."""
        display = self.text_actor.GetInput() or ""
        layer = ui_layer(self.renderer)
        box = [0.0, 0.0, 0.0, 0.0]
        # The box is relative to the actor's position, which the text
        # representation sets; offset it into viewport coordinates.
        self.text_actor.GetBoundingBox(layer, box)
        origin = self.text_actor.GetPositionCoordinate() \
            .GetComputedViewportValue(layer)
        box = [box[0] + origin[0], box[1] + origin[0],
               box[2] + origin[1], box[3] + origin[1]]
        text_property = self.text_actor.GetTextProperty()
        dpi = max(1, self.interactor.GetRenderWindow().GetDPI())
        renderer = vtk.vtkTextRenderer.GetInstance()

        def width(text):
            if not text:
                return 0.0
            extent = [0, 0, 0, 0]
            renderer.GetBoundingBox(text_property, text, extent, dpi)
            return float(extent[1] - extent[0] + 1)

        full = width(display)
        scale = (box[1] - box[0]) / full if full > 0 else 1.0
        return box[0] + width(display[:display_index]) * scale, box

    def _index_at_x(self, x):
        """Nearest editable index to viewport x (for clicks and drags)."""
        best, best_distance = 0, None
        start = self._scroll_start if self.editing else 0
        shown = len(self.text_actor.GetInput() or "")
        for index in range(len(self.text) + 1):
            if not 0 <= self._full_display_index(index) - start <= shown:
                continue                    # scrolled out of view
            position, _box = self._display_x(self._display_index(index))
            distance = abs(position - x)
            if best_distance is None or distance < best_distance:
                best, best_distance = index, distance
        return best

    def _selection_actor(self):
        actor = getattr(self, "_selection_highlight", None)
        if actor is None:
            mapper = vtk.vtkPolyDataMapper2D()
            mapper.SetColorModeToDirectScalars()
            mapper.SetScalarModeToUseCellData()
            actor = vtk.vtkActor2D()
            actor.SetMapper(mapper)
            actor.IsUI = True
            actor.PickableOff()
            actor.SetVisibility(False)
            add_actor_2d(ui_layer(self.renderer), actor)
            self._selection_highlight = actor
        return actor

    def _caret_actor(self):
        actor = getattr(self, "_caret_line", None)
        if actor is None:
            mapper = vtk.vtkPolyDataMapper2D()
            mapper.SetColorModeToDirectScalars()
            mapper.SetScalarModeToUseCellData()
            actor = vtk.vtkActor2D()
            actor.SetMapper(mapper)
            actor.IsUI = True
            actor.PickableOff()
            actor.SetVisibility(False)
            add_actor_2d(ui_layer(self.renderer), actor)
            self._caret_line = actor
        return actor

    def _update_caret_display(self):
        """Draw the caret as a thin line (unless an inline glyph is used)."""
        buffer = getattr(self, "_text_buffer", None)
        show = bool(self.editing and not self.caret_text and self.GetEnabled()
                    and not (buffer is not None and buffer.hasSelection()))
        actor = getattr(self, "_caret_line", None)
        if not show:
            if actor is not None:
                actor.SetVisibility(False)
            return
        actor = self._caret_actor()
        x, box = self._display_x(self._display_index(self.caret_index))
        text_property = self.text_actor.GetTextProperty()
        height = box[3] - box[2]
        if height <= 0 or not (self.text_actor.GetInput() or ""):
            # Empty field: centre a font-height caret on the text anchor.
            origin = self.text_actor.GetPositionCoordinate() \
                .GetComputedViewportValue(ui_layer(self.renderer))
            height = max(8.0, float(text_property.GetFontSize()))
            x = float(origin[0])
            if text_property.GetVerticalJustification() == 1:   # centred
                box = [x, x, origin[1] - height / 2, origin[1] + height / 2]
            else:
                box = [x, x, float(origin[1]), origin[1] + height]
        width = max(1.0, 1.5 * ui_scale())
        color = tuple(int(255 * channel)
                      for channel in text_property.GetColor()[:3]) + (255,)
        actor.GetMapper().SetInputData(rounded_rect_polydata(
            x - width / 2, box[2] - 1, width, box[3] - box[2] + 2,
            [0, 0, 0, 0], color))
        actor.SetVisibility(True)

    def _update_selection_display(self):
        self._update_caret_display()
        buffer = getattr(self, "_text_buffer", None)
        show = bool(self.editing and buffer is not None
                    and buffer.hasSelection() and self.GetEnabled())
        actor = getattr(self, "_selection_highlight", None)
        if not show:
            if actor is not None:
                actor.SetVisibility(False)
            return
        actor = self._selection_actor()
        start, end = buffer.selection()
        x0, box = self._display_x(self._display_index(start))
        x1, _box = self._display_x(self._display_index(end))
        accent = theme_value(self.renderer, "accent_color_rgb",
                             (0.012, 0.486, 0.965))
        color = tuple(int(255 * channel) for channel in accent[:3]) + (90,)
        actor.GetMapper().SetInputData(rounded_rect_polydata(
            min(x0, x1), box[2] - 1, abs(x1 - x0), box[3] - box[2] + 2,
            [0, 0, 0, 0], color))
        actor.SetVisibility(True)

    def _click_count(self):
        """1, 2 or 3 for single, double and triple clicks in quick succession."""
        now = time.monotonic()
        last, count = getattr(self, "_click_series", (0.0, 0))
        count = count + 1 if now - last <= 0.35 else 1
        self._click_series = (now, count if count < 3 else 3)
        return count

    def _begin_drag_select(self):
        if getattr(self, "_drag_tags", None):
            return
        self._drag_tags = [
            self.ownObserver(self.interactor, "MouseMoveEvent",
                             self._on_drag_move, 0.7),
            self.ownObserver(self.interactor, "LeftButtonReleaseEvent",
                             self._end_drag_select, 0.7),
        ]

    def _on_drag_move(self, caller, _event):
        if not self.editing:
            return
        buffer = self._edit_buffer()
        x = caller.GetEventPosition()[0]
        index = self._index_at_x(x)
        _x, box = self._display_x(0)
        # Dragging past an edge of a scrolled field scrolls by a character.
        if x > box[1] and index >= buffer.caret:
            index = min(len(self.text), max(index, buffer.caret + 1))
        elif x < box[0] and index <= buffer.caret:
            index = max(0, min(index, buffer.caret - 1))
        buffer.move(index, select=True)
        self._apply_buffer(False)

    def _end_drag_select(self, caller=None, _event=None):
        for tag in getattr(self, "_drag_tags", None) or ():
            self.observerRegistry().remove(self.interactor, tag)
        self._drag_tags = None

    def _insert_text_at_caret(self, s: str):
        """Insert at the caret (replacing any selection)."""
        if s == "":
            return 1
        self._apply_buffer(self._edit_buffer().insert(s))
        return 1

    def _update_edit_display(self):
        """Update the actor with affixes, value, and an inline editing caret."""
        caret_index = self.caret_index if self.editing else None
        display = self._compose_display_text(self.text, caret_index=caret_index)
        if (not self.editing and not self.text and self._placeholder_text and
                not self.prepend_text and not self.append_text):
            display = self._placeholder_text
        if not getattr(self, "editing", False):
            display = self._elided(display)
            self._scroll_start = 0
        else:
            display = self._scrolled(display)
        self.text_actor.SetInput(display)
        self.text_actor.Modified()
        self._update_selection_display()

    def _elided(self, display):
        """Shorten *display* with an ellipsis to fit the widget's width."""
        if not self.elide_to_bounds or self.scale_text_to_widget:
            return display
        window_width = max(1, self.interactor.GetRenderWindow().GetSize()[0])
        available = max(1, round(self._locked_size[0] * window_width * 0.94))
        text_property = self.text_actor.GetTextProperty()
        key = (available, display, int(self.text_size),
               bool(text_property.GetBold()))
        if key == self._elide_key:
            return self._elide_value
        renderer = vtk.vtkTextRenderer.GetInstance()
        dpi = max(1, self.interactor.GetRenderWindow().GetDPI())

        def width(text):
            box = [0, 0, 0, 0]
            renderer.GetBoundingBox(text_property, text or " ", box, dpi)
            return box[1] - box[0] + 1

        result = display
        if width(display) > available:
            low, high = 0, len(display)
            while low < high:      # longest prefix that fits with an ellipsis
                mid = (low + high + 1) // 2
                if width(display[:mid].rstrip() + "\u2026") <= available:
                    low = mid
                else:
                    high = mid - 1
            result = display[:low].rstrip() + "\u2026"
        self._elide_key, self._elide_value = key, result
        self._elided_full = display if result != display else None
        if self._elided_full and self._elide_hover is None and \
                ENABLE_HOVER_TEXT:
            # Hovering a shortened field shows its whole text.
            self._elide_hover = _ElidedTextHover(self)
            get_hover_text_overlay(self.renderer, self.interactor).register(
                self._elide_hover)
        return result

    def on_render_event(self, caller, event):
        # # Keep caret and panel geometry updated if window is resized or render happens.
        # if self.panel_visible:
        #     self._update_panel_geometry()
        #     # reset text actor position inside panel (in case panel geometry changed)
        #     self.edit_text_actor.SetDisplayPosition(int(self.panel_x + self.panel_margin), int(self.panel_y + self.panel_margin))
        #     # update caret pos
        """Handle render event."""
        self._update_edit_display()

        return 1

TOOLTIP_DELAY_MS = 700


def set_tooltip_delay(ms):
    """Set how long the pointer must rest on a button before its tooltip."""
    global TOOLTIP_DELAY_MS
    TOOLTIP_DELAY_MS = max(0, int(ms))


def tooltip_delay():
    return TOOLTIP_DELAY_MS


class HoverTextOverlay(WidgetMixin):
    """One renderer-level tooltip actor shared by context-painted buttons.

    As in Qt, a tooltip appears once the pointer has rested on a button for
    ``tooltip_delay()`` ms, switches immediately to a neighbouring button
    while one is showing, and is hidden by a press until the pointer leaves
    that button.
    """

    def __init__(self, renderer, interactor):
        self.renderer = renderer
        self.interactor = interactor
        self.initWidget('hover_text_overlay')
        self.buttons = []
        self.active_button = None
        self.text_actor = vtk.vtkTextActor()
        self.text_actor.IsUI = True
        self.text_actor.PickableOff()
        self.text_actor.SetVisibility(False)
        text_property = self.text_actor.GetTextProperty()
        tokens = getattr(getattr(renderer, "theme", None), "tokens", None)
        # One style for every tooltip: theme colours (dark fallback).
        text_property.SetColor(*(tokens["text"] if tokens else (1.0, 1.0, 1.0)))
        text_property.SetBackgroundColor(
            *(tokens["tooltip"] if tokens else (0.08, 0.08, 0.09)))
        text_property.SetBackgroundOpacity(0.97 if tokens else 0.92)
        text_property.SetFrame(True)
        text_property.SetFrameColor(
            *(tokens["border"] if tokens else (0.55, 0.55, 0.58)))
        text_property.SetJustificationToLeft()
        text_property.SetVerticalJustificationToBottom()
        apply_ui_font(text_property)
        add_actor_2d(ui_layer(self.renderer), self.text_actor)
        self._observer_id = self.ownObserver(
            interactor, 'MouseMoveEvent', self._on_mouse_move, 0.9)
        self.ownObserver(interactor, 'LeftButtonPressEvent',
                         self._on_press, 0.9)
        from .timer import Timer

        self._pending_button = None
        self._suppressed_button = None
        self._show_timer = Timer(interactor, single_shot=True)
        self._show_timer.timeout.connect(self._show_pending)

    def register(self, button):
        if button not in self.buttons:
            self.buttons.append(button)

    def unregister(self, button):
        if button in self.buttons:
            self.buttons.remove(button)
        if self._pending_button is button:
            self._show_timer.stop()
            self._pending_button = None
        if self.active_button is button:
            self.active_button = None
            self.text_actor.SetVisibility(False)

    def setVisible(self, visible):
        visible = bool(visible)
        old = self.isVisible()
        self._ui_visible = visible
        if not visible:
            self.active_button = None
            self.text_actor.SetVisibility(False)
        if old != visible:
            self.visibilityChanged.emit(visible)

    def isVisible(self):
        return bool(self._ui_visible)

    def _applyTheme(self):
        tokens = getattr(getattr(self.renderer, 'theme', None), 'tokens', None)
        if tokens is None:
            return
        text_property = self.text_actor.GetTextProperty()
        text_property.SetColor(*tokens['text'])
        text_property.SetBackgroundColor(*tokens['tooltip'])
        text_property.SetFrameColor(*tokens['border'])
        text_property.Modified()
        self.text_actor.Modified()

    def Delete(self):
        self.observerRegistry().clear()
        remove_actor_2d(ui_layer(self.renderer), self.text_actor)
        self.buttons.clear()

    def _hovered_button(self):
        x, y = self.interactor.GetEventPosition()
        for button in reversed(self.buttons):
            if (button.enabled and button.actor.GetVisibility() and
                    button.hover_text):
                button._update_pixel_bounds()
                if button._point_in_bounds(x, y):
                    return button
        return None

    def _hide(self):
        self._show_timer.stop()
        self._pending_button = None
        if self.active_button is not None:
            self.active_button = None
            self.text_actor.SetVisibility(False)
            self.text_actor.Modified()
            # Hover moves do not render on their own (the interactor style
            # only renders while dragging), so ask for a frame.
            self.requestRender()

    def _on_press(self, caller=None, event=None):
        hovered = self._hovered_button()
        self._hide()
        self._suppressed_button = hovered

    def _on_mouse_move(self, caller=None, event=None):
        if not self.isVisible():
            return
        hovered = self._hovered_button()
        if hovered is not self._suppressed_button:
            self._suppressed_button = None
        if hovered is None or hovered is self._suppressed_button:
            self._hide()
            return
        if hovered is self.active_button or hovered is self._pending_button:
            return          # placement does not follow the pointer
        if self.active_button is not None or tooltip_delay() == 0:
            self._show(hovered)              # already showing: switch now
            return
        self._pending_button = hovered
        self._show_timer.start(tooltip_delay())

    def _show_pending(self):
        button, self._pending_button = self._pending_button, None
        if button is not None and button is self._hovered_button():
            self._show(button)

    def _show(self, hovered):
        self._show_timer.stop()
        self._pending_button = None
        x0, x1, y0, y1 = hovered.pixel_bounds
        window = self.interactor.GetRenderWindow()
        window_width, window_height = window.GetSize()
        text_property = self.text_actor.GetTextProperty()
        text_property.SetFontSize(max(11, panel_title_text_size(self.interactor) - 3))
        # A space either side of each line pads the framed background.
        text = "\n".join(f" {line} " for line in hovered.hover_text.splitlines())
        box = [0, 0, 0, 0]
        vtk.vtkTextRenderer.GetInstance().GetBoundingBox(
            text_property, text, box, max(1, window.GetDPI()))
        text_width, text_height = box[1] - box[0] + 1, box[3] - box[2] + 1
        gap, margin = 6, 4
        # Centred over the button; below it only when there is no room above.
        text_x = (x0 + x1) / 2.0 - text_width / 2.0
        text_x = min(max(margin, text_x), window_width - text_width - margin)
        text_y = y1 + gap
        if text_y + text_height > window_height - margin:
            text_y = y0 - gap - text_height
        # Actor2D insertion order is the dependable foreground mechanism
        # across the OpenGL and context-renderer paths used by this GUI.
        remove_actor_2d(ui_layer(self.renderer), self.text_actor)
        add_actor_2d(ui_layer(self.renderer), self.text_actor)
        self.active_button = hovered
        self.text_actor.SetInput(text)
        self.text_actor.SetDisplayPosition(int(text_x), int(max(margin, text_y)))
        self.text_actor.SetVisibility(True)
        self.text_actor.Modified()
        self.requestRender()


class _ElidedTextHover:
    """What :class:`HoverTextOverlay` shows for a :class:`TextWidget`
    whose text is shortened with an ellipsis: the full text, while it is
    shortened and not being edited."""

    def __init__(self, field):
        self._field_ref = weakref.ref(field)
        self.pixel_bounds = None

    def _field(self):
        return self._field_ref()

    @property
    def enabled(self):
        field = self._field()
        return bool(field is not None and field.GetEnabled() and
                    not field.editing)

    @property
    def actor(self):
        field = self._field()
        return field.text_actor if field is not None else _HIDDEN_ACTOR

    @property
    def hover_text(self):
        field = self._field()
        return field._elided_full if field is not None else None

    def _update_pixel_bounds(self):
        field = self._field()
        if field is None:
            self.pixel_bounds = None
            return
        width, height = field.interactor.GetRenderWindow().GetSize()
        x0, x1, y0, y1 = field.GetBounds()[:4]
        self.pixel_bounds = (x0 * width, x1 * width, y0 * height,
                             y1 * height)

    def _point_in_bounds(self, x, y):
        if self.pixel_bounds is None:
            return False
        x0, x1, y0, y1 = self.pixel_bounds
        return x0 <= x <= x1 and y0 <= y <= y1


_HIDDEN_ACTOR = vtk.vtkTextActor()
_HIDDEN_ACTOR.SetVisibility(False)


def get_hover_text_overlay(renderer, interactor):
    """Return the shared tooltip overlay for one renderer."""
    overlay = getattr(renderer, '_hover_text_overlay', None)
    if overlay is None:
        overlay = HoverTextOverlay(renderer, interactor)
        renderer._hover_text_overlay = overlay
    return overlay


class _LegacyHoverTracker:
    """Hover state for legacy buttons, one per interactor (W7).

    The router only hit-tests while native widgets exist; legacy buttons
    therefore track the pointer themselves. Rectangle tests against cached
    pixel bounds on mouse moves; never consumes the event.
    """

    _instances = weakref.WeakKeyDictionary()

    @classmethod
    def for_interactor(cls, interactor):
        tracker = cls._instances.get(interactor)
        if tracker is None:
            tracker = cls._instances[interactor] = cls(interactor)
        return tracker

    def __init__(self, interactor):
        self._interactor_ref = weakref.ref(interactor)
        self._buttons = weakref.WeakSet()
        self._hovered_ref = None
        self._tags = [interactor.AddObserver("MouseMoveEvent", self._on_move,
                                             0.95),
                      interactor.AddObserver("LeaveEvent", self._on_leave,
                                             0.95)]

    def add(self, button):
        self._buttons.add(button)

    def discard(self, button):
        self._buttons.discard(button)
        if self.hovered() is button:
            self._set(None)

    def hovered(self):
        return None if self._hovered_ref is None else self._hovered_ref()

    def _on_move(self, caller, _event=None):
        x, y = caller.GetEventPosition()
        hit = None
        for button in list(self._buttons):
            if (button._shown and button.actor.GetVisibility()
                    and getattr(button, "pixel_bounds", None) is not None
                    and button._point_in_bounds(x, y)):
                hit = button
                break
        if hit is not self.hovered():
            self._set(hit)

    def _on_leave(self, _caller=None, _event=None):
        self._set(None)

    def _set(self, button):
        previous = self.hovered()
        self._hovered_ref = None if button is None else weakref.ref(button)
        for widget, inside in ((previous, False), (button, True)):
            if widget is not None:
                widget._ui_under_mouse = inside
                widget.updateStyleState()


class VectorButtonWidget(WidgetMixin):
    """
    A vector button that draws polydata onto a vtkContextScene
    without subclassing vtkContextItem directly.
    """

    # Icons of unavailable buttons draw at this opacity (W7), unless the
    # host already shows them in grayscale.
    DISABLED_OPACITY = 0.4

    @property
    def enabled(self):
        """Availability. Assigning it (as hosts do) notifies like
        ``setEnabled``: ``enabledChanged``, ``styleStateChanged``, repaint."""
        return self.__dict__.get("_available_flag", True)

    @enabled.setter
    def enabled(self, value):
        value = bool(value)
        old = self.__dict__.get("_available_flag", True)
        self.__dict__["_available_flag"] = value
        if old != value and getattr(self, "_ui_api_ready", False) and \
                hasattr(self, "painter"):
            self.enabledChanged.emit(value)
            self.updateStyleState()
            self.requestRender()


    def __init__(self, renderer, interactor, svg_path_str=None, input_data=None, callback=None,
                 bounds=(0.8, 0.9, 0.5, 0.6), color=None, opacity=1.0, invert_y=True,
                 initial_state=0, enabled=True, show_background=False, grabbable=True, wireframe=False,
                 verbose=False, icon_name=None, name=None,
                 grayscale_states=None, grayscale_brightness=.10,
                 hover_text=None, interactive=True,
                 ui_z_order=UI_Z_SCROLL_ROWS, tint_states=None):
        """Initialize the instance.

        ``tint_states`` (one entry per state, RGB or None) recolours only the
        icon's coloured cells -- white/grey parts such as a switch knob keep
        their colour, unlike ``color`` which paints every cell."""
        self.renderer = renderer
        self.interactor = interactor
        self.initWidget(name)
        self.clicked = Signal(self)
        self.pressed = Signal(self)
        self.released = Signal(self)
        self.toggled = Signal(self)
        self.callback = callback
        is_color_sequence = (
            isinstance(color, (list, tuple)) and bool(color)
            and isinstance(color[0], (list, tuple, np.ndarray)))
        self.color_states = list(color) if is_color_sequence else [color]
        if grayscale_states is None:
            grayscale_states = [False]
        elif isinstance(grayscale_states, bool):
            grayscale_states = [grayscale_states]
        self.grayscale_states = list(grayscale_states)
        self.grayscale_brightness = float(grayscale_brightness)
        self.tint_states = list(tint_states) if tint_states else [None]
        self.opacity = opacity
        self.state = initial_state
        self.normalized_bounds = bounds
        self.panel_bounds = bounds
        self.svg_path_str = svg_path_str
        self.invert_y = invert_y
        self.wireframe = wireframe
        self.icon_name = icon_name
        self.name = name
        self.hover_text = str(hover_text) if hover_text else None
        self.interactive = bool(interactive)
        if self.interactive:
            self.registerFocus(interactor, policy="StrongFocus")
        self.ui_z_order = int(ui_z_order)

        self.verbose = verbose

        self.pd = None  # Cache for polydata if built from shapes

        if input_data is None:
            input_data = np.array([[0.333, 0.166],
                        [0.166, 0.833],
                        [0.333, 0.833],
                        [0.500, 0.333],
                        [0.666, 0.833],
                        [0.833, 0.833],
                        [0.666, 0.166],
                        [0.333, 0.166]])





        # A vector button may use one geometry source or a source per state.
        # A numeric list remains a single point array; a list/tuple of paths or
        # numpy arrays is interpreted as multiple states.
        is_state_sequence = (
            isinstance(input_data, (list, tuple)) and bool(input_data)
            and all(isinstance(item, (str, np.ndarray)) for item in input_data))
        self.input_states = (list(input_data) if is_state_sequence
                             else [input_data])
        self.total_states = max(
            len(self.input_states), len(self.color_states),
            len(self.grayscale_states), len(self.tint_states))
        self.state = int(initial_state) % self.total_states
        self.input_data = self.input_states[self.state % len(self.input_states)]
        self.color = self.color_states[self.state % len(self.color_states)]
        self.grayscale = self.grayscale_states[
            self.state % len(self.grayscale_states)]
        self.tint = self.tint_states[self.state % len(self.tint_states)]
        self.axis_enabled = None
        self.show_background = show_background
        # Two independent states (previously one flag served both):
        # ``enabled`` means available/interactive and is what hosts set to
        # grey out or lock a button; ``_shown`` is controlled by containers
        # through SetVisibility/SetEnabled. A click needs both.
        self.enabled = enabled
        self._shown = True
        self.equal_aspect_ratio = True


        self.polydata = None

        self.grabbable = grabbable




        self.make_representation()

        # if self.grabbable:
        #     # self.SetSelectable(True)
        #     self.SetProcessEvents(True)
        # else:
        #     # self.SetSelectable(False)
        #     self.SetProcessEvents(False)

        # Set up context actor and scene
        self.actor = vtk.vtkContextActor()
        self.scene = self.actor.GetScene()
        ui_layer(self.renderer).AddActor(self.actor)
        register_ui_drawable(
            renderer, self, self.ui_z_order,
            name or (icon_name if isinstance(icon_name, str)
                     else self.__class__.__name__))

        # Make the SVG path into a vtkPath object
        if self.svg_path_str is not None:
            self.vtk_path = self._parse_svg_path(self.svg_path_str)

        elif self.input_data is not None:
            self.polydata = self.build_symbols(self.input_data)
            # self.polydata = self.scale_polydata(self.polydata, window_size=self.interactor.GetRenderWindow().GetSize(), pixel_offset=(0, 0), xy_offset=(0, 0))

        # else:
        #     raise ValueError("Either svg_path_str or input_data must be provided")

        # Add our painter object (non-subclass)
        self.painter = self._make_painter()
        self.scene.AddItem(self.painter)

        # Handle clicks
        self._click_observer_id = None
        if self.interactive:
            self._click_observer_id = self.ownObserver(
                interactor, "LeftButtonPressEvent", self._on_click)
        if self.interactive and self.hover_text and ENABLE_HOVER_TEXT:
            get_hover_text_overlay(renderer, interactor).register(self)

        # Force update of bounds in pixels
        self._update_pixel_bounds()
        # Hover, focus, checked and disabled come from the router and the
        # Style (W7); repaint when they change.
        self.styleStateChanged.connect(self._on_style_state)
        if self.interactive:
            _LegacyHoverTracker.for_interactor(interactor).add(self)



    def color_to_RGBA_255(color, opacity=1):

        """Execute the color to rgba 255 operation."""
        colors = vtk.vtkNamedColors()

        alpha = int(opacity * 255)

        if isinstance(color, tuple):
            color = np.array(color)

        if isinstance(color, str):
            RGBA_color = *colors.GetColor3ub(color), alpha
        elif isinstance(color, (list, tuple)):
            if all(cvalue < 1.00001 for cvalue in color):
                RGBA_color = (np.array(color) * 255).astype(np.uint8)

            if len(color) == 3:
                RGBA_color = color[0], color[1], color[2], alpha
            elif len(color) == 4:
                RGBA_color = color[0], color[1], color[2], color[3]

        elif isinstance(color, vtk.vtkColor3ub):
            RGBA_color = color.GetRed(), color.GetGreen(), color.GetBlue(), alpha
        elif isinstance(color, vtk.vtkColor4ub):
            RGBA_color = (
                color.GetRed(),
                color.GetGreen(),
                color.GetBlue(),
            )
            color.GetAlpha()
        elif isinstance(color, (vtk.vtkFloatArray, vtk.vtkUnsignedCharArray)):
            RGBA_color = color.GetPointer(0)
            if len(color) == 3:
                RGBA_color = color[0], color[1], color[2], alpha
            elif len(color) == 4:
                RGBA_color = color[0], color[1], color[2], color[3]
            else:
                raise ValueError("Invalid color format")
        elif isinstance(color, np.ndarray):
            if np.all(color < 1.00001):
                color = (color * 255).astype(np.uint8)

            if color.ndim == 1 and color.size == 3:
                RGBA_color = color[0], color[1], color[2], alpha
            elif color.ndim == 1 and color.size == 4:
                RGBA_color = color[0], color[1], color[2], color[3]
            else:
                raise ValueError("Invalid color format")

        return np.asarray([int(c) for c in RGBA_color])




    def build_symbols(self, input_points):


        """Build symbols."""
        if self.pd is not None:

            copy_pd = vtk.vtkPolyData()
            copy_pd.DeepCopy(self.pd)

            return copy_pd


        if isinstance(input_points, str):


            if not os.path.exists(input_points):
                logger.warning(f"{bcolors.WARNING}Input points string does not exist: {input_points}, trying fallback...{bcolors.ENDC}")

                # Prefer the vector SVG source, then the PNG, from the
                # matching format folder (vtk_icons -> svg_icons/png_icons;
                # only that folder and the extension change); build the
                # missing .vtk once and cache it so later runs just load it.
                from .resources import icon_sources
                missing_vtk = input_points if input_points.endswith(".vtk") else None
                for fallback_icon_path in icon_sources(input_points):
                    if os.path.exists(fallback_icon_path):
                        input_points = self._build_cached_icon(
                            fallback_icon_path, missing_vtk)
                        break
                else:
                    raise FileNotFoundError(f"{bcolors.FAIL}Input points string must be a valid file path: {input_points} {bcolors.ENDC}")

            if isinstance(input_points, str):
                assert os.path.isfile(input_points), f"{bcolors.FAIL}Input points string must be a valid file path: {input_points} {bcolors.ENDC}"

            if not isinstance(input_points, str):
                pass        # already converted by the fallback above
            elif input_points.endswith(".vtk"):
                reader = vtk.vtkPolyDataReader()
                reader.SetFileName(input_points)
                reader.Update()
                input_points = reader.GetOutput()
            elif input_points.endswith(".svg"):
                input_points = _icon_converter().convert_svg_to_triangles(
                    input_points)
            elif input_points.endswith(".png"):
                input_points = _icon_converter().convert_image_to_triangles(
                    input_points, ignore_background=False, show_plots=False)
            else:
                raise ValueError("Unsupported file format for input_points: " + input_points)

        if isinstance(input_points, vtk.vtkPolyData):
            if self.verbose:
                logger.debug("Input is already vtkPolyData, using directly.")

            if self.color is not None:
                colors = vtk.vtkUnsignedCharArray()
                colors.SetNumberOfComponents(4)
                color_rgba = [int(self.color[0] * 255), int(self.color[1] * 255), int(self.color[2] * 255), int(self.opacity * 255)]
                for i in range(input_points.GetNumberOfCells()):
                    colors.InsertNextTuple4(color_rgba[0], color_rgba[1], color_rgba[2], color_rgba[3])
                input_points.GetCellData().SetScalars(colors)
            elif getattr(self, "tint", None) is not None:
                source_polydata = input_points
                input_points = vtk.vtkPolyData()
                input_points.DeepCopy(source_polydata)
                scalars = input_points.GetCellData().GetScalars()
                if scalars is not None and scalars.GetNumberOfComponents() >= 3:
                    tint = [int(round(c * 255)) for c in self.tint[:3]]
                    for cell_index in range(scalars.GetNumberOfTuples()):
                        rgba = list(scalars.GetTuple(cell_index))
                        # Coloured (saturated) cells take the tint; neutral
                        # whites/greys/blacks are left alone.
                        if max(rgba[:3]) - min(rgba[:3]) > 40:
                            rgba[:3] = tint
                            scalars.SetTuple(cell_index, rgba)
                    scalars.Modified()
            elif self.grayscale:
                source_polydata = input_points
                input_points = vtk.vtkPolyData()
                input_points.DeepCopy(source_polydata)
                scalars = input_points.GetCellData().GetScalars()
                if scalars is not None and scalars.GetNumberOfComponents() >= 3:
                    lift = np.clip(self.grayscale_brightness, 0.0, 1.0)
                    for cell_index in range(scalars.GetNumberOfTuples()):
                        rgba = list(scalars.GetTuple(cell_index))
                        gray = (0.2126 * rgba[0] + 0.7152 * rgba[1] +
                                0.0722 * rgba[2])
                        gray += (255.0 - gray) * lift
                        rgba[:3] = [gray, gray, gray]
                        scalars.SetTuple(cell_index, rgba)
                    scalars.Modified()
            elif self.axis_enabled is not None:
                # Enabled transform icons carry intrinsic red/green/blue cell
                # colours. Black out the colours belonging to locked axes.
                source_polydata = input_points
                input_points = vtk.vtkPolyData()
                input_points.DeepCopy(source_polydata)
                scalars = input_points.GetCellData().GetScalars()
                if scalars is not None:
                    for cell_index in range(scalars.GetNumberOfTuples()):
                        rgba = list(scalars.GetTuple(cell_index))
                        rgb = rgba[:3]
                        largest = max(range(3), key=rgb.__getitem__)
                        ordered = sorted(rgb, reverse=True)
                        is_axis_color = (ordered[0] > 0 and
                                         ordered[0] >= ordered[1] * 1.2)
                        if is_axis_color and not self.axis_enabled[largest]:
                            rgba[:3] = [0, 0, 0]
                            scalars.SetTuple(cell_index, rgba)

            self.pd = input_points
            return input_points

        pd = vtk.vtkPolyData()



        colors = vtk.vtkUnsignedCharArray()
        colors.SetNumberOfComponents(4)

        points = vtk.vtkPoints()
        cells = vtk.vtkCellArray()
        append_filter = vtk.vtkAppendPolyData()


        if isinstance(input_points, list):


            vertex_counter = 0

            opacity_255 = int(self.opacity * 255)

            for shape in input_points:

                shape_vtk_points = vtk.vtkPoints()
                shape_vtk_cells = vtk.vtkCellArray()
                shape_vtk_colors = vtk.vtkUnsignedCharArray()
                shape_vtk_colors.SetNumberOfComponents(4)
                shape_pd = vtk.vtkPolyData()



                shape_vertices = np.array(shape[0])
                shape_indices = np.array(shape[1])
                shape_color = np.array(shape[2])

                logger.debug("%s %s %s", shape_vertices.shape, shape_indices.shape, shape_color.shape)

                if shape_vertices.ndim != 2 or shape_vertices.shape[1] != 2:
                    raise ValueError("Shape vertices must be a 2D array with shape (N, 2)")
                if shape_indices.ndim != 2:
                    raise ValueError("Shape indices must be a 2D array with shape (M, K) where K is the number of vertices per cell")
                if shape_color.shape != (3,):
                    raise ValueError("Shape color must be a 1D array with 3 elements representing RGB values")


                if self.invert_y:
                    shape_vertices[:, 1] = 1.0 - shape_vertices[:, 1]

                # total_vertices = shape_vertices.shape[0]



                for i, (x, y) in enumerate(shape_vertices):
                    pid = shape_vtk_points.InsertNextPoint(x, y, 0.0)
                for cell in shape_indices:
                    polygon = vtk.vtkPolygon()
                    polygon.GetPointIds().SetNumberOfIds(len(cell))
                    shape_vtk_colors.InsertNextTuple4(int(shape_color[0] * 255), int(shape_color[1] * 255), int(shape_color[2] * 255), opacity_255)

                    for j, idx in enumerate(cell):
                        polygon.GetPointIds().SetId(j, idx + vertex_counter)
                    shape_vtk_cells.InsertNextCell(polygon)

                # vertex_counter += total_vertices



                shape_pd.SetPoints(shape_vtk_points)
                shape_pd.SetPolys(shape_vtk_cells)
                shape_pd.GetCellData().SetScalars(shape_vtk_colors)

                append_filter.AddInputData(shape_pd)

            append_filter.Update()

            pd.DeepCopy(append_filter.GetOutput())
            # let's clean the polydata to ensure it's optimized for rendering
            cleaner = vtk.vtkCleanPolyData()
            cleaner.SetInputData(pd)
            cleaner.PointMergingOn()
            cleaner.Update()

            pd = cleaner.GetOutput()

            self.pd = pd

            return pd


        elif isinstance(input_points, np.ndarray):

            polygon = vtk.vtkPolygon()
            polygon.GetPointIds().SetNumberOfIds(input_points.shape[0])

            # color_rbga = self.color_to_RGBA_255(self.color, opacity=1.0)

            color_rgba = [int(self.color[0] * 255), int(self.color[1] * 255), int(self.color[2] * 255), 255]  # orange color

            for i, (x, y) in enumerate(input_points):
                pid = points.InsertNextPoint(x, y, 0.0)
                polygon.GetPointIds().SetId(i, pid)

                colors.InsertNextTuple4(color_rgba[0], color_rgba[1], color_rgba[2], color_rgba[3])


            cells.InsertNextCell(polygon)
            pd.SetPoints(points)
            pd.SetPolys(cells)
            pd.GetCellData().SetScalars(colors)

            return pd

        else:
            raise ValueError("Unsupported input_points type for build_symbols", type(input_points))

    @staticmethod
    def _build_cached_icon(source_path, vtk_path=None):
        """Convert an SVG/PNG icon (never plotting) and cache it as .vtk.

        Returns the icon polydata read back through the normal .vtk loader
        so it matches pre-built icons exactly; if the cache cannot be
        written, the converted shapes are returned instead.
        """
        import copy
        if source_path.endswith(".svg"):
            shapes = _icon_converter().convert_svg_to_triangles(
                source_path, plot=False, triangulate_opts='pq10')
        else:
            shapes = _icon_converter().convert_image_to_triangles(
                source_path, ignore_background=False, show_plots=False)
        if vtk_path:
            try:
                os.makedirs(os.path.dirname(vtk_path) or ".", exist_ok=True)
                # save_shapes_as_polydata flips the shapes in place.
                _icon_converter().save_shapes_as_polydata(
                    copy.deepcopy(shapes), vtk_path)
                logger.debug(f"{bcolors.OKGREEN}Built icon cache {vtk_path} from {source_path}{bcolors.ENDC}")
                reader = vtk.vtkPolyDataReader()
                reader.SetFileName(vtk_path)
                reader.Update()
                return reader.GetOutput()
            except OSError as exc:
                logger.warning(f"{bcolors.WARNING}Could not cache icon {vtk_path}: {exc}{bcolors.ENDC}")
        return shapes

    def SetAxisEnabled(self, axes):
        """Mask intrinsic RGB axis colours using three capability booleans."""
        self.axis_enabled = tuple(bool(value) for value in axes)
        self.pd = None
        self.Modified()

    def convert_xy_to_screen(self, x, y, window_size=(800, 600), pixel_offset=(200, 200), xy_offset=(0.0, 0.0)):

        """Convert xy to screen."""
        px = ((x - xy_offset[0]) * window_size[0]) + pixel_offset[0]
        py = ((y - xy_offset[1]) * window_size[1]) + pixel_offset[1]

        return px, py


    def scale_polydata(self, polydata, window_size=(800, 600), pixel_offset=(200, 200), xy_offset=(0.0, 0.0)):
        """Execute the scale polydata operation."""
        # Never transform the cached, normalized icon geometry in place.  The
        # context painter calls this on every render; mutating the cache here
        # compounds display coordinates until the icon moves off-screen.
        # Topology and colours are shared (ShallowCopy); only the points are
        # replaced, transformed in one vectorised step.
        scaled = vtk.vtkPolyData()
        scaled.ShallowCopy(polydata)
        points = polydata.GetPoints()
        new_points = vtk.vtkPoints()
        if points is not None and points.GetNumberOfPoints():
            xy = vtk_to_numpy(points.GetData())[:, :2].astype(float)
            screen = np.zeros((xy.shape[0], 3))
            screen[:, 0] = (xy[:, 0] - xy_offset[0]) * window_size[0] + pixel_offset[0]
            screen[:, 1] = (xy[:, 1] - xy_offset[1]) * window_size[1] + pixel_offset[1]
            new_points.SetData(numpy_to_vtk(screen, deep=True))
        scaled.SetPoints(new_points)


        return scaled

    # --- SVG parsing into vtkPath ---
    def _parse_svg_path(self, svg_path_str):
        """Parse svg path."""
        path = vtk.vtkPath()
        import re
        tokens = re.findall(r"[MmLlZz]|-?\d+\.?\d*", svg_path_str)
        i = 0
        # cur = [0, 0]
        mode = None
        while i < len(tokens):
            t = tokens[i]
            if t in "MmLlZz":
                mode = t
                i += 1
                continue
            x = float(t)
            y = float(tokens[i + 1])
            i += 2
            if mode in ("M", "L"):
                # cur = [x, y]
                if path.GetNumberOfPoints() == 0 or mode == "M":
                    path.InsertNextPoint([x, y, 0], 0)
                    # path.InsertNextCell(vtk.vtkPath.MOVE_TO, 1, [path.GetNumberOfPoints()-1])
                else:
                    path.InsertNextPoint([x, y, 0], 0)
                    # path.InsertNextCell(vtk.vtkPath.LINE_TO, 1, [path.GetNumberOfPoints()-1])
            elif mode == "Z" or mode == "z":
                # path.InsertNextCell(vtk.vtkPath.CLOSE, 0, [])
                pass
        return path

    def _make_painter(self):
        """Creates an object with a Paint(painter) method."""
        button = self

        painter = vtk.vtkPythonItem()

        class Painter():

            def Initialize(self, vtkSelf=None):
                """Execute the initialize operation."""
                return True


            @profiled_paint("VectorButtonWidget")
            def Paint(self, painter):


                """Execute the paint operation."""
                painter.PushMatrix()

                pen = painter.GetPen()
                # brush = painter.GetBrush()


                if button.color is not None:
                    r, g, b = button.color
                    pen.SetColor(int(r * 255), int(g * 255), int(b * 255), 255)
                    pen.SetWidth(2)


                window_size = button.interactor.GetRenderWindow().GetSize()

                paint_bounds = button._paint_bounds()
                button_size = [
                    (paint_bounds[1] - paint_bounds[0]) * window_size[0],
                    (paint_bounds[3] - paint_bounds[2]) * window_size[1]]
                button_bottom_left = (
                    paint_bounds[0] * window_size[0],
                    paint_bounds[2] * window_size[1])


                if getattr(button, "background_style", None) == "rounded":
                    for tile in button._tile_polydata(
                            button_bottom_left, button_size):
                        painter.DrawPolyData(
                            0.0, 0.0, tile, tile.GetCellData().GetScalars(),
                            vtk.VTK_SCALAR_MODE_USE_CELL_DATA)
                    # Inset the icon so the tile frames it.
                    inset = 0.14
                    button_bottom_left = (
                        button_bottom_left[0] + button_size[0] * inset,
                        button_bottom_left[1] + button_size[1] * inset)
                    button_size = [button_size[0] * (1 - 2 * inset),
                                   button_size[1] * (1 - 2 * inset)]

                if button.show_background:
                    painter.GetBrush().SetColor(200, 200, 200, 255)
                    painter.DrawRect(paint_bounds[0] * window_size[0],
                                    paint_bounds[2] * window_size[1],
                                    button_size[0],
                                    button_size[1])

                # Icon geometry only changes when the state (pd reset), the
                # bounds or the window size change; rebuilding and rescaling
                # it on every frame was the dominant cost of the 2D UI.
                if button.pd is None:
                    button.build_symbols(button.input_data)
                source = button.pd
                if source is None:  # array input paths do not cache
                    source = button.build_symbols(button.input_data)
                button.polydata = source
                cache_key = (id(source), source.GetMTime(),
                             tuple(window_size), tuple(paint_bounds))
                if getattr(button, "_paint_cache_key", None) != cache_key:
                    button._paint_cache = button.scale_polydata(
                        source, window_size=button_size,
                        pixel_offset=button_bottom_left, xy_offset=(0.0, 0.0))
                    button._paint_cache_key = cache_key
                scaled_polydata = button._paint_cache
                if not button.enabled and not button.grayscale and \
                        button.DISABLED_OPACITY < 1.0:
                    scaled_polydata = button._dimmed(scaled_polydata)

                painter.DrawPolyData(
                    0.0,
                    0.0,
                    scaled_polydata,
                    scaled_polydata.GetCellData().GetScalars(),
                    vtk.VTK_SCALAR_MODE_USE_CELL_DATA,
                )

                painter.PopMatrix()

                return True

        painter.SetPythonObject(Painter)

        return painter

    def _update_pixel_bounds(self):
        """Update pixel bounds."""
        rw = self.interactor.GetRenderWindow()
        size = rw.GetSize()
        if len(self.normalized_bounds) == 4:
            nx0, nx1, ny0, ny1 = self.normalized_bounds
        elif len(self.normalized_bounds) == 6:
            nx0, nx1, ny0, ny1, _, _ = self.normalized_bounds

        # if self.equal_aspect_ratio:
        #     # Adjust bounds to maintain aspect ratio of the button
        #     aspect_ratio = (nx1 - nx0) / (ny1 - ny0)
        #     window_aspect = size[0] / size[1]
        #     if aspect_ratio > window_aspect:
        #         # Button is wider than window aspect, adjust height
        #         desired_height = (nx1 - nx0) / window_aspect
        #         center_y = (ny0 + ny1) / 2
        #         ny0 = center_y - desired_height / 2
        #         ny1 = center_y + desired_height / 2
        #     else:
        #         # Button is taller than window aspect, adjust width
        #         desired_width = (ny1 - ny0) * window_aspect
        #         center_x = (nx0 + nx1) / 2
        #         nx0 = center_x - desired_width / 2
        #         nx1 = center_x + desired_width / 2

        if self.equal_aspect_ratio:
            width_pixels = abs(nx1 - nx0) * size[0]
            height_pixels = abs(ny1 - ny0) * size[1]
            square_pixels = min(width_pixels, height_pixels)
            center_x = (nx0 + nx1) * .5
            center_y = (ny0 + ny1) * .5
            half_width = square_pixels / (2 * max(size[0], 1))
            half_height = square_pixels / (2 * max(size[1], 1))
            nx0, nx1 = center_x - half_width, center_x + half_width
            ny0, ny1 = center_y - half_height, center_y + half_height

        x0 = int(nx0 * size[0])
        x1 = int(nx1 * size[0])
        y0 = int(ny0 * size[1])
        y1 = int(ny1 * size[1])
        self.pixel_bounds = [x0, x1, y0, y1]

    def _on_style_state(self, new=frozenset(), old=frozenset()):
        # Only repaint for states this button shows: "disabled" always,
        # hover/pressed/checked only on a rounded tile.
        changed = set(new) ^ set(old)
        shown = {"disabled"}
        if getattr(self, "background_style", None) == "rounded":
            shown |= {"hover", "pressed", "checked"}
        if changed & shown:
            self.Modified()
            self.requestRender()

    def _tile_colors(self):
        """Tile fill and border for the current style state (``Style``)."""
        from .style import Style

        states = set(self.styleState())
        if "disabled" in states:
            states -= {"hover", "pressed"}       # no hover response
        style = Style.for_renderer(self.renderer)
        theme = getattr(self.renderer, "theme", None)
        if getattr(theme, "tokens", None) is None:
            # No theme tokens: the historical colours.
            fill = theme_value(self.renderer, "button_color",
                               (0.93, 0.94, 0.96))
            border = theme_value(self.renderer, "border_color",
                                 (0.75, 0.77, 0.8))
            if "hover" in states or "checked" in states:
                fill = theme_value(self.renderer, "button_hover_color",
                                   (0.88, 0.9, 0.93))
            return fill, border
        return (style.color("button", "background", states, widget=self),
                style.color("button", "border", states, widget=self))

    def _dimmed(self, polydata):
        """``polydata`` with its colours at DISABLED_OPACITY (cached)."""
        key = (id(polydata), polydata.GetMTime())
        cached = getattr(self, "_dimmed_cache", None)
        if cached is not None and cached[0] == key:
            return cached[1]
        scalars = polydata.GetCellData().GetScalars()
        if scalars is None or scalars.GetNumberOfComponents() != 4:
            return polydata
        dimmed = vtk.vtkPolyData()
        dimmed.ShallowCopy(polydata)
        colors = vtk.vtkUnsignedCharArray()
        colors.DeepCopy(scalars)
        for index in range(colors.GetNumberOfTuples()):
            r, g, b, a = colors.GetTuple4(index)
            colors.SetTuple4(index, r, g, b,
                             int(round(a * self.DISABLED_OPACITY)))
        dimmed.GetCellData().SetScalars(colors)
        self._dimmed_cache = (key, dimmed)
        return dimmed

    def _tile_polydata(self, bottom_left, size):
        """Cached rounded-square tile (border + fill) behind the icon."""
        fill, border = self._tile_colors()
        key = (round(bottom_left[0]), round(bottom_left[1]),
               round(size[0]), round(size[1]), tuple(fill), tuple(border))
        if getattr(self, "_tile_key", None) != key:
            x, y = bottom_left
            w, h = size
            radius = 0.22 * min(w, h)
            self._tile_pds = [
                rounded_rect_polydata(x, y, w, h, (radius,) * 4, _rgba255(border)),
                rounded_rect_polydata(x + 1.5, y + 1.5, w - 3, h - 3,
                                      (max(0.0, radius - 1.5),) * 4, _rgba255(fill)),
            ]
            self._tile_key = key
        return self._tile_pds

    def _paint_bounds(self):
        """Return the aspect-corrected normalized bounds used for painting."""
        self._update_pixel_bounds()
        width, height = self.interactor.GetRenderWindow().GetSize()
        width, height = max(width, 1), max(height, 1)
        x0, x1, y0, y1 = self.pixel_bounds
        return x0 / width, x1 / width, y0 / height, y1 / height

    def _point_in_bounds(self, x, y):
        """Execute the point in bounds operation."""
        x0, x1, y0, y1 = self.pixel_bounds
        return x0 <= x <= x1 and y0 <= y <= y1

    def _on_click(self, obj, ev):
        """Handle click."""
        pos = self.interactor.GetEventPosition()
        if self.enabled and self._shown:
            self._update_pixel_bounds()
            if self._point_in_bounds(pos[0], pos[1]):
                self.setFocus(reason="mouse")
                self.pressed.emit()
                old_state = self.state
                if self.total_states > 1:
                    self.state = (self.state + 1) % self.total_states
                    self.input_data = self.input_states[
                        self.state % len(self.input_states)]
                    self.color = self.color_states[
                        self.state % len(self.color_states)]
                    self.grayscale = self.grayscale_states[
                        self.state % len(self.grayscale_states)]
                    self.tint = self.tint_states[
                        self.state % len(self.tint_states)]
                    self.pd = None
                    self.Modified()
                else:
                    # Action buttons with one icon have no visual state to
                    # toggle; they remain in their sole state but still fire.
                    self.state = 0

                if self.callback:
                    logger.debug("VectorButtonWidget state changed to %s", self.state)
                    self.callback(self, vtk.vtkCommand.StateChangedEvent)
                else:
                    logger.debug("VectorButtonWidget state changed to %s", self.state)
                    logger.debug("No legacy callback defined for VectorButtonWidget")
                self.clicked.emit(self.isChecked())
                if self.state != old_state:
                    self.toggled.emit(self.isChecked())
                    self.updateStyleState()
                self.released.emit()

    def stateValue(self):
        return int(self.state)

    def setAction(self, action):
        """Drive this button from an ``Action`` (like ``QToolButton``).

        A click triggers the action (checkable buttons pass their new state);
        the action's availability, tool tip and checked state follow onto
        the button whenever it changes.
        """
        old = getattr(self, "_action", None)
        if old is not None:
            for signal, slot in ((old.changed, self._sync_from_action),
                                 (old.toggled, self._sync_checked)):
                try:
                    signal.disconnect(slot)
                except ValueError:
                    pass
        self._action = action
        if action is None:
            return
        self.callback = self._trigger_action
        action.changed.connect(self._sync_from_action, unique=True)
        action.toggled.connect(self._sync_checked, unique=True)
        self._sync_from_action()

    def action(self):
        return getattr(self, "_action", None)

    def _trigger_action(self, _widget=None, _event=None):
        action = self._action
        if action.isCheckable():
            # The click already moved the button to its new state.
            if action.isEnabled():
                action.setChecked(bool(self.state))
                action.triggered.emit(action.isChecked())
        else:
            action.trigger()

    def _sync_checked(self, checked=None):
        action = self._action
        if action is not None and action.isCheckable() and \
                bool(self.state) != action.isChecked():
            self.setState(1 if action.isChecked() else 0)
            self.Modified()

    def _sync_from_action(self):
        action = self._action
        self.enabled = action.isEnabled()
        self.hover_text = action.toolTip() or self.hover_text
        if self.hover_text and getattr(self, "interactive", True) and \
                ENABLE_HOVER_TEXT:
            get_hover_text_overlay(self.renderer, self.interactor).register(self)
        self._sync_checked()
        self.Modified()
        self.requestRender()

    def setState(self, state):
        old = self.state
        self.GetRepresentation().SetState(state)
        if old != self.state:
            self.toggled.emit(self.isChecked())
            self.updateStyleState()

    def isChecked(self):
        return bool(self.state)

    def setChecked(self, checked):
        self.setState(1 if checked else 0)

    def toggle(self):
        self.setState((self.state + 1) % max(1, self.total_states))

    def click(self):
        self.pressed.emit()
        self.toggle()
        if self.callback is not None:
            self.callback(self, vtk.vtkCommand.StateChangedEvent)
        self.clicked.emit(self.isChecked())
        self.released.emit()

    def saveState(self):
        state = super().saveState()
        state['state'] = self.stateValue()
        return state

    def restoreState(self, state):
        if 'state' in state:
            self.setState(state['state'])
        return super().restoreState({
            key: state[key] for key in (
                'objectName', 'enabled', 'visible', 'geometry',
                'toolTip', 'statusTip') if key in state})

    def SetVisibility(self, visible):
        """
        Sets the visibility of the SVG button widget.
        Args:
            visible (bool): True to make the widget visible, False to hide it.
        """
        self._shown = bool(visible)
        self.actor.SetVisibility(1 if visible else 0)

    def GetVisibility(self):
        return self._shown

    def SetEnabled(self, enabled):
        """Show or hide the button (container protocol, as on VTK widgets).

        This does not change availability; set ``enabled`` (or call
        ``setEnabled``) to grey out or lock a visible button.
        """
        self.SetVisibility(enabled)

    def isEnabled(self):
        """Qt-style availability (independent of visibility)."""
        return bool(self.enabled)

    def setEnabled(self, enabled):
        self.enabled = bool(enabled)      # the property notifies

    def isVisible(self):
        return bool(self._shown)

    def SetPosition(self, x, y, width=None, height=None):
        """
        Sets the position of the SVG button widget.
        Args:
            x (float): The x-coordinate of the button's position in normalized
                viewport coordinates.
            y (float): The y-coordinate of the button's position in normalized
                viewport coordinates.
        """
        if width is None:
            width = self.normalized_bounds[1] - self.normalized_bounds[0]
        if height is None:
            height = self.normalized_bounds[3] - self.normalized_bounds[2]

        self.normalized_bounds = (x, x + width, y, y + height)
        self._update_pixel_bounds()

    def SetBounds(self, x0, x1, y0, y1):
        """Sets the bounds of the SVG button widget.
        Args:
            x0 (float): The minimum x-coordinate of the button's bounds in normalized
                viewport coordinates.
            x1 (float): The maximum x-coordinate of the button's bounds in normalized
                viewport coordinates.
            y0 (float): The minimum y-coordinate of the button's bounds in normalized
                viewport coordinates.
            y1 (float): The maximum y-coordinate of the button's bounds in normalized
                viewport coordinates.
        """
        self.normalized_bounds = (x0, x1, y0, y1)
        self._update_pixel_bounds()

    def defaultSizePolicy(self):
        return SizePolicy(SizePolicy.Fixed, SizePolicy.Fixed)

    def sizeHint(self):
        return (32.0, 32.0)

    def minimumSizeHint(self):
        return (20.0, 20.0)

    def GetBounds(self):
        """Gets the bounds of the SVG button widget.
        Returns:
            tuple: A tuple containing the bounds of the button in normalized viewport coordinates
                (x0, x1, y0, y1).
        """
        return self.normalized_bounds

    def GetEnabled(self):
        """Whether the button is shown (container protocol; see SetEnabled)."""
        return self._shown

    def SetSize(self, width, height):
        # """
        # Sets the size of the SVG button widget.
        # Args:
        #     width (float): The width of the button in normalized viewport coordinates.
        #     height (float): The height of the button in normalized viewport coordinates.
        # """
        """Execute the set size operation."""
        x0 = self.normalized_bounds[0]
        y0 = self.normalized_bounds[2]

        self.normalized_bounds = (x0, x0 + width, y0, y0 + height)
        self._update_pixel_bounds()

        pass

    def make_representation(self):
        """
        Creates the representation of the SVG button widget.
        Returns:
            vtkPythonItem: The representation of the SVG button widget.

        """

        class VectorButtonRepresentation():
            def __init__(self, button_widget):
                """Initialize the instance."""
                self.button_widget = button_widget

            def GetState(self):
                """Execute the get state operation."""
                return self.button_widget.state

            def SetState(self, state):
                """Select a state and its corresponding vector geometry."""
                button = self.button_widget
                button.state = (int(state) % button.total_states
                                if button.total_states > 1 else 0)
                button.input_data = button.input_states[
                    button.state % len(button.input_states)]
                button.color = button.color_states[
                    button.state % len(button.color_states)]
                button.grayscale = button.grayscale_states[
                    button.state % len(button.grayscale_states)]
                button.tint = button.tint_states[
                    button.state % len(button.tint_states)]
                button.pd = None
                button.Modified()

            def SetColor(self, color):
                """Execute the set color operation."""
                button = self.button_widget
                button.color_states = [color]
                button.color = color

            def GetColor(self):
                """Execute the get color operation."""
                return self.button_widget.color


        self.Representation = VectorButtonRepresentation(self)

        return

    def GetRepresentation(self):
        """
        Gets the representation of the SVG button widget.
        Returns:
            vtkPythonItem: The representation of the SVG button widget.
        """
        return self.Representation

    def Delete(self):
        """
        Deletes the SVG button widget from the renderer.
        """
        self.enabled = False
        self.callback = None
        tracker = _LegacyHoverTracker._instances.get(self.interactor)
        if tracker is not None:
            tracker.discard(self)
        observer_id = getattr(self, '_click_observer_id', None)
        if observer_id is not None and self.interactor is not None:
            self.interactor.RemoveObserver(observer_id)
            self._click_observer_id = None
        if self.scene is not None and self.painter is not None:
            self.scene.RemoveItem(self.painter)
        ui_layer(self.renderer).RemoveActor(self.actor)
        del self

    def Modified(self):

        """Execute the modified operation."""
        self.painter.Modified()


class value_wrapper:
    def __init__(self, value):
        """Initialize the instance."""
        self.value = value
    def SetValue(self, *args):
        """Execute the set value operation."""
        val = []
        for arg in args:
            val.append(arg)
        if len(val) == 1:
            val = val[0]
        self.value = val
    def GetValue(self):
        """Execute the get value operation."""
        return self.value
    def SetCoordinateSystemToNormalizedDisplay(self):
        """Execute the set coordinate system to normalized display operation."""
        pass
    def __getitem__(self, index):
        """Execute the getitem operation."""
        if isinstance(self.value, (list, tuple, np.ndarray)):
            return self.value[index]
        else:
            raise TypeError(f"'{type(self.value).__name__}' object is not subscriptable")
    def __setitem__(self, index, value):
        """Execute the setitem operation."""
        if isinstance(self.value, list):
            self.value[index] = value
        elif isinstance(self.value, tuple):
            # Convert tuple to list, modify, then convert back
            temp_list = list(self.value)
            temp_list[index] = value
            self.value = tuple(temp_list)
        elif isinstance(self.value, np.ndarray):
            self.value[index] = value
        else:
            raise TypeError(f"'{type(self.value).__name__}' object does not support item assignment")
    def __repr__(self):
        """Return the developer-facing representation."""
        return f"value_wrapper({self.value})"

class ValueChangerWidget(WidgetMixin):
    # Soft X/Y/Z colours for the axis letter inside the field (as in Qt).
    AXIS_COLORS = {"X": (0.85, 0.33, 0.33), "Y": (0.36, 0.72, 0.36),
                   "Z": (0.36, 0.52, 0.90)}

    def _centre_field_text(self):
        """Vertically centre the value and axis letter inside the field."""
        if not getattr(self, "_themed", False) or not hasattr(self, "value_text_widget"):
            return
        x, y = self.Representation.position[0], self.Representation.position[1]
        width, height = self.Representation.size[0], self.Representation.size[1]
        centre = y + height / 2.0
        line = text_line_height(self.Representation.interactor,
                                self._field_text_size)
        place_text_centred(self.value_text_widget, x + height, centre,
                           max(0.001, width - 2 * height), line, centre_x=True)
        label = getattr(self, "prepended_text_widget", None)
        if label is not None:
            place_text_centred(label, x - height, centre, height,
                               text_line_height(self.Representation.interactor,
                                                self._field_text_size, True),
                               centre_x=True)

    def _field_bounds(self):
        """Field spans the axis label slot through the right stepper."""
        x, y = self.Representation.position[0], self.Representation.position[1]
        width, height = self.Representation.size[0], self.Representation.size[1]
        label = height if self.Representation.prepended_text is not None else 0.0
        grow = 0.04 * height        # slightly taller; rows keep a small gap
        return (x - label, x + width, y - grow, y + height + grow)

    def _place_steppers(self):
        """Smaller ‹ › chevrons, centred in their square slots."""
        if not getattr(self, "_themed", False):
            return
        x, y = self.Representation.position[0], self.Representation.position[1]
        width, height = self.Representation.size[0], self.Representation.size[1]
        window_width, window_height = self.Representation.interactor.GetRenderWindow().GetSize()
        side_px = 0.55 * height * max(1, window_height)
        sx, sy = side_px / max(1, window_width), side_px / max(1, window_height)
        cy = y + height / 2.0
        for button, cx in ((self.left_button, x + height / 2.0),
                           (self.right_button, x + width - height / 2.0)):
            button.SetBounds(cx - sx / 2.0, cx + sx / 2.0, cy - sy / 2.0, cy + sy / 2.0)

    @ui_scoped
    def __init__(self, renderer, interactor, initial_value, min_value, max_value,
                 step=1, position=(0.0, 0.0), size=(0.2, 0.05), name=None,
                 use_relative_position=True, callback=None, prepended_text=None,
                 text_color=(0, 0, 0), text_size=12):

        """Initialize the instance."""
        self.initWidget(name)
        self.valueChanged = Signal(self)
        self.editingFinished = Signal(self)
        self.Representation = self.Representation(min_value, max_value, initial_value,
                                                 renderer, interactor,
                                                 position=position, size=size,
                                                 step=step, name=name,
                                                 use_relative_position=use_relative_position,
                                                 prepended_text=prepended_text)

        self.callback = callback

        def set_value_on_drag_callback(obj, event=None):
            """Set value on drag callback."""
            logger.debug("%s %s", "Drag callback invoked", time.time())
            self.set_value_from_drag()
            if self.callback is not None:
                self.callback(property_name=self.Representation.name, new_value=self.Representation.current_value)

        def decrease_value_callback(obj, event=None):
            """Handle the decrease value callback event."""
            self.decrease_value()
            if self.callback is not None:
                self.callback(property_name=self.Representation.name, new_value=self.Representation.current_value)

        def increase_value_callback(obj, event=None):
            """Handle the increase value callback event."""
            self.increase_value()
            if self.callback is not None:
                self.callback(property_name=self.Representation.name, new_value=self.Representation.current_value)

        self.elements = []

        # self.background_widget = PanelBackgroundWidget(
        #     renderer=self.Representation.renderer,
        #     interactor=self.Representation.interactor,
        #     panel_bounds=(self.Representation.position[0],
        #                   self.Representation.position[0] + self.Representation.size[0],
        #                   self.Representation.position[1],
        #                   self.Representation.position[1] + self.Representation.size[1]),
        #     panel_color=(0.8, 0.8, 0.8),
        #     opacity=0.5,
        #     border_width=2,
        #     buffer=0,
        #     grabbable=False,
        # )

        # self.elements.append(background_widget)

        # self.draggable_area_widget = drag_patch_widget(
        #     renderer=self.Representation.renderer,
        #     interactor=self.Representation.interactor,
        #     panel_bounds=(self.Representation.position[0] + self.Representation.size[1], self.Representation.position[0] + self.Representation.size[0] - self.Representation.size[1],
        #                   self.Representation.position[1], self.Representation.position[1] + self.Representation.size[1]),
        #     panel_color=(0.8, 0.8, 0.8),
        #     opacity=0.5,
        #     border_width=2,
        #     buffer=0,
        #     grabbable=True,
        #     callback=set_value_on_drag_callback
        # )

        # self.elements.append(self.draggable_area_widget)

        text_position = (self.Representation.position[0] + self.Representation.size[1], self.Representation.position[1])


        def end_of_edit_callback(property_name, new_value):
            """Handle the end of edit callback event."""
            self.SetValue(new_value)
            if self.callback is not None:
                self.callback(property_name=self.Representation.name,
                              new_value=self.Representation.current_value)
            self.editingFinished.emit()



        # Blender-style field: one rounded, recessed field holding the axis
        # letter, quiet ‹ › steppers and the centred value. Created first so
        # it paints beneath the text and buttons.
        renderer_ = self.Representation.renderer
        self._themed = getattr(renderer_, "theme", None) is not None
        if self._themed:
            self.background_widget = VectorPanelBackground(
                renderer=renderer_, interactor=self.Representation.interactor,
                bounds=self._field_bounds(),
                panel_color=theme_value(renderer_, "well_color", (0.9, 0.9, 0.9)),
                border_color=theme_value(renderer_, "border_color", (0.6, 0.6, 0.6)),
                border_width=1.5, corner_radius=1000.0, opacity=1,   # pill
                movable=False, resizable=False, name="value_field",
                ui_z_order=UI_Z_PANEL_BACKGROUND + 5)
        stepper_color = theme_value(renderer_, "muted_text_color", None)
        if self._themed:
            # One fixed size for the value and the axis letter.
            text_size = max(10, panel_title_text_size(
                self.Representation.interactor) - 4)
        self._field_text_size = text_size

        self.value_text_widget = TextWidget(
            renderer=self.Representation.renderer,
            interactor=self.Representation.interactor,
            text=f"{self.Representation.initial_value:.2f}",
            position=text_position,
            size=(self.Representation.size[0] - (2 * self.Representation.size[1]), self.Representation.size[1]),
            grabbable=False,
            editable=True,
            force_to_float=True,
            end_of_edit_callback=end_of_edit_callback,
            text_color=text_color,
            text_size=text_size,
            scale_text_to_widget=False,
            fit_text_to_bounds=not self._themed,
            horizontal_alignment="center" if self._themed else "left",
        )


        # self.elements.append(value_text_widget)




        self.left_button = VectorButtonWidget(
            renderer=self.Representation.renderer,
            interactor=self.Representation.interactor,
            input_data=os.path.join(ICON_ROOT, "vtk_icons",
                "chevron_left.vtk" if self._themed else "minus.vtk"),
            callback=decrease_value_callback,
            bounds=(self.Representation.position[0], self.Representation.position[0] + self.Representation.size[1],
                    self.Representation.position[1], self.Representation.position[1] + self.Representation.size[1]),
            color=stepper_color if self._themed else (1, 0, 0),
            initial_state=0,
            enabled=self.Representation.enabled,
            show_background=False,
            grabbable=False
        )

        # self.elements.append(left_button)

        self.right_button = VectorButtonWidget(
            renderer=self.Representation.renderer,
            interactor=self.Representation.interactor,
            input_data=os.path.join(ICON_ROOT, "vtk_icons",
                "chevron_right.vtk" if self._themed else "plus.vtk"),
            callback=increase_value_callback,
            bounds=(self.Representation.position[0] + self.Representation.size[0] - self.Representation.size[1], self.Representation.position[0] + self.Representation.size[0],
                    self.Representation.position[1], self.Representation.position[1] + self.Representation.size[1]),
            color=stepper_color if self._themed else (0, 1, 0),
            initial_state=0,
            enabled=True,
            show_background=False,
            grabbable=False
        )


        if self.Representation.prepended_text is not None:
            axis = self.Representation.prepended_text.replace(":", "").strip().upper()
            label_text = axis if (self._themed and axis in self.AXIS_COLORS) \
                else self.Representation.prepended_text
            self.prepended_text_widget = TextWidget(
                renderer=self.Representation.renderer,
                interactor=self.Representation.interactor,
                text=label_text,
                position=(self.Representation.position[0] - 0.05, self.Representation.position[1]),
                size=(0.05, self.Representation.size[1]),
                grabbable=False,
                bold=self._themed,
                horizontal_alignment="center" if self._themed else "left",
                text_color=(self.AXIS_COLORS.get(axis, text_color)
                            if self._themed else text_color),
                text_size=text_size,
                scale_text_to_widget=False,
                fit_text_to_bounds=not self._themed,
            )
            # self.elements.append(self.prepended_text_widget)

        else:
            self.prepended_text_widget = None


    class Representation:
        def __init__(self, min_value, max_value, initial_value, renderer, interactor,
                     position=(0.0, 0.0), size=(0.2, 0.05), step=1, name=None, use_relative_position=True,
                     enabled=True, prepended_text=None):
            """Initialize the instance."""
            self.min_value = min_value
            self.max_value = max_value
            self.initial_value = initial_value
            self.current_value = initial_value
            self.min_value = min_value
            self.max_value = max_value
            self.renderer = renderer
            self.interactor = interactor
            self.name = name
            # self.width = size[0]
            # self.height = size[1]
            self.step_increment = step
            self.position = value_wrapper(position)
            self.size = value_wrapper(size)
            self.use_relative_position = use_relative_position
            self.enabled = enabled
            self.prepended_text = prepended_text

        def GetPositionCoordinate(self):
            """Execute the get position coordinate operation."""
            return self.position
            # pass

        def GetPosition2Coordinate(self):
            """Execute the get position2 coordinate operation."""
            return self.size
            # pass


    def viewportSource(self):
        """Renderer and interactor live on the representation."""
        renderer = self.Representation.renderer
        overlay = getattr(renderer, "ui_overlay", None)
        return renderer if overlay is None else overlay

    def renderScheduler(self):
        from .core import RenderScheduler

        interactor = self.Representation.interactor
        return RenderScheduler.for_window(interactor.GetRenderWindow(),
                                          interactor)

    def _label_width(self, height):
        return height if self.Representation.prepended_text is not None else 0.0

    def GetBounds(self):
        """Bounds including the axis label slot, as viewport fractions."""
        x, y = self.Representation.position[0], self.Representation.position[1]
        width, height = self.Representation.size[0], self.Representation.size[1]
        label = self._label_width(height)
        return (x - label, x + width, y, y + height)

    def SetBounds(self, x0, x1, y0, y1):
        height = y1 - y0
        label = self._label_width(height)
        self.Representation.position.SetValue(x0 + label, y0)
        self.Representation.size.SetValue(max(0.0, x1 - x0 - label), height)
        self.Modified()

    def defaultSizePolicy(self):
        return SizePolicy(SizePolicy.Expanding, SizePolicy.Fixed)

    def sizeHint(self):
        label = 26.0 if self.Representation.prepended_text is not None else 0.0
        return (140.0 + label, 26.0)

    def minimumSizeHint(self):
        # Two square stepper slots plus room for a short number.
        label = 22.0 if self.Representation.prepended_text is not None else 0.0
        return (80.0 + label, 22.0)

    def GetRepresentation(self):
        """Execute the get representation operation."""
        return self.Representation

    def decrease_value(self):
        """Execute the decrease value operation."""
        new_value = self.Representation.current_value - self.Representation.step_increment
        self.SetValue(new_value)
        self.Representation.interactor.GetRenderWindow().Render()

    def increase_value(self):
        """Execute the increase value operation."""
        new_value = self.Representation.current_value + self.Representation.step_increment
        self.SetValue(new_value)
        self.Representation.interactor.GetRenderWindow().Render()

    def set_value_from_drag(self, round_to_step=True):

        """Set value from drag."""
        current_screen_pos = self.Representation.interactor.GetEventPosition()
        rw = self.Representation.interactor.GetRenderWindow()
        size = rw.GetSize()

        relative_x = (current_screen_pos[0] - (self.Representation.position[0] * size[0])) / (self.Representation.size[0] * size[0])
        if relative_x < 0:
            relative_x = 0
        if relative_x > 1:
            relative_x = 1

        value_range = self.Representation.max_value - self.Representation.min_value
        new_value = self.Representation.min_value + (relative_x * value_range)

        if round_to_step:
            steps = round((new_value - self.Representation.min_value) / self.Representation.step_increment)
            new_value = self.Representation.min_value + (steps * self.Representation.step_increment)

        self.SetValue(new_value)
        if self.callback is not None:
            self.callback(property_name=self.Representation.name,
                          new_value=self.Representation.current_value)
        # self.Representation.current_value = new_value
        # self.value_text_widget.GetTextActor().SetInput(f"{self.Representation.current_value:.2f}")
        # self.value_text_widget.GetTextActor().Modified()
        # self.Representation.interactor.GetRenderWindow().Render()

    # def set_value(self, normalized_value):
    #     value_range = self.Representation.max_value - self.Representation.min_value
    #     actual_value = self.Representation.min_value + (normalized_value * value_range)
    #     self.value_setter(actual_value)

    def GetValue(self):
        """Current value (counterpart of SetValue)."""
        return self.Representation.current_value

    def value(self):
        return self.GetValue()

    def SetValue(self, value):

        """Execute the set value operation."""
        if not isinstance(value, (int, float)):
            try:
                value = float(value)
            except Exception as e:
                logger.warning(f"Error converting value to float: {e}")
                return

        if value < self.Representation.min_value:
            value = self.Representation.min_value
        if value > self.Representation.max_value:
            value = self.Representation.max_value
        old_value = self.Representation.current_value
        self.Representation.current_value = value
        self.value_text_widget.GetTextActor().SetInput(f"{self.Representation.current_value:.2f}")
        self._centre_field_text()   # width may change (e.g. 0.00 -> -10.00)
        self.value_text_widget.GetTextActor().Modified()
        if not math.isclose(old_value, value, rel_tol=0.0, abs_tol=1e-12):
            self.valueChanged.emit(value)
        # self.Representation.interactor.GetRenderWindow().Render()

    def setValue(self, value):
        self.SetValue(value)

    def minimum(self):
        return self.Representation.min_value

    def maximum(self):
        return self.Representation.max_value

    def setRange(self, minimum, maximum):
        minimum, maximum = float(minimum), float(maximum)
        if minimum > maximum:
            raise ValueError("minimum cannot exceed maximum")
        self.Representation.min_value = minimum
        self.Representation.max_value = maximum
        self.SetValue(self.value())

    def setMinimum(self, minimum):
        self.setRange(minimum, self.maximum())

    def setMaximum(self, maximum):
        self.setRange(self.minimum(), maximum)

    def singleStep(self):
        return self.Representation.step_increment

    def setSingleStep(self, step):
        step = float(step)
        if step <= 0:
            raise ValueError("single step must be greater than zero")
        self.Representation.step_increment = step

    def prefix(self):
        return self.Representation.prepended_text or ""

    def setPrefix(self, prefix):
        self.Representation.prepended_text = str(prefix)
        if self.prepended_text_widget is not None:
            self.prepended_text_widget.setText(prefix)

    def saveState(self):
        state = super().saveState()
        state.update({
            'value': self.value(),
            'minimum': self.minimum(),
            'maximum': self.maximum(),
            'singleStep': self.singleStep(),
            'prefix': self.prefix(),
        })
        return state

    def restoreState(self, state):
        if 'minimum' in state or 'maximum' in state:
            self.setRange(state.get('minimum', self.minimum()),
                          state.get('maximum', self.maximum()))
        if 'singleStep' in state:
            self.setSingleStep(state['singleStep'])
        if 'prefix' in state:
            self.setPrefix(state['prefix'])
        if 'value' in state:
            self.setValue(state['value'])
        return super().restoreState({
            key: state[key] for key in (
                'objectName', 'enabled', 'visible', 'geometry',
                'toolTip', 'statusTip') if key in state})

    def Modified(self):

        """Execute the modified operation."""
        if hasattr(self, 'background_widget'):
            self.background_widget.SetBounds(*self._field_bounds())

        if hasattr(self, 'draggable_area_widget'):

            self.draggable_area_widget.SetPosition(self.Representation.position[0] + self.Representation.size[1],
                                                self.Representation.position[1])
            self.draggable_area_widget.SetSize(self.Representation.size[0] - (2 * self.Representation.size[1]),
                                            self.Representation.size[1])
            self.draggable_area_widget.Modified()

        self.value_text_widget.SetPosition(self.Representation.position[0] + self.Representation.size[1],
                                          self.Representation.position[1])
        self.value_text_widget.SetSize(self.Representation.size[0] - (2 * self.Representation.size[1]),
                                      self.Representation.size[1])
        self.value_text_widget.RefitTextToBounds()
        self.value_text_widget.Modified()

        self.left_button.SetPosition(self.Representation.position[0],
                                     self.Representation.position[1])
        self.left_button.SetSize(self.Representation.size[1],
                                 self.Representation.size[1])
        self.left_button.Modified()

        self.right_button.SetPosition(self.Representation.position[0] + self.Representation.size[0] - self.Representation.size[1],
                                      self.Representation.position[1])
        self.right_button.SetSize(self.Representation.size[1],
                                 self.Representation.size[1])
        self.right_button.Modified()


        if self.prepended_text_widget is not None:
            self.prepended_text_widget.SetPosition(self.Representation.position[0] - self.Representation.size[1],
                                                  self.Representation.position[1])
            self.prepended_text_widget.SetSize(self.Representation.size[1],
                                              self.Representation.size[1])
            self.prepended_text_widget.RefitTextToBounds()
            self.prepended_text_widget.Modified()
        # Last, so the generic placement above does not undo it.
        self._centre_field_text()
        self._place_steppers()

        # for element in self.elements:
        #     if hasattr(element, 'Modified'):
        #         element.Modified()
        #     else:
        #         pass

    def SetEnabled(self, enabled):
        """Execute the set enabled operation."""
        self.Representation.enabled = enabled
        if hasattr(self, 'background_widget'):
            self.background_widget.SetEnabled(enabled)
        if hasattr(self, 'left_button'):
            self.left_button.SetEnabled(enabled)
        if hasattr(self, 'right_button'):
            self.right_button.SetEnabled(enabled)
        if hasattr(self, 'draggable_area_widget'):
            self.draggable_area_widget.SetEnabled(enabled)
        if hasattr(self, 'value_text_widget'):
            self.value_text_widget.SetEnabled(enabled)
        if self.prepended_text_widget is not None:
            self.prepended_text_widget.SetEnabled(enabled)


    def GetEnabled(self):
        """Execute the get enabled operation."""
        return self.Representation.enabled




class ColorPaletteWidget(WidgetMixin):
    """Python-painted colour swatches and a continuous 2D colour field."""

    # Matplotlib Tableau/tab20 colours followed by practical neutrals and
    # high-saturation accents. Values are stored as RGB floats for VTK.
    SWATCHES = [tuple(component / 255.0 for component in rgb) for rgb in (
        (31, 119, 180), (255, 127, 14), (44, 160, 44), (214, 39, 40),
        (148, 103, 189), (140, 86, 75), (227, 119, 194), (127, 127, 127),
        (188, 189, 34), (23, 190, 207),
        (174, 199, 232), (255, 187, 120), (152, 223, 138), (255, 152, 150),
        (197, 176, 213), (196, 156, 148), (247, 182, 210), (199, 199, 199),
        (219, 219, 141), (158, 218, 229),
        (0, 0, 0), (64, 64, 64), (128, 128, 128), (192, 192, 192),
        (255, 255, 255), (255, 0, 0), (255, 128, 0), (255, 255, 0),
        (0, 255, 0), (0, 255, 255), (0, 128, 255), (0, 0, 255),
        (128, 0, 255), (255, 0, 255), (255, 0, 128), (139, 69, 19),
    )]

    def __init__(self, renderer, interactor, callback=None,
                 bounds=(0.2, 0.4, 0.2, 0.4), mode='swatches'):
        self.renderer = renderer
        self.interactor = interactor
        self.initWidget('color_palette')
        self.colorChanged = Signal(self)
        self.colorSelected = Signal(self)
        self.callback = callback
        self.normalized_bounds = list(bounds[:4])
        self.panel_bounds = np.asarray((*bounds[:4], 0., 0.))
        self.panel_offset = np.asarray((0.5, -1.0))
        self.panel_size = np.asarray((1.0, 1.0))
        self.mode = mode
        self.enabled = True
        self.available = True
        self.selected_color = (0.5, 0.5, 0.5)
        self.actor = vtk.vtkContextActor()
        self.actor.IsUI = True
        self.actor.PickableOff()
        self.scene = self.actor.GetScene()
        ui_layer(renderer).AddActor(self.actor)
        register_ui_drawable(renderer, self, UI_Z_SCROLL_ROWS,
                             'actor_appearance_palette')
        self.painter = self._make_painter()
        self.scene.AddItem(self.painter)
        self._click_observer_id = self.ownObserver(
            interactor, 'LeftButtonPressEvent', self._on_click, 0.2)

    def _pixel_bounds(self):
        width, height = self.interactor.GetRenderWindow().GetSize()
        x0, x1, y0, y1 = self.normalized_bounds
        return x0 * width, x1 * width, y0 * height, y1 * height

    def _make_painter(self):
        widget = self
        item = vtk.vtkPythonItem()

        class Painter:
            def Initialize(self, vtk_self=None):
                return True

            @profiled_paint("ColorPaletteWidget")
            def Paint(self, painter):
                x0, x1, y0, y1 = widget._pixel_bounds()
                width, height = x1 - x0, y1 - y0
                alpha = 255 if widget.available else 85
                brush = painter.GetBrush()
                pen = painter.GetPen()
                pen.SetColor(35, 35, 35, alpha)
                pen.SetWidth(1)
                if widget.mode == 'swatches':
                    columns = 9
                    rows = int(np.ceil(len(widget.SWATCHES) / columns))
                    cell_w, cell_h = width / columns, height / rows
                    for index, color in enumerate(widget.SWATCHES):
                        column, row = index % columns, index // columns
                        brush.SetColor(*[int(c * 255) for c in color], alpha)
                        painter.DrawRect(x0 + column * cell_w,
                                         y1 - (row + 1) * cell_h,
                                         cell_w - 1, cell_h - 1)
                else:
                    # Adjacent cells overlap slightly, and a transparent pen
                    # prevents grid lines appearing in the continuous field.
                    pen.SetColor(0, 0, 0, 0)
                    columns, rows = 32, 20
                    cell_w, cell_h = width / columns, height / rows
                    for column in range(columns):
                        hue = column / max(columns - 1, 1)
                        for row in range(rows):
                            saturation = row / max(rows - 1, 1)
                            color = colorsys.hsv_to_rgb(hue, saturation, 1.0)
                            brush.SetColor(
                                *[int(c * 255) for c in color], alpha)
                            painter.DrawRect(x0 + column * cell_w,
                                             y0 + row * cell_h,
                                             cell_w + 1, cell_h + 1)
                return True

        item.SetPythonObject(Painter)
        return item

    def _on_click(self, caller, event):
        if not self.enabled or not self.available:
            return
        x, y = self.interactor.GetEventPosition()
        x0, x1, y0, y1 = self._pixel_bounds()
        if not (x0 <= x <= x1 and y0 <= y <= y1):
            return
        u = min(max((x - x0) / max(x1 - x0, 1), 0.0), 0.999999)
        v = min(max((y - y0) / max(y1 - y0, 1), 0.0), 0.999999)
        if self.mode == 'swatches':
            columns = 9
            rows = int(np.ceil(len(self.SWATCHES) / columns))
            row = min(int((1.0 - v) * rows), rows - 1)
            index = row * columns + int(u * columns)
            if index >= len(self.SWATCHES):
                return
            color = self.SWATCHES[index]
        else:
            color = colorsys.hsv_to_rgb(u, v, 1.0)
        self.selected_color = color
        self.colorChanged.emit(color)
        self.colorSelected.emit(color)
        if self.callback is not None:
            self.callback(color)

    def SetMode(self, mode):
        if mode not in {'swatches', 'continuous'}:
            raise ValueError("palette mode must be swatches or continuous")
        self.mode = mode
        self.Modified()

    def modeValue(self):
        return self.mode

    def setMode(self, mode):
        self.SetMode(mode)

    def currentColor(self):
        return tuple(self.selected_color)

    def setCurrentColor(self, color):
        color = tuple(float(component) for component in color)
        if len(color) != 3 or any(component < 0 or component > 1
                                  for component in color):
            raise ValueError("color must contain three values in the range 0..1")
        if color == tuple(self.selected_color):
            return
        self.selected_color = color
        self.Modified()
        self.colorChanged.emit(color)

    def colors(self):
        return tuple(self.SWATCHES)

    def setColors(self, colors):
        self.SWATCHES = [tuple(color) for color in colors]
        self.Modified()

    def saveState(self):
        state = super().saveState()
        state.update({
            'mode': self.modeValue(),
            'currentColor': self.currentColor(),
            'colors': self.colors(),
        })
        return state

    def restoreState(self, state):
        if 'colors' in state:
            self.setColors(state['colors'])
        if 'mode' in state:
            self.setMode(state['mode'])
        if 'currentColor' in state:
            self.setCurrentColor(state['currentColor'])
        return super().restoreState({
            key: state[key] for key in (
                'objectName', 'enabled', 'visible', 'geometry',
                'toolTip', 'statusTip') if key in state})

    def SetAvailable(self, available):
        self.available = bool(available)
        self.Modified()

    def SetBounds(self, x0, x1, y0, y1):
        self.normalized_bounds = [x0, x1, y0, y1]
        self.panel_bounds = np.asarray((x0, x1, y0, y1, 0., 0.))
        self.Modified()

    def GetBounds(self):
        return tuple(self.normalized_bounds)

    def defaultSizePolicy(self):
        return SizePolicy(SizePolicy.Expanding, SizePolicy.Fixed)

    def sizeHint(self):
        return (200.0, 84.0)

    def minimumSizeHint(self):
        return (96.0, 48.0)

    def SetEnabled(self, enabled):
        self.enabled = bool(enabled)
        self.actor.SetVisibility(bool(enabled))

    def GetEnabled(self):
        return int(self.enabled)

    def Modified(self):
        self.painter.Modified()
        self.actor.Modified()

    def Delete(self):
        self.observerRegistry().clear()
        if self.scene is not None and self.painter is not None:
            self.scene.RemoveItem(self.painter)
        ui_layer(self.renderer).RemoveActor(self.actor)
        self.painter = None
        self.actor = None




__all__ = [
    "ButtonWidget",
    "ColorPaletteWidget",
    "HoverTextOverlay",
    "set_tooltip_delay",
    "tooltip_delay",
    "SliderWidget",
    "TextWidget",
    "ValueChangerWidget",
    "VectorButtonWidget",
    "VectorPanelBackground",
]
