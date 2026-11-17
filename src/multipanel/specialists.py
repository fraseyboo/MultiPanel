"""Scene manipulation, reconstruction, and probe widgets."""

from ._widget_support import *
from .controls import *
from .radiation import (  # re-exported for compatibility until 1.0
    calculate_compton_angle,
    create_radiation_marker,
    reconstruction_backend,
    refresh_compton_widgets,
    refresh_reconstruction_callback,
    set_auto_reconstruction_callback,
    set_reconstruction_selection_callback,
    spectrum_button_callback,
)
import logging

logger = logging.getLogger(__name__)

def add_logo(
    renderer,
    interactor,
    icon_name,
    logo_size=0.15,
    interactable=False,
    opacity=0.9,
):
    """Adds a logo to a VTK renderer using a logo widget.

    Parameters
    ----------
    renderer : vtkRenderer
        The VTK renderer to which the logo will be added.
    interactor : vtkRenderWindowInteractor
        The interactor associated with the renderer.
    icon_name : str
        A PNG file: a path, or the name (without extension) of an icon in
        the package's ``icons/png_icons`` folder. MultiPanel ships no
        logos; pass your own image.
    logo_size : float, optional
        The size of the logo as a fraction of the render window.
        Defaults to 0.15.
    interactable : bool, optional
        Whether the logo is interactable (clickable). Defaults to False.
    opacity : float, optional
        The opacity of the logo image. Defaults to 0.9.

    Notes
    -----
    - The logo image must be a PNG.
    - If `interactable` is set to True, clicking the logo will print a message
    to the console.
    - The function adds the logo widget to the `widgets` attribute of the
    renderer for future reference.

    Raises
    ------
    FileNotFoundError
        If the specified icon file does not exist.
    """

    icon_path = os.fspath(icon_name)
    if not os.path.isfile(icon_path):
        current_directory = os.path.dirname(os.path.abspath(__file__))
        icon_path = os.path.join(current_directory, "icons", "png_icons",
                                 f"{icon_name}.png")
    if not os.path.isfile(icon_path):
        raise FileNotFoundError(f"logo image not found: {icon_name!r}")

    reader = vtk.vtkPNGReader()
    reader.SetFileName(icon_path)

    reader.Update()

    image = reader.GetOutput()

    logoRepresentation = vtk.vtkLogoRepresentation()
    logoRepresentation.SetImage(image)
    logoRepresentation.GetImageProperty().SetOpacity(1)

    position = (1 - logo_size, 0.98 - logo_size)

    logoRepresentation.SetPosition(position[0], position[1])
    logoRepresentation.SetPosition2(logo_size, logo_size)

    logoRepresentation.SetShowBorder(False)

    logoWidget = vtk.vtkLogoWidget()
    logoWidget.SetInteractor(interactor)
    logoWidget.SetRepresentation(logoRepresentation)

    logoWidget.SetSelectable(interactable)
    logoWidget.SetProcessEvents(interactable)

    def logo_clicked(obj, event):
        # feel free to add additional names here, might be a nice easter egg.
        """Execute the logo clicked operation."""
        logger.debug("GUI developed by Dr. Fraser Holloway for the ANP group at LBNL")

    if interactable:
        logoWidget.AddObserver("StartInteractionEvent", logo_clicked)

    renderWindow = interactor.GetRenderWindow()

    renderWindow.Render()

    if not hasattr(renderer, "widgets"):
        renderer.widgets = {}
    renderer.widgets.update({"logo_widget": logoWidget})

    logoWidget.On()


def add_caption_widget(
    renderer,
    interactor,
    text,
    anchor_position,
    screen_position=None,
    screen_size=None,
    font_size=20,
    grabbable=True,
    background_color=(1, 1, 1),
    opacity=0.9,
    text_color=(0, 0, 0),
    border_color=(0, 0, 0),
):
    """
    Adds a caption widget to a VTK renderer using a text actor.

    Parameters
    ----------
    renderer : vtkRenderer
        The VTK renderer to which the caption will be added.
    interactor : vtkRenderWindowInteractor
        The interactor associated with the renderer.
    text : str
        The text to display in the caption.
    anchor_position : tuple of float
        The (x,y,z) coordinates of the anchor point of the caption.
    screen_position : tuple of float
        The normalized display coordinates (x, y) of the bottom-left corner of the
        caption.
    screen_size : tuple of float
        The size of the caption in normalized display coordinates (width, height).
    grabbable : bool
        Whether the caption is grabbable and can be moved by the user.

    Returns
    -------
    vtk.vtkTextWidget
        The created text widget representing the caption.

    Notes
    -----
    - The function modifies the `renderer` object by adding a `widgets`
      attribute if it does not already exist.
    - The `widgets` attribute is a dictionary that stores the created text
      widget with the specified `name`.
    """

    if screen_position is None:
        screen_position = (0.3, 0.9)
    if screen_size is None:
        screen_size = (0.2, 0.05)

    caption_rep = vtk.vtkCaptionRepresentation()
    caption_rep.SetPosition(screen_position[0], screen_position[1])
    caption_rep.SetPosition2(screen_size[0], screen_size[1])

    caption_rep.SetAnchorPosition(anchor_position)
    caption_rep.SetShowPolygonToOn()
    caption_rep.SetPolygonColor(colormap_utils.color_to_RGB_255(background_color))
    caption_rep.SetPolygonOpacity(opacity)
    caption_rep.SetBorderColor(colormap_utils.color_to_RGB(border_color))
    caption_rep.SetShowBorderToOn()
    caption_rep.SetBorderThickness(4)

    caption_widget = vtk.vtkCaptionWidget()
    caption_widget.SetInteractor(interactor)
    caption_widget.SetRepresentation(caption_rep)

    caption_actor = caption_rep.GetCaptionActor2D()

    caption_actor.SetCaption(text)
    caption_actor.GetTextActor().GetTextProperty().SetFontSize(font_size)
    caption_actor.GetTextActor().GetTextProperty().SetColor(colormap_utils.color_to_RGB(text_color))
    caption_actor.GetTextActor().GetTextProperty().SetFontFamilyToArial()
    caption_actor.GetTextActor().GetTextProperty().SetJustificationToCentered()
    caption_actor.GetTextActor().GetTextProperty().SetVerticalJustificationToCentered()
    caption_actor.GetTextActor().GetTextProperty().SetBold(False)
    caption_actor.GetTextActor().GetTextProperty().SetItalic(False)
    caption_actor.GetTextActor().GetTextProperty().SetShadow(False)
    caption_actor.SetPadding(10)
    # caption_rep.SetCornerRadiusStrength(0.1)

    caption_widget.SetSelectable(grabbable)
    caption_widget.SetProcessEvents(grabbable)
    caption_widget.On()

    if not hasattr(renderer, "widgets"):
        renderer.widgets = {}
    renderer.widgets.update({"caption_widget": caption_widget})

    return caption_widget


class ColorBarWidget(vtk.vtkScalarBarWidget, WidgetMixin):
    """
    Adds a color bar to a VTK visualization, either as a standalone scalar bar
    or as a widget attached to an interactor.
    Parameters:
        actor (vtk.vtkActor or vtk.vtkScalarBarActor): The actor or scalar bar
            actor to which the color bar will be linked. If a scalar bar actor
            is provided, it will be used directly.
        interactor (vtk.vtkRenderWindowInteractor, optional): The interactor
            to attach the scalar bar widget to. Required if `return_widget` is True.
        title (str, optional): The title displayed on the color bar.
            Defaults to "Values".
        orientation (str, optional): The orientation of the color bar. Can be
            "vertical" or "horizontal". Defaults to "vertical".
        return_widget (bool, optional): Whether to return a scalar bar widget
            instead of a scalar bar actor. Defaults to True.
        total_ticks (int, optional): The number of tick labels to display on the
            color bar. Defaults to 10.
        background (bool, optional): Whether to draw a background behind the
            scalar bar. Defaults to False.
        opacity (float, optional): The opacity of the scalar bar or its background.
            Defaults to 1.0.
        position (tuple of float, optional): The normalized display coordinates
            (x, y) of the bottom-left corner of the scalar bar. Defaults to (0.9, 0.1).
        bar_width (float, optional): The normalized width of the scalar bar.
            Defaults to 0.04.
        bar_height (float, optional): The normalized height of the scalar bar.
            Defaults to 0.7.
        bar_width_ratio (float, optional): The ratio of the bar width to the total
            width of the scalar bar. Defaults to 0.6.
        label_format (str, optional): The format string for the tick labels.
            Defaults to "- %2.3g ".
    Returns:
        vtk.vtkScalarBarWidget or vtk.vtkScalarBarActor: The scalar bar widget
        if `return_widget` is True, otherwise the scalar bar actor.
    Notes:
        - If `return_widget` is True, the `interactor` parameter must be provided.
        - The scalar bar widget is added to the renderer's widget collection for
          proper management.
    """

    def __init__(self,
                actor,
                interactor=None,
                title="Values",
                orientation="vertical",
                return_widget=True,
                total_ticks=10,
                background=False,
                opacity=1.0,
                position=(0.9, 0.1),
                bar_width=0.04,
                bar_height=0.7,
                bar_width_ratio=0.6,
                label_format="- %2.3g ",
                object_name="widgets/scalar_bar",
                enabled=True,
                show_above_swatch=False,
                show_below_swatch=False,
               ):

        """Initialize the instance."""
        super().__init__()
        self.initWidget(object_name)

        self.actor = actor
        self.interactor = interactor
        self._title = str(title)
        self._orientation = str(orientation).lower()
        self.return_widget = return_widget
        self.total_ticks = total_ticks
        self.background = background
        self.opacity = opacity
        self.position = position
        self.bar_width = bar_width
        self.bar_height = bar_height
        self.bar_width_ratio = bar_width_ratio
        self._label_format = str(label_format)
        self.object_name = object_name
        self.enabled = enabled


        # if orientation.lower() == "horizontal":

        # self.panel_background = PanelBackgroundWidget(
        #     interactor=interactor,
        #     renderer= interactor.GetRenderWindow().GetRenderers().GetFirstRenderer(),
        #     panel_bounds=(position[0], position[0] + bar_width, position[1], position[1] + bar_height),
        #     buffer=0.01,
        #     panel_color=(1.0, 1.0, 1.0),
        #     border_color=(0, 0, 0),
        #     opacity=opacity,
        #     name="scalar_bar_background",
        # )


        if interactor is not None:
            self.SetInteractor(interactor)

        if isinstance(actor, vtk.vtkScalarBarActor):
            self.scalar_bar = actor
        else:
            self.scalar_bar = self.create_scalar_bar()

        self.SetInteractor(interactor)
        self.SetScalarBarActor(self.scalar_bar)
        self.ResizableOn()
        self.SetObjectName(object_name)

        rep = self.GetRepresentation()
        rep.SetCornerRadiusStrength(0.1)
        rep.SetShowVerticalBorder(True)
        rep.SetShowBorder(True)
        rep.SetBorderColor(0.0, 0.0, 0.0)
        rep.SetShowPolygon(True)
        rep.SetPolygonColor(1.0, 1.0, 1.0)
        rep.SetPolygonOpacity(opacity)
        rep.SetBorderThickness(2)

        rep.GetPositionCoordinate().SetCoordinateSystemToNormalizedDisplay()
        rep.GetPosition2Coordinate().SetCoordinateSystemToNormalizedDisplay()
        rep.GetPositionCoordinate().SetValue(position[0], position[1])

        rep.GetPosition2Coordinate().SetValue(bar_width, bar_height)

        if orientation.lower() == "horizontal":
            rep.SetOrientation(0)
        elif orientation.lower() == "vertical":
            rep.SetOrientation(1)

        if enabled:
            self.On()
        else:
            self.Off()

        if show_above_swatch:
            self.scalar_bar.SetDrawAboveRangeSwatch(True)
            self.scalar_bar.SetAboveRangeAnnotation("Above")
            self.scalar_bar.AnnotationTextScalingOff()
            self.scalar_bar.GetAnnotationTextProperty().SetColor(0.0, 0.0, 0.0)
            self.scalar_bar.GetAnnotationTextProperty().SetFontFamilyToArial()
            self.scalar_bar.GetAnnotationTextProperty().ItalicOff()
            self.scalar_bar.GetAnnotationTextProperty().BoldOff()
            self.scalar_bar.GetAnnotationTextProperty().ShadowOff()
            self.scalar_bar.GetAnnotationTextProperty().SetJustificationToCentered()
            self.scalar_bar.GetAnnotationTextProperty().SetVerticalJustificationToCentered()
            self.scalar_bar.GetAnnotationTextProperty().SetFontSize(12)

        else:
            self.scalar_bar.SetDrawAboveRangeSwatch(False)
        if show_below_swatch:
            self.scalar_bar.SetDrawBelowRangeSwatch(True)
            self.scalar_bar.SetBelowRangeAnnotation("Below")
            self.scalar_bar.AnnotationTextScalingOff()
            self.scalar_bar.GetAnnotationTextProperty().SetColor(0.0, 0.0, 0.0)
            self.scalar_bar.GetAnnotationTextProperty().SetFontFamilyToArial()
            self.scalar_bar.GetAnnotationTextProperty().ItalicOff()
            self.scalar_bar.GetAnnotationTextProperty().BoldOff()
            self.scalar_bar.GetAnnotationTextProperty().ShadowOff()
            self.scalar_bar.GetAnnotationTextProperty().SetJustificationToCentered()
            self.scalar_bar.GetAnnotationTextProperty().SetVerticalJustificationToCentered()
            self.scalar_bar.GetAnnotationTextProperty().SetFontSize(12)
        else:
            self.scalar_bar.SetDrawBelowRangeSwatch(False)


        scalar_value_range = self.actor.GetMapper().GetScalarRange() if isinstance(self.actor, vtk.vtkActor) else self.actor.GetProperty().GetScalarRange()

        renderer = interactor.GetRenderWindow().GetRenderers().GetFirstRenderer()

        if not hasattr(renderer, "widgets"):
            renderer.widgets = {}
        renderer.widgets.update({object_name: self})


        # widget_bounds = self.GetRepresentation().GetBounds()
        shifted_position = (position[0] - (bar_height/2), position[1] + (bar_height / 2))


        def update_actor_scalar_range(widget, event, actor, bound_type='min', verbose=False):
            """
            Callback function to update the scalar bar widget's actor scalar range
            when the actor's scalar range changes.
            """

            value = widget.GetRepresentation().GetValue()

            old_min = actor.GetMapper().GetScalarRange()[0]
            old_max = actor.GetMapper().GetScalarRange()[1]

            if bound_type == 'min':
                if verbose:
                    logger.debug("%s %s", 'min:', value)
                if value > old_max:
                    logger.warning(f"{bcolors.WARNING}Min value cannot be greater than the current max value. {bcolors.ENDC}")
                    widget.GetRepresentation().SetValue(old_min)
                    return
                actor.GetMapper().SetScalarRange(value, actor.GetMapper().GetScalarRange()[1])
            elif bound_type == 'max':
                if verbose:
                    logger.debug("%s %s", 'max:', value)
                if value < old_min:
                    logger.warning(f"{bcolors.WARNING}Max value cannot be less than the current min value. {bcolors.ENDC}")
                    widget.GetRepresentation().SetValue(old_max)
                    return
                actor.GetMapper().SetScalarRange(actor.GetMapper().GetScalarRange()[0], value)
            else:
                raise ValueError("Invalid bound type. Use 'min' or 'max'.")


        min_slider = SliderWidget(renderer, interactor, position=shifted_position,
                              bar_length=bar_height, use_relative_position=True,
                              min_value=scalar_value_range[0],
                              max_value=scalar_value_range[1],
                              initial_value=scalar_value_range[0],
                              callback=partial(update_actor_scalar_range, actor=self.actor, bound_type='min'),
                              title=None, object_name=f"{object_name}_min_slider",)

        self.min_slider = min_slider


        self.min_slider.SetEnabled(enabled)

        max_slider = SliderWidget(renderer, interactor, position=(shifted_position[0] + bar_height, shifted_position[1]),
                              bar_length=bar_height, use_relative_position=True,
                              min_value=scalar_value_range[0],
                              max_value=scalar_value_range[1],
                              initial_value=scalar_value_range[1],
                              callback=partial(update_actor_scalar_range, actor=self.actor, bound_type='max'),
                              label_placement="below",
                              title=None, object_name=f"{object_name}_max_slider")

        self.max_slider = max_slider
        self.max_slider.SetEnabled(enabled)


        self.ownObserver(self, 'ModifiedEvent', self.on_move_callback)
        self.ownObserver(self, 'InteractionEvent', self.on_move_callback)
        self.ownObserver(self, 'ResizeEvent', self.on_move_callback)

        self.on_move_callback(None, None)

    def title(self):
        return self._title

    def setTitle(self, title):
        title = str(title)
        if title == self._title:
            return
        self._title = title
        self.scalar_bar.SetTitle(f"  {title}  ")
        self.scalar_bar.Modified()

    def orientation(self):
        return self._orientation

    def setOrientation(self, orientation):
        orientation = str(orientation).lower()
        if orientation not in {"horizontal", "vertical"}:
            raise ValueError("orientation must be horizontal or vertical")
        if orientation == self._orientation:
            return
        self._orientation = orientation
        if orientation == "horizontal":
            self.scalar_bar.SetOrientationToHorizontal()
            self.GetRepresentation().SetOrientation(0)
        else:
            self.scalar_bar.SetOrientationToVertical()
            self.GetRepresentation().SetOrientation(1)
        self.scalar_bar.Modified()
        self.on_move_callback(None, None)

    def labelFormat(self):
        return self._label_format

    def setLabelFormat(self, label_format):
        self._label_format = str(label_format)
        self.scalar_bar.SetLabelFormat(self._label_format)
        self.scalar_bar.Modified()

    def lookupTable(self):
        return self.scalar_bar.GetLookupTable()

    def setLookupTable(self, lookup_table):
        self.scalar_bar.SetLookupTable(lookup_table)
        self.scalar_bar.Modified()


    def on_move_callback(self, caller, event):
        """
        Callback function to update the scalar bar widget's slider position
        when the scalar bar widget is resized.

        """

        position_1 = self.GetRepresentation().GetPositionCoordinate().GetValue()
        position_2 = self.GetRepresentation().GetPosition2Coordinate().GetValue()

        orientation = self.GetRepresentation().GetOrientation()


        if orientation == 0:
            bar_width = position_2[0]
            bar_height = position_2[1]


            shifted_position_1 = (position_1[0], position_1[1] - (1 * bar_height), position_1[2])
            shifted_position_2 = (position_1[0], position_1[1] - (1.5 * bar_height), position_1[2])

        elif orientation == 1:
            bar_width = position_2[1]
            bar_height = position_2[0]
            shifted_position_1 = (position_1[0] - (1 * bar_height), position_1[1], position_1[2])
            shifted_position_2 = (position_1[0] - (1.5 * bar_height), position_1[1], position_1[2])

        self.min_slider.update_position(caller, event, position_1=shifted_position_1, position_2=position_2, orientation=orientation)
        self.max_slider.update_position(caller, event, position_1=shifted_position_2, position_2=position_2, orientation=orientation)

        self.min_slider.update_size(caller, event, size=(bar_width, bar_height))
        self.max_slider.update_size(caller, event, size=(bar_width, bar_height))


        current_renderer = self.GetCurrentRenderer()

        if current_renderer:
            current_renderer.GetRenderWindow().Render()


    def create_scalar_bar(self):


        """Create scalar bar."""
        scalar_bar = vtk.vtkScalarBarActor()

        if isinstance(self.actor, vtk.vtkActor):
            # If the actor is a vtkActor, we need to set the mapper's lookup table
            if self.actor.GetMapper() is None:
                raise ValueError("The provided actor does not have a mapper.")
            if self.actor.GetMapper().GetLookupTable() is None:
                raise ValueError("The provided actor's mapper does not have a lookup table.")
            else:
                # Set the lookup table from the actor's mapper
                scalar_bar.SetLookupTable(self.actor.GetMapper().GetLookupTable())
        elif isinstance(self.actor, vtk.vtkVolume):
            # If the actor is a vtkVolume, we need to set the volume's lookup table

            logger.debug("%s %s", self.actor.GetProperty(), sorted(dir(self.actor.GetProperty())))
            if self.actor.GetProperty() is None:
                raise ValueError("The provided volume does not have a property.")
            if self.actor.GetProperty().GetLookupTable() is None:
                raise ValueError("The provided volume's property does not have a lookup table.")
            else:
                # Set the lookup table from the volume's property
                scalar_bar.SetLookupTable(self.actor.GetProperty().GetLookupTable())

        elif isinstance(self.actor, MeshProbeWidget):
            self.actor = self.actor.probe_mesh
            scalar_bar.SetLookupTable(self.actor.GetMapper().GetLookupTable())
        else:
            raise TypeError("The provided actor must be a vtkScalarBarActor, vtkActor, or vtkVolume.")

        # scalar_bar.SetLookupTable(actor.GetMapper().GetLookupTable())

        scalar_bar.SetBarRatio(self.bar_width_ratio)

        scalar_bar.SetDrawBackground(False)

        # The properties of the scalar values on the right of the bar

        scalar_bar.GetLabelTextProperty().SetColor(0.0, 0.0, 0.0)
        scalar_bar.GetLabelTextProperty().SetFontFamilyToArial()
        scalar_bar.GetLabelTextProperty().ItalicOff()
        scalar_bar.GetLabelTextProperty().BoldOff()
        scalar_bar.GetLabelTextProperty().ShadowOff()
        scalar_bar.GetLabelTextProperty().SetJustificationToLeft()
        scalar_bar.GetLabelTextProperty().SetVerticalJustificationToCentered()
        scalar_bar.Modified()

        padded_title = f"  {self._title}  "

        scalar_bar.SetTitle(padded_title)
        scalar_bar.GetTitleTextProperty().SetColor(0.0, 0.0, 0.0)
        scalar_bar.GetTitleTextProperty().SetFontFamilyToArial()
        scalar_bar.GetTitleTextProperty().BoldOff()
        scalar_bar.GetTitleTextProperty().ShadowOff()
        scalar_bar.GetTitleTextProperty().ItalicOff()
        scalar_bar.GetTitleTextProperty().SetJustificationToCentered()
        scalar_bar.GetTitleTextProperty().SetVerticalJustificationToBottom()
        scalar_bar.AnnotationTextScalingOn()
        scalar_bar.SetVerticalTitleSeparation(10)

        scalar_bar.SetDrawAnnotations(True)
        scalar_bar.SetDrawAboveRangeSwatch(False)
        scalar_bar.SetDrawBelowRangeSwatch(False)

        scalar_bar.SetDrawFrame(False)

        if self._orientation == "horizontal":
            scalar_bar.SetOrientationToHorizontal()
        elif self._orientation == "vertical":
            scalar_bar.SetOrientationToVertical()
        else:
            raise ValueError("Orientation must be 'horizontal' or 'vertical', not '%s'" % self._orientation)

        scalar_bar.SetVisibility(1)
        scalar_bar.SetNumberOfLabels(self.total_ticks)

        scalar_bar.SetLabelFormat(self._label_format)

        scalar_bar.UseOpacityOn()
        if self.background:
            scalar_bar.DrawBackgroundOn()
            scalar_bar.GetBackgroundProperty().SetOpacity(self.opacity)

        scalar_bar.GetPositionCoordinate().SetValue(self.position[0], self.position[1])
        if self._orientation == "vertical":
            scalar_bar.GetPosition2Coordinate().SetValue(self.bar_width, self.bar_height)
        elif self._orientation == "horizontal":
            scalar_bar.GetPosition2Coordinate().SetValue(self.bar_height, self.bar_width)

        scalar_bar.Modified()

        return scalar_bar


class Cursor3DWidget(vtk.vtk3DCursorWidget, WidgetMixin):
    """
    A widget for creating a 3D cursor in a VTK renderer.

    This widget allows users to interact with a 3D cursor that can be used
    for various purposes, such as selecting points in a 3D scene.

    Parameters
    ----------
    ren : vtkRenderer
        The renderer to which the widget will be added.
    iren : vtkRenderWindowInteractor
        The interactor associated with the renderer.
    actor : vtkActor
        The actor that the widget will interact with.
    cursor_radius : float, optional
        The radius of the cursor. Defaults to 0.1.
    cursor_color : tuple, optional
        RGB color of the cursor as a tuple of floats (0 to 1). Defaults to (1, 0, 0).
    enabled : bool, optional
        If True, the widget is enabled. Defaults to True.

    Returns
    -------
    vtk.vtk3DCursorWidget
        The created 3D cursor widget.
    """
    def __init__(self, ren, iren, actor, cursor_radius=0.1, cursor_color=(1,0,0), enabled=True):

        """Initialize the instance."""
        super().__init__()
        self.initWidget('widgets/cursor_3D_widget')
        self.positionChanged = Signal(self)
        self.interactionStarted = Signal(self)
        self.interactionFinished = Signal(self)
        cursor = self
        cursor.SetInteractor(iren)
        # cursor.SetViewProp(actor)
        # cursor.SetRadius(cursor_radius)
        # cursor.SetCursorShapeToSphere()
        # cursor.GetCursorProperty().SetColor(cursor_color)
        cursor.CreateDefaultRepresentation()

        cursor.Get3DCursorRepresentation().SetCursorShape(1)  # 1 = sphere, 2 = cube, 3 = cone, 4 = arrow
        cursor.Get3DCursorRepresentation().SetHandleSize(cursor_radius)
        cursor.Get3DCursorRepresentation().PlaceWidget(actor.GetBounds())


        cursor.SetObjectName('widgets/cursor_3D_widget')

        if enabled:
            cursor.On()
        else:
            cursor.Off()



        if not hasattr(ren, 'widgets'):
            ren.widgets = dict()
        ren.widgets.update({'widgets/cursor_3D_widget': cursor})

        self.ownObserver(self, 'StartInteractionEvent',
                         lambda *_: self.interactionStarted.emit())
        self.ownObserver(self, 'InteractionEvent', self._emit_position_changed)
        self.ownObserver(self, 'EndInteractionEvent',
                         lambda *_: self.interactionFinished.emit())

    def _emit_position_changed(self, *_):
        self.positionChanged.emit(self.positionValue())

    def positionValue(self):
        bounds = self.Get3DCursorRepresentation().GetBounds()
        if bounds is None:
            return None
        return tuple((bounds[index] + bounds[index + 1]) * 0.5
                     for index in (0, 2, 4))

    def setPosition(self, position):
        position = tuple(float(value) for value in position)
        if position == self.positionValue():
            return
        representation = self.Get3DCursorRepresentation()
        bounds = representation.GetBounds()
        if bounds is None:
            raise RuntimeError('cursor representation has not been placed')
        centre = self.positionValue()
        delta = tuple(position[i] - centre[i] for i in range(3))
        representation.PlaceWidget(tuple(
            bounds[index] + delta[index // 2]
            for index in range(6)))
        representation.Modified()
        self.positionChanged.emit(position)

    def handleSize(self):
        return float(self.Get3DCursorRepresentation().GetHandleSize())

    def setHandleSize(self, size):
        self.Get3DCursorRepresentation().SetHandleSize(float(size))
        self.Get3DCursorRepresentation().Modified()


class LassoWidget(vtk.vtkImageTracerWidget, WidgetMixin):
    """
    A widget for creating a lasso selection in a VTK renderer.

    This widget allows users to draw freehand or snap lines to select regions
    in a 3D scene. It supports various interaction modes, including dragging,
    erasing, and snapping.

    # 1) left button click over the image, hold and drag draws a free hand line.
    # 2) left button click and release erases the widget line, if it exists, and repositions the first handle.
    # 3) middle button click starts a snap drawn line. The line is terminated by clicking the middle button while depressing the ctrl key.
    # 4) when tracing a continuous or snap drawn line, if the last cursor position is within a specified tolerance to the first handle, the widget line will form a closed loop.
    # 5) right button clicking and holding on any handle that is part of a snap drawn line allows handle dragging: existing line segments are updated accordingly. If the path is open and AutoClose is set to On, the path can be closed by repositioning the first and last points over one another.
    # 6) ctrl key + right button down on any handle will erase it: existing snap drawn line segments are updated accordingly. If the line was formed by continuous tracing, the line is deleted leaving one handle.
    # 7) shift key + right button down on any snap drawn line segment will insert a handle at the cursor position. The line segment is split accordingly.


    Parameters
    ----------
    ren : vtkRenderer
        The renderer to which the widget will be added.
    iren : vtkRenderWindowInteractor
        The interactor associated with the renderer.
    actor : vtkActor
        The actor that the widget will interact with.
    closest_region_only : bool, optional
        If True, only the closest region to the drawn path will be selected.
        Defaults to False.
    enabled : bool, optional
        If True, the widget is enabled. Defaults to True.

    Returns
    -------
    vtkImageTracerWidget
        The created lasso widget.
    """
    def __init__(self, ren, iren, actor, closest_region_only=False, enabled=True,
                 voxel_size=[0.05, 0.05, 0.05], grid_size=None,
                 reconstruction_type='full', object_name='widgets/image_tracer',
                 auto_reconstruct=True, verbose=True):
        """Initialize the instance."""
        super().__init__()
        self.initWidget(object_name)
        self.selectionChanged = Signal(self)
        self.reconstructionStarted = Signal(self)
        self.reconstructionFinished = Signal(self)
        self.failed = Signal(self)


        self.GetLineProperty().SetLineWidth(3)
        self.GetLineProperty().SetColor(1,0,0)
        self.SetInteractor(iren)
        self.SetViewProp(actor)
        self.verbose = verbose
        self.widget_name = object_name
        self.axes = None
        self.slicer = None
        self.cut_actor = None
        self.colormap = 'hot'


        self.voxel_size = voxel_size
        self.grid_size = grid_size
        self.reconstruction_type = reconstruction_type


        # self.On()
        self.SetEnabled(enabled)
        self.AutoCloseOn()
        self.SetKeyPressActivationValue('l')
        self.SetObjectName(object_name)
        self.ren = ren
        self.iren = iren

        handle_properties = self.GetHandleProperty()

        handle_properties.SetLineWidth(3)
        handle_properties.SetColor(1,0,0)

        selected_handle_properties = self.GetHandleProperty()

        selected_handle_properties.SetLineWidth(3)
        selected_handle_properties.SetColor(0,1,0)

        if hasattr(self.ren, 'auto_reconstruct'):
            if self.ren.auto_reconstruct:
                logger.debug("Auto reconstruction is enabled.")
            else:
                logger.debug("Auto reconstruction is disabled.")
        else:
            logger.debug("%s %s", 'Setting renderer auto_reconstruct to ', auto_reconstruct)
            self.ren.auto_reconstruct = auto_reconstruct

        def on_tracer_start(caller, event):

            """Handle tracer start."""
            cut_actor = delete_actor(ren, actor_name=self.widget_name+'_cut_actor', verbose=True)
            # bound_actor = delete_actor(ren, actor_name=self.widget_name+'_cut_actor_bounds')

        def on_tracer_complete(caller, event):

            """Handle tracer complete."""
            tracer_polydata = vtk.vtkPolyData()
            self.GetPath(tracer_polydata)

            SelectionFilter = vtk.vtkImplicitSelectionLoop()
            SelectionFilter.SetLoop(tracer_polydata.GetPoints())

            view_normal = np.asarray(ren.GetActiveCamera().GetViewPlaneNormal())
            SelectionFilter.SetNormal(view_normal)


            ClipFilter = vtk.vtkClipPolyData()
            ClipFilter.InsideOutOn()
            ClipFilter.SetClipFunction(SelectionFilter)
            ClipFilter.SetInputData(actor.GetMapper().GetInput())
            ClipFilter.Update()

            clipped_data = ClipFilter.GetOutput()

            def get_closest_region(tracer_polydata):
                """Return closest region."""
                connectivityFilter = vtk.vtkConnectivityFilter()
                connectivityFilter.SetInputData(ClipFilter.GetOutput())
                # connectivityFilter.SetExtractionModeToClosestPointRegion()
                connectivityFilter.SetExtractionModeToLargestRegion()
                connectivityFilter.SetClosestPoint(tracer_polydata.GetCenter())
                connectivityFilter.Update()

                closest_region = connectivityFilter.GetOutput()

                return closest_region

            if closest_region_only:

                clipped_data = get_closest_region(clipped_data)

            logger.debug('Lasso selection complete')

            def get_number_of_cells(polydata):
                """Return number of cells."""
                number_of_cells = polydata.GetNumberOfCells()
                logger.debug("%s %s", 'Number of cells:', number_of_cells)
                return number_of_cells

            if get_number_of_cells(clipped_data) == 0:
                logger.warning(f'{bcolors.WARNING}No suitable region found{bcolors.ENDC}')
                cut_actor = delete_actor(ren, actor_name=self.widget_name+'_cut_actor')
                self.cut_actor = None
                self.failed.emit('No suitable region found')
                self.selectionChanged.emit(None)
                # bound_actor = delete_actor(ren, actor_name=self.widget_name+'cut_actor_bounds')


                return


            cut_mapper = vtk.vtkPolyDataMapper()
            cut_mapper.SetInputData(clipped_data)

            self.cut_actor = vtk.vtkActor()
            self.cut_actor.SetMapper(cut_mapper)
            self.cut_actor.GetProperty().SetColor(0, 1, 0)  # Set color to green
            self.cut_actor.SetObjectName(self.widget_name+'_cut_actor')

            ren.AddActor(self.cut_actor)
            self.selectionChanged.emit(self.cut_actor)

            # bound_actor = show_actor_bounds(cut_actor, ren, color=(0,1,0),
            #                                 opacity=0.5, name=self.widget_name+'cut_actor_bounds')

            actor_bounds = self.cut_actor.GetBounds()
            logger.debug("%s", 'Bounds of selected region: {:.4f}, {:.4f}, {:.4f}, {:.4f}, {:.4f}, {:.4f}'.format(*actor_bounds))


            if hasattr(self.ren, 'auto_reconstruct'):
                logger.debug("%s", self.ren.auto_reconstruct)
                if self.ren.auto_reconstruct:
                    self.reconstruct_from_object(actor_bounds)
                else:
                    pass
                    # ren.AddActor(bound_actor)
                    return

            ren.Render()


        self.ownObserver(self, "StartInteractionEvent", on_tracer_start)
        self.ownObserver(self, "EndInteractionEvent", on_tracer_complete)

        if not hasattr(ren, 'widgets'):
            ren.widgets = dict()
        ren.widgets.update({'widgets/image_tracer': self})

    def path(self):
        polydata = vtk.vtkPolyData()
        self.GetPath(polydata)
        return polydata

    def selection(self):
        return self.cut_actor

    def clearSelection(self):
        if self.cut_actor is not None:
            self.ren.RemoveActor(self.cut_actor)
            self.cut_actor = None
            self.selectionChanged.emit(None)

    def apply(self):
        if self.cut_actor is None:
            return None
        if self.autoReconstruct():
            self.reconstruct_from_object(self.cut_actor.GetBounds())
        return self.cut_actor

    def cancel(self):
        self.clearSelection()

    def autoReconstruct(self):
        return bool(getattr(self.ren, 'auto_reconstruct', False))

    def setAutoReconstruct(self, enabled):
        self.ren.auto_reconstruct = bool(enabled)

    def isAutoClosed(self):
        return bool(self.GetAutoClose())

    def setAutoClosed(self, auto_close):
        self.SetAutoClose(bool(auto_close))

    def create_new_volume(self, box_bounds, new_compton_array, name='compton_volume'):
        """Create new volume."""
        buffer = 0.00001
        lower_bound = np.asarray([box_bounds[0] - buffer, box_bounds[2] - buffer, box_bounds[4] - buffer])
        upper_bound = np.asarray([box_bounds[1] + buffer, box_bounds[3] + buffer, box_bounds[5] + buffer])
        spacings = (np.asarray([1,1,1])/(new_compton_array.shape)) * (upper_bound - lower_bound)
            # volume = vtk_utils.add_volume(new_compton_array, spacing=spacings, origin=(lower_bound + upper_bound)/2, c_range=(0,np.max(new_compton_array)/2))
        volume = _vtk_utils().add_volume(new_compton_array, spacing=spacings, origin=lower_bound,
                                      c_range=(0,np.max(new_compton_array)/2), name=name)
        return spacings, volume


    def reconstruct_from_object(self, box_bounds):


        """Execute the reconstruct from object operation."""
        if hasattr(self, 'Compton_Events'):
            logger.debug('Compton Event Collection exists in widget, using it for reconstruction')
            Compton_Events = self.Compton_Events
        elif hasattr(self.ren, 'Compton_Events'):
            logger.debug('Compton Event Collection exists in renderer, using it for reconstruction')
            Compton_Events = self.ren.Compton_Events
        else:
            logger.debug('No Compton Event Collection found, unable to reconstruct')
            self.failed.emit('No Compton Event Collection found')
            return

        self.reconstructionStarted.emit()

        if self.grid_size is not None:

            grid_size = self.grid_size

            voxel_size = np.zeros(3)
            voxel_size[0] = (box_bounds[1] - box_bounds[0]) / grid_size[0]
            voxel_size[1] = (box_bounds[3] - box_bounds[2]) / grid_size[1]
            voxel_size[2] = (box_bounds[5] - box_bounds[4]) / grid_size[2]

            widget_text = 'Recomputing Compton array \nDynamic voxel size: (%.4f, %.4f, %.4f) \nGrid size (%i, %i, %i)' % (voxel_size[0], voxel_size[1], voxel_size[2], grid_size[0], grid_size[1], grid_size[2])

        elif self.voxel_size is not None:
            voxel_size = self.voxel_size

            grid_size = [math.ceil((box_bounds[1] - box_bounds[0]) / voxel_size[0]), math.ceil((box_bounds[3] - box_bounds[2]) / voxel_size[1]), math.ceil((box_bounds[5] - box_bounds[4]) / voxel_size[2])]

            widget_text = 'Recomputing Compton array \nFixed voxel size: (%.4f, %.4f, %.4f) \nDynamic grid size: (%i, %i, %i)' % (voxel_size[0], voxel_size[1], voxel_size[2], grid_size[0], grid_size[1], grid_size[2])


        else:
            voxel_size = [0.01, 0.01, 0.01]

            grid_size = [math.ceil((box_bounds[1] - box_bounds[0]) / voxel_size[0]), math.ceil((box_bounds[3] - box_bounds[2]) / voxel_size[1]), math.ceil((box_bounds[5] - box_bounds[4]) / voxel_size[2])]

            widget_text = 'Recomputing Compton array \nFixed voxel size: (%.4f, %.4f, %.4f) \nDynamic grid size: (%i, %i, %i)' % (voxel_size[0], voxel_size[1], voxel_size[2], grid_size[0], grid_size[1], grid_size[2])


        if not hasattr(self, 'text_widget') or self.text_widget is None:

            text_widget = create_text_widget(self.ren, self.iren, text=widget_text, position_1=[0.3, 0.9], position_2=[0.2, 0.05], object_name=self.widget_name+'_text')

            self.text_widget = text_widget

        else:
            self.text_widget.GetTextActor().SetInput(widget_text)


        # Compton_Events.validity = np.copy(Compton_Events.initial_validity)
        # Compton_Events.Event_Selection.Reset()

        if self.reconstruction_type in ['full_ellipse', 'ellipse', 'full', 'full ellipse']:

            ComptonArray, Compton_Events = reconstruction_backend().perform_compton_reconstruction(box_bounds, voxel_size, Compton_Events)

        elif self.reconstruction_type =='iterative':

            ComptonArray, Compton_Events = reconstruction_backend().perform_compton_reconstruction(box_bounds, voxel_size, Compton_Events)
            ComptonArray, Compton_Events = reconstruction_backend().perform_iterative_compton_reconstruction(ComptonArray, Compton_Events)

        else:
            raise ValueError("Invalid reconstruction type: %s. Choose from 'full_ellipse', 'ellipse', 'full', 'full ellipse', or 'iterative'." % self.reconstruction_type)

        new_compton_array = ComptonArray.compton_array
        # valid_events = Compton_Events.validity
        events_in_bounds = Compton_Events.events_in_bounds


        total_valid_events = np.sum(events_in_bounds)

        if total_valid_events == 0:
            Compton_Events.events_in_widget_bounds = None
        else:
            Compton_Events.events_in_widget_bounds = events_in_bounds

        if self.verbose:
            logger.debug("%s %s", 'Valid events', total_valid_events)
            logger.debug("%s %s", 'Fraction of events valid', total_valid_events / events_in_bounds.shape[0])

        final_text = 'Valid events: (%i/%i)\nVoxel size: (%.4f, %.4f, %.4f) \nGrid size (%i, %i, %i)' % (total_valid_events, events_in_bounds.shape[0], voxel_size[0], voxel_size[1], voxel_size[2], grid_size[0], grid_size[1], grid_size[2])

        self.text_widget.GetTextActor().SetInput(final_text)


        spacings, volume = self.create_new_volume(box_bounds, new_compton_array, name=self.widget_name+'_compton_volume')

        self.bounds = box_bounds
        self.ren.compton_array = new_compton_array
        self.ren.voxel_size = spacings
        # self.ren.Compton_Events.validity = valid_events


        if self.slicer is None:
            self.slicer = VolumeSlicer(volume, self.ren, self.iren, name=self.widget_name+'_slicer') # this function must return something to keep it in memory
        else:
            logger.debug('Slicer already exists, updating input data')
            for slicewidget in self.slicer.planeWidgets:
                slicewidget.SetInputData(volume.GetMapper().GetInput())
                slicewidget.Modified()
            if self.slicer.show_intersection:
                self.slicer.plot_plane_intersections()

        if self.axes is None:
            axes = _vtk_utils().add_axes(source_object=volume, source_renderer=self.ren, name=self.widget_name+'_axes', color=[0,0,0])
            # colorbar = aux_material.colorbar(actor=probed_mesh, interactor=iren, title='Overlaps') # this function must return something to keep it in memory
            self.ren.AddActor(axes)
            self.axes = axes
        else:
            # self.axes.SetInputData(volume.GetMapper().GetInput())
            self.axes.SetBounds(volume.GetBounds())
            self.axes.Modified()

        if self.cut_actor is not None:

            new_compton_mesh = MeshProbeWidget(
                dataset=volume,
                probe_mesh=self.cut_actor,
                renderer=self.ren,
                colormap=self.colormap,
                probe_subdivisions=0,
                name=self.widget_name+'_cut_actor',
                enabled=True,  # Always refresh the widget as enabled
                replace_actor=True,  # Always replace the actor
                clip_to_bounds=False  # Do not clip to bounds
            ).probe_mesh

            self.cut_actor.GetMapper().SetInputData(new_compton_mesh.GetMapper().GetInput())
            self.cut_actor.Modified()

        self.reconstructionFinished.emit(self.cut_actor)


class CameraOrientationWidget(vtk.vtkCameraOrientationWidget, WidgetMixin):

    def __init__(self, renderer, interactor, enabled=True, position=(0.6,0.9), size=(0.1, 0.1), name='orientation_widget'):
        """Initialize the instance."""
        super().__init__()
        self.initWidget(name)
        self.SetParentRenderer(renderer)
        self.SetInteractor(interactor)
        self.SetEnabled(enabled)
        # self.SetPosition(position)
        # self.SetSize(size)
        self.SetObjectName(name)
        # Enable the widget.
        self.On()


        self._position = tuple(position)
        self._size = tuple(size)

        # vtkCameraOrientationWidget renders on *every* mouse move anywhere
        # in the window (to update its hover highlight). Only let it see
        # events while the pointer is over its own viewport, for one move
        # after leaving it (so the highlight clears), or while it is still
        # hovering/dragging a handle (dragging rotates the camera even
        # outside the widget). This observer runs before the widget's own.
        self._pointer_inside = False
        self._gate_tags = [
            self.ownObserver(interactor, 'MouseMoveEvent',
                             self._gate_events, 10.0),
            self.ownObserver(interactor, 'LeftButtonPressEvent',
                             self._gate_events, 10.0),
        ]

        self.ownObserver(self, 'ModifiedEvent', self.update_position_callback)
        # self.AddObserver('InteractionEvent', self.update_position)

        # add an observer that looks for a window resize event and updates the position of the widget accordingly
        self.ownObserver(self.GetInteractor(), 'ConfigureEvent',
                         self.update_position_callback)

        if hasattr(self, "SetViewport"):
            self.SetViewport(position[0], position[1], position[0] + size[0], position[1] + size[1])

            logger.debug("Set camera orientation widget viewport")

        else:
            # Older versions of VTK (< 9.3) do not expose SetViewport on the
            # camera orientation widget.  In those versions the widget renders in
            # the lower-left corner by default, so we simply skip the call.

            logger.debug("Camera orientation widget has no SetViewport API")

            self.set_position(position[0], position[1])
            self.set_size(size[0], size[1])

            logger.debug("Set camera orientation widget position=%s size=%s",
                         position, size)

            self.Modified()

            pass

        self.set_colors()

        # self.panel_offset = position
        # self.panel_size = size
        # self.panel_bounds = [position[0], position[0] + size[0], position[1], position[1] + size[1]]

        # # self.set_colors()
        # self.set_position(position[0], position[1])

    def _pointer_over_widget(self, margin=6):
        renderer = self.GetCurrentRenderer()
        interactor = self.GetInteractor()
        if renderer is None or interactor is None:
            return True
        width, height = interactor.GetRenderWindow().GetSize()
        x, y = interactor.GetEventPosition()
        x0, y0, x1, y1 = renderer.GetViewport()
        return (x0 * width - margin <= x <= x1 * width + margin and
                y0 * height - margin <= y <= y1 * height + margin)

    def _gate_events(self, _caller=None, _event=None):
        inside = self._pointer_over_widget()
        engaged = self.GetRepresentation().GetInteractionState() != 0
        process = inside or self._pointer_inside or engaged
        if bool(self.GetProcessEvents()) != process:
            self.SetProcessEvents(int(process))
        self._pointer_inside = inside

    def set_colors(self):
        """Apply the editor's red-X, green-Y, blue-Z convention."""
        axis_colors = (
            (1.0, 0.35, 0.35),
            (0.35, 0.90, 0.35),
            (0.38, 0.62, 1.0),
        )
        rep = self.GetRepresentation()

        label_properties = (
            (rep.GetXPlusLabelProperty(), rep.GetXMinusLabelProperty()),
            (rep.GetYPlusLabelProperty(), rep.GetYMinusLabelProperty()),
            (rep.GetZPlusLabelProperty(), rep.GetZMinusLabelProperty()),
        )
        label_color = (0.0, 0.0, 0.0)
        for axis, properties in enumerate(label_properties):
            for text_property in properties:
                text_property.SetColor(*label_color)
                text_property.SetInteriorLinesColor(*label_color)
                text_property.SetFrameColor(*label_color)
                text_property.SetBackgroundColor(*axis_colors[axis])
                text_property.SetOpacity(1.0)
                text_property.Modified()
        # Camera-orientation labels are texture-backed. Rebuild after changing
        # their vtkTextProperty or the old (black) texture remains visible.
        rep.Modified()
        rep.BuildRepresentation()

        # vtkCameraOrientationRepresentation exposes the label properties but,
        # in VTK 9.3, not public axis actor color setters. Its three shafts are
        # one shared actor with direct per-cell RGB values; the six end handles
        # are separate actors. Detect axes geometrically so prop traversal order
        # and repeated references to the shared shaft actor do not matter.
        actors = vtk.vtkPropCollection()
        rep.GetActors(actors)
        actors.InitTraversal()
        seen = set()
        for _ in range(actors.GetNumberOfItems()):
            actor = actors.GetNextProp()
            if actor is None or not hasattr(actor, 'GetMapper'):
                continue
            identity = actor.__this__
            if identity in seen:
                continue
            seen.add(identity)
            mapper = actor.GetMapper()
            mapper.Update()
            polydata = mapper.GetInput()
            if polydata is None:
                continue

            scalars = polydata.GetCellData().GetScalars()
            if scalars is not None and scalars.GetNumberOfComponents() >= 3:
                for cell_index in range(polydata.GetNumberOfCells()):
                    cell = polydata.GetCell(cell_index)
                    center = np.zeros(3)
                    for point_index in range(cell.GetNumberOfPoints()):
                        center += np.asarray(cell.GetPoints().GetPoint(point_index))
                    center /= max(cell.GetNumberOfPoints(), 1)
                    axis = int(np.argmax(np.abs(center)))
                    for component, value in enumerate(axis_colors[axis]):
                        scalars.SetComponent(cell_index, component, value)
                scalars.Modified()
            else:
                bounds = polydata.GetBounds()
                center = np.asarray((
                    bounds[0] + bounds[1],
                    bounds[2] + bounds[3],
                    bounds[4] + bounds[5],
                )) * 0.5
                if np.linalg.norm(center) > 1e-9:
                    actor.GetProperty().SetColor(
                        *axis_colors[int(np.argmax(np.abs(center)))])
            actor.Modified()


    def set_position(self, x, y):
        """
        Update the position of the camera orientation widget.
        """
        rep = self.GetRepresentation()
        # rep.GetViewportCoordinate().SetCoordinateSystemToNormalizedDisplay()
        # rep.GetViewportCoordinate().SetValue(self.panel_bounds[0], self.panel_bounds[2])
        # rep.GetViewportSizeCoordinate().SetCoordinateSystemToNormalizedDisplay()
        # rep.GetViewportSizeCoordinate().SetValue(self.panel_size[0], self.panel_size[1])
        # display_size = self.GetInteractor().GetRenderWindow().GetSize()

        # rep.SetSize(int(self.panel_size[0] * display_size[0]), int(self.panel_size[1] * display_size[1]))
        # rep.SetPosition(int(x * display_size[0]), int(y * display_size[1]))
        # bounds = rep.GetBounds()
        rep.SetUseBounds(True)




    def set_size(self, x_size, y_size):

        """Set size."""
        display_size = self.GetInteractor().GetRenderWindow().GetSize()
        rep = self.GetRepresentation()
        rep.SetSize(int(x_size * display_size[0]), int(y_size * display_size[1]))
        # rep.SetSize(int(self.panel_size[0] * display_size[0]), int(self.panel_size[1] * display_size[1]))


        # rep.
        # rep.SetXAxisColor(1,0,0)
        # rep.SetYAxisColor(0,1,0)
        # rep.SetZAxisColor(0,0,1)
        # rep.SetViewportCoordinate(x, y)
        # rep.SetViewportSizeCoordinate(self.panel_size[0], self.panel_size[1])

        # self.position = x

        rep.Modified()

    def positionValue(self):
        return self._position

    def setPosition(self, position):
        self._position = tuple(float(value) for value in position)
        if hasattr(self, 'SetViewport'):
            x, y = self._position
            width, height = self._size
            self.SetViewport(x, y, x + width, y + height)
        else:
            self.set_position(*self._position)
        self.Modified()

    def sizeValue(self):
        return self._size

    def setSize(self, size):
        self._size = tuple(float(value) for value in size)
        if hasattr(self, 'SetViewport'):
            x, y = self._position
            width, height = self._size
            self.SetViewport(x, y, x + width, y + height)
        self.set_size(*self._size)
        self.Modified()

    def update_position_callback(self, caller, event):



        # get the screen size of the render window
        """Update position callback."""
        if getattr(self, 'managed_by_viewport_panel', False):
            return
        display_size = self.GetInteractor().GetRenderWindow().GetSize()
        if display_size[1] <= 0:
            return

        aspect_ratio = display_size[0] / display_size[1]


        if aspect_ratio < 1:

            new_x = self._size[0]
            new_y = self._size[0] * aspect_ratio

            if new_x > new_y:
                new_x =  new_y

            # self.set_position(self.position[0], self.position[1])




            self.set_size(new_x, new_y)

        elif aspect_ratio > 1:

            new_x = self._size[0] / aspect_ratio
            new_y = self._size[1]

            self.set_size(new_x, new_y)


def show_actor_bounds(actor, ren, color=(1,0,0), opacity=0.5, name='cut_actor_bounds'):

    """Show actor bounds."""
    bounds = actor.GetBounds()

    bounds_actor = vtk.vtkCubeSource()
    bounds_actor.SetBounds(bounds)
    bounds_actor.Update()

    bounds_mapper = vtk.vtkPolyDataMapper()
    bounds_mapper.SetInputConnection(bounds_actor.GetOutputPort())

    bounds_actor = vtk.vtkActor()
    bounds_actor.SetMapper(bounds_mapper)
    bounds_actor.GetProperty().SetColor(color)
    bounds_actor.GetProperty().SetOpacity(opacity)
    bounds_actor.SetObjectName(name)

    ren.AddActor(bounds_actor)

    return bounds_actor


class BoxWidget(vtk.vtkBoxWidget2, WidgetMixin):
    """
    A custom box widget that extends vtk.vtkBoxWidget to include additional
    functionality such as text display and interaction events.
    """

    def check_if_smaller(self, old_bounds, new_bounds):
        """
        Check if the new bounds are smaller than the old bounds.
        if all new bounds are smaller than the old bounds, return True.
        """
        if len(old_bounds) != len(new_bounds):
            raise ValueError("Bounds must have the same length.")

        if new_bounds[0] < old_bounds[0]:
            return False
        if new_bounds[1] > old_bounds[1]:
            return False
        if new_bounds[2] < old_bounds[2]:
            return False
        if new_bounds[3] > old_bounds[3]:
            return False
        if new_bounds[4] < old_bounds[4]:
            return False
        if new_bounds[5] > old_bounds[5]:
            return False

        return True

    def boundsValue(self):
        representation = self.GetRepresentation()
        return tuple(representation.GetBounds())

    def setBounds(self, bounds):
        bounds = tuple(float(value) for value in bounds)
        if len(bounds) != 6:
            raise ValueError('bounds must contain six values')
        if np.allclose(bounds, self.boundsValue(), atol=1e-12):
            return
        self.GetRepresentation().PlaceWidget(bounds)
        self.boundsChanged.emit(bounds)

    def reset(self):
        if hasattr(self, 'initial_bounds'):
            self.setBounds(self.initial_bounds)


    def on_interaction_event(self, caller, event):

        """Handle interaction event."""
        current_time = time.time()

        if current_time - self.last_modified < self.update_interval:
            return
        else:

            box_representation = self.GetRepresentation()

            if hasattr(self, 'bounds'):
                old_bounds = self.bounds
            else:
                old_bounds = box_representation.GetBounds()

            box_bounds = box_representation.GetBounds()
            self.boundsChanged.emit(tuple(box_bounds))

            # if self.check_if_smaller(old_bounds, box_bounds):
            #     validity = self.ren.Compton_Events.Event_Selection.selection
            # else:
            #     validity = self.ren.Compton_Events.Event_Selection.initial_validity

            validity = self.ren.Compton_Events.Event_Selection.selection

            # # Update the validity mask
            # self.ren.Compton_Events.Event_Selection.validity = validity

            self.Modified()
            current_time = time.time()
            self.last_modified = current_time


            if self.slicer is not None:
                if isinstance(self.slicer, list):
                    for slicer in self.slicer:
                        slicer.Off()
                        slicer.RemoveAllObservers()
                        slicer.SetInteractor(None)
                        slicer = None
                    self.slicer = None
                elif isinstance(self.slicer, VolumeSlicer):
                    for slicer in self.slicer.planeWidgets:
                        slicer.Off()
                        slicer.RemoveAllObservers()
                        slicer.SetInteractor(None)
                        slicer = None
                    self.slicer = None


            if hasattr(self.ren, 'auto_reconstruct'):
                logger.debug("%s", self.ren.auto_reconstruct)
                if self.ren.auto_reconstruct:
                    logger.debug("Auto reconstruction is enabled.")
                else:
                    logger.debug("Auto reconstruction is disabled.")


                    if self.grid_size is not None:

                        grid_size = self.grid_size

                        voxel_size = np.zeros(3)
                        voxel_size[0] = (box_bounds[1] - box_bounds[0]) / grid_size[0]
                        voxel_size[1] = (box_bounds[3] - box_bounds[2]) / grid_size[1]
                        voxel_size[2] = (box_bounds[5] - box_bounds[4]) / grid_size[2]
                        widget_text = 'Compton array \nDynamic voxel size: (%.4f, %.4f, %.4f) \nGrid size (%i, %i, %i)' % (voxel_size[0], voxel_size[1], voxel_size[2], grid_size[0], grid_size[1], grid_size[2])


                    elif self.voxel_size is not None:
                        voxel_size = self.voxel_size
                        grid_size = [math.ceil((box_bounds[1] - box_bounds[0]) / voxel_size[0]), math.ceil((box_bounds[3] - box_bounds[2]) / voxel_size[1]), math.ceil((box_bounds[5] - box_bounds[4]) / voxel_size[2])]
                        widget_text = 'Compton array \nFixed voxel size: (%.4f, %.4f, %.4f) \nDynamic grid size: (%i, %i, %i)' % (voxel_size[0], voxel_size[1], voxel_size[2], grid_size[0], grid_size[1], grid_size[2])


                    else:
                        voxel_size = [0.01, 0.01, 0.01]
                        grid_size = [math.ceil((box_bounds[1] - box_bounds[0]) / voxel_size[0]), math.ceil((box_bounds[3] - box_bounds[2]) / voxel_size[1]), math.ceil((box_bounds[5] - box_bounds[4]) / voxel_size[2])]
                        widget_text = 'Compton array \nFixed voxel size: (%.4f, %.4f, %.4f) \nDynamic grid size: (%i, %i, %i)' % (voxel_size[0], voxel_size[1], voxel_size[2], grid_size[0], grid_size[1], grid_size[2])


                    if not hasattr(self, 'text_widget') or self.text_widget is None:

                        text_widget = create_text_widget(self.ren, self.iren, text=widget_text, position_1=[0.3, 0.9], position_2=[0.2, 0.05], object_name=self.widget_name+'_text')
                        self.text_widget = text_widget

                    else:
                        self.text_widget.GetTextActor().SetInput(widget_text)

                    return

            else:
                self.ren.auto_reconstruct = self.auto_reconstruct


            if self.grid_size is not None:

                grid_size = self.grid_size

                voxel_size = np.zeros(3)
                voxel_size[0] = (box_bounds[1] - box_bounds[0]) / grid_size[0]
                voxel_size[1] = (box_bounds[3] - box_bounds[2]) / grid_size[1]
                voxel_size[2] = (box_bounds[5] - box_bounds[4]) / grid_size[2]

                widget_text = 'Recomputing Compton array \nDynamic voxel size: (%.4f, %.4f, %.4f) \nGrid size (%i, %i, %i)' % (voxel_size[0], voxel_size[1], voxel_size[2], grid_size[0], grid_size[1], grid_size[2])

            elif self.voxel_size is not None:
                voxel_size = self.voxel_size

                grid_size = [math.ceil((box_bounds[1] - box_bounds[0]) / voxel_size[0]), math.ceil((box_bounds[3] - box_bounds[2]) / voxel_size[1]), math.ceil((box_bounds[5] - box_bounds[4]) / voxel_size[2])]

                widget_text = 'Recomputing Compton array \nFixed voxel size: (%.4f, %.4f, %.4f) \nDynamic grid size: (%i, %i, %i)' % (voxel_size[0], voxel_size[1], voxel_size[2], grid_size[0], grid_size[1], grid_size[2])


            else:
                voxel_size = [0.01, 0.01, 0.01]

                grid_size = [math.ceil((box_bounds[1] - box_bounds[0]) / voxel_size[0]), math.ceil((box_bounds[3] - box_bounds[2]) / voxel_size[1]), math.ceil((box_bounds[5] - box_bounds[4]) / voxel_size[2])]

                widget_text = 'Recomputing Compton array \nFixed voxel size: (%.4f, %.4f, %.4f) \nDynamic grid size: (%i, %i, %i)' % (voxel_size[0], voxel_size[1], voxel_size[2], grid_size[0], grid_size[1], grid_size[2])


            if not hasattr(self, 'text_widget') or self.text_widget is None:

                text_widget = create_text_widget(self.ren, self.iren, text=widget_text, position_1=[0.3, 0.9], position_2=[0.2, 0.05], object_name=self.widget_name+'_text')

                self.text_widget = text_widget

            else:
                self.text_widget.GetTextActor().SetInput(widget_text)


            # progressbar_widget = add_progressbar_widget(ren, iren, progress=0.0)
            # self.progress_bar = progressbar_widget

            self.ren.GetRenderWindow().Render()

            # new_compton_array, _, _ = reconstruction_backend().reproject_in_volume(box_bounds, voxel_size, scatterer_positions, cone_parameters, progressbar_widget=progressbar_widget)


            # validity = self.ren.Compton_Events.validity

            # new_compton_array, _, valid_events = reconstruction_backend().reproject_in_volume(box_bounds, voxel_size, self.Compton_Event_Collection, validity=validity)

            self.reconstructionStarted.emit(tuple(box_bounds))

            if self.reconstruction_type in ['full_ellipse', 'ellipse', 'full', 'full ellipse']:

                ComptonArray, Compton_Events = reconstruction_backend().perform_compton_reconstruction(box_bounds, voxel_size, self.Compton_Event_Collection)

            elif self.reconstruction_type =='iterative':

                ComptonArray, Compton_Events = reconstruction_backend().perform_compton_reconstruction(box_bounds, voxel_size, self.Compton_Event_Collection)
                ComptonArray, Compton_Events = reconstruction_backend().perform_iterative_compton_reconstruction(ComptonArray, Compton_Events)

            else:
                raise ValueError("Invalid reconstruction type: %s. Choose from 'full_ellipse', 'ellipse', 'full', 'full ellipse', or 'iterative'." % self.reconstruction_type)

            new_compton_array = ComptonArray.compton_array
            valid_events = Compton_Events.events_in_bounds


            total_valid_events = np.sum(valid_events)

            if self.verbose:
                logger.debug("%s %s", 'Valid events', total_valid_events)
                logger.debug("%s %s", 'Fraction of events valid', total_valid_events / valid_events.shape[0])

            final_text = 'Valid events: (%i/%i)\nVoxel size: (%.4f, %.4f, %.4f) \nGrid size (%i, %i, %i)' % (total_valid_events, valid_events.shape[0], voxel_size[0], voxel_size[1], voxel_size[2], grid_size[0], grid_size[1], grid_size[2])


            if total_valid_events == 0:
                Compton_Events.events_in_widget_bounds = None
            else:
                Compton_Events.events_in_widget_bounds = Compton_Events.events_in_bounds

            self.text_widget.GetTextActor().SetInput(final_text)


            spacings, volume = self.create_new_volume(box_bounds, new_compton_array, name=self.widget_name+'_compton_volume')

            self.bounds = box_bounds
            self.ren.compton_array = new_compton_array
            self.ren.voxel_size = spacings
            self.ren.Compton_Events.validity = valid_events

            multi_plane_slicer = VolumeSlicer(volume, self.ren, self.iren, name=self.widget_name+'_slicer') # this function must return something to keep it in memory

            self.slicer = multi_plane_slicer

            if self.axes is None:
                axes = _vtk_utils().add_axes(source_object=volume, source_renderer=self.ren, name=self.widget_name+'_axes', color=[0,0,0])
                # colorbar = aux_material.colorbar(actor=probed_mesh, interactor=iren, title='Overlaps') # this function must return something to keep it in memory
                self.ren.AddActor(axes)
                self.axes = axes
            else:
                # self.axes.SetInputData(volume.GetMapper().GetInput())
                self.axes.SetBounds(volume.GetBounds())
                self.axes.Modified()

            self.reconstructionFinished.emit(volume)

            # list_widgets(ren)

    def create_new_volume(self, box_bounds, new_compton_array, name='compton_volume'):
        """Create new volume."""
        buffer = 0.00001
        lower_bound = np.asarray([box_bounds[0] - buffer, box_bounds[2] - buffer, box_bounds[4] - buffer])
        upper_bound = np.asarray([box_bounds[1] + buffer, box_bounds[3] + buffer, box_bounds[5] + buffer])
        spacings = (np.asarray([1,1,1])/(new_compton_array.shape)) * (upper_bound - lower_bound)
            # volume = vtk_utils.add_volume(new_compton_array, spacing=spacings, origin=(lower_bound + upper_bound)/2, c_range=(0,np.max(new_compton_array)/2))
        volume = _vtk_utils().add_volume(new_compton_array, spacing=spacings, origin=lower_bound,
                                      c_range=(0,np.max(new_compton_array)/2), name=name)
        return spacings,volume

            # plotting_utils.plot_compton_slices(new_compton_array, voxel_sizes=spacings)


    def __init__(self, ren, iren, Compton_Event_Collection, grid_size=[100, 100, 100],
                voxel_size=None, box_bounds=None, auto_reconstruct=True, run_initially=True, initial_compton_array=None,
                update_at='end', enable_scaling=False, enable_translation=True, enable_rotation=False,
                update_interval=0.03, enabled=True, verbose=False, widget_name='widgets/box_widget', reconstruction_type='full_ellipse'):

        """Initialize the instance."""
        super().__init__()
        self.initWidget(widget_name)
        self.interactionStarted = Signal(self)
        self.boundsChanged = Signal(self)
        self.interactionFinished = Signal(self)
        self.reconstructionStarted = Signal(self)
        self.reconstructionFinished = Signal(self)

        self.grid_size = None
        self.voxel_size = None
        self.last_modified = time.time()
        self.verbose = False
        self.update_interval = update_interval
        self.auto_reconstruct = auto_reconstruct

        self.reconstruction_type = reconstruction_type

        self.ren = ren
        self.iren = iren
        self.Compton_Event_Collection = Compton_Event_Collection
        self.widget_name = widget_name


        self.volume = None
        self.axes = None
        self.text_widget = None
        self.slicer = None


        self.SetInteractor(iren)

        self.SetRotationEnabled(enable_rotation)
        self.SetScalingEnabled(enable_scaling)
        self.SetTranslationEnabled(enable_translation)
        self.SetMoveFacesEnabled(True)
        self.SetKeyPressActivationValue('b')

        if box_bounds is not None:
            self.GetRepresentation().PlaceWidget(box_bounds)
            self.initial_bounds = tuple(box_bounds)
        else:
            bounds = np.asarray(self.volume.GetBounds())
            centre = np.asarray(self.volume.GetCenter())

            centre_stack = np.asarray([centre[0], centre[0], centre[1], centre[1], centre[2], centre[2]])
            new_bounds = (bounds - centre_stack) * 2 + centre_stack

            self.GetRepresentation().PlaceWidget(new_bounds)

        self.GetRepresentation().SetObjectName('widgets/box_widget')
        self.SetObjectName('widgets/box_widget')

        if enabled:
            self.On()
        else:
            self.Off()


        if update_at == 'end':
            event = 'EndInteractionEvent'
        elif update_at == 'start':
            event = 'StartInteractionEvent'
        elif update_at == 'interaction':
            event = 'InteractionEvent'

        current_time = time.time()
        self.last_modified = current_time

        if initial_compton_array is not None:

                box_bounds = self.GetRepresentation().GetBounds()
                spacings, volume = self.create_new_volume(box_bounds, initial_compton_array)
                multi_plane_slicer = VolumeSlicer(volume, ren, iren) # this function must return something to keep it in memory
                self.slicer = multi_plane_slicer

        else:
            self.slicer = None

        self.voxel_size = voxel_size
        self.grid_size = grid_size
        self.verbose = verbose

        self.ownObserver(self, 'StartInteractionEvent',
                         lambda *_: self.interactionStarted.emit())
        self.ownObserver(self, event, self.on_interaction_event)
        self.ownObserver(self, 'EndInteractionEvent',
                         lambda *_: self.interactionFinished.emit(
                             self.boundsValue()))

        if not hasattr(ren, 'widgets'):
            ren.widgets = dict()
        ren.widgets.update({widget_name: self})

        if run_initially:
            self.on_interaction_event(None, None)
            ren.GetRenderWindow().Render()


def rotate_coordinate(coord, origin, angles):

    """Execute the rotate coordinate operation."""
    rotation = import_optional(
        "scipy.spatial.transform", extra="scientific",
        purpose="coordinate rotation").Rotation
    r = rotation.from_euler("xyz", angles, degrees=True)
    new_rotation_matrix = r.as_matrix()

    full_rotation = new_rotation_matrix

    rotated_coord = np.dot(coord,full_rotation) + origin

    return rotated_coord


def extract_triangles(actor):

    """Execute the extract triangles operation."""
    actual_points = actor.GetMapper().GetInput().GetPoints().GetData()
    actual_points = numpy_support.vtk_to_numpy(actual_points)

    actual_indices = numpy_support.vtk_to_numpy(actor.GetMapper().GetInput().GetPolys().GetData()) # array is typically 1D with the number of vertices included.
    actual_indices = actual_indices.reshape([-1,4]) # reshapes to a n*4 with (hopefully) the first collumn being 3s

    assert np.all(actual_indices[:, 0] == 3), "mesh cells contain non-triangles, try using vtkTriangleFilter first"

    actual_indices = actual_indices[:,1:] # this removes the first column

    return actual_points, actual_indices


def extract_triangles_points(actor):

    """Execute the extract triangles points operation."""
    actual_points = actor.GetMapper().GetInput().GetPoints().GetData()
    actual_points = numpy_support.vtk_to_numpy(actual_points)

    return actual_points


def extract_scalars(actor):

    """Execute the extract scalars operation."""
    array_data = actor.GetMapper().GetInput().GetPointData()

    scalars = numpy_support.vtk_to_numpy(array_data.GetScalars())

    return scalars

class SphereProbeWidget(vtk.vtkSphereWidget, WidgetMixin):

    def __init__(self, volume, ren, iren, sphere_radius=0.5, sphere_center=(0,0,0),
                 rotation=None, resolution=400, update_interval=0.03, update_at='end',
                 clip_to_volume=True, deform_mesh=False, show_edges=False, use_lighting=False,
                 colormap='viridis', enable_scaling=True, enable_translation=False,
                 show_axes=False, widget_name='widgets/sphere_widget', enabled=True):


        """Initialize the instance."""
        super().__init__()
        self.initWidget(widget_name)
        self.centerChanged = Signal(self)
        self.radiusChanged = Signal(self)
        self.probeFinished = Signal(self)
        self.volume = volume
        self.ren = ren
        self.iren = iren
        self.sphere_radius = sphere_radius
        self.sphere_center = sphere_center
        self.rotation = rotation
        self.resolution = resolution
        self.update_interval = update_interval
        self.update_at = update_at
        self.clip_to_volume = clip_to_volume
        self.deform_mesh = deform_mesh
        self.show_edges = show_edges
        self.use_lighting = use_lighting
        self.colormap = colormap
        self.enable_scaling = enable_scaling
        self.enable_translation = enable_translation
        self.show_axes = show_axes
        self.widget_name = widget_name
        self.enabled = enabled


        self.SetObjectName(widget_name)
        self.SetInteractor(iren)
        self.SetRepresentationToSurface()
        self.SetThetaResolution(2  * resolution)
        self.SetPhiResolution(resolution)
        self.SetRadius(sphere_radius)
        self.SetCenter(sphere_center)
        self.SetTranslation(enable_translation)
        self.SetScale(enable_scaling)

        self.SetEnabled(enabled)

        self.GetSphereProperty().SetColor(1,0,0)
        self.GetSphereProperty().SetOpacity(0.01)
        self.GetSelectedSphereProperty().SetColor(0,1,0)
        self.GetSelectedSphereProperty().SetOpacity(0.5)
        self.last_modified = time.time()

        if update_at == 'end':
            event = 'EndInteractionEvent'
        elif update_at == 'start':
            event = 'StartInteractionEvent'
        elif update_at == 'interaction':
            event = 'InteractionEvent'

        self.ownObserver(self, 'StartInteractionEvent', self.on_start_interaction)

        self.ownObserver(self, event, self.on_interaction_event)

        sphere_center = self.GetCenter()
        widget_text = 'Sphere radius = %0.2f, centre (%.2f, %.2f, %.2f)' % (sphere_radius, sphere_center[0], sphere_center[1], sphere_center[2])

        text_widget = create_text_widget(ren, iren, text=widget_text, color=[0,0,0], position_1=[0.2, 0.0], position_2=[0.8, 0.05],
                                        object_name=widget_name+'_text', enabled=enabled)

        self.text_widget = text_widget

        if enabled:
            self.on_interaction_event(None, None)

        if not hasattr(self.ren, 'widgets'):
            self.ren.widgets = dict()
        self.ren.widgets.update({self.widget_name: self})

    def center(self):
        return tuple(self.GetCenter())

    def setCenter(self, center):
        center = tuple(float(value) for value in center)
        if center == self.center():
            return
        self.SetCenter(center)
        self.sphere_center = center
        self.centerChanged.emit(center)

    def radius(self):
        return float(self.GetRadius())

    def setRadius(self, radius):
        radius = float(radius)
        if radius <= 0:
            raise ValueError('radius must be greater than zero')
        if math.isclose(radius, self.radius(), rel_tol=0.0, abs_tol=1e-12):
            return
        self.SetRadius(radius)
        self.sphere_radius = radius
        self.radiusChanged.emit(radius)


    def on_start_interaction(self, caller, event):

        # delete_probe(ren, actor_name='sphere_probe')
        """Handle start interaction."""
        probe_actor = return_actor(self.ren, actor_name='widgets/self')

        return probe_actor

    def rotate_polydata(polydata, rotation, sphere_center):

        """Execute the rotate polydata operation."""
        points = numpy_support.vtk_to_numpy(polydata.GetPoints().GetData())
        origin = np.asarray(sphere_center)
        rotated_points = rotate_coordinate(points, origin, rotation)
        new_polydata = vtk.vtkPolyData()
        new_points = vtk.vtkPoints()
        new_points.SetData(numpy_support.numpy_to_vtk(rotated_points))
        new_polydata.SetPoints(new_points)
        new_polydata.SetPolys(polydata.GetPolys())

        return new_polydata


    def warp_actor(actor, scale=0.0001, small_shift=-0.0001, use_mean=True):

        # probed_values = actor.GetMapper().GetInput().GetPointData().GetScalars()

        """Execute the warp actor operation."""
        normals = vtk.vtkPolyDataNormals()
        normals.SetInputData(actor.GetMapper().GetInput())
        normals.ComputePointNormalsOn()
        normals.ComputeCellNormalsOn()
        normals.Update()

        actor.GetMapper().SetInputData(normals.GetOutput())

        warp = vtk.vtkWarpScalar()

        if use_mean:
            warp_values = numpy_support.vtk_to_numpy(actor.GetMapper().GetInput().GetPointData().GetScalars())
            warp_backup = np.copy(warp_values)
            # mean_value = np.mean(warp_values)
            # warp_values = (warp_values - mean_value) * 1.1
            min_value = np.min(warp_values)
            warp_values = (warp_values - min_value) + small_shift

            warp_values = numpy_support.numpy_to_vtk(warp_values)
            actor.GetMapper().GetInput().GetPointData().SetScalars(warp_values)
            warp.SetInputData(actor.GetMapper().GetInput())
            # warp.SetInputData(warp_values)
        else:
            warp.SetInputData(actor.GetMapper().GetInput())

        warp.SetScaleFactor(scale)
        # warp.SetInputArrayToProcess(0, 0, 0, vtk.vtkDataObject.FIELD_ASSOCIATION_POINTS, 'Overlaps')
        warp.Update()


        actor.GetMapper().SetInputData(warp.GetOutput())
        actor.GetMapper().GetInput().GetPointData().SetScalars(numpy_support.numpy_to_vtk(warp_backup))

        return actor


    def on_interaction_event(self, caller, event):


        """Handle interaction event."""
        current_time = time.time()

        renderer = self.ren



        if current_time - self.last_modified < self.update_interval:
            return
        else:


            probe_polydata = vtk.vtkPolyData()
            self.GetPolyData(probe_polydata)

            if self.rotation is not None:


                probe_polydata = self.rotate_polydata(probe_polydata, self.rotation, self.sphere_center)

            probe_actor = return_actor(self.ren, actor_name='widgets/sphere_widget_mesh')

            if self.show_axes:
                delete_actor(self.ren, actor_name='sphere_axes')

            if probe_actor is None:
                probed_points = MeshProbeWidget(self.volume, probe_polydata, renderer, colormap=self.colormap, clip_to_bounds=self.clip_to_volume,
                                             opacity=1, name='widgets/sphere_widget_mesh', use_lighting=self.use_lighting,
                                             existing_probe=probe_actor, include_RGB=False).probe_mesh

                if self.deform_mesh:

                    constant = 0.5

                    probe_radius = self.GetRadius()
                    probe_value_range = probed_points.GetMapper().GetInput().GetPointData().GetScalars().GetRange()
                    scale = constant * probe_radius / (probe_value_range[1] - probe_value_range[0])

                    probed_points = self.warp_actor(probed_points, scale=scale)

                probed_points.SetPickable(False)
                self.ren.AddActor(probed_points)
            else:
                probe_actor.GetProperty().SetOpacity(0.01)
                probed_points = MeshProbeWidget(self.volume, probe_polydata, renderer, colormap=self.colormap, clip_to_bounds=self.clip_to_volume,
                                                opacity=1, name='widgets/sphere_widget_mesh', use_lighting=self.use_lighting,
                                                existing_probe=probe_actor, include_RGB=False).probe_mesh
                probed_points.GetProperty().SetOpacity(1)

                if self.deform_mesh:

                    constant = 0.5

                    probe_radius = self.GetRadius()
                    probe_value_range = probed_points.GetMapper().GetInput().GetPointData().GetScalars().GetRange()
                    if probe_value_range[1] - probe_value_range[0] == 0:
                        scale = 0
                    else:
                        scale = constant * probe_radius / (probe_value_range[1] - probe_value_range[0])

                    probed_points = self.warp_actor(probed_points, scale=scale)

                    probed_points.SetPickable(False)


            if self.show_edges:
                edges_actor = return_actor(self.ren, actor_name='non_manifold_edges')

                if edges_actor is None:
                    edges_actor = generate_feature_edges(probed_points, 361/self.resolution, existing_actor=edges_actor)
                    self.ren.AddActor(edges_actor)
                else:
                    edges_actor = generate_feature_edges(probed_points, 361/self.resolution, existing_actor=edges_actor)
                    edges_actor.Modified()

            self.SetInputData(probe_polydata)
            self.Modified()

            if self.show_axes:
                sphere_axes = add_sphere_axes(self.ren, source_actor=probed_points, name='sphere_axes')

                self.ren.AddActor(sphere_axes)

                self.axes = sphere_axes

            self.SetInputData(probe_polydata)
            self.Modified()


            current_radius = self.GetRadius()

            probed_points.Modified()

            probe_value_range = probed_points.GetMapper().GetInput().GetPointData().GetScalars().GetRange()


            widget_text = 'Sphere radius = %0.2f, Value range = %0.2f - %0.2f,  centre (%.2f, %.2f, %.2f)' % (current_radius, probe_value_range[0], probe_value_range[1], self.sphere_center[0], self.sphere_center[1], self.sphere_center[2])

            self.text_widget.GetTextActor().SetInput(widget_text)

            centre = tuple(self.GetCenter())
            radius = float(self.GetRadius())
            if centre != tuple(self.sphere_center):
                self.sphere_center = centre
                self.centerChanged.emit(centre)
            if not math.isclose(radius, self.sphere_radius):
                self.sphere_radius = radius
                self.radiusChanged.emit(radius)
            self.probeFinished.emit(probed_points)

            current_time = time.time()
            self.last_modified = current_time


def generate_feature_edges(input_actor, feature_angle, existing_actor=None):


    """Execute the generate feature edges operation."""
    edges = vtk.vtkFeatureEdges()
    edges.SetInputData(input_actor.GetMapper().GetInput())
    edges.BoundaryEdgesOff()
    edges.FeatureEdgesOn()
    edges.ManifoldEdgesOff()
    edges.NonManifoldEdgesOff()
    edges.SetFeatureAngle(feature_angle)
    edges.Update()

    if existing_actor is None:

        edge_mapper = vtk.vtkPolyDataMapper()
        edge_mapper.SetInputConnection(edges.GetOutputPort())
        edge_mapper.ScalarVisibilityOff()

        edge_actor = vtk.vtkActor()
        edge_actor.SetMapper(edge_mapper)
        edge_actor.GetProperty().SetRepresentationToWireframe()
        edge_actor.GetProperty().SetEdgeVisibility(True)
        edge_actor.GetProperty().SetColor(1, 0, 0)  # Red color for non-manifold edges
        edge_actor.GetProperty().SetLineWidth(2)
        edge_actor.SetObjectName('non_manifold_edges')

    else:

        existing_actor.GetMapper().SetInputConnection(edges.GetOutputPort())
        existing_actor.Modified()
        edge_actor = existing_actor

    return edge_actor


def create_plane_probe(volume, ren, iren, plane_normal=(0,0,1), plane_center=(0,0,0), resolution=400, update_interval=0.03, update_at='end', clip_to_volume=True, use_lighting=False, colormap='viridis', widget_name = 'widgets/plane_probe'):

    """Create plane probe."""
    def on_interaction_event(caller, event):

        """Handle interaction event."""
        current_time = time.time()

        if current_time - planeWidget.last_modified < update_interval:
            return
        else:


            probe_polydata = vtk.vtkPolyData()
            planeWidget.GetPolyData(probe_polydata)

            probe_actor = return_actor(ren, actor_name='plane_probe')

            if probe_actor is None:
                probed_points = probe_points(volume, probe_polydata, colormap=colormap, clip_to_bounds=clip_to_volume, opacity=1, name='plane_probe', use_lighting=use_lighting, existing_probe=probe_actor)

                ren.AddActor(probed_points)
            else:
                probe_actor.GetProperty().SetOpacity(0.01)
                probed_points = probe_points(volume, probe_polydata, colormap=colormap, clip_to_bounds=clip_to_volume, opacity=1, name='plane_probe', use_lighting=use_lighting, existing_probe=probe_actor)
                probed_points.GetProperty().SetOpacity(1)


            planeWidget.SetInputData(probe_polydata)
            planeWidget.Modified()


            current_time = time.time()
            planeWidget.last_modified = current_time


    planeWidget = vtk.vtkPlaneWidget()
    planeWidget.SetInteractor(iren)
    planeWidget.SetResolution(resolution)

    planeWidget.UpdatePlacement()
    planeWidget.SetRepresentationToSurface()
    planeWidget.SetCenter(plane_center)
    planeWidget.SetHandleSize(0.05)


    planeWidget.SetRepresentationToSurface()
    planeWidget.GetPlaneProperty().SetOpacity(0.01)
    planeWidget.GetSelectedPlaneProperty().SetOpacity(0.5)
    planeWidget.GetPlaneProperty().SetColor(1,0,0)
    planeWidget.GetSelectedPlaneProperty().SetColor(0,1,0)

    planeWidget.On()

    if update_at == 'end':
        event = 'EndInteractionEvent'
    elif update_at == 'start':
        event = 'StartInteractionEvent'
    elif update_at == 'interaction':
        event = 'InteractionEvent'

    current_time = time.time()
    planeWidget.last_modified = current_time

    planeWidget.AddObserver(event, on_interaction_event)


    if not hasattr(ren, 'widgets'):
        ren.widgets = dict()
    ren.widgets.update({widget_name: planeWidget})


    return planeWidget


def create_volume_single_slicer(volume, ren, iren, colormap='viridis', slice_axis=2, interpolate=False, interactive=True):


    """Create volume single slicer."""
    old_number_of_actors = ren.GetViewProps().GetNumberOfItems()


    LUT = colormap_utils.make_LUT(colormap=colormap, c_range=(0, 1))
    LUT.SetSaturationRange(1.0, 1.0)
    LUT.SetTableRange(0,1)

    picker = vtk.vtkCellPicker()
    picker.SetTolerance(0.005)

    plane = ['x','y','z']
    widget_name = 'widgets/slice-%s' % plane[slice_axis]
    actor_name = 'probes/slice-%s' % plane[slice_axis]

    volume_data = volume.GetMapper().GetInput()
    slice_index = math.ceil(volume_data.GetDimensions()[slice_axis]/2)

    imageplane = vtk.vtkImagePlaneWidget()
    imageplane.SetInteractor(iren)
    imageplane.SetInputData(volume.GetMapper().GetInput())
    imageplane.SetPlaneOrientation(slice_axis)
    imageplane.TextureInterpolateOn()
    imageplane.SetSliceIndex(slice_index)
    imageplane.SetPicker(picker)
    imageplane.DisplayTextOn()
    imageplane.GetTextProperty().SetColor(1,0,0)
    imageplane.SetLookupTable(LUT)
    imageplane.EnabledOn()
    imageplane.SetInteraction(interactive)

    if interpolate:
        imageplane.SetResliceInterpolateToLinear()
    else:
        imageplane.SetResliceInterpolateToNearestNeighbour()
    imageplane.SetObjectName(widget_name)
    imageplane.On()

    image_actor = ren.GetViewProps().GetItemAsObject(old_number_of_actors + 1)
    image_actor.SetObjectName(actor_name)

    if not hasattr(ren, 'widgets'):
        ren.widgets = dict()
    ren.widgets.update({widget_name: imageplane})

    return imageplane

class VolumeSlicer(WidgetMixin):

    def __init__(self, volume, ren, iren, axes_enabled=[True, True, True], slicing_indices=[None, None, None],
                 colormap='viridis', opacity=1, interpolate=False, interactive=True, enabled=True,
                 name='widgets/slice', show_intersection=True):

        """Initialize the instance."""
        self.initWidget(name)
        self.sliceChanged = Signal(self)
        self.axisEnabledChanged = Signal(self)
        self.volume = volume
        self.ren = ren
        self.iren = iren
        self.axes_enabled = list(axes_enabled)
        self.slicing_indices = list(slicing_indices)
        self.colormap = colormap
        self.opacity = opacity
        self.interpolate = interpolate
        self.interactive = interactive
        self.show_intersection = show_intersection
        self.enabled = enabled
        self.name = name

        if isinstance(volume, vtk.vtkVolume):
                volume_data = volume.GetMapper().GetInput()

                dimensions = volume_data.GetDimensions()

                if dimensions[0] == 1:
                    logger.warning('Volume is a 2D image, cannot slice in other dimensions')
                    axes_enabled = [True, False, False]

                if dimensions[1] == 1:
                    logger.warning('Volume is a 2D image, cannot slice in other dimensions')
                    axes_enabled = [False, True, False]

                if dimensions[2] == 1:
                    logger.warning('Volume is a 2D image, cannot slice in other dimensions')
                    axes_enabled = [False, False, True]


        if isinstance(volume, vtk.vtkOverlappingAMR):
            volume_data = volume
            logger.debug("%s", dir(volume_data))


        LUT = colormap_utils.make_LUT(colormap=colormap, c_range=(0, 1))
        LUT.SetSaturationRange(1.0, 1.0)
        LUT.SetTableRange(0,1)

        picker = vtk.vtkCellPicker()
        picker.SetTolerance(0.005)

        self.planeWidgets = list()
        self.planePolyData = list()

        plane = ['x','y','z']

        for i in range(3):

            widget_name = name + '-%s' % plane[i]

            if not axes_enabled[i]:
                continue

            total_preexisting_actors = self.ren.GetViewProps().GetNumberOfItems()


            imageplane = vtk.vtkImagePlaneWidget()
            imageplane.SetInteractor(iren)
            imageplane.SetPicker(picker)
            imageplane.RestrictPlaneToVolumeOn()
            if opacity != 1:
                imageplane.GetTexturePlaneProperty().SetOpacity(opacity)

            if interpolate:
                imageplane.TextureInterpolateOn()
                imageplane.SetResliceInterpolateToLinear()
            else:
                imageplane.SetResliceInterpolateToNearestNeighbour()
                imageplane.TextureInterpolateOff()
            imageplane.SetInputData(volume_data)
            imageplane.SetPlaneOrientation(i)
            if slicing_indices[i] is not None:
                imageplane.SetSliceIndex(slicing_indices[i])
            else:
                imageplane.SetSliceIndex(math.ceil(volume_data.GetDimensions()[i]/2))
            imageplane.DisplayTextOn()
            imageplane.GetTextProperty().SetColor(1,0,0)


            imageplane.SetDefaultRenderer(ren)

            imageplane.SetInteraction(interactive)

            if enabled:
                imageplane.On()
            else:
                imageplane.Off()

            imageplane.SetKeyPressActivationValue('m')

            imageplane.SetLookupTable(LUT)
            imageplane.SetObjectName(widget_name)

            if not hasattr(ren, 'widgets'):
                ren.widgets = dict()
            ren.widgets.update({widget_name: imageplane})

            self.planeWidgets.append(imageplane)
            self.ownObserver(
                imageplane, 'InteractionEvent', self._plane_interacted)


            new_total_actors = self.ren.GetViewProps().GetNumberOfItems()


            if new_total_actors > total_preexisting_actors:
                total_added_actors = new_total_actors - total_preexisting_actors
                for j in range(total_added_actors):
                    image_actor = self.ren.GetViewProps().GetItemAsObject(total_preexisting_actors + j)

                    if j == 0: # the outline
                        image_actor.GetProperty().SetColor(0, 0, 0)  # Black color for the outline
                        image_actor.GetProperty().SetLineWidth(2)
                        # image_actor.SetObjectName(widget_name + '-outline')
                        image_actor.GetProperty().SetRenderLinesAsTubes(True)  # Optional: render lines as tubes for better visibility
                        image_actor.Modified()  # Ensure the outline is updated
                    elif j == 1:  # the slice
                        image_actor.GetProperty().SetColor(1, 1, 1)  # uncoloured for the slicing plane
                        # image_actor.SetObjectName(widget_name + '-image')
                        image_actor.GetProperty().SetOpacity(self.opacity)  # Set the opacity to 0.01 for the image plane
                        self.planePolyData.append(image_actor)
                    elif j == 2:  # the cursor
                        image_actor.GetProperty().SetColor(1, 0, 0)  # Red color for the cursor
                        image_actor.GetProperty().SetLineWidth(2)
                        # image_actor.SetObjectName(widget_name + '-cursor')
                        image_actor.GetProperty().SetRenderLinesAsTubes(True)  # Optional: render lines as tubes for better visibility
                        image_actor.Modified()  # Ensure the cursor is updated
                    elif j == 3:  # the border rotators
                        image_actor.GetProperty().SetColor(0, 0, 1)
                        image_actor.GetProperty().SetLineWidth(2)  # Blue color for the border rotators
                        # image_actor.SetObjectName(widget_name + '-border-rotators')
                        image_actor.GetProperty().SetRenderLinesAsTubes(True)  # Optional: render lines as tubes for better visibility
                        image_actor.Modified()  # Ensure the border rotators are updated
                    elif j == 4:  # not sure what this is?
                        image_actor.GetProperty().SetColor(0, 1, 1)  # Cyan color for the mystery
                        # image_actor.SetObjectName(widget_name + '-mystery')
                        image_actor.Modified()  # Ensure the mystery is updated


        if show_intersection:

            for i, planeWidget in enumerate(self.planeWidgets):
                self.ownObserver(
                    planeWidget, 'InteractionEvent',
                    self.plot_plane_intersections)

            self.plot_plane_intersections()

    @staticmethod
    def _axis_index(axis):
        if isinstance(axis, str):
            try:
                return {'x': 0, 'y': 1, 'z': 2}[axis.lower()]
            except KeyError as exc:
                raise ValueError("axis must be x, y, z, 0, 1, or 2") from exc
        axis = int(axis)
        if axis not in (0, 1, 2):
            raise ValueError("axis must be x, y, z, 0, 1, or 2")
        return axis

    def _plane_widget(self, axis):
        axis = self._axis_index(axis)
        for widget in self.planeWidgets:
            if widget.GetPlaneOrientation() == axis:
                return widget
        return None

    def _plane_interacted(self, widget, _event=None):
        axis = int(widget.GetPlaneOrientation())
        index = int(widget.GetSliceIndex())
        self.slicing_indices[axis] = index
        self.sliceChanged.emit(axis, index)

    def sliceIndex(self, axis):
        widget = self._plane_widget(axis)
        return None if widget is None else int(widget.GetSliceIndex())

    def setSliceIndex(self, axis, index):
        axis = self._axis_index(axis)
        widget = self._plane_widget(axis)
        if widget is None:
            raise ValueError(f"axis {axis} was not enabled when the slicer was created")
        index = int(index)
        dimensions = widget.GetInput().GetDimensions()
        index = max(0, min(dimensions[axis] - 1, index))
        if index == widget.GetSliceIndex():
            return
        widget.SetSliceIndex(index)
        widget.Modified()
        self.slicing_indices[axis] = index
        self.sliceChanged.emit(axis, index)
        if self.show_intersection:
            self.plot_plane_intersections()

    def axisEnabled(self, axis):
        widget = self._plane_widget(axis)
        return bool(widget is not None and widget.GetEnabled())

    def setAxisEnabled(self, axis, enabled):
        axis = self._axis_index(axis)
        widget = self._plane_widget(axis)
        if widget is None and enabled:
            raise ValueError(f"axis {axis} was not created; recreate the slicer with it enabled")
        if widget is None:
            return
        enabled = bool(enabled)
        if bool(widget.GetEnabled()) == enabled:
            return
        widget.SetEnabled(enabled)
        self.axes_enabled[axis] = enabled
        self.axisEnabledChanged.emit(axis, enabled)

    def opacityValue(self):
        return float(self.opacity)

    def setOpacity(self, opacity):
        opacity = min(1.0, max(0.0, float(opacity)))
        self.opacity = opacity
        for widget in self.planeWidgets:
            widget.GetTexturePlaneProperty().SetOpacity(opacity)
            widget.Modified()

    def colorMap(self):
        return self.colormap

    def setColorMap(self, colormap):
        lookup_table = colormap_utils.make_LUT(colormap=colormap, c_range=(0, 1))
        lookup_table.SetSaturationRange(1.0, 1.0)
        lookup_table.SetTableRange(0, 1)
        self.colormap = colormap
        for widget in self.planeWidgets:
            widget.SetLookupTable(lookup_table)
            widget.Modified()

    def hasInterpolation(self):
        return bool(self.interpolate)

    def setInterpolation(self, interpolate):
        self.interpolate = bool(interpolate)
        for widget in self.planeWidgets:
            if self.interpolate:
                widget.TextureInterpolateOn()
                widget.SetResliceInterpolateToLinear()
            else:
                widget.TextureInterpolateOff()
                widget.SetResliceInterpolateToNearestNeighbour()
            widget.Modified()

    def Delete(self):
        self.observerRegistry().clear()
        for widget in self.planeWidgets:
            widget.Off()
            widget.RemoveAllObservers()
            widget.SetInteractor(None)
        for actor in getattr(self, 'intersections', {}).values():
            self.ren.RemoveActor(actor)
        self.planeWidgets.clear()
        self.planePolyData.clear()

    #     self.modify_slicer_texture()


    # def modify_slicer_texture(self):
    #     """
    #     Modify the texture of the slicing plane.
    #     """
    #     for plane in self.planePolyData:
    #         tex = plane.GetProperty().GetTexture()

    #         # planeWidget.Modified()


    def plot_plane_intersections(self, caller=None, event=None):
        """
        Calculates the intersection lines of the planes in self.planePolyData and plots them as vtkPolyData actors.
        """
        if not hasattr(self, "planePolyData") or len(self.planePolyData) < 2:
            return


        self.intersections = {}
        for i in range(len(self.planePolyData) - 1):
            for j in range(i + 1, len(self.planePolyData)):
                w1, w2 = self.planePolyData[i], self.planePolyData[j]

                p1 = w1.GetMapper().GetInput()
                p2 = w2.GetMapper().GetInput()


                triangulation_filter1 = vtk.vtkTriangleFilter()
                triangulation_filter1.SetInputData(p1)
                triangulation_filter1.Update()
                p1 = triangulation_filter1.GetOutput()

                triangulation_filter2 = vtk.vtkTriangleFilter()
                triangulation_filter2.SetInputData(p2)
                triangulation_filter2.Update()
                p2 = triangulation_filter2.GetOutput()


                intersection_filter = vtk.vtkIntersectionPolyDataFilter()
                intersection_filter.SetInputData(0, p1)
                intersection_filter.SetInputData(1, p2)
                intersection_filter.Update()

                intersection_polydata = intersection_filter.GetOutput()


                intersection_actor = return_actor(self.ren, actor_name=f"{self.name}-plane_intersection_{i}_{j}")
                if intersection_actor:
                    # If the intersection actor already exists, update its polydata
                    intersection_actor.GetMapper().SetInputData(intersection_polydata)
                    intersection_actor.Modified()
                else:
                    logger.debug(f"Creating intersection actor for planes {i} and {j}")
                    # Create a new actor for the intersection line
                    mapper = vtk.vtkPolyDataMapper()
                    mapper.SetInputData(intersection_polydata)
                    actor = vtk.vtkActor()
                    actor.SetMapper(mapper)
                    actor.GetProperty().SetColor(0, 0, 0)  # Red color for intersection lines
                    actor.GetProperty().SetLineWidth(4)
                    # actor.GetProperty().SetRenderLinesAsTubes(True)  # Optional: render lines as tubes for better visibility
                    actor.SetObjectName(f"{self.name}-plane_intersection_{i}_{j}")

                    self.ren.AddActor(actor)
                    self.intersections.update({f"{self.name}-plane_intersection_{i}_{j}": actor})


def return_actor(ren, actor_name='probe'):

    """Execute the return actor operation."""
    actors = ren.GetActors()

    for actor in actors:
        if actor.GetObjectName() == actor_name:
            return actor

    return None


def delete_actor(ren, actor_name='probe', wildcard=False, verbose=False):

    """Delete actor."""
    actors = ren.GetActors()

    if verbose:
        logger.debug(f'Removing actors fitting {actor_name}')
        if wildcard:
            logger.debug('Using wildcard matching')

    if wildcard:
        for actor in actors:
            checked_actor_name = actor.GetObjectName()
            if checked_actor_name.startswith(actor_name):
                ren.RemoveActor(actor)
                if verbose:
                    logger.debug(f"Removed actor: {checked_actor_name}")
        return
    else:
        for actor in actors:
            checked_actor_name = actor.GetObjectName()
            if checked_actor_name == actor_name:
                ren.RemoveActor(actor)
                if verbose:
                    logger.debug(f"Removed actor: {checked_actor_name}")
                return


def add_cube_axes(renderer, source_actor=None, bounds=[0,1,0,1,0,1], name='axes'):

    """Add cube axes."""
    axes = vtk.vtkCubeAxesActor()
    axes.SetCamera(renderer.GetActiveCamera())
    axes.GetProperty().SetColor((0,0,0))
    # axes.SetFlyModeToFurthestTriad()
    axes.SetFlyModeToOuterEdges()
    # axes.SetFlyModeToStaticEdges()

    if source_actor is not None:
        axes.SetBounds(source_actor.GetBounds())
    else:
        axes.SetBounds(bounds)

    axes_units = 'm'
    axes.SetXTitle('X-Axis')
    axes.SetXUnits(axes_units)
    axes.GetXAxesLinesProperty().SetColor(0.0, 0.0, 0.0)
    axes.GetTitleTextProperty(0).SetColor(0.0, 0.0, 0.0)
    axes.GetLabelTextProperty(0).SetColor(0.0, 0.0, 0.0)

    axes.SetYTitle('Y-Axis')
    axes.SetYUnits(axes_units)
    axes.GetYAxesLinesProperty().SetColor(0.0, 0.0, 0.0)
    axes.GetTitleTextProperty(1).SetColor(0.0, 0.0, 0.0)
    axes.GetLabelTextProperty(1).SetColor(0.0, 0.0, 0.0)

    axes.SetZTitle('Z-Axis')
    axes.SetZUnits(axes_units)
    axes.GetZAxesLinesProperty().SetColor(0.0, 0.0, 0.0)
    axes.GetTitleTextProperty(2).SetColor(0.0, 0.0, 0.0)
    axes.GetLabelTextProperty(2).SetColor(0.0, 0.0, 0.0)

    axes.GetXAxesGridlinesProperty().SetColor(0.0, 0.0, 0.0)
    axes.GetYAxesGridlinesProperty().SetColor(0.0, 0.0, 0.0)
    axes.GetZAxesGridlinesProperty().SetColor(0.0, 0.0, 0.0)

    axes.DrawXGridlinesOn()
    axes.DrawYGridlinesOn()
    axes.DrawZGridlinesOn()
    axes.SetGridLineLocation(axes.VTK_GRID_LINES_FURTHEST)

    axes.SetObjectName(name)
    axes.Modified()

    return axes

def add_sphere_axes(renderer, source_actor=None, pole=None, max_radius=None, name='sphere_axes'):


    """Add sphere axes."""
    axes = vtk.vtkPolarAxesActor()
    axes.SetCamera(renderer.GetActiveCamera())
    axes.GetProperty().SetColor((0,0,0))


    if pole is not None:
        axes.SetPole(pole)
    else:
        if source_actor is not None:
            actor_bounds = source_actor.GetBounds()

            source_radius = np.sqrt((actor_bounds[1] - actor_bounds[0])**2 + (actor_bounds[3] - actor_bounds[2])**2 + (actor_bounds[5] - actor_bounds[4])**2) / 2

            # pole_x = (actor_bounds[0] + actor_bounds[1]) / 2
            # pole_y = (actor_bounds[2] + actor_bounds[3]) / 2
            # pole_z = ( actor_bounds[5]) / 2

            # pole = [pole_x, pole_y, pole_z]
            # axes.SetPole(pole)
            axes.SetMaximumRadius(source_radius)

    axes.SetPole(0, 0, 0)

    axes.SetMinimumRadius(0.0)
    if max_radius is not None:
        axes.SetMaximumRadius(max_radius)
    axes.SetRequestedNumberOfPolarAxes(5)
    axes.SetMinimumAngle(0)
    axes.SetMaximumAngle(360.0)

    axesProp = axes.GetPolarAxisProperty()
    axesProp.SetColor(0,0,0)
    axesProp.SetLineWidth(2.0)

    axesProp2 = axes.GetSecondaryPolarArcsProperty()
    axesProp2.SetColor(0,0,0)
    axesProp2.SetLineWidth(2.0)

    axesProp3 = axes.GetSecondaryRadialAxesProperty()
    axesProp3.SetColor(0,0,0)
    axesProp3.SetLineWidth(2.0)

    axesProp4 = axes.GetLastRadialAxisProperty()
    axesProp4.SetColor(0,0,0)
    axesProp4.SetLineWidth(2.0)

    axesProp4 = axes.GetPolarArcsProperty()
    axesProp4.SetColor(0,0,0)
    axesProp4.SetLineWidth(2.0)

    textprop = axes.GetPolarAxisTitleTextProperty()
    textprop.SetColor(0,0,0)
    textprop.SetFontSize(24)

    textprop2 = axes.GetPolarAxisLabelTextProperty()
    textprop2.SetColor(0,0,0)
    textprop2.SetFontSize(20)

    textprop3 = axes.GetLastRadialAxisTextProperty()
    textprop3.SetColor(0,0,0)
    textprop3.SetFontSize(20)

    textprop4 = axes.GetSecondaryRadialAxesTextProperty()
    textprop4.SetColor(0,0,0)
    textprop4.SetFontSize(20)

    axes.SetCamera(renderer.GetActiveCamera())
    axes.Modified()
    axes.SetObjectName(name)


    return axes


# def create_text_widget(ren, iren, text='widget_text', object_name='text_widget',
#                        color=[0,0,0], position_1=[0.2, 0.0], position_2=[0.8, 0.05],
#                        enabled=True):

#     textWidget = vtk.vtkTextWidget()
#     textWidget.SetInteractor(iren)
#     # textWidget.SetTextActor(ren)

#     self.text_actor = vtk.vtkTextActor()
#     self.text_actor.SetInput(text)
#     self.text_actor.GetTextProperty().SetColor(color[0], color[1], color[2])
#     self.text_actor.GetTextProperty().SetJustificationToLeft()
#     self.text_actor.GetTextProperty().SetShadow(1)
#     self.text_actor.SetObjectName(object_name)

#     # Create the text representation. Used for positioning the self.text_actor
#     text_representation = vtk.vtkTextRepresentation()
#     text_representation.GetPositionCoordinate().SetCoordinateSystemToNormalizedDisplay()
#     text_representation.GetPositionCoordinate().SetValue(position_1[0], position_1[1])
#     text_representation.GetPosition2Coordinate().SetValue(position_2[0], position_2[1])


#     textWidget.SetRepresentation(text_representation)

#     textWidget.SelectableOff()
#     textWidget.SetTextActor(self.text_actor)
#     textWidget.SetRepresentation(text_representation)
#     textWidget.SetObjectName(object_name)


#     if not hasattr(ren, 'widgets'):
#         ren.widgets = dict()
#     ren.widgets.update({object_name: textWidget})

#     if enabled:
#         textWidget.On()
#     else:
#         textWidget.Off()

#     return textWidget


class SplineWidget(vtk.vtkSplineWidget, WidgetMixin):
    """
    A class to create a spline widget in VTK.
    This widget allows the user to interactively create and manipulate a spline in 3D space.
    """

    def __init__(self, ren, iren, points=None, name='widgets/spline_widget', enabled=True,
                 labels=None, label_offset=[0, 0, 0.2], label_color=[1, 1, 1],
                 project_to_plane=True, projection_plane='z'):
        """Initialize the instance."""
        super().__init__()
        self.initWidget(name)
        self.pointsChanged = Signal(self)


        self.SetInteractor(iren)
        self.SetObjectName(name)

        if isinstance(points, vtk.vtkPoints):
            point_array = np.asarray([
                points.GetPoint(index)
                for index in range(points.GetNumberOfPoints())])
        elif points is not None:
            point_array = np.asarray(points, dtype=float)
        else:
            point_array = np.empty((0, 3), dtype=float)
        if point_array.ndim != 2 or point_array.shape[1:] != (3,):
            raise ValueError('points must be an N by 3 array')
        if len(point_array) < 2:
            raise ValueError('SplineWidget requires at least two points')
        number_of_points = len(point_array)
        self.SetNumberOfHandles(number_of_points)
        for index, point in enumerate(point_array):
            self.SetHandlePosition(index, *point)
        self._current_point = -1


        logger.debug(f'Spline widget created with {number_of_points} points.')


        self.label_offset = np.asarray(label_offset)

        def on_interaction_event(caller, event):

            """Handle interaction event."""
            current_time = time.time()

            if current_time - self.last_modified < 0.03:
                return
            else:
                self.last_modified = current_time

                actors = ren.GetActors()

                for i in range(self.GetNumberOfHandles()):
                    handle_position = np.asarray(self.GetHandlePosition(i))

                    handle_name = name + '_text_%d' % i

                    follower = None
                    for actor in actors:
                        if actor.GetObjectName() == handle_name:
                            follower = actor
                            break
                    if follower is not None:
                        follower.SetPosition(handle_position + self.label_offset)
                    else:
                        pass
                self.pointsChanged.emit(self.points())

        if labels is not None:

            if isinstance(labels, list):
                for i, label in enumerate(labels):

                    textsource = vtk.vtkVectorText()
                    textsource.SetText(label)
                    mapper = vtk.vtkPolyDataMapper()
                    mapper.SetInputConnection(textsource.GetOutputPort())

                    follower = vtk.vtkFollower()
                    follower.SetMapper(mapper)
                    follower.Modified()
                    follower.SetCamera(ren.GetActiveCamera())
                    follower.SetScale(0.1, 0.1, 0.1)
                    follower.SetPosition(self.GetHandlePosition(i) + self.label_offset)
                    follower.GetProperty().SetColor(label_color[0], label_color[1], label_color[2])
                    follower.SetObjectName(name + '_text_%d' % i)
                    if enabled:
                        follower.SetVisibility(True)
                    else:
                        follower.SetVisibility(False)
                    ren.AddActor(follower)


            elif isinstance(labels, np.ndarray):
                for i, label in enumerate(labels):
                    textsource = vtk.vtkVectorText()
                    textsource.SetText(str(label))
                    mapper = vtk.vtkPolyDataMapper()
                    mapper.SetInputConnection(textsource.GetOutputPort())

                    follower = vtk.vtkFollower()
                    follower.SetMapper(mapper)
                    follower.Modified()
                    follower.SetCamera(ren.GetActiveCamera())
                    follower.SetScale(0.1, 0.1, 0.1)
                    follower.SetPosition(self.GetHandlePosition(i) + self.label_offset)
                    follower.GetProperty().SetColor(label_color[0], label_color[1], label_color[2])
                    follower.SetObjectName(name + '_text_%d' % i)
                    if enabled:
                        follower.SetVisibility(True)
                    else:
                        follower.SetVisibility(False)
                    ren.AddActor(follower)


        if enabled:
            self.On()
            self.SetProcessEvents(True)
        else:
            self.Off()


        self.last_modified = time.time()

        self.SetProjectToPlane(project_to_plane)
        if project_to_plane:
            if projection_plane.lower() == 'x':
                self.SetProjectionNormalToXAxes()
                offsets = point_array[:, 0]
                if not np.all(offsets == offsets[0]):
                    logger.warning(f'{bcolors.WARNING}Warning: Not all x-coordinates are the same, setting projection position to the first x-coordinate value.{bcolors.ENDC}')
                    # If all z-coordinates are the same, set projection position to 0.0
                self.SetProjectionPosition(offsets[0])
            elif projection_plane.lower() == 'y':
                self.SetProjectionNormalToYAxes()
                offsets = point_array[:, 1]
                if not np.all(offsets == offsets[0]):
                    logger.warning(f'{bcolors.WARNING}Warning: Not all y-coordinates are the same, setting projection position to the first y-coordinate value.{bcolors.ENDC}')
                self.SetProjectionPosition(offsets[0])

            elif projection_plane.lower() == 'z':
                self.SetProjectionNormalToZAxes()
                offsets = point_array[:, 2]
                if not np.all(offsets == offsets[0]):
                    logger.warning(f'{bcolors.WARNING}Warning: Not all z-coordinates are the same, setting projection position to the first z-coordinate value.{bcolors.ENDC}')
                self.SetProjectionPosition(offsets[0])


            else:
                raise ValueError('Invalid projection plane: %s. Use "x", "y", or "z".' % projection_plane)


        self.ownObserver(self, 'InteractionEvent', on_interaction_event)

        self.Modified()

        if not hasattr(ren, 'widgets'):
            ren.widgets = dict()
        ren.widgets.update({name: self})

    def pointCount(self):
        return int(self.GetNumberOfHandles())

    def points(self):
        return tuple(tuple(self.GetHandlePosition(index))
                     for index in range(self.pointCount()))

    def setPoints(self, points):
        points = np.asarray(points, dtype=float)
        if points.ndim != 2 or points.shape[1:] != (3,) or len(points) < 2:
            raise ValueError('points must be an N by 3 array with at least two rows')
        self.SetNumberOfHandles(len(points))
        for index, point in enumerate(points):
            self.SetHandlePosition(index, *point)
        self.Modified()
        self.pointsChanged.emit(self.points())

    def addPoint(self, point):
        points = list(self.points())
        points.append(tuple(point))
        self.setPoints(points)

    def insertPoint(self, index, point):
        points = list(self.points())
        points.insert(int(index), tuple(point))
        self.setPoints(points)

    def removePoint(self, index):
        points = list(self.points())
        if len(points) <= 2:
            raise ValueError('a spline must retain at least two points')
        removed = points.pop(int(index))
        self.setPoints(points)
        return removed

    def clear(self):
        self.SetNumberOfHandles(0)
        self._current_point = -1
        self.Modified()
        self.pointsChanged.emit(())

    def currentPoint(self):
        return self._current_point

    def setCurrentPoint(self, index):
        index = int(index)
        if index < -1 or index >= self.pointCount():
            raise IndexError(index)
        self._current_point = index

    def isClosed(self):
        return bool(self.GetClosed())

    def setClosed(self, closed):
        self.SetClosed(bool(closed))
        self.Modified()


class MeshProbeWidget(WidgetMixin):

    def __init__(self, dataset, probe_mesh, renderer, colormap='viridis', probe_subdivisions=0,
                 opacity=1, name='widgets/mesh_probe', use_lighting=True, include_RGB=True, existing_probe=None,
                 enabled=True, replace_actor=True, clip_to_bounds=False):

        """Initialize the instance."""
        self.initWidget(name)
        self.probeFinished = Signal(self)
        self.probe_mesh = probe_mesh
        self._dataset = dataset
        self.ren = renderer
        self.colormap = colormap
        self.probe_subdivisions = probe_subdivisions
        self.opacity = opacity
        self.name = name
        self.use_lighting = use_lighting
        self.include_RGB = include_RGB
        self.existing_probe = existing_probe
        self.enabled = enabled
        self.replace_actor = replace_actor


        volume_bounds = dataset.GetMapper().GetInput().GetBounds()

        if probe_subdivisions > 0:

            logger.debug('subdividing mesh, may take a while')

            # subdivider = vtk.vtkAdaptiveSubdivisionFilter()
            # subdivider = vtk.vtkButterflySubdivisionFilter()
            subdivider = vtk.vtkLinearSubdivisionFilter()
            # subdivider.SetMaximumNumberOfPasses(probe_subdivisions)
            subdivider.SetNumberOfSubdivisions(probe_subdivisions)



            tri_filter = vtk.vtkTriangleFilter()
            tri_filter.SetInputData(probe_mesh.GetMapper().GetInput())
            tri_filter.Update()
            subdivider.SetInputData(tri_filter.GetOutput())

            # subdivider.SetInputData(probe_mesh.GetMapper().GetInput())
            subdivider.Update()

            sample_points = subdivider.GetOutput().GetPoints().GetData()

            probe_mesh.GetMapper().SetInputConnection(subdivider.GetOutputPort())
            probe_mesh.Modified()
            probe_mesh.GetMapper().Update()


        else:
            if isinstance(probe_mesh, vtk.vtkActor):

                probe_mesh.GetMapper().Update()
                mesh = probe_mesh.GetMapper().GetInput().GetPoints()
                sample_points = mesh.GetData()

            elif isinstance(probe_mesh, vtk.vtkPolyData):

                sample_points = probe_mesh.GetPoints().GetData()

            if clip_to_bounds:
                sample_points = self.fit_to_bounds(sample_points, volume_bounds)

        if not isinstance(sample_points, np.ndarray):
            pts = numpy_support.vtk_to_numpy(sample_points)
        else:
            pts = sample_points

        def _readpoints():
            """Execute the readpoints operation."""
            output = src.GetPolyDataOutput()
            points = vtk.vtkPoints()
            points.SetData(numpy_support.numpy_to_vtk(pts))
            output.SetPoints(points)

            cells = vtk.vtkCellArray()
            cells.InsertNextCell(len(pts))
            for i in range(len(pts)):
                cells.InsertCellPoint(i)
            output.SetVerts(cells)

        src = vtk.vtkProgrammableSource()
        src.SetExecuteMethod(_readpoints)
        src.Update()
        img = dataset.GetMapper().GetInput()

        self.probeFilter = vtk.vtkProbeFilter()
        self.probeFilter.SetSourceData(img)
        self.probeFilter.SetInputConnection(src.GetOutputPort())
        self.probeFilter.Update()


        probe_values = self.probeFilter.GetOutput().GetPointData().GetScalars()
        probe_values.SetName("Overlaps")

        numpy_values = numpy_support.vtk_to_numpy(probe_values)

        numpy_range = [np.min(numpy_values), np.max(numpy_values)]

        lut = colormap_utils.make_LUT(colormap=colormap, c_range=numpy_range, nan_color=(0,0,1,1), set_outside_colors_to_edges=True)

        vtk_color_data = vtk.vtkUnsignedCharArray()
        vtk_color_data.SetNumberOfComponents(3)
        vtk_color_data.SetName("Colors")
        for val in numpy_values:
            col = [0., 0., 0.]
            lut.GetColor(val, col)
            col = [int(c * 255) for c in col]
            vtk_color_data.InsertNextTuple3(col[0], col[1], col[2])


        if replace_actor and isinstance(probe_mesh, vtk.vtkActor):

            probe_mesh.GetMapper().GetInput().GetPointData().AddArray(probe_values)
            probe_mesh.GetMapper().GetInput().GetPointData().SetActiveScalars("Overlaps")
            if include_RGB:
                probe_mesh.GetMapper().GetInput().GetPointData().AddArray(vtk_color_data)

            probe_mesh.GetMapper().SetLookupTable(lut)
            probe_mesh.GetProperty().SetOpacity(opacity)
            probe_mesh.GetMapper().ScalarVisibilityOn()
            probe_mesh.GetMapper().SetScalarRange(numpy_range)

            if use_lighting:
                probe_mesh.GetProperty().LightingOn()
            else:
                probe_mesh.GetProperty().LightingOff()

            probe_mesh.SetObjectName(name)

            probe_mesh.GetProperty().SetAmbient(0.8)
            probe_mesh.GetProperty().SetDiffuse(1)
            probe_mesh.GetProperty().SetSpecular(0.05)
            probe_mesh.GetProperty().SetSpecularPower(50)

            if enabled:
                probe_mesh.SetVisibility(True)
            else:
                probe_mesh.SetVisibility(False)


            probe_mesh.SetObjectName(self.name)
            probe_mesh.Modified()

            self.probe_mesh = probe_mesh

        else:

            if existing_probe is not None:


                existing_probe.GetMapper().SetInputData(probe_mesh)
                existing_probe.GetMapper().GetInput().GetPointData().AddArray(probe_values)
                existing_probe.GetMapper().GetInput().GetPointData().SetActiveScalars("Overlaps")
                if include_RGB:
                    existing_probe.GetMapper().GetInput().GetPointData().AddArray(vtk_color_data)
                existing_probe.Modified()
                existing_probe.SetObjectName(name)

                self.probe_mesh = existing_probe

            else:

                new_actor = vtk.vtkActor()
                new_actor.SetMapper(vtk.vtkPolyDataMapper())
                poly_copy = vtk.vtkPolyData()
                if isinstance(probe_mesh, vtk.vtkActor):
                    poly_copy.DeepCopy(probe_mesh.GetMapper().GetInput())
                else:
                    poly_copy.DeepCopy(probe_mesh)
                new_actor.GetMapper().SetInputData(poly_copy)
                new_actor.GetMapper().SetLookupTable(lut)
                new_actor.GetMapper().ScalarVisibilityOn()
                new_actor.GetMapper().SetScalarRange(numpy_range)
                new_actor.GetProperty().SetOpacity(opacity)
                new_actor.SetObjectName(name)

                new_actor.GetMapper().GetInput().GetPointData().AddArray(probe_values)
                new_actor.GetMapper().GetInput().GetPointData().SetActiveScalars("Overlaps")
                if include_RGB:
                    new_actor.GetMapper().GetInput().GetPointData().AddArray(vtk_color_data)


                if enabled:
                    new_actor.SetVisibility(True)
                else:
                    new_actor.SetVisibility(False)

                self.probe_mesh = new_actor


        if not hasattr(self.ren, 'widgets'):
            self.ren.widgets = dict()
        self.ren.widgets.update({name: self})
        self.probeFinished.emit(self.probe_mesh)

    def dataset(self):
        return self._dataset

    def setDataset(self, dataset, reprobe=True):
        self._dataset = dataset
        if reprobe:
            self.ReProbe(dataset)

    def probeMesh(self):
        return self.probe_mesh

    def result(self):
        scalars = (self.probe_mesh.GetMapper().GetInput()
                   .GetPointData().GetScalars())
        return None if scalars is None else numpy_support.vtk_to_numpy(scalars)

    def probe(self, dataset=None):
        self.ReProbe(dataset)
        return self.probe_mesh

    def setVisible(self, visible):
        visible = bool(visible)
        if visible == self.isVisible():
            return
        self._ui_visible = visible
        self.probe_mesh.SetVisibility(visible)
        self.visibilityChanged.emit(visible)

    def isVisible(self):
        return bool(self.probe_mesh.GetVisibility())


    def fit_to_bounds(self, points, bounds, buffer=0.0001):

        """Execute the fit to bounds operation."""
        points = numpy_support.vtk_to_numpy(points)

        below_x_bounds = points[:, 0] < bounds[0]
        above_x_bounds = points[:, 0] > bounds[1]
        below_y_bounds = points[:, 1] < bounds[2]
        above_y_bounds = points[:, 1] > bounds[3]
        below_z_bounds = points[:, 2] < bounds[4]
        above_z_bounds = points[:, 2] > bounds[5]

        points[below_x_bounds, 0] = bounds[0] + buffer
        points[above_x_bounds, 0] = bounds[1] - buffer
        points[below_y_bounds, 1] = bounds[2] + buffer
        points[above_y_bounds, 1] = bounds[3] - buffer
        points[below_z_bounds, 2] = bounds[4] + buffer
        points[above_z_bounds, 2] = bounds[5] - buffer


        return points

    def ReProbe(self, dataset=None):

        """Execute the re probe operation."""
        if dataset is not None:
            self._dataset = dataset
        dataset = self._dataset

        if isinstance(dataset, vtk.vtkVolume):
            dataset = dataset.GetMapper().GetInput()


        self.probeFilter.SetSourceData(dataset)
        self.probeFilter.Update()

        new_probe_values = self.probeFilter.GetOutput().GetPointData().GetScalars()

        self.probe_mesh.GetMapper().GetInput().GetPointData().SetScalars(new_probe_values)


        numpy_values = numpy_support.vtk_to_numpy(new_probe_values)

        numpy_range = [np.min(numpy_values), np.max(numpy_values)]

        lut = colormap_utils.make_LUT(colormap=self.colormap, c_range=numpy_range, nan_color=(0,0,1,1), set_outside_colors_to_edges=True)

        vtk_color_data = vtk.vtkUnsignedCharArray()
        vtk_color_data.SetNumberOfComponents(3)
        vtk_color_data.SetName("Colors")
        for val in numpy_values:
            col = [0., 0., 0.]
            lut.GetColor(val, col)
            col = [int(c * 255) for c in col]
            vtk_color_data.InsertNextTuple3(col[0], col[1], col[2])


        if self.include_RGB:
            self.probe_mesh.GetMapper().GetInput().GetPointData().AddArray(vtk_color_data)

        self.probe_mesh.GetMapper().SetLookupTable(lut)
        self.probe_mesh.GetMapper().SetScalarRange(numpy_range)
        self.probe_mesh.Modified()
        self.probeFinished.emit(self.probe_mesh)
        return self.probe_mesh


def write_gltf(source, savename='exported_scene.gltf', verbose=True):

    """Write gltf."""
    if verbose:
        logger.debug("%s", 'Writing GLTF to %s' % savename)
    try:
        exporter = vtk.vtkGLTFExporter()
    except AttributeError:
        logger.debug('Gltf exporting is not supported in your version of VTK, try updating')
    exporter.SetInput(source)
    exporter.InlineDataOn()
    exporter.SaveNormalOn()
    exporter.SetFileName(savename)
    exporter.Update()
    exporter.Write()
    if verbose:
        logger.debug('File written')


def export_button_callback(widget, event):
    """Export button callback."""
    value = widget.GetRepresentation().GetState()
    renwin = widget.GetCurrentRenderer().GetRenderWindow()

    logger.debug("%s %s", "Export Button pressed!", value)
    write_gltf(renwin)
    return


def plot_sphere_probe_callback(widget, event):
    """Plot sphere probe callback."""
    value = widget.GetRepresentation().GetState()
    renwin = widget.GetCurrentRenderer().GetRenderWindow()

    logger.debug("%s %s", "Sphere Button pressed!", value)


    probed_points = widget_utils.return_actor(widget.renderer, actor_name='widgets/sphere_widget_mesh')

    if probed_points is None:
        logger.debug('No probed points found')
        return
    else:
        sphere_coordinates = probed_points.GetMapper().GetInput().GetPoints().GetData()
        sphere_coordinates = vtk_to_numpy(sphere_coordinates)

        sphere_values = probed_points.GetMapper().GetInput().GetPointData().GetScalars()
        sphere_values = vtk_to_numpy(sphere_values)


        _mpl_utils().plot_spherical_slice(sphere_coordinates, sphere_values)

        return


def toggle_visibility_callback(widget, event, keys, wildcard=True):

    """Toggle visibility callback."""
    actors = widget.renderer.GetActors()
    value = widget.GetRepresentation().GetState()


    found_match = False

    if isinstance(keys, str):
        keys = [keys]

    for key in keys:
        for actor in actors:
            actor_name = actor.GetObjectName()

            if wildcard:
                if actor_name.startswith(key):
                    if value == 1:
                        actor.SetVisibility(True)
                    elif value == 0:
                        actor.SetVisibility(False)
                    found_match = True
            else:
                if actor_name == key:
                    if value == 1:
                        actor.SetVisibility(True)
                    elif value == 0:
                        actor.SetVisibility(False)
                    found_match = True

        volumes = widget.renderer.GetVolumes()
        for volume in volumes:
            actor_name = volume.GetObjectName()

            if wildcard:
                if actor_name.startswith(key):
                    if value == 1:
                        volume.SetVisibility(True)
                    elif value == 0:
                        volume.SetVisibility(False)
                    found_match = True
            else:
                if actor_name == key:
                    if value == 1:
                        volume.SetVisibility(True)
                    elif value == 0:
                        volume.SetVisibility(False)
                    found_match = True


        if hasattr(widget.renderer, 'widgets'):
            widgets = widget.renderer.widgets

            for widget_name, widget_actor in widgets.items():
                if wildcard:
                    if widget_name.startswith(key):
                        found_match = True
                        if hasattr(widget_actor, 'SetEnabled'):
                            # For widgets that have SetEnabled method
                            if value == 1:
                                widget_actor.SetEnabled(True)
                            elif value == 0:
                                widget_actor.SetEnabled(False)

                else:
                    if widget_name == key:
                        found_match = True
                        if hasattr(widget_actor, 'SetEnabled'):
                            if value == 1:
                                widget_actor.SetEnabled(True)
                            elif value == 0:
                                widget_actor.SetEnabled(False)
                            found_match = True

        if not found_match:
            logger.debug("%s", bcolors.WARNING + f'No actor or volume found with name {key}' + bcolors.ENDC)


def rendering_properties_callback(widget, event, keys, property, wildcard=True):

    """Handle the rendering properties callback event."""
    actors = widget.renderer.GetActors()

    if isinstance(widget.GetRepresentation(), vtk.vtkButtonRepresentation):
        value = widget.GetRepresentation().GetState()
    elif isinstance(widget.GetRepresentation(), vtk.vtkSliderRepresentation):
        value = widget.GetRepresentation().GetValue()
    else:
        logger.warning("%s", bcolors.WARNING + 'Unsupported widget representation for rendering properties callback' + bcolors.ENDC)
        return

    def change_property(actor, property, value):
        """Execute the change property operation."""
        if hasattr(actor, 'GetProperty'):
            if property.lower() == 'opacity':
                actor.GetProperty().SetOpacity(value)
            elif property.lower() == 'color':
                actor.GetProperty().SetColor(value)
            elif property.lower() == 'specular':
                actor.GetProperty().SetSpecular(value)
            elif property.lower() == 'specular power':
                actor.GetProperty().SetSpecularPower(value)
            elif property.lower() == 'ambient':
                actor.GetProperty().SetAmbient(value)
            elif property.lower() == 'diffuse':
                actor.GetProperty().SetDiffuse(value)
            elif property.lower() == 'lighting':
                if value:
                    actor.GetProperty().LightingOn()
                else:
                    actor.GetProperty().LightingOff()
            elif property.lower() == 'visibility':
                if value == 1:
                    actor.SetVisibility(True)
                elif value == 0:
                    actor.SetVisibility(False)
            elif property.lower() == 'scalar_visibility':
                if value:
                    actor.GetMapper().ScalarVisibilityOn()
                else:
                    actor.GetMapper().ScalarVisibilityOff()
            elif property.lower() == 'wireframe':
                if value:
                    actor.GetProperty().SetRepresentationToWireframe()
                else:
                    actor.GetProperty().SetRepresentationToSurface()

            elif property.lower() == 'smooth shading':
                if value:
                    actor.GetProperty().SetInterpolationToGouraud()
                    if actor.GetMapper().GetInput().GetPointData().GetNormals() is None:
                        new_normals = vtk.vtkPolyDataNormals()
                        new_normals.SetInputData(actor.GetMapper().GetInput())
                        new_normals.ComputePointNormalsOn()
                        new_normals.ComputeCellNormalsOn()
                        new_normals.SetAutoOrientNormals(True)
                        new_normals.SetConsistency(True)
                        new_normals.Update()
                        actor.GetMapper().SetInputData(new_normals.GetOutput())
                    if actor.GetMapper().GetInput().GetCellData().GetNormals() is None:
                        new_normals = vtk.vtkPolyDataNormals()
                        new_normals.SetInputData(actor.GetMapper().GetInput())
                        new_normals.ComputePointNormalsOn()
                        new_normals.ComputeCellNormalsOn()
                        new_normals.SetAutoOrientNormals(True)
                        new_normals.SetConsistency(True)
                        new_normals.Update()
                        actor.GetMapper().SetInputData(new_normals.GetOutput())
                else:
                    actor.GetProperty().SetInterpolationToFlat()
            else:
                logger.warning("%s", bcolors.WARNING + f'Unknown property: {property}' + bcolors.ENDC)

            actor.Modified()

    found_match = False

    if isinstance(keys, str):
        keys = [keys]

    for key in keys:
        for actor in actors:
            actor_name = actor.GetObjectName()

            if wildcard:
                if actor_name.startswith(key):


                    change_property(actor, property, value)
                    found_match = True
            else:
                if actor_name == key:
                    change_property(actor, property, value)
                    found_match = True

        volumes = widget.renderer.GetVolumes()
        for volume in volumes:
            actor_name = volume.GetObjectName()

            if wildcard:
                if actor_name.startswith(key):
                    change_property(volume, property, value)
                    found_match = True
            else:
                if actor_name == key:
                    change_property(volume, property, value)
                    found_match = True


        if hasattr(widget.renderer, 'widgets'):
            widgets = widget.renderer.widgets

            for widget_name, widget_actor in widgets.items():
                if wildcard:
                    if widget_name.startswith(key):
                        change_property(widget_actor, property, value)
                        found_match = True
                else:
                    if widget_name == key:
                        change_property(widget_actor, property, value)
                        found_match = True

        if not found_match:
            logger.debug("%s", bcolors.WARNING + f'No actor or volume found with name {key}' + bcolors.ENDC)


def plot_button_callback(widget, event):
    """Plot button callback."""
    value = widget.GetRepresentation().GetState()
    renwin = widget.GetCurrentRenderer().GetRenderWindow()

    logger.debug("%s %s", "Plot Button pressed!", value)

    compton_array = widget.renderer.Compton_Array.compton_array
    logger.debug("%s", compton_array.shape)
    voxel_size = widget.renderer.Compton_Array.voxel_size

    # def plot_compton_slices():
    #     plotting_utils.plot_compton_slices(compton_array, voxel_sizes=voxel_size)

    # plot_thread = threading.Thread(target=plot_compton_slices)
    # plot_thread.start()
    # plot_thread.join()

    _mpl_utils().plot_compton_slices(compton_array, voxel_sizes=voxel_size)

    return


def flip_state_callback(widget, event, statename, ren):

    """Handle the flip state callback event."""
    value = widget.GetRepresentation().GetState()
    # ren = widget.renderer

    if hasattr(ren, statename):


        if value == 1:
            ren.statename = True
        else:
            ren.statename = False

        ren.Modified()

        logger.debug(f'{statename} set to {ren.statename}')

    return


def threshold_slider_callback(widget, event, keys, verbose=False, update_interval=0.03, wildcard=True):

    """Handle the threshold slider callback event."""
    value = widget.GetRepresentation().GetValue()

    if value < 1:
        value = 1

    if not hasattr(widget, 'last_modified'):
        last_modified = time.time()
        widget.last_modified = last_modified

    last_modified = widget.last_modified
    current_time = time.time()

    if current_time - last_modified < update_interval:
        if verbose:
            logger.debug("Threshold Slider callback ignored, too soon after last modification")
        return
    else:
        widget.last_modified = current_time
        if verbose:
            logger.debug("Threshold Slider callback executed, last modified time updated")

    # widget_names = widget.renderer.widgets.keys()
    actors = widget.renderer.GetActors()

    if isinstance(keys, str):
        keys = [keys]

    for key in keys:
        for actor in actors:
            widget_name = actor.GetObjectName()
            if widget_name.startswith(key):

                if not actor.GetVisibility():
                    continue

                if hasattr(actor, 'threshold_filter'):

                    actor.threshold_value = value
                    threshold_type = actor.threshold_type
                    if threshold_type == 'above':
                        actor.threshold_filter.SetUpperThreshold(value)
                        actor.threshold_filter.SetLowerThreshold(0.0)
                    elif threshold_type == 'below':
                        actor.threshold_filter.SetUpperThreshold(0.0)
                        actor.threshold_filter.SetLowerThreshold(value)
                    elif threshold_type == 'between':
                        # actor.threshold_filter.SetUpperThreshold(actor.upper_threshold_value)
                        # actor.threshold_filter.SetLowerThreshold(actor.lower_threshold_value)
                        pass

                    actor.threshold_filter.Update()

                    c_range = actor.threshold_filter.GetOutput().GetScalarRange()
                    actor.GetMapper().SetScalarRange(c_range)


                elif hasattr(actor, 'contour_filter'):
                    actor.contour_value = value
                    actor.contour_filter.SetValue(0, value)
                    actor.contour_filter.Update()
    return


def plot_slices_callback(widget, event, verbose=True):
    """Plot slices callback."""
    value = widget.GetRepresentation().GetState()
    renwin = widget.GetCurrentRenderer().GetRenderWindow()

    logger.debug("%s %s", "Slicer Button pressed!", value)

    sliced_axes = ['x', 'y', 'z']

    for slice_axis in sliced_axes:

        imageplane = widget_utils.return_widget(widget.renderer, widget_name='widgets/slice-%s' % slice_axis, verbose=False)

        if imageplane is None:
            if verbose:
                logger.debug("%s", 'No probed points found for slice %s' % slice_axis)
            continue

        else:

            image_data = imageplane.GetResliceOutput()



            # imageplane.Update()
            origin = np.array(imageplane.GetOrigin())
            point1 = np.array(imageplane.GetPoint1())
            point2 = np.array(imageplane.GetPoint2())

            v1 = point1 - origin
            v2 = point2 - origin

            v1 = v1 / np.linalg.norm(v1)
            v2 = v2 / np.linalg.norm(v2)


            if np.isclose(v1[0], 1.0):
                x_label = 'X'
            elif np.isclose(v1[1], 1.0):
                x_label = 'Y'
            elif np.isclose(v1[2], 1.0):
                x_label = 'Z'
            else:
                x_label = '(%.2fx, %.2fy, %.2fz)' % (v1[0], v1[1], v1[2])


            if np.isclose(v2[0], 1.0):
                y_label = 'X'
            elif np.isclose(v2[1], 1.0):
                y_label = 'Y'
            elif np.isclose(v2[2], 1.0):
                y_label = 'Z'
            else:
                y_label = '(%.2fx, %.2fy, %.2fz)' % (v2[0], v2[1], v2[2])


            if image_data is None:
                if verbose:
                    logger.debug("%s", f'{bcolors.WARNING}No image data found for slice %s{bcolors.ENDC}' % slice_axis)
                continue

            point_data = image_data.GetPointData()
            if point_data is None:
                if verbose:
                    logger.debug("%s", f'{bcolors.WARNING}No point data found for slice %s{bcolors.ENDC}' % slice_axis)
                continue

            if point_data.GetScalars() is None:
                if verbose:
                    logger.debug("%s", f'{bcolors.WARNING}No scalars found for slice %s{bcolors.ENDC}' % slice_axis)
                continue

            slice_image = vtk_to_numpy(image_data.GetPointData().GetScalars())

            if slice_axis == 'x':
                slice_image = np.reshape(slice_image, (image_data.GetDimensions()[1], image_data.GetDimensions()[0]))
            elif slice_axis == 'y':
                slice_image = np.reshape(slice_image, (image_data.GetDimensions()[1], image_data.GetDimensions()[0]))
            elif slice_axis == 'z':
                slice_image = np.reshape(slice_image, (image_data.GetDimensions()[1], image_data.GetDimensions()[0]))


            aspect_ratio = image_data.GetSpacing()[1] / image_data.GetSpacing()[0]

            _mpl_utils().plot_compton_slice(
                slice_image, aspect_ratio=aspect_ratio,
                xlabel=x_label, ylabel=y_label)


    import_optional(
        "matplotlib.pyplot", extra="scientific",
        purpose="plot display").show()

    # write_gltf(renwin)
    return


def modify_selection_callback(widget, event, method='reset'):

    """Handle the modify selection callback event."""
    ren = widget.renderer
    Event_Selections = ren.Compton_Events.Event_Selection

    if method == 'reset':
        Event_Selections.Reset()
    elif method == 'invert':
        Event_Selections.Invert()
    elif method == 'select_all':
        Event_Selections.SetAllToTrue()
    elif method == 'select_none':
        Event_Selections.SetAllToFalse()
    elif method == 'add_to_selection':
        if ren.Compton_Events.events_in_widget_bounds is not None:
            indices_to_add = ren.Compton_Events.events_in_widget_bounds
            Event_Selections.AddToSelection(indices_to_add)
        else:
            logger.debug(f'{bcolors.WARNING}No events selected in widget bounds.{bcolors.ENDC}')
    elif method == 'remove_from_selection':
        if ren.Compton_Events.events_in_widget_bounds is not None:
            indices_to_remove = ren.Compton_Events.events_in_widget_bounds
            Event_Selections.RemoveFromSelection(indices_to_remove)
        else:
            logger.debug(f'{bcolors.WARNING}No events selected in widget bounds.{bcolors.ENDC}')

    else:

        logger.warning("%s", bcolors.WARNING + f'Unknown method: {method}' + bcolors.ENDC)

    return


def list_actors(renderer):
    """Execute the list actors operation."""
    logger.debug('listing actors')
    actors = []

    for i in range(renderer.GetViewProps().GetNumberOfItems()):

        prop = renderer.GetViewProps().GetItemAsObject(i)
        prop_name = prop.GetObjectName()

        logger.debug("%s %s %s", 'Checking item', i, prop_name)

        if isinstance(prop, vtk.vtkActor):
            if isinstance(prop, vtk.vtkImageActor):
                logger.debug("%s %s", 'found image actor', prop.GetObjectName())
            else:
                logger.debug("%s %s", 'Is a (non-image) actor', prop.GetObjectName())

            actors.append(prop)
        elif isinstance(prop, vtk.vtkVolume):
            logger.debug("%s %s", 'found volume', prop)
        elif isinstance(prop, vtk.vtkButtonWidget):
            logger.debug("%s %s", 'found button', prop.GetObjectName())

    logger.debug("%s %s", 'Found actors:', actors)

    return actors


def list_widgets(renderer, verbose=True):

    """Execute the list widgets operation."""
    widgets = []

    if not hasattr(renderer, 'widgets'):
        logger.debug('No widgets found (no dictionary)')
    else:
        if verbose:
            logger.debug('Listing widgets')
        for key, value in renderer.widgets.items():
            if verbose:
                logger.debug("%s %s", 'Widget name:', key)
                logger.debug("%s %s", 'Widget type:', type(value))
                logger.debug("%s %s", 'Widget object name:', value.GetObjectName())
            widgets.append(value)

    if verbose:
        logger.debug("%s", 'Found %i widgets' % len(widgets))

    return widgets


def return_widget(renderer, widget_name, verbose=False):

    """Execute the return widget operation."""
    if not hasattr(renderer, 'widgets'):
        logger.debug('No widgets found (no dictionary)')
    else:
        for key, value in renderer.widgets.items():
            if key == widget_name:
                if verbose:
                    logger.debug("%s %s", 'Found widget:', key)
                return value
    if verbose:
        logger.warning('Widget not found')

    return None


__all__ = [
    "BoxWidget",
    "CameraOrientationWidget",
    "ColorBarWidget",
    "Cursor3DWidget",
    "LassoWidget",
    "MeshProbeWidget",
    "SphereProbeWidget",
    "SplineWidget",
    "VolumeSlicer",
]
