"""Panels, scrolling containers, and dock implementations."""

from ._widget_support import *
from .controls import *
from .controls import _SliderAPI, dummy_callback
import logging

logger = logging.getLogger(__name__)

def _button_types():
    """The native and composite icon-button classes."""
    from .composite import ButtonWidget as CompositeButtonWidget

    return (vtk.vtkButtonWidget, CompositeButtonWidget)


class ScrollableElement(WidgetMixin):
    def __init__(self, interactor, renderer, x, y, width, height,
                 panel_color=(1,1,1), opacity=0.5, show_background=True,
                 use_vector_button=True, border_width=4):
        """Initialize the instance."""
        self.interactor = interactor
        self.renderer = renderer
        self.initWidget()
        self.clicked = Signal(self)
        self.doubleClicked = Signal(self)
        self.selectionChanged = Signal(self)
        self._data = None
        self._selected = False
        self.x = x
        self.y = y
        self.width = width
        self.height = height
        self.list_index = 0
        self.visible = True
        self.show_background = show_background
        self.use_vector_button = use_vector_button
        self.border_width = border_width

        self.width_fraction = 0.95


        self.elements = []
        self.element_offsets = []
        self.element_sizes = []


        if self.show_background:
            theme = getattr(renderer, "theme", None)
            extra = {}
            offset_x, size_x = 0.01, self.width_fraction
            if getattr(theme, "well_color", None) is not None:
                # Themed rows: invisible until selected, then a soft accent
                # bar (accent blended over the list well) across the row.
                well = theme.well_color
                accent = theme.accent_color_rgb
                alpha = 0.32 if theme.dark_mode else 0.20
                extra["highlight_color"] = tuple(
                    w + (a - w) * alpha for w, a in zip(well, accent))
                panel_color, opacity, border_width = well, 0.0, 0
                offset_x, size_x = 0.0, 1.0
            background = PanelBackgroundWidget(
                renderer=renderer,
                interactor=interactor,
                panel_bounds=(x, x + (width * size_x), y, y + height),
                panel_color=(*panel_color,),
                opacity=opacity,
                border_width=border_width,
                buffer=0,
                grabbable=False,
                ui_z_order=UI_Z_SCROLL_ROWS,
                **extra,
            )

            self.add_element(background, offset_x=offset_x, offset_y=0, size_x=size_x, size_y=1)





    def add_element(self, element, offset_x=0, offset_y=0, size_x=1, size_y=1):
        """Add element."""
        self.elements.append(element)
        self.element_offsets.append((offset_x, offset_y))
        self.element_sizes.append((size_x, size_y))

    def calculate_pixel_height(self):
        """Calculate pixel height."""
        window_size = self.interactor.GetRenderWindow().GetSize()
        pixel_height = int(self.height * window_size[1])
        return pixel_height

    def update_element_positions(self, new_x=None, new_y=None, new_width=None,
                                 new_height=None, window_size=None,
                                 resize_elements=True):

        """Update element positions."""
        if new_x is not None:
            self.x = new_x
        if new_y is not None:
            self.y = new_y
        if new_width is not None:
            self.width = new_width
        if new_height is not None:
            self.height = new_height

        if new_x is None:
            new_x = self.x
        if new_y is None:
            new_y = self.y
        if new_width is None:
            new_width = self.width
        if new_height is None:
            new_height = self.height



        window_width, window_height = self.interactor.GetRenderWindow().GetSize()


        if window_width == 0:
            window_width = 1
        if window_height == 0:
            window_height = 1

        window_aspect_ratio = window_width / window_height


        for element, offset, size in zip(self.elements, self.element_offsets, self.element_sizes):


            if hasattr(element, 'SetPixelPosition'):


                pixel_x = int(new_x * window_size[0]) + int(offset[0] * window_size[0])
                pixel_y = int(new_y * window_size[1]) + int(offset[1] * window_size[1])
                pixel_width = int(self.height * window_size[0] * size[0])
                pixel_height = int(self.height * window_size[1] * size[1])

                element.SetPixelPosition(pixel_x, pixel_y, pixel_width, pixel_height)

            elif hasattr(element, 'SetPosition'):

                element.SetPosition(new_x + (offset[0] * new_width) , new_y + (offset[1] * new_height))
                if hasattr(element, 'SetSize'):
                    if resize_elements:
                        # Aspect-ratio adjustments belong to this element only.
                        # Mutating new_width/new_height here used to shrink every
                        # sibling laid out after a square vector button.
                        element_width = new_width * size[0]
                        element_height = new_height * size[1]

                        if (hasattr(element, 'equal_aspect_ratio') and
                                element.equal_aspect_ratio):
                            # Fit a square in display pixels. Normalized x/y
                            # units differ with the render-window aspect ratio.
                            pixel_side = min(
                                element_width * window_width,
                                element_height * window_height)
                            element_width = pixel_side / window_width
                            element_height = pixel_side / window_height

                        element.SetSize(element_width, element_height)
                        if hasattr(element, 'RefitTextToBounds'):
                            element.RefitTextToBounds()
                else:
                    logger.debug("%s %s", f"{bcolors.WARNING}Element has no SetSize method:{bcolors.ENDC}", element)

            else:
                logger.debug("%s %s", f"{bcolors.WARNING}Element has no SetPosition or SetPixelPosition method:{bcolors.ENDC}", element)

    def update_element_visibility(self, visible):
        """Update element visibility."""
        self.visible = visible
        for element in self.elements:
            element.SetVisibility(visible)

    def GetVisibility(self):
        """Execute the get visibility operation."""
        return self.visible

    def Delete(self):
        """Execute the delete operation."""
        for element in self.elements:
            element.Delete()

    def Highlight(self, highlight=True):
        """Execute the highlight operation."""
        old = self._selected
        self._selected = bool(highlight)
        for element in self.elements:
            if hasattr(element, 'Highlight'):
                element.Highlight(highlight)
            else:
                pass
        if old != self._selected:
            self.selectionChanged.emit(self._selected)

    def data(self):
        return self._data

    def setData(self, data):
        self._data = data

    def isSelected(self):
        return self._selected

    def setSelected(self, selected):
        self.Highlight(selected)

    def index(self):
        return self.list_index


class ScrollBox(WidgetMixin):
    """Reusable normalized-display scroll viewport for native VTK UI layouts.

    The box owns the scrollbar, clipping blinders, scroll metrics, and visible
    row registry.  It deliberately knows nothing about actors or hierarchy
    nodes; a containing widget supplies and lays out ``ScrollableElement`` rows.
    Bounds and sizes use normalized display coordinates consistently.
    """

    def __init__(self, renderer, interactor, bounds, row_height=0.02,
                 buffer=0.01, panel_color=(1, 1, 1), add_blinders=True,
                 scroll_callback=None, rounded_thumb=False, scrollbar_side='right',
                 scrollbar_padding=-0.00):
        self.renderer = renderer
        self.interactor = interactor
        self.initWidget()
        self.valueChanged = Signal(self)
        self.row_height = float(row_height)
        self.buffer = float(buffer)
        self.panel_color = tuple(panel_color)
        self.add_blinders = bool(add_blinders) and ENABLE_SCROLL_BLINDERS
        self.scrollbar_side = scrollbar_side
        self.scrollbar_padding = scrollbar_padding
        self.scroll_offset = 0.0
        self.total_height = 0.0
        self.visible_elements = {}
        self.scrollable_elements = []
        self.top_blinder = None
        self.bottom_blinder = None
        self.enabled = True
        self.SetBounds(*bounds)
        self._viewport_height = self.height
        callback = scroll_callback or dummy_callback

        if self.scrollbar_side == 'right':
            logger.debug("Placing scrollbar on right at %s", self.x + self.width)
            scrollbar_x = self.x + self.width
        elif self.scrollbar_side == 'left':
            logger.debug("Placing scrollbar on left at %s",
                         self.x - self.scrollbar_padding)
            scrollbar_x = self.x - self.scrollbar_padding # Adjust the offset for left side

        self.slider = SliderWidget(
            renderer, interactor, min_value=0.0, max_value=1.0,
            initial_value=0.0, title=None, callback=callback,
            position=(scrollbar_x, self.y + self.height),
            bar_length=self.height, slider_thickness=0.05,
            slider_bar_fraction=1.0, use_relative_position=True,
            orientation='vertical', show_value=False, enabled=False,
            ui_z_order=UI_Z_SCROLLBAR, register_draw_order=False)
        self.rounded_thumb = rounded_thumb
        self._style_scrollbar()
        self.update_slider_geometry()

    def _style_scrollbar(self):
        """Keep VTK's slider interaction with a modern visual thumb."""
        # Themed: a subtle track in the border colour and a muted thumb
        # (white track / black / crimson without a theme, as before).
        track = theme_value(self.renderer, "border_color", (1.0, 1.0, 1.0))
        native_thumb = theme_value(
            self.renderer, "muted_text_color", (0.0, 0.0, 0.0))
        rep = self.slider.rep
        rep.GetTubeProperty().SetColor(*track)
        rep.GetCapProperty().SetColor(*track)
        # The native thumb remains the hit target but is covered by the custom
        # rounded rectangle, so its square corners cannot show around it.
        rep.GetSliderProperty().SetColor(*native_thumb)
        rep.GetSelectedProperty().SetColor(*native_thumb)

        self._thumb_polydata = vtk.vtkPolyData()
        mapper = vtk.vtkPolyDataMapper2D()
        mapper.SetInputData(self._thumb_polydata)
        coordinate = vtk.vtkCoordinate()
        coordinate.SetCoordinateSystemToNormalizedViewport()
        mapper.SetTransformCoordinate(coordinate)

        if self.rounded_thumb:

            self._thumb_actor = vtk.vtkActor2D()
            self._thumb_actor.SetMapper(mapper)
            self._thumb_actor.GetProperty().SetColor(*theme_value(
                self.renderer, "muted_text_color",
                colormap_utils.color_to_RGB("alizarin_crimson")))
            self._thumb_actor.GetProperty().SetOpacity(1.0)
            self._thumb_actor.PickableOff()
            self._thumb_actor.SetVisibility(False)
            self._thumb_actor.IsUI = True
            add_actor_2d(ui_layer(self.renderer), self._thumb_actor)
            self.slider.overlay_actor = self._thumb_actor
            self.ownObserver(
                self.slider, vtk.vtkCommand.InteractionEvent,
                lambda _caller, _event: self._update_rounded_thumb())

    @staticmethod
    def _rounded_rectangle_polydata(x0, x1, y0, y1, radius_x, radius_y=None,
                                    corner_segments=5):
        """Build a filled rounded rectangle in normalized viewport space."""
        if radius_y is None:
            radius_y = radius_x
        radius_x = max(0.0, min(float(radius_x), (x1 - x0) / 2.0))
        radius_y = max(0.0, min(float(radius_y), (y1 - y0) / 2.0))
        corners = (
            (x1 - radius_x, y1 - radius_y, 0.0, np.pi / 2.0),
            (x0 + radius_x, y1 - radius_y, np.pi / 2.0, np.pi),
            (x0 + radius_x, y0 + radius_y, np.pi, 3.0 * np.pi / 2.0),
            (x1 - radius_x, y0 + radius_y,
             3.0 * np.pi / 2.0, 2.0 * np.pi),
        )
        outline = []
        for center_x, center_y, start, stop in corners:
            for angle in np.linspace(start, stop, corner_segments,
                                     endpoint=False):
                outline.append((center_x + radius_x * np.cos(angle),
                                center_y + radius_y * np.sin(angle), 0.0))
        points = vtk.vtkPoints()
        polygon = vtk.vtkPolygon()
        polygon.GetPointIds().SetNumberOfIds(len(outline))
        for index, point in enumerate(outline):
            points.InsertNextPoint(*point)
            polygon.GetPointIds().SetId(index, index)
        cells = vtk.vtkCellArray()
        cells.InsertNextCell(polygon)
        polydata = vtk.vtkPolyData()
        polydata.SetPoints(points)
        polydata.SetPolys(cells)
        return polydata

    def _update_rounded_thumb(self):
        """Synchronize the decorative thumb with the native slider value."""
        window_width, window_height = self.interactor.GetRenderWindow().GetSize()
        track_height = min(
            self.height, max(0.0, getattr(self, "_viewport_height", self.height)))
        track_height = max(
            0.0, track_height - getattr(self, "scrollbar_top_inset", 0.0))
        width = 20.0 / max(1, window_width)
        minimum_height = 18.0 / max(1, window_height)
        visible_fraction = getattr(self, "_visible_fraction", 1.0)
        thumb_height = min(track_height, max(
            minimum_height, track_height * visible_fraction))
        value_range = self.slider.rep.GetMaximumValue() - self.slider.rep.GetMinimumValue()
        fraction = (0.0 if value_range == 0.0 else
                    (self.slider.rep.GetValue() - self.slider.rep.GetMinimumValue()) /
                    value_range)
        # The point coordinates were already aspect-corrected when the native
        # vertical representation was laid out.  EndCapLength is consequently
        # the final normalized-display inset here; applying the window aspect
        # ratio again makes the overlay agree only in square windows.
        end_cap_inset = self.slider.rep.GetEndCapLength()
        top_center = (
            self.y + track_height - end_cap_inset - thumb_height / 2.0)
        bottom_center = self.y + end_cap_inset + thumb_height / 2.0
        if top_center < bottom_center:
            top_center = bottom_center = self.y + track_height / 2.0
        travel = top_center - bottom_center
        center_y = top_center - fraction * travel
        center_x = self.x + self.width
        # Define roundness in display pixels, then convert each axis back to
        # normalized viewport coordinates.  Equal normalized radii stretch in
        # wide or tall windows because their X/Y pixel scales differ.
        radius_pixels = min(
            width * max(1, window_width) / 2.0,
            thumb_height * max(1, window_height) / 2.0)
        radius_x = radius_pixels / max(1, window_width)
        radius_y = radius_pixels / max(1, window_height)
        geometry = self._rounded_rectangle_polydata(
            center_x - width / 2.0, center_x + width / 2.0,
            center_y - thumb_height / 2.0,
            center_y + thumb_height / 2.0, radius_x, radius_y)
        self._thumb_polydata.ShallowCopy(geometry)
        self._thumb_polydata.Modified()

    def SetBounds(self, x_min, x_max, y_min, y_max):
        values = tuple(float(value) for value in
                       (x_min, x_max, y_min, y_max))
        if values[1] <= values[0] or values[3] <= values[2]:
            raise ValueError("ScrollBox normalized bounds must have positive size")
        self.bounds = values
        self.x, self.y = values[0], values[2]
        self.width = values[1] - values[0]
        self.height = values[3] - values[2]
        if hasattr(self, 'slider'):
            self.update_slider_geometry()

    def GetBounds(self):
        return self.bounds

    def SetPosition(self, x, y):
        self.SetBounds(x, x + self.width, y, y + self.height)

    def SetSize(self, width, height):
        self.SetBounds(self.x, self.x + width, self.y, self.y + height)

    def viewport_height(self, title_band_height=0.0):
        return max(self.row_height, self.height - float(title_band_height))

    def viewport_top(self, title_band_height=0.0):
        return self.y + self.viewport_height(title_band_height)

    def set_content_height(self, total_height, viewport_height=None):
        self.total_height = max(0.0, float(total_height))
        viewport = (self.height if viewport_height is None
                    else max(self.row_height, float(viewport_height)))
        self._viewport_height = viewport
        maximum = max(0.0, self.total_height - viewport)
        self.scroll_offset = min(self.scroll_offset, maximum)
        fraction = (1.0 if self.total_height <= 0.0
                    else min(1.0, viewport / self.total_height))
        self.update_slider_geometry(fraction)
        if self.enabled and fraction < 1.0:
            self.slider.EnabledOn()
        else:
            self.slider.EnabledOff()
        return fraction

    def update_slider_geometry(self, visible_fraction=None):
        """Place and size the vertical scrollbar from normalized UI bounds."""
        if not hasattr(self, 'slider'):
            return
        if visible_fraction is None:
            visible_fraction = self.slider.rep.GetSliderLength() / max(
                self.height, 1e-12)
        visible_fraction = min(1.0, max(0.0, float(visible_fraction)))
        self._visible_fraction = visible_fraction

        window_width, window_height = self.interactor.GetRenderWindow().GetSize()
        aspect_ratio = max(1, window_width) / max(1, window_height)
        # The box includes the panel header, while its interactive viewport
        # does not. Keep the native track and overlay thumb out of that header.
        track_height = min(
            self.height, max(0.0, getattr(self, "_viewport_height", self.height)))
        track_height = max(
            0.0, track_height - getattr(self, "scrollbar_top_inset", 0.0))
        adjusted_span = track_height * aspect_ratio
        midpoint_y = self.y + track_height / 2.0
        point1 = self.slider.rep.GetPoint1Coordinate()
        point2 = self.slider.rep.GetPoint2Coordinate()
        point1.SetCoordinateSystemToNormalizedDisplay()
        point2.SetCoordinateSystemToNormalizedDisplay()
        point1.SetValue(self.x + self.width + self.scrollbar_padding,
                        midpoint_y + adjusted_span / 2.0)
        point2.SetValue(self.x + self.width + self.scrollbar_padding,
                        midpoint_y - adjusted_span / 2.0)
        self.slider.rep.SetSliderLength(visible_fraction * track_height)
        self.slider.Modified()
        self.slider.rep.Modified()
        self._update_rounded_thumb()

    def set_scroll_fraction(self, fraction, viewport_height=None):
        fraction = min(1.0, max(0.0, float(fraction)))
        old_fraction = float(self.slider.rep.GetValue())
        viewport = (self.height if viewport_height is None
                    else float(viewport_height))
        self.scroll_offset = fraction * max(
            0.0, self.total_height - viewport)
        self.slider.rep.SetValue(fraction)
        self.slider.rep.Modified()
        if not math.isclose(old_fraction, fraction, rel_tol=0.0,
                            abs_tol=1e-12):
            self.valueChanged.emit(fraction)
        return self.scroll_offset

    def value(self):
        return float(self.slider.rep.GetValue())

    def setValue(self, value):
        return self.set_scroll_fraction(value, self._viewport_height)

    def minimum(self):
        return 0.0

    def maximum(self):
        return 1.0

    def pageStep(self):
        if self.total_height <= 0:
            return 1.0
        return min(1.0, self._viewport_height / self.total_height)

    def scrollToTop(self):
        self.setValue(0.0)

    def scrollToBottom(self):
        self.setValue(1.0)

    def update_blinders(self, viewport_top, title_height, resize=True):
        if not self.add_blinders:
            return
        # Panels may restrict the masks to a recessed list well and colour
        # them to match it (blinder_extent = (x0, x1, y_min)).
        extent = getattr(self, "blinder_extent", None)
        x0 = extent[0] if extent else self.x
        width = (extent[1] - extent[0]) if extent else self.width * .97
        bottom = self.y - self.buffer + .01
        if extent:
            bottom = max(bottom, extent[2])
        bottom_height = max(0.0, self.y + self.row_height - bottom)
        color = getattr(self, "blinder_color", None) or self.panel_color
        if self.top_blinder is None:
            self.top_blinder = PanelBackgroundWidget(
                renderer=self.renderer, interactor=self.interactor,
                panel_bounds=(x0, x0 + width,
                              viewport_top, self.y + self.height + self.buffer),
                panel_color=color, opacity=1, buffer=0,
                grabbable=False, place_factor=1, border_width=0,
                ui_z_order=UI_Z_BLINDER)
            self.bottom_blinder = PanelBackgroundWidget(
                renderer=self.renderer, interactor=self.interactor,
                panel_bounds=(x0, x0 + width, bottom, bottom + bottom_height),
                panel_color=color, opacity=1, buffer=0,
                grabbable=False, place_factor=1, border_width=0,
                ui_z_order=UI_Z_BLINDER)
        else:
            self.top_blinder.SetPosition(x0, viewport_top)
            self.bottom_blinder.SetPosition(x0, bottom)
            # Always resize: the list's width changes without a full relayout
            # (e.g. when the scrollbar appears or the pane is resized).
            self.top_blinder.SetSize(width, max(0.0, title_height))
            self.bottom_blinder.SetSize(width, bottom_height)

    def SetVisibility(self, visible):
        self.enabled = bool(visible)
        for row in self.visible_elements.values():
            row.update_element_visibility(self.enabled)
        if not self.enabled:
            self.slider.EnabledOff()
        else:
            self.set_content_height(
                self.total_height, self._viewport_height)
        for blinder in (self.top_blinder, self.bottom_blinder):
            if blinder is not None:
                blinder.SetEnabled(self.enabled)

    def Delete(self):
        for row in list(self.visible_elements.values()):
            row.Delete()
        self.visible_elements.clear()
        self.scrollable_elements.clear()
        self.slider.SetEnabled(False)
        remove_actor_2d(ui_layer(self.renderer), self._thumb_actor)
        for blinder in (self.top_blinder, self.bottom_blinder):
            if blinder is not None:
                blinder.Delete()

class ScrollablePanel(WidgetMixin):
    # Re-sorts its own drawables after creating children (see
    # register_ui_drawable), so late lower-z children are expected.
    ui_sorts_draw_order = True


    # Row text is 55% of the row height (device pixels), clamped to a
    # readable range; panel titles use the same scale in bold.
    ROW_TEXT_FRACTION = 0.55

    def _row_text_size(self):
        # Based on the standard 0.02 row so every list uses the same text
        # size; taller rows (e.g. Scene Validation) just get more spacing.
        from ._widget_support import device_scale, user_scale
        window_height = self.interactor.GetRenderWindow().GetSize()[1]
        # Points, not device pixels: VTK scales font sizes by the DPI.
        row_points = max(1, round(
            min(self.element_height, 0.02 * user_scale()) * window_height
            / device_scale()))
        return max(9, min(32, round(row_points * self.ROW_TEXT_FRACTION)))

    @ui_scoped
    def __init__(self, interactor, iterable,
                 x=0.05, y=0.4,
                 width=0.3, height=0.3,
                 element_height=0.02,
                 buffer=0.01,
                 indent_size=0.05,
                 title="Scrollable Panel",
                 use_vector_buttons=True,
                 add_blinders=True,
                 panel_color=(1, 1, 1),
                 text_color=(0.0, 0.0, 0.0),
                 element_color=(1, 1, 1),
                 callback=dummy_callback,
                 use_background=True,
                 editable=False,
                 icon=None,
                 embedded=False,
                 pass_scroll_events=False,
                 ):

        """Initialize the instance."""
        self.interactor = interactor
        self.renderer = interactor.GetRenderWindow().GetRenderers().GetFirstRenderer()
        self.initWidget(title)
        self.currentItemChanged = Signal(self)
        self.itemClicked = Signal(self)
        self.itemDoubleClicked = Signal(self)
        self.itemActivated = Signal(self)
        self.itemsChanged = Signal(self)
        self._current_item = None
        self.iterable = iterable
        self.widgets = []
        self.scroll_offset = 0.0
        self.panel_title = title
        self.buffer = buffer
        self.use_vector_buttons = use_vector_buttons
        self.fixed_text_length = None
        self.add_blinders = bool(add_blinders) and ENABLE_SCROLL_BLINDERS
        self.element_color = element_color
        self.panel_color = panel_color
        self.text_color = text_color
        self.callback = callback
        self.editable = editable
        self.use_background = use_background
        self.embedded = bool(embedded)
        self.pass_scroll_events = bool(pass_scroll_events)
        self.parent_panel = None
        self._expanded_tree_keys = set()
        self._default_tree_keys_applied = set()
        self._root_items = []
        self._row_nodes = []
        self.collapsed = False
        self.collapse_button = None
        self._expanded_panel_size = (width, height)
        self.indent_size = indent_size


        # Fixed height per item, scaled by the UI scale preference.
        self.element_height = element_height * user_scale()  # a fraction


        if icon is None:
            self.icon = "default_icon"
        else:
            self.icon = icon

        self.x, self.y, self.width, self.height = x, y, width, height

        self.bounds = (self.x, self.x + self.width, self.y, self.y + self.height)

        if isinstance(iterable, vtk.vtkActorCollection):
            roots = self._renderer_scene_props()
            logger.debug("Using renderer top-level props for actor panel")
            self.is_actors = True

        else:
            logger.debug("Actors is not a vtkActorCollection, assuming it's an iterable list")
            roots = list(iterable)
            self.is_actors = False

        self._root_items = roots
        actors, self._row_nodes = self._flatten_hierarchy(roots)

        total_actors = len(actors)


        self.total_height = total_actors * self.element_height
        self.scroll_offset = min(
            self.scroll_offset,
            max(0.0, self.total_height - self._scroll_region_height()))



        # if self.total_height < height:
        # else:
        #     scrollbar_fraction = height / self.total_height


        self.base_x = x
        self.base_y = y

        self.scrollable_elements = []
        # Only rows intersecting the viewport are instantiated.  Native VTK
        # widgets are considerably heavier than Qt list items (and editable
        # TextWidgets add interactor observers), so retaining one row per scene
        # prop makes interaction cost grow with the entire scene.
        self._visible_elements = {}
        self._actors_list = actors
        self._row_colors = None
        self.top_blinder = None
        self.bottom_blinder = None
        self.panel_title_widget = None


        # self.panel_background = PanelBackgroundWidget(
        #     renderer=self.renderer,
        #     interactor=self.interactor,
        #     panel_bounds=(self.x, self.x + (self.width), self.y, self.y + self.height),
        #     panel_color=(*self.panel_color,),
        #     opacity=1,
        #     buffer=self.buffer,
        #     grabbable=False,
        # )

        self.panel_background = VectorPanelBackground(
            renderer=self.renderer,
            interactor=self.interactor,
            bounds=(self.x, self.x + (self.width), self.y, self.y + self.height),
            panel_color=(*self.panel_color,),
            parent=self,
            opacity=1,
            movable=not self.embedded,
            resizable=True,
            draggable_edges=(VectorPanelBackground.EDGE_BOTTOM
                             if self.embedded else None),
            minimum_height_pixels=max(
                50, int(self.element_height * max(
                    1, interactor.GetRenderWindow().GetSize()[1]) * 2.5)),
        )


        # self.panel_background.AddObserver("ResizeEvent", partial(self.update_layout, update_actors=True))
        self.ownObserver(
            self.panel_background, "EndInteractionEvent",
            partial(self.update_layout, update_actors=False))
        # Header band drawn as its own layer above the scroll masks
        # (blinders) and below the title, so masking never covers it.
        self.header_layer = None
        if not self.embedded and theme_value(self.renderer, "title_color", None) is not None:
            self.header_layer = VectorPanelBackground(
                renderer=self.renderer, interactor=self.interactor,
                bounds=(self.x, self.x + self.width, self.y, self.y + self.height),
                panel_color=(*self.panel_color,), parent=self, opacity=1,
                movable=False, resizable=False, decorations_only=True,
                corner_radius=self.panel_background.corner_radius,
                name="panel_header", ui_z_order=UI_Z_BLINDER + 5)
        if self.embedded:
            self.ownObserver(
                self.panel_background, "InteractionEvent",
                self._embedded_resize_callback)
        # self.panel_background.AddObserver("ModifiedEvent", partial(self.update_layout, update_actors=True))

        # QVTKRenderWindowInteractor reports Qt widget resizing as
        # ConfigureEvent, while standalone VTK windows normally emit
        # WindowResizeEvent on the render window. Listen to both paths.
        self._last_layout_window_size = tuple(
            self.interactor.GetRenderWindow().GetSize())
        self.ownObserver(
            self.interactor, "ConfigureEvent", self._on_window_resize)
        self.ownObserver(
            self.interactor.GetRenderWindow(), "WindowResizeEvent",
            self._on_window_resize)

        if self.total_height == 0:
            self.total_height = self.height  # prevent division by zero

        self.scroll_box = ScrollBox(
            renderer=self.renderer, interactor=self.interactor,
            bounds=self.bounds, row_height=self.element_height,
            buffer=self.buffer, panel_color=self.panel_color,
            add_blinders=self.add_blinders,
            scroll_callback=self.scroll_callback)
        self.scroll_box.visible_elements = self._visible_elements
        self.scroll_box.set_content_height(
            self.total_height, self._scroll_region_height())
        # Compatibility aliases retained while callers migrate to ScrollBox.
        self.slider = self.scroll_box.slider
        # Blinders are created by the first layout; give them the well
        # colour/extent before that.
        self._apply_panel_decor()

        self.update_layout(update_actors=True)
        register_ui_drawable(
            self.renderer, self.slider, UI_Z_SCROLLBAR,
            f'{self.panel_title}_scrollbar')
        if not self.embedded:
            self.collapse_button = VectorButtonWidget(
                self.renderer, self.interactor,
                input_data=[
                    os.path.join(ICON_ROOT, "vtk_icons", "chevron_down.vtk"),
                    os.path.join(ICON_ROOT, "vtk_icons", "chevron_up.vtk"),
                ],
                icon_name=["chevron_down", "chevron_up"],
                initial_state=0,
                callback=self.toggle_panel,
                bounds=(0, 0.01, 0, 0.01),
                name=f"{self.panel_title}_collapse_button",
                color=self.text_color,
                ui_z_order=UI_Z_PANEL_CONTROL,
            )
            self.collapse_button.equal_aspect_ratio = True
            self._position_collapse_button()
        self._enforce_draw_order()

    def _position_collapse_button(self):
        """Centre the collapse control in the header band's right end."""
        self._apply_panel_decor()
        if self.collapse_button is None:
            return
        band, size_x, size_y, inset_x, _title_inset = panel_header_metrics(
            self.interactor)
        bounds = self.panel_background.GetBounds()
        right = bounds[1] - inset_x
        centre = ((bounds[2] + bounds[3]) / 2.0 if getattr(self, "collapsed", False)
                  else bounds[3] - band / 2.0)
        self.collapse_button.SetBounds(
            right - size_x, right, centre - size_y / 2.0, centre + size_y / 2.0)

    def _apply_panel_decor(self):
        """Header band and recessed list well (theme colours)."""
        background = self.panel_background
        if background is None:
            return
        well = theme_value(self.renderer, "well_color", None)
        if self.embedded:
            # Embedded lists already sit in their own box: tint the box and
            # its scroll masks alike.
            if well is not None and not getattr(self, "_well_tinted", False):
                background.panel_color = tuple(well)
                self._well_tinted = True
            scroll_box = getattr(self, "scroll_box", None)
            if well is not None and scroll_box is not None:
                scroll_box.blinder_color = tuple(well)
            if scroll_box is not None and not getattr(self, "_scrollbar_inset", False):
                # Embedded lists fill their box, so pull the scrollbar inside
                # the border (non-embedded lists get this from the well inset).
                window_width = max(1, self.interactor.GetRenderWindow().GetSize()[0])
                scroll_box.scrollbar_padding -= 10.0 / window_width
                self._scrollbar_inset = True
                scroll_box.update_slider_geometry()
            return
        band = panel_header_metrics(self.interactor)[0]
        bounds = background.GetBounds()
        header = getattr(self, "header_layer", None)
        if getattr(self, "collapsed", False):
            background.set_collapsed_header(True)
            background.wells = []
            if header is not None:
                header.SetBounds(*bounds)
                header.header_height = 0.0
                header.mask_strips = []
            return
        background.set_collapsed_header(False)
        if header is not None:
            header.SetBounds(*bounds)
            header.corner_radius = background.corner_radius
            header.header_height = band
        else:
            background.header_height = band
        if well is None:
            return
        window_width, window_height = self.interactor.GetRenderWindow().GetSize()
        pad_x = 6.0 / max(1, window_width)
        pad_y = 6.0 / max(1, window_height)
        # Equal gaps on all four sides of the well (under the band too).
        well_rect = (bounds[0] + pad_x, bounds[1] - pad_x,
                     bounds[2] + pad_y, bounds[3] - band - pad_y)
        background.wells = [well_rect]
        if header is not None:
            # Panel-coloured gap strips above the scroll masks, so rows
            # sliding past the list's edges never show in the gaps. Only
            # needed with blinders (partial rows are otherwise hidden).
            header.panel_color = background.panel_color
            header.mask_strips = (
                [(bounds[3] - band - pad_y, bounds[3] - band),
                 (bounds[2], bounds[2] + pad_y)]
                if ENABLE_SCROLL_BLINDERS else [])
        scroll_box = getattr(self, "scroll_box", None)
        if scroll_box is not None:
            corner = 4.0 / max(1, window_width)
            scroll_box.blinder_color = tuple(well)
            scroll_box.blinder_extent = (well_rect[0] + corner,
                                         well_rect[1] - corner, well_rect[2])

    def GetScrollBox(self):
        """Return the reusable viewport component owned by this panel."""
        return self.scroll_box

    def _embedded_resize_callback(self, caller=None, event=None):
        """Resize this viewport and let its enclosing panel absorb the delta."""
        self.update_layout(update_actors=False)
        if self.parent_panel is not None:
            self.parent_panel.embedded_child_resized(self)

    def defaultSizePolicy(self):
        return SizePolicy(SizePolicy.Expanding, SizePolicy.Expanding)

    def sizeHint(self):
        return (200.0, 160.0)

    def minimumSizeHint(self):
        return (80.0, 60.0)

    def GetBounds(self):
        return self.panel_background.GetBounds()

    def SetBounds(self, x_min, x_max, y_min, y_max):
        self.panel_background.SetBounds(x_min, x_max, y_min, y_max)
        self.update_layout(update_actors=False)

    def SetPosition(self, x, y):
        bounds = self.GetBounds()
        self.SetBounds(x, x + bounds[1] - bounds[0],
                       y, y + bounds[3] - bounds[2])

    def SetSize(self, width, height):
        bounds = self.GetBounds()
        self.SetBounds(bounds[0], bounds[0] + width,
                       bounds[2], bounds[2] + height)

    def SetEnabled(self, enabled):
        was_shown = self._is_shown()
        self.scroll_box.SetVisibility(enabled)
        self.panel_background.SetVisibility(enabled)
        if self.panel_title_widget is not None:
            self.panel_title_widget.SetVisibility(enabled and not self.embedded)
        if self.collapse_button is not None:
            self.collapse_button.SetEnabled(enabled)
        self._sync_shown_rows(was_shown)

    def GetEnabled(self):
        return int(self.scroll_box.enabled)

    def _is_shown(self):
        """False while hidden (inactive dock tab, collapsed pane, closed)."""
        scroll_box = getattr(self, 'scroll_box', None)
        return scroll_box is None or bool(scroll_box.enabled)

    def _sync_shown_rows(self, was_shown):
        """Drop rows on hide and rebuild them (from current items) on show,
        so updates made while hidden never draw over other tabs."""
        shown = self._is_shown()
        if shown == was_shown or not hasattr(self, '_visible_elements'):
            return
        if shown:
            if not self.collapsed:
                self.update_layout(update_actors=self.is_actors)
        else:
            self.update_positions(resize_elements=False)

    def toggle_panel(self, caller, event=None):
        """Toggle the rows, scrollbar, and clipping masks for this panel."""
        self.collapsed = bool(caller.GetRepresentation().GetState())
        # WidgetPanel historically exposes this spelling; keep it in sync so
        # generic containers can query either panel type consistently.
        self._panel_collapsed = self.collapsed
        if self.collapsed:
            bounds = self.panel_background.GetBounds()
            self._expanded_panel_size = (
                bounds[1] - bounds[0], bounds[3] - bounds[2])
            for index, row in self._visible_elements.items():
                if index < len(self._actors_list):
                    actor = self._actors_list[index]
                    if getattr(actor, 'UI_element', None) is row:
                        actor.UI_element = None
                row.Delete()
            self._visible_elements.clear()
            self.scrollable_elements = []
            self.scroll_box.scrollable_elements = self.scrollable_elements
            self.slider.EnabledOff()
            for blinder in (self.top_blinder, self.bottom_blinder):
                if blinder is not None:
                    blinder.SetEnabled(False)
            title_height = self._title_band_height() + self.buffer
            if getattr(self, 'parent_pane', None) is None:
                self.panel_background.SetBounds(
                    bounds[0], bounds[1], bounds[3] - title_height, bounds[3])
        else:
            bounds = self.panel_background.GetBounds()
            expanded_width, expanded_height = self._expanded_panel_size
            if getattr(self, 'parent_pane', None) is None:
                self.panel_background.SetBounds(
                    bounds[0], bounds[0] + expanded_width,
                    bounds[3] - expanded_height, bounds[3])
            # Rows are clipped before entering the title band, so the top
            # blinder is unnecessary. Re-enabling it here also places it over
            # the already-created title actor in the 2-D draw order.
            if self.top_blinder is not None:
                self.top_blinder.SetEnabled(False)
            if self.bottom_blinder is not None:
                self.bottom_blinder.SetEnabled(True)
            if self.panel_background.GetEnabled() and not self.scroll_box.enabled:
                # Shown while collapsed: the list itself was left disabled.
                self.scroll_box.SetVisibility(True)
        parent_pane = getattr(self, 'parent_pane', None)
        if parent_pane is not None:
            # The pane owns docked positions and heights. Reflow the complete
            # stack so following panels immediately consume/release the space.
            parent_pane.layout(render=False)
        if not self.collapsed:
            self.update_layout(update_actors=True)
        render_window = self.interactor.GetRenderWindow()
        if self.interactor.GetInitialized():
            render_window.Render()
        else:
            render_window.Modified()

    def _on_window_resize(self, caller=None, event=None):
        """Refresh pixel-dependent slider geometry after an actual resize."""
        window_size = tuple(self.interactor.GetRenderWindow().GetSize())
        if window_size == self._last_layout_window_size:
            return
        self._last_layout_window_size = window_size
        update_background = getattr(
            self.panel_background, "_update_pixel_bounds", None)
        if update_background is not None:
            update_background()
        self.update_layout(update_actors=False)

    def _renderer_scene_props(self):
        """Return only user-visible, top-level scene actors and assemblies."""
        props = self.renderer.GetViewProps()
        props.InitTraversal()
        result = []
        for _ in range(props.GetNumberOfItems()):
            prop = props.GetNextProp()
            if not isinstance(prop, (vtk.vtkActor, vtk.vtkAssembly)):
                continue
            if getattr(prop, 'IsUI', False):
                continue
            # Retained boolean sources and assembly children must not become
            # independent rows; GetViewProps itself supplies top-level props.
            if getattr(prop, '_boolean_source_hidden', False):
                continue
            result.append(self._scene_prop_node(prop))
        return result

    def _scene_prop_node(self, prop, parent_assembly=None):
        """Represent an assembly and its direct parts as a stable tree."""
        if parent_assembly is not None:
            prop._ui_parent_assembly = parent_assembly
        elif hasattr(prop, '_ui_parent_assembly'):
            del prop._ui_parent_assembly
        children = []
        if isinstance(prop, vtk.vtkAssembly):
            parts = prop.GetParts()
            parts.InitTraversal()
            for _ in range(parts.GetNumberOfItems()):
                part = parts.GetNextProp()
                if (part is None or getattr(part, 'IsUI', False) or
                        getattr(part, '_boolean_source_hidden', False)):
                    continue
                children.append(self._scene_prop_node(part, prop))
        label = prop.GetObjectName() or prop.GetClassName()
        instance_id = getattr(prop, '_scene_instance_id', None)
        if instance_id is None:
            instance_id = uuid.uuid4().hex
            prop._scene_instance_id = instance_id
        return HierarchyNode(
            label=label, value=prop, children=children,
            key=("scene-prop", instance_id))

    def _flatten_hierarchy(self, roots):
        """Return displayed values and row metadata for expanded tree nodes."""
        values = []
        rows = []

        def visit(item, depth):
            if isinstance(item, HierarchyNode):
                node = item
            else:
                label = (item.GetObjectName()
                         if hasattr(item, 'GetObjectName') else str(item))
                node = HierarchyNode(label=label, value=item,
                                     key=("flat-item", id(item)))
            values.append(node.value)
            rows.append((node, depth))
            if (node.expanded_by_default
                    and node.key not in self._default_tree_keys_applied):
                self._expanded_tree_keys.add(node.key)
                self._default_tree_keys_applied.add(node.key)
            if node.children and node.key in self._expanded_tree_keys:
                for child in node.children:
                    visit(child, depth + 1)

        for root in roots:
            visit(root, 0)
        return values, rows



    def update_layout(self, caller=None, event=None, x=None, y=None, width=None, height=None, update_actors=False, new_iterables=None, colors=None):


        """Update layout."""
        previous_actors_list = list(self._actors_list)
        window_size = self.interactor.GetRenderWindow().GetSize()


        if isinstance(self.panel_background, vtk.vtkBorderWidget):

            anchor_positions = np.asarray(self.panel_background.GetRepresentation().GetPositionCoordinate().GetValue()) + np.asarray(
                [self.buffer, self.buffer, self.buffer]
            )
            panel_height = self.panel_background.GetRepresentation().GetPosition2Coordinate().GetValue()[1] - (2 * self.buffer)
            panel_width = self.panel_background.GetRepresentation().GetPosition2Coordinate().GetValue()[0] - (2 * self.buffer)

        elif isinstance(self.panel_background, VectorPanelBackground):

            bounds = self.panel_background.GetBounds()
            anchor_positions = np.asarray([bounds[0] + self.buffer, bounds[2] + self.buffer])
            panel_width = bounds[1] - bounds[0] - (2 * self.buffer)
            panel_height = bounds[3] - bounds[2] - (2 * self.buffer)

        else:

            raise TypeError("Unknown panel background representation type")

        # new_panel_size = np.asarray([panel_width, panel_height])

        old_panel_size = self.panel_background.panel_size
        if old_panel_size is None:
            old_panel_size = np.asarray([panel_width, panel_height])

        old_panel_size -= np.asarray([2 * self.buffer, 2 * self.buffer])

        self.base_x = anchor_positions[0]
        self.base_y = anchor_positions[1]
        self.width = panel_width
        self.height = panel_height

        self.bounds = (self.base_x, self.base_x + self.width, self.base_y, self.base_y + self.height)
        # A collapsed pill can be shorter than the header; the (hidden) list
        # keeps its last bounds until there is room again.
        if hasattr(self, 'scroll_box') and self.width > 1e-6 and self.height > 1e-6:
            self.scroll_box.SetBounds(*self.bounds)


        if self.is_actors:

            if update_actors:
                self._root_items = self._renderer_scene_props()
                actors_list, self._row_nodes = self._flatten_hierarchy(
                    self._root_items)
                self._actors_list = actors_list
            else:
                actors_list = self._actors_list

            total_actors = len(actors_list)

        else:
            if new_iterables is not None:
                self._root_items = list(new_iterables)
                actors_list, self._row_nodes = self._flatten_hierarchy(
                    self._root_items)
                self._actors_list = actors_list
            elif update_actors:
                actors_list, self._row_nodes = self._flatten_hierarchy(
                    self._root_items)
                self._actors_list = actors_list
            else:
                actors_list = self._actors_list
            total_actors = len(actors_list)

        self.total_height = total_actors * self.element_height
        scroll_height = self._scroll_region_height()
        self.scroll_offset = min(
            self.scroll_offset, max(0.0, self.total_height - scroll_height))
        if hasattr(self, 'scroll_box'):
            self.scroll_box.scroll_offset = self.scroll_offset
            self.scroll_box.set_content_height(
                self.total_height, scroll_height)

        if self.collapsed or not self._is_shown():
            scrollbar_fraction = 1.0
            self.slider.EnabledOff()
        elif self.total_height <= scroll_height:
            scrollbar_fraction = 1.0
            self.slider.EnabledOff()
        else:
            scrollbar_fraction = scroll_height / self.total_height
            self.slider.EnabledOn()


        if update_actors:
            for index, scrollable_element in self._visible_elements.items():
                if index < len(previous_actors_list):
                    actor = previous_actors_list[index]
                    if getattr(actor, 'UI_element', None) is scrollable_element:
                        actor.UI_element = None
                scrollable_element.Delete()
            self.widgets = []
            self.scrollable_elements = []
            self._visible_elements.clear()
            if colors is not None:
                self._row_colors = list(colors)





        self.scroll_box.update_slider_geometry(scrollbar_fraction)

        self.update_positions()

    @ui_scoped
    def _create_visible_element(self, index, position_y):
        """Create one viewport row, binding callbacks to its current item."""
        actor = self._actors_list[index]
        node, depth = self._row_nodes[index]
        element_name = node.label
        button_color = (
            theme_value(self.renderer, "accent_color_rgb", (0.1, 0.6, 1.0))
            if self._row_colors is None or index >= len(self._row_colors)
            else self._row_colors[index])
        row = ScrollableElement(
            interactor=self.interactor, renderer=self.renderer,
            x=self.base_x, y=position_y, width=self.width - 0.01,
            height=self.element_height, panel_color=(*self.panel_color,),
            opacity=0.3, border_width=0,
            show_background=self.use_background)
        row.list_index = index

        def end_of_edit_callback(_property_name, new_value, target=actor):
            if hasattr(target, 'SetObjectName'):
                target.SetObjectName(new_value)

        def select_actor_callback(_label, target=actor):
            if not self.is_actors or target is None:
                return
            style = self.interactor.GetInteractorStyle()
            manager = getattr(style, 'actor_manager', None)
            if manager is None:
                return
            # WidgetActivateEvent can be delivered after the Qt/VTK adapter
            # has cleared its instantaneous modifier flags. The scene style
            # caches the state at LeftButtonPressEvent for this UI path.
            control = bool(
                self.interactor.GetControlKey() or
                getattr(manager, '_pointer_control_key', False))
            shift = bool(
                self.interactor.GetShiftKey() or
                getattr(manager, '_pointer_shift_key', False))
            manager.select_actor_from_ui(
                target, additive=shift and not control, toggle=control)
            self.interactor.selected_actors = manager.selected_actors
            self.interactor.GetRenderWindow().Render()

        # Scroll movement must not ask vtkTextRepresentation to refit the font.
        # Choose a fixed pixel font from the row's on-screen height instead.
        # The bounds keep compact and very high-DPI windows readable without
        # producing the oversized text that PROP scaling previously caused.
        # One font size per panel, from the row height, so every row matches;
        # long names are shortened with an ellipsis rather than shrunk.
        row_text_size = self._row_text_size()

        label = TextWidget(
            renderer=self.renderer, interactor=self.interactor,
            text=element_name, position=(self.base_x, position_y),
            size=(self.width, self.element_height), grabbable=False,
            fixed_text_length=self.fixed_text_length, editable=self.editable,
            clickable=True,
            # Rows can overlap the list's scrollbar; keep VTK's own hit box.
            claim_cell_clicks=False,
            end_of_edit_callback=end_of_edit_callback,
            click_callback=select_actor_callback if self.is_actors else None,
            edit_on_double_click=self.is_actors,
            scale_text_to_widget=False,
            elide_to_bounds=True,
            text_size=row_text_size,
            text_color=self.text_color,
            ui_z_order=UI_Z_SCROLL_ROWS)
        label.clicked.connect(
            lambda current=actor: self._on_item_clicked(current))
        label.doubleClicked.connect(
            lambda current=actor: self._on_item_double_clicked(current))
        row_indent = min(0.55, depth * self.indent_size)
        # Plain text rows (ScrollableTextPanel) need no disclosure slot.
        label_offset = getattr(self, "label_inset", 0.08) + row_indent
        has_disclosure_slot = bool(node.children) or node.value is None

        if node.children:
            expanded = node.key in self._expanded_tree_keys
            expand_button = VectorButtonWidget(
                renderer=self.renderer, interactor=self.interactor,
                # Collapsed folders point right, open ones down.
                input_data=[
                    os.path.join(ICON_ROOT, "vtk_icons",
                                 "chevron_right.vtk"),
                    os.path.join(ICON_ROOT, "vtk_icons",
                                 "chevron_down.vtk"),
                ],
                initial_state=int(expanded),
                callback=partial(self._toggle_tree_node, node.key),
                bounds=(self.base_x, self.base_x + self.element_height,
                        position_y, position_y + self.element_height),
                color=(node.chevron_colors
                       if node.chevron_colors else button_color),
                ui_z_order=UI_Z_SCROLL_ROWS)
            expand_button.equal_aspect_ratio = True
            row.add_element(expand_button, offset_x=row_indent,
                            size_x=0.10, size_y=0.70)
            label_offset = 0.08 + row_indent
        elif node.value is None:
            # A valueless hierarchy node represents a folder. If it has no
            # children, retain the disclosure column with a static hyphen;
            # ordinary leaf values do not need a marker.
            leaf_marker = VectorButtonWidget(
                renderer=self.renderer, interactor=self.interactor,
                input_data=os.path.join(ICON_ROOT, "vtk_icons", "hyphen.vtk"),
                icon_name="hyphen", callback=None, interactive=False,
                bounds=(self.base_x, self.base_x + self.element_height,
                        position_y, position_y + self.element_height),
                color=button_color, ui_z_order=UI_Z_SCROLL_ROWS)
            leaf_marker.equal_aspect_ratio = True
            row.add_element(leaf_marker, offset_x=row_indent,
                            size_x=0.10, size_y=0.70)
            label_offset = 0.08 + row_indent

        if getattr(self, "show_item_icons", True) is False:
            pass            # plain text rows: no per-item icon
        elif actor is not None and self.use_vector_buttons:
            icon_names = (list(self.icon)
                          if isinstance(self.icon, (list, tuple))
                          else [self.icon])
            icon_paths = [os.path.join(ICON_ROOT, "vtk_icons", icon_name + ".vtk")
                for icon_name in icon_names]
            initial_state = 0
            if (len(icon_paths) > 1 and hasattr(actor, 'GetVisibility')):
                initial_state = 0 if actor.GetVisibility() else 1
            button = VectorButtonWidget(
                renderer=self.renderer, interactor=self.interactor,
                input_data=(icon_paths if len(icon_paths) > 1
                            else icon_paths[0]),
                icon_name=icon_names,
                initial_state=initial_state,
                callback=partial(self.callback, actor),
                bounds=(self.base_x, self.base_x + self.element_height,
                        position_y, position_y + self.element_height),
                color=button_color, ui_z_order=UI_Z_SCROLL_ROWS)
            button.equal_aspect_ratio = True
            action_offset = row_indent + (0.11 if has_disclosure_slot else 0.0)
            row.add_element(button, offset_x=action_offset,
                            size_x=0.10, size_y=0.70)
            label_offset = 0.08 + action_offset
        elif actor is not None:
            button = ButtonWidget(
                renderer=self.renderer, interactor=self.interactor,
                icon_name=['visible', 'invisible'],
                widget_bounds=(self.base_x,
                               self.base_x + self.element_height,
                               position_y, position_y + self.element_height),
                callback=partial(self.callback, actor),
                name=f"button_{element_name}", show_bounds=True)
            action_offset = row_indent + (0.11 if has_disclosure_slot else 0.0)
            row.add_element(button, offset_x=action_offset,
                            size_x=0.10, size_y=0.70)
            label_offset = 0.08 + action_offset
        # Row buttons sit left of the label, so it may use the full width.
        row.add_element(label, offset_x=label_offset,
                        size_x=max(0.2, 0.96 - label_offset), size_y=0.7)
        # Scene props use this back-reference for selection highlighting, while
        # generic panels (such as the material selector) commonly contain
        # immutable strings which cannot accept arbitrary attributes.
        if self.is_actors and actor is not None:
            actor.UI_element = row
        return row

    def _toggle_tree_node(self, key, _button, _event=None):
        """Expand/collapse a branch after the current button event returns."""
        if key in self._expanded_tree_keys:
            self._expanded_tree_keys.remove(key)
        else:
            self._expanded_tree_keys.add(key)
        if getattr(self, '_tree_refresh_pending', False):
            return
        self._tree_refresh_pending = True

        def refresh(_caller=None, _event=None):
            observer_id = getattr(self, '_tree_refresh_observer_id', None)
            if observer_id is not None:
                self.observerRegistry().remove(self.interactor, observer_id)
            self._tree_refresh_observer_id = None
            self._tree_refresh_pending = False
            self.update_layout(update_actors=True)
            render_window = self.interactor.GetRenderWindow()
            if self.interactor.GetInitialized():
                render_window.Render()
            else:
                render_window.Modified()

        self._tree_refresh_observer_id = self.ownObserver(
            self.interactor, vtk.vtkCommand.TimerEvent, refresh, 100.0)
        self.interactor.CreateOneShotTimer(1)

    def update_items_deferred(self, items, colors=None):
        """Replace panel items safely after the active UI event completes."""
        self._pending_items_update = (list(items), colors)
        if getattr(self, '_items_update_pending', False):
            return
        self._items_update_pending = True

        def refresh(_caller=None, _event=None):
            observer_id = getattr(self, '_items_update_observer_id', None)
            if observer_id is not None:
                self.observerRegistry().remove(self.interactor, observer_id)
                self._items_update_observer_id = None
            self._items_update_pending = False
            pending_items, pending_colors = self._pending_items_update
            self.update_layout(
                new_iterables=pending_items, colors=pending_colors,
                update_actors=True)
            render_window = self.interactor.GetRenderWindow()
            if self.interactor.GetInitialized():
                render_window.Render()
            else:
                render_window.Modified()

        self._items_update_observer_id = self.ownObserver(
            self.interactor, vtk.vtkCommand.TimerEvent, refresh, 100.0)
        self.interactor.CreateOneShotTimer(1)


    # def make_toggle_callback(self, actor):
    #     def callback(widget, event):
    #         rep = widget.GetRepresentation()
    #         state = rep.GetState()
    #         actor.SetVisibility(state == 0)
    #     return callback

    def _title_band_height(self):
        """Height reserved at the top of the panel for its title."""
        if self.embedded:
            return 0.0
        window_height = self.interactor.GetRenderWindow().GetSize()[1]
        gap = 6.0 / max(1, window_height)   # same as the well's side gaps
        return panel_header_metrics(self.interactor)[0] + gap

    def _header_layout(self):
        """Return title geometry anchored to the outer panel bounds."""
        bounds = self.panel_background.GetBounds()
        window_width = self.interactor.GetRenderWindow().GetSize()[0]
        band, control_width, _h, control_inset_x, title_inset = (
            panel_header_metrics(self.interactor))
        gap = 6.0 / max(1, window_width)
        title_height = min(panel_title_text_height(self.interactor),
                           max(0.001, bounds[3] - bounds[2]))
        title_x = bounds[0] + title_inset
        # A text-high box centred on the band (see panel_title_text_height),
        # or on the pill while collapsed.
        centre = ((bounds[2] + bounds[3]) / 2.0 if getattr(self, "collapsed", False)
                  else bounds[3] - band / 2.0)
        title_y = centre - title_height / 2.0
        button_left = bounds[1] - control_inset_x - control_width
        title_width = max(0.001, button_left - gap - title_x)
        return title_x, title_y, title_width, title_height

    def _scroll_region_height(self):
        """Usable list height below the title band."""
        return max(self.element_height,
                   self.height - self._title_band_height())

    def _scroll_region_top(self):
        return self.base_y + self._scroll_region_height()

    def _check_if_visible(self, position_y):

        """Check if visible."""
        visible_bounds = (self.base_y, self._scroll_region_top())
        epsilon = 1e-9
        if position_y + self.element_height > visible_bounds[1] + epsilon:
            return False
        if position_y < visible_bounds[0] - epsilon:
            return False
        return True

    def scroll_callback(self, caller, event):
        """Handle the scroll callback event."""
        value = caller.GetRepresentation().GetValue()
        # Scroll offset ranges from 0 to total scrollable height

        scroll_height = self._scroll_region_height()

        if self.total_height <= scroll_height:
            self.scroll_offset = 0.0
        else:
            self.scroll_offset = value * (self.total_height - scroll_height)
        self.scroll_box.scroll_offset = self.scroll_offset

        self.update_positions(resize_elements=False)

    @ui_scoped
    def update_positions(self, delta=0.06, resize_elements=True):


        """Update positions."""
        window_size = self.interactor.GetRenderWindow().GetSize()



        # Determine the small rolling window of rows intersecting the panel.
        # The extra candidate either side handles partially visible boundary
        # rows without scanning every item in the scene.
        count = len(self._actors_list)
        if (self.collapsed or self.element_height <= 0
                or not self._is_shown()):
            # Hidden panels (inactive tab, collapsed pane) keep no rows;
            # they are rebuilt when the panel is shown again.
            desired = set()
        else:
            approximate_first = int(self.scroll_offset / self.element_height)
            capacity = int(np.ceil(
                self._scroll_region_height() / self.element_height)) + 3
            candidates = range(
                max(0, approximate_first - 2),
                min(count, approximate_first + capacity))
            desired = {
                i for i in candidates
                if self._check_if_visible(
                    self._scroll_region_top() - self.element_height
                    - (i * self.element_height) + self.scroll_offset)
            }

        for index in set(self._visible_elements) - desired:
            row = self._visible_elements.pop(index)
            actor = self._actors_list[index]
            if getattr(actor, 'UI_element', None) is row:
                del actor.UI_element
            row.Delete()

        for index in sorted(desired):
            position_y = (
                self._scroll_region_top() - self.element_height
                - (index * self.element_height) + self.scroll_offset)
            row = self._visible_elements.get(index)
            created = row is None
            if row is None:
                try:
                    row = self._create_visible_element(index, position_y)
                    self._visible_elements[index] = row
                except Exception as error:
                    logger.warning("%s %s", f"{bcolors.WARNING}Error creating scrollable element "
                          f"for actor {self._actors_list[index]}:"
                          f"{bcolors.ENDC}", error)
                    continue
            row.update_element_positions(
                new_x=self.base_x, new_y=position_y,
                new_width=self.width, window_size=window_size,
                resize_elements=(resize_elements or created))

        self.scrollable_elements = [
            self._visible_elements[i] for i in sorted(self._visible_elements)]
        self.scroll_box.scrollable_elements = self.scrollable_elements


        if self.add_blinders and not self.collapsed and self._is_shown():
            self.scroll_box.update_blinders(
                self._scroll_region_top(),
                self._title_band_height() + self.buffer - .01,
                resize=resize_elements)
            self.top_blinder = self.scroll_box.top_blinder
            self.bottom_blinder = self.scroll_box.bottom_blinder
        elif self.collapsed or not self._is_shown():
            for blinder in (self.top_blinder, self.bottom_blinder):
                if blinder is not None:
                    blinder.SetEnabled(False)

        title_x, title_y, title_width, title_height = self._header_layout()
        title_position = (title_x, title_y)
        if not self.embedded and self.panel_title_widget is None:
            self.panel_title_widget = TextWidget(
                renderer=self.renderer, interactor=self.interactor,
                text=self.panel_title, position=title_position,
                size=(title_width, title_height),
                grabbable=False,
                text_color=self.text_color,
                scale_text_to_widget=False, elide_to_bounds=True,
                text_size=panel_title_text_size(self.interactor),
                bold=True,
                ui_z_order=UI_Z_PANEL_TITLE)
            if not self._is_shown():
                self.panel_title_widget.SetVisibility(False)
        elif self.panel_title_widget is not None:
            self.panel_title_widget.SetPosition(*title_position)
            if resize_elements:
                self.panel_title_widget.SetSize(
                    title_width, title_height)
        self._position_collapse_button()
        self._enforce_draw_order()

    def _enforce_draw_order(self):
        """Keep masks above rows but below the fixed panel header."""
        drawables = [self.panel_background]
        for row in self._visible_elements.values():
            drawables.extend(
                element for element in row.elements
                if hasattr(element, 'ui_z_order'))
        drawables.extend(
            blinder for blinder in (self.top_blinder, self.bottom_blinder)
            if blinder is not None)
        if getattr(self, "header_layer", None) is not None:
            drawables.append(self.header_layer)
        if self.panel_title_widget is not None:
            drawables.append(self.panel_title_widget)
        drawables.append(self.slider)
        if self.collapse_button is not None:
            drawables.append(self.collapse_button)
        enforce_ui_draw_order(self.renderer, drawables)


    def SetVisibility(self, visible):
        """Set visibility."""
        was_shown = self._is_shown()
        self.panel_background.SetVisibility(visible)
        if getattr(self, "header_layer", None) is not None:
            self.header_layer.SetVisibility(visible)
        self.scroll_box.SetVisibility(visible and not self.collapsed)
        self._sync_shown_rows(was_shown)
        if self.panel_title_widget is not None:
            self.panel_title_widget.SetVisibility(visible and not self.embedded)
        if self.collapse_button is not None:
            self.collapse_button.SetVisibility(visible)
        self._enforce_draw_order()


    def is_within_bounds(self, x, y):
        """Return whether within bounds."""
        if not self.GetEnabled() or self.collapsed:
            return False
        panel_bounds = self.bounds
        if x < panel_bounds[0] or x > panel_bounds[1]:
            return False
        if y < panel_bounds[2] or y > panel_bounds[3]:
            return False
        return True

    def handle_mouse_wheel(self, x, y, direction):
        """Scroll list rows when the pointer is over an overflowing viewport."""
        if not self.is_within_bounds(x, y):
            return False
        viewport = self._scroll_region_height()
        maximum = max(0.0, self.total_height - viewport)
        if maximum <= 0.0:
            # This viewport has no active scrollbar, so it is not a valid
            # consumer regardless of its boundary pass-through setting.
            return False
        step = max(self.element_height * 3.0, viewport * 0.08)
        new_offset = min(
            maximum, max(0.0, self.scroll_offset - direction * step))
        if abs(new_offset - self.scroll_offset) <= 1e-12:
            return not self.pass_scroll_events
        self.scroll_offset = new_offset
        self.scroll_box.scroll_offset = self.scroll_offset
        self.scroll_box.set_scroll_fraction(
            self.scroll_offset / maximum, viewport)
        self.scroll_box.update_slider_geometry()
        self.update_positions(resize_elements=False)
        self.interactor.GetRenderWindow().Render()
        return True

    def handle_mouse_move(self, caller, event):
        """Handle mouse move events within the panel."""
        # mouse_pos = self.interactor.GetEventPosition()
        # normalized_x = mouse_pos[0] / self.interactor.GetRenderWindow().GetSize()[0]
        # normalized_y = mouse_pos[1] / self.interactor.GetRenderWindow().GetSize()[1]
        pass

    def handle_left_button_down(self, caller, event):
        """Handle left button down events within the panel."""
        pass

    def handle_left_button_up(self, caller, event):
        """Handle left button up events within the panel."""
        pass

    def handle_right_button_down(self, caller, event):
        """Handle right button down events within the panel."""
        pass

    def handle_right_button_up(self, caller, event):
        """Handle right button up events within the panel."""
        pass

    def _on_item_clicked(self, item):
        self.setCurrentItem(item)
        self.itemClicked.emit(item)

    def _on_item_double_clicked(self, item):
        self.setCurrentItem(item)
        self.itemDoubleClicked.emit(item)
        self.itemActivated.emit(item)

    def count(self):
        return len(self.iterable)

    def item(self, index):
        return self.iterable[index]

    def currentItem(self):
        return self._current_item

    def setCurrentItem(self, item):
        if item is self._current_item:
            return
        previous = self._current_item
        self._current_item = item
        self.currentItemChanged.emit(item, previous)

    def selectedItems(self):
        return ([] if self._current_item is None else [self._current_item])

    def setModel(self, items):
        """Show ``items`` (a list) or an :class:`~multipanel.models.ItemModel`.

        With a model the panel shows each row's ``"user"`` value (or its
        text) and follows the model's changes. Changes made in one event
        are coalesced into a single row rebuild; for per-row updates of
        large models use :class:`~multipanel.views.ListView`.
        """
        from .models import ItemModel

        previous = getattr(self, '_item_model', None)
        if previous is not None:
            for signal in (previous.dataChanged, previous.rowsInserted,
                           previous.rowsRemoved, previous.modelReset):
                signal.disconnect(self._sync_item_model)
            self._item_model = None
        if isinstance(items, ItemModel):
            self._item_model = items
            for signal in (items.dataChanged, items.rowsInserted,
                           items.rowsRemoved, items.modelReset):
                signal.connect(self._sync_item_model)
            items = self._item_model_values()
        self.iterable = list(items)
        self.update_items_deferred(self.iterable)
        self.itemsChanged.emit()

    def itemModel(self):
        """The ItemModel passed to :meth:`setModel`, or None."""
        return getattr(self, '_item_model', None)

    def _item_model_values(self):
        model = self._item_model
        values = []
        for row in range(model.rowCount()):
            index = model.index(row, 0)
            value = index.data("user")
            values.append(value if value is not None else index.data())
        return values

    def _sync_item_model(self, *_args):
        self.iterable = self._item_model_values()
        self.update_items_deferred(self.iterable)
        self.itemsChanged.emit()

    def addItem(self, item):
        self.insertItem(self.count(), item)

    def insertItem(self, index, item):
        model = self.itemModel()
        if model is not None and hasattr(model, 'insert'):
            model.insert(int(index), {'display': str(item), 'user': item})
            return
        items = list(self.iterable)
        items.insert(int(index), item)
        self.setModel(items)

    def takeItem(self, index):
        model = self.itemModel()
        if model is not None and hasattr(model, 'removeRow'):
            item = list(self.iterable)[int(index)]
            model.removeRow(int(index))
            if item is self._current_item:
                self.setCurrentItem(None)
            return item
        items = list(self.iterable)
        item = items.pop(int(index))
        self.setModel(items)
        if item is self._current_item:
            self.setCurrentItem(None)
        return item

    def removeItem(self, item):
        self.takeItem(list(self.iterable).index(item))

    def clear(self):
        self.setCurrentItem(None)
        model = self.itemModel()
        if model is not None and hasattr(model, 'clear'):
            model.clear()
            return
        self.setModel([])

    def saveState(self):
        state = super().saveState()
        try:
            current_index = list(self.iterable).index(self._current_item)
        except ValueError:
            current_index = -1
        state.update({
            'collapsed': self.collapsed,
            'scrollOffset': self.scroll_offset,
            'currentIndex': current_index,
        })
        return state

    def restoreState(self, state):
        if not isinstance(state, dict):
            raise TypeError('panel state must be a dictionary')
        self.scroll_offset = max(
            0.0, float(state.get('scrollOffset', self.scroll_offset)))
        index = int(state.get('currentIndex', -1))
        if 0 <= index < self.count():
            self.setCurrentItem(self.item(index))
        else:
            self.setCurrentItem(None)
        collapsed = bool(state.get('collapsed', self.collapsed))
        if collapsed != self.collapsed:
            if self.collapse_button is not None:
                self.collapse_button.setChecked(collapsed)
                self.toggle_panel(self.collapse_button)
            else:
                self.collapsed = collapsed
                self._panel_collapsed = collapsed
                self.scroll_box.SetVisibility(not collapsed)
        common = {key: state[key] for key in (
            'objectName', 'enabled', 'visible', 'geometry',
            'toolTip', 'statusTip') if key in state}
        super().restoreState(common)
        self.update_positions(resize_elements=False)
        return True

    def Delete(self):
        self.observerRegistry().clear()
        for row in list(self._visible_elements.values()):
            row.Delete()
        self._visible_elements.clear()
        for widget in (self.collapse_button, self.panel_title_widget,
                       self.header_layer, self.panel_background,
                       getattr(self, 'scroll_box', None)):
            if widget is not None and hasattr(widget, 'close'):
                widget.close()
            elif widget is not None and hasattr(widget, 'Delete'):
                widget.Delete()



class ScrollableTextPanel(ScrollablePanel):
    """Read-only multi-line text in a scrollable list at a fixed readable size.

    Each (wrapped) line is a row, so long text scrolls instead of shrinking.
    Accepts text the way a vtkTextActor does -- ``GetTextActor().SetInput``
    -- so existing callers such as the Info Panel updater work unchanged.
    """

    CONTINUATION_INDENT = "   "
    label_inset = 0.02          # no chevron column for plain text rows
    show_item_icons = False     # nor a per-item icon

    class _TextSink:
        def __init__(self, panel):
            self.panel = panel

        def SetInput(self, text):
            self.panel.set_text(text)

        def GetInput(self):
            return self.panel.text

        def Modified(self):
            pass

    def __init__(self, interactor, iterable=(), text="", **kwargs):
        self.text = ""
        self._wrap_width_px = None
        super().__init__(interactor, [], **kwargs)
        self._sink = self._TextSink(self)
        self.set_text(text, immediate=True)

    def GetTextActor(self):
        return self._sink

    def _available_width_px(self):
        window_width = max(1, self.interactor.GetRenderWindow().GetSize()[0])
        # Same geometry as the row label (row width = width - 0.01; label =
        # 0.96 - inset of it) and the 0.94 fit factor used for elision.
        return max(40.0, (self.width - 0.01) * (0.96 - self.label_inset)
                   * window_width * 0.94)

    def _wrap(self, text):
        prop = vtk.vtkTextProperty()
        prop.SetFontSize(self._row_text_size())
        apply_ui_font(prop)
        window = self.interactor.GetRenderWindow()
        dpi = max(1, window.GetDPI())
        renderer = vtk.vtkTextRenderer.GetInstance()
        available = self._available_width_px()

        def width(line):
            box = [0, 0, 0, 0]
            renderer.GetBoundingBox(prop, line or " ", box, dpi)
            return box[1] - box[0] + 1

        lines = []
        for raw in (str(text).splitlines() or [""]):
            if width(raw) <= available:
                lines.append(raw)
                continue
            current = ""
            for word in raw.split(" "):
                candidate = f"{current} {word}" if current else word
                if width(candidate) <= available or not current:
                    current = candidate
                    # A single word wider than the line: break it.
                    while width(current) > available and len(current) > 1:
                        cut = len(current) - 1
                        while cut > 1 and width(current[:cut]) > available:
                            cut -= 1
                        lines.append(current[:cut])
                        current = self.CONTINUATION_INDENT + current[cut:]
                else:
                    lines.append(current)
                    current = self.CONTINUATION_INDENT + word
            lines.append(current)
        return lines

    def set_text(self, text, immediate=False):
        """Replace the text, re-wrapping it to the current width.

        Rows are rebuilt after the current UI event (like other panels'
        update_items_deferred): rebuilding text widgets mid-event and then
        receiving a click before the next render crashes VTK.
        """
        self.text = str(text)
        self._wrap_width_px = self._available_width_px()
        nodes = [HierarchyNode(label=line, value=("text-line", index))
                 for index, line in enumerate(self._wrap(self.text))]
        if immediate:
            self.update_layout(new_iterables=nodes, update_actors=True)
        else:
            self.update_items_deferred(nodes)

    def setText(self, text):
        self.set_text(text)

    def append(self, text):
        separator = "\n" if self.text else ""
        self.set_text(self.text + separator + str(text))

    def clear(self):
        self.set_text("")

    def SetBounds(self, x_min, x_max, y_min, y_max):
        super().SetBounds(x_min, x_max, y_min, y_max)
        if (self._wrap_width_px is not None and
                abs(self._available_width_px() - self._wrap_width_px) > 2.0):
            self.set_text(self.text)       # re-wrap for the new width


def _set_shown_raw(widget, shown):
    """Show/hide a widget's actors without touching its visible flag."""
    setter = getattr(widget, "SetVisibility", None)
    if callable(setter):
        setter(bool(shown))
        return
    enabler = getattr(widget, "SetEnabled", None)
    if callable(enabler):
        enabler(bool(shown))


class WidgetPanel(WidgetMixin):

    @ui_scoped
    def  __init__(
        self,
        renderer,
        interactor,
        panel_elements,
        panel_title="Widget Panel",
        panel_position=(0.05, 0.25),
        panel_width=0.1,
        panel_opacity=1.0,
        panel_radius=PANEL_CORNER_RADIUS,
        text_color=(0.0, 0.0, 0.0),
        buffer=0.003,
        panel_color=(1.0, 1.0, 1.0),
        collapsed=False,
        closable=False,
        grabbable=True,
        keep_aspect_ratio=False
    ):
        """
        Adds a customizable widget panel to a VTK renderer and interactor.
        This function creates a panel with various interactive widgets such as buttons,
        sliders, textboxes, and compasses. The panel is dynamically updated based on
        the widgets added and can respond to window resizing and user interactions.

        Parameters
        ----------
        renderer : vtk.vtkRenderer
            The VTK renderer where the panel will be added.
        interactor : vtk.vtkRenderWindowInteractor
            The VTK interactor for handling user interactions.
        panel_elements : dict
            A dictionary defining the widgets to be added to the panel. Each key is
            the widget name, and the value is a dictionary with widget-specific
            attributes such as type, size, position, and callbacks.

        panel_title : str, optional
            The title of the panel. Defaults to 'Widget Panel'.
        panel_position : tuple, optional
            The normalized display coordinates (x, y) of the panel's top-left corner.
            Defaults to (0.05, 0.25).
        panel_width : float, optional
            The normalized width of the panel. Defaults to 0.1.
        panel_opacity : float, optional
            The opacity of the panel background. Defaults to 0.9.
        buffer : float, optional
            The padding around the panel's widgets. Defaults to 0.01.

        Notes
        -----
        - The function dynamically adjusts the panel's bounds to fit all added
        widgets.
        - Widgets are positioned relative to the panel's anchor point and can be
        resized or repositioned when the panel is resized.
        - Supported widget types include:
        - "button": A clickable button with icons.
        - "slider": A slider with a title and callback.
        - "textbox": A text display widget.
        - "compass": A compass widget for orientation.
        - The panel responds to window resizing and user interactions to maintain
        its layout.

        Example
        -------
        ```python
        renderer = vtk.vtkRenderer()
        interactor = vtk.vtkRenderWindowInteractor()
        panel_elements = {
            "button1": {
                "widget_type": "button",
                "button_size": [0.1, 0.05],
                "panel_offset": [0.1, 0.2],
                "icon_names": ["icon1.png", "icon2.png"],
                "callback": some_function,
            },
            "slider1": {
                "widget_type": "slider",
                "slider_size": [0.2, 0.05],
                "panel_offset": [0.3, 0.4],
                "slider_initial_value": 0.5,
                "slider_min_value": 0.0,
                "slider_max_value": 1.0,
                "slider_title": "Slider Title",
                "callback": another_function,
            },
        }
        add_widget_panel(renderer, interactor, panel_elements, panel_title="My Panel")
        ```
        """

        assert isinstance(renderer, vtk.vtkRenderer), "Renderer is not a vtkRenderer"
        assert isinstance(
            interactor, vtk.vtkRenderWindowInteractor
        ), "Interactor is not a vtkRenderWindowInteractor"
        self.initWidget(panel_title)
        self.collapsedChanged = Signal(self)
        self.closed = Signal(self)
        self.layoutChanged = Signal(self)

        self.panel_bounds = np.array(
            (
                panel_position[0],
                panel_position[0] + panel_width,
                panel_position[1],
                panel_position[1] + panel_width,
            )
        )
        self.panel_width = panel_width
        self.panel_position = np.array(panel_position)
        self.panel_opacity = panel_opacity
        self.panel_color = panel_color
        self.panel_radius = panel_radius
        self.panel_title = panel_title

        self.anchor_positions = np.asarray([self.panel_bounds[0], self.panel_bounds[2]])


        self.panel_elements = panel_elements
        self.buffer = buffer
        self.renderer = renderer
        self.interactor = interactor
        self.grabbable = grabbable
        self.closable = bool(closable)
        self._panel_collapsed = bool(collapsed)
        self._pane_visible = True
        self.parent_pane = None


        self.use_vector_buttons = True
        self.keep_aspect_ratio = keep_aspect_ratio


        # panel_background = PanelBackgroundWidget(
        #     renderer,
        #     interactor,
        #     self.panel_bounds,
        #     panel_color=panel_color,
        #     border_color=(0, 0, 0),
        #     opacity=panel_opacity,
        #     radius=self.panel_radius,
        #     name="button_panel_background",
        #     grabbable=self.grabbable,
        # )

        panel_background = VectorPanelBackground(
            renderer,
            interactor,
            bounds=self.panel_bounds,
            panel_color=panel_color,
            border_color=theme_value(renderer, "border_color", (0, 0, 0)),
            opacity=panel_opacity,
            corner_radius=self.panel_radius,
            name="button_panel_background",
            parent=self,
            movable=self.grabbable,
            resizable=self.grabbable,
            keep_aspect_ratio=self.keep_aspect_ratio

        )

        text_anchor = TextWidget(
            renderer,
            interactor,
            text=self.panel_title,
            position=self.panel_position,
            size=(self.panel_width, (self.panel_width * 0.5)),
            grabbable=False,
            text_color=text_color,
            # Same fixed bold heading size as every other panel title.
            scale_text_to_widget=False,
            elide_to_bounds=True,
            text_size=panel_title_text_size(interactor),
            bold=True,
        )
        text_anchor.panel_size = np.asarray([0.8, 0.25])
        text_anchor.panel_offset = np.asarray([0.4, -(text_anchor.panel_size[1]/2)])

        assert text_anchor.panel_offset[0] - (text_anchor.panel_size[0]/2) == 0, (
            f"Panel offset {text_anchor.panel_offset} and size {text_anchor.panel_size} are not valid"
        )
        assert text_anchor.panel_offset[0] + (text_anchor.panel_size[0]/2) < 1, (
            f"Panel offset {text_anchor.panel_offset} and size {text_anchor.panel_size} are not valid"
        )

        self.panel_background = panel_background
        self.panel_background.panel_size = None
        self.text_anchor = text_anchor

        added_widgets = {}

        added_widgets.update({"panel_title": text_anchor})


        if self.use_vector_buttons:

            header_icons = (["checkbox_cross"] if self.closable else
                            ["chevron_down", "chevron_up"])
            header_shapes = [
                os.path.join(ICON_ROOT, "vtk_icons", f"{name}.vtk")
                for name in header_icons]

            self.collapse_button = VectorButtonWidget(
                renderer,
                interactor,
                input_data=(header_shapes[0] if self.closable
                            else header_shapes),
                icon_name=header_icons,
                callback=(self.close_panel if self.closable
                          else self.toggle_panel),
                bounds=(panel_position[0] + panel_width - 0.05, panel_position[0] + panel_width, panel_position[1], panel_position[1] + 0.05),
                name="collapse_button",
                color=text_color,
                hover_text=("Close panel" if self.closable else
                            "Collapse or expand panel")
            )
            self.collapse_button.equal_aspect_ratio = True
        else:

            self.collapse_button = ButtonWidget(
                renderer,
                interactor,
                icon_name=["chevron_down", "chevron_up"],
                callback=self.toggle_panel,
                initial_state=0,
                widget_bounds=(panel_position[0] + panel_width - 0.05, panel_position[0] + panel_width, panel_position[1], panel_position[1] + 0.05),
                name="collapse_button",
            )
        self.collapse_button.panel_offset = np.asarray([0.95, -0.125])
        self.collapse_button.panel_size = np.asarray([0.1, 0.1])


        assert self.collapse_button.panel_offset[0] - (self.collapse_button.panel_size[0]/2) > 0, (
            f"Panel offset {self.collapse_button.panel_offset} and size {self.collapse_button.panel_size} are not valid"
        )
        assert self.collapse_button.panel_offset[0] - (self.collapse_button.panel_size[0]/2) < 1, (
            f"Panel offset {self.collapse_button.panel_offset} and size {self.collapse_button.panel_size} are not valid"
        )

        added_widgets.update({"collapse_button": self.collapse_button})


        for widget_name, widget_info in self.panel_elements.items():
            panel_offset = np.asarray(widget_info["panel_offset"])



            screen_offset = panel_offset * panel_width

            widget_type = widget_info.get("widget_type", None)

            if widget_type is None:
                # print(
                #   'Widget type not specified for %s' % widget_name,
                #   ', checking for unique attributes'
                # )

                if "button_size" in widget_info:
                    widget_type = "button"
                elif "slider_size" in widget_info:
                    widget_type = "slider"
                elif "textbox_size" in widget_info:
                    widget_type = "textbox"
                elif "scrollbox_size" in widget_info:
                    widget_type = "scrollbox"

            if widget_type in ("scrollbox", "scrolltext"):
                scrollbox_size = np.asarray(widget_info["scrollbox_size"])
                half_size = scrollbox_size * panel_width / 2.0
                if (panel_offset[0] + scrollbox_size[0] / 2 > 1.0 or
                        panel_offset[0] - scrollbox_size[0] / 2 < 0.0):
                    raise ValueError(
                        f"Widget {widget_name} exceeds panel width")
                widget_bounds = (
                    self.anchor_positions[0] + screen_offset[0] - half_size[0],
                    self.anchor_positions[0] + screen_offset[0] + half_size[0],
                    self.anchor_positions[1] + screen_offset[1] - half_size[1],
                    self.anchor_positions[1] + screen_offset[1] + half_size[1])
                # "scrolltext": read-only wrapped text (e.g. the Info Panel).
                text_kwargs = ({"text": widget_info.get("text", "")}
                               if widget_type == "scrolltext" else {})
                panel_class = (ScrollableTextPanel if widget_type == "scrolltext"
                               else ScrollablePanel)
                scroll_panel = panel_class(
                    interactor, widget_info.get("items", []),
                    **text_kwargs,
                    x=widget_bounds[0], y=widget_bounds[2],
                    width=widget_bounds[1] - widget_bounds[0],
                    height=widget_bounds[3] - widget_bounds[2],
                    element_height=widget_info.get("element_height", .02),
                    buffer=widget_info.get("buffer", self.buffer),
                    callback=widget_info.get("callback", dummy_callback),
                    title=widget_info.get("title", ""),
                    use_background=widget_info.get("use_background", False),
                    panel_color=widget_info.get("panel_color", panel_color),
                    text_color=widget_info.get("text_color", text_color),
                    icon=widget_info.get("icon"), embedded=True,
                    pass_scroll_events=widget_info.get(
                        "pass_scroll_events", False))
                scroll_panel.panel_offset = panel_offset
                scroll_panel.panel_size = scrollbox_size
                scroll_panel.panel_bounds = np.asarray((*widget_bounds, 0., 0.))
                scroll_panel.parent_panel = self
                added_widgets[widget_name] = scroll_panel

            elif widget_type == "color_palette":
                palette_size = np.asarray(widget_info["widget_size"])
                half_size = palette_size * panel_width / 2.0
                widget_bounds = (
                    self.anchor_positions[0] + screen_offset[0] - half_size[0],
                    self.anchor_positions[0] + screen_offset[0] + half_size[0],
                    self.anchor_positions[1] + screen_offset[1] - half_size[1],
                    self.anchor_positions[1] + screen_offset[1] + half_size[1])
                palette = ColorPaletteWidget(
                    renderer, interactor,
                    callback=widget_info.get("callback"),
                    bounds=widget_bounds,
                    mode=widget_info.get("mode", "swatches"))
                palette.panel_offset = panel_offset
                palette.panel_size = palette_size
                added_widgets[widget_name] = palette

            elif widget_type == "textbox":

                textbox_size = np.asarray(widget_info["textbox_size"])

                half_size = (
                    np.asarray([textbox_size[0] / 2, textbox_size[1] / 2]) * panel_width
                )

                assert panel_offset[0] + textbox_size[0] / 2 <= 1.0, (
                    f"Widget {widget_name} exceeds panel bounds: "
                    f"panel_offset {panel_offset}, textbox_size {textbox_size}"
                )

                assert panel_offset[0] - textbox_size[0] / 2 >= 0.0, (
                    f"Widget {widget_name} exceeds panel bounds: "
                    f"panel_offset {panel_offset}, textbox_size {textbox_size}"
                )

                widget_bounds = (
                    self.anchor_positions[0] + screen_offset[0] - half_size[0],
                    self.anchor_positions[0] + screen_offset[0] + half_size[0],
                    self.anchor_positions[1] + screen_offset[1] - half_size[1],
                    self.anchor_positions[1] + screen_offset[1] + half_size[1],
                    0.0,
                    0.0,
                )

                textbox_position = np.asarray([widget_bounds[0], widget_bounds[2]])

                # "caption": small fixed-size, left-aligned secondary text
                # (e.g. "Current Material: ...") instead of box-scaled text.
                caption = widget_info.get("text_style") == "caption"
                caption_options = dict(
                    scale_text_to_widget=False,
                    text_size=max(10, panel_title_text_size(interactor) - 4),
                    horizontal_alignment="left",
                    elide_to_bounds=True,     # long captions end in "…"
                ) if caption else {}
                text_options = dict(
                    scale_text_to_widget=widget_info.get(
                        "scale_text_to_widget", True),
                    fit_text_to_bounds=widget_info.get(
                        "fit_text_to_bounds", False),
                    horizontal_alignment=widget_info.get(
                        "horizontal_alignment", "left"),
                )
                text_options.update(caption_options)
                default_color = (theme_value(renderer, "muted_text_color", text_color)
                                 if caption else text_color)
                text_widget = TextWidget(
                    renderer,
                    interactor,
                    text=widget_info["text"],
                    unique_name=widget_name,
                    position=textbox_position,
                    size=textbox_size,
                    grabbable=False,
                    editable=widget_info.get("editable", False),
                    force_to_float=widget_info.get("force_to_float", False),
                    end_of_edit_callback=widget_info.get(
                        "end_of_edit_callback"),
                    edit_on_double_click=widget_info.get(
                        "edit_on_double_click", False),
                    text_color=widget_info.get("text_color", default_color),
                    prepend_text=widget_info.get("prepend_text", ()),
                    append_text=widget_info.get("append_text", ()),
                    **text_options,
                )
                text_widget.panel_offset = np.asarray(panel_offset)
                text_widget.panel_size = np.asarray(widget_info["textbox_size"])

                added_widgets.update({widget_name: text_widget})


            elif widget_type == "slider":

                slider_size = np.asarray(widget_info["slider_size"])

                half_size = np.asarray([slider_size[0] / 2, slider_size[1] / 2])

                assert panel_offset[0] + (slider_size[0] / 2) <= 1.0, (
                    f"Widget {widget_name} exceeds panel bounds: "
                    f"panel_offset {panel_offset}, slider_size {slider_size}"
                )

                assert panel_offset[0] - (slider_size[0] / 2) >= 0.0, (
                    f"Widget {widget_name} exceeds panel bounds: "
                    f"panel_offset {panel_offset}, slider_size {slider_size}"
                )

                widget_bounds = (
                    self.anchor_positions[0] + screen_offset[0] - half_size[0],
                    self.anchor_positions[0] + screen_offset[0] + half_size[0],
                    self.anchor_positions[1] + screen_offset[1] - half_size[1],
                    self.anchor_positions[1] + screen_offset[1] + half_size[1],
                    0.0,
                    0.0,
                )

                slider_initial_value = widget_info["slider_initial_value"]
                slider_min_value = widget_info["slider_min_value"]
                slider_max_value = widget_info["slider_max_value"]

                slider_length = panel_width * slider_size[0]
                slider_height_fraction = slider_size[1] / slider_size[0]

                slider = SliderWidget(
                    renderer,
                    interactor,
                    min_value=slider_min_value,
                    max_value=slider_max_value,
                    initial_value=slider_initial_value,
                    title=widget_info["slider_title"],
                    callback=widget_info["callback"],
                    position=[widget_bounds[0], widget_bounds[2]],
                    bar_length=slider_length,
                    use_relative_position=True,
                    slider_thickness=slider_height_fraction,
                )

                slider.panel_offset = panel_offset
                slider.panel_size = slider_size
                if widget_info.get("flat", True):
                    slider.apply_flat_style()

                added_widgets.update({widget_name: slider})

            elif widget_type == "button":
                button_size = np.asarray(widget_info["button_size"])

                half_size = (
                    np.asarray([button_size[0] / 2, button_size[1] / 2]) * panel_width
                )

                assert panel_offset[0] + (button_size[0] / 2) <= 1.0, (
                    f"Widget {widget_name} exceeds panel bounds: "
                    f"panel_offset {panel_offset}, button_size {button_size}"
                    f", computed max {panel_offset[0] + (button_size[0] / 2)}"
                )

                assert panel_offset[0] - (button_size[0] / 2) >= 0.0, (
                    f"Widget {widget_name} exceeds panel bounds: "
                    f"panel_offset {panel_offset}, button_size {button_size}"
                    f", computed min {panel_offset[0] - (button_size[0] / 2)}"
                )

                widget_bounds = (
                    self.anchor_positions[0] + screen_offset[0] - half_size[0],
                    self.anchor_positions[0] + screen_offset[0] + half_size[0],
                    self.anchor_positions[1] + screen_offset[1] - half_size[1],
                    self.anchor_positions[1] + screen_offset[1] + half_size[1],
                    0.0,
                    0.0,
                )

                object_name = f"buttons/{widget_name}_button"

                # button = ButtonWidget(
                #     renderer,
                #     interactor,
                #     widget_info["icon_names"],
                #     widget_info["callback"],
                #     initial_state=widget_info.get("state", 0),
                #     widget_bounds=widget_bounds,
                #     name=object_name,
                # )




                if self.use_vector_buttons:

                    button_color = widget_info.get("button_color", None)


                    icon_names = widget_info.get(
                        "icon_names", ["question_sign"])
                    if isinstance(icon_names, str):
                        icon_names = [icon_names]
                    shapes = [
                        os.path.join(ICON_ROOT, "vtk_icons",
                                     f"{icon_name}.vtk")
                        for icon_name in icon_names
                    ]
                    if len(shapes) == 1:
                        shapes = shapes[0]
                    if "input_data" in widget_info:
                        # Ready-made geometry (e.g. a colour swatch disc).
                        shapes = widget_info["input_data"]


                    button = VectorButtonWidget(
                        renderer=self.renderer,
                        interactor=self.interactor,
                        icon_name=icon_names,
                        input_data=shapes,
                        callback=widget_info["callback"],
                        interactive=widget_info.get("interactive", True),
                        bounds=widget_bounds,
                        color=button_color,
                        initial_state=widget_info.get("state", 0),
                        hover_text=widget_info.get("hover_text"),
                        tint_states=widget_info.get("tint_states"),
                    )
                    # Icon-sized buttons get a rounded-square tile; small
                    # inline controls (locks, steppers) stay bare.
                    if (button.interactive and
                            min(widget_info.get("button_size", (0, 0))) >= 0.2):
                        button.background_style = "rounded"
                    # button.equal_aspect_ratio = True

                else:
                    button = ButtonWidget(
                        renderer=self.renderer,
                        interactor=self.interactor,
                        icon_name=widget_info["icon_names"],
                        widget_bounds = widget_bounds,
                        callback=widget_info["callback"],
                        initial_state=widget_info.get("state", 0),
                        name=object_name,
                        # show_bounds=True
                    )

                button.panel_offset = panel_offset
                button.panel_size = button_size

                added_widgets.update({widget_name: button})

            elif widget_type == "compass":
                compass = add_compass_widget(renderer, interactor)

                widget_size = np.asarray(widget_info["widget_size"])
                half_size = (
                    np.asarray([widget_size[0] / 2, widget_size[1] / 2]) * panel_width
                )

                assert panel_offset[0] + (widget_size[0] / 2) <= 1.0, (
                    f"Widget {widget_name} exceeds panel bounds: "
                    f"panel_offset {panel_offset}, widget_size {widget_size}"
                )

                compass.panel_offset = panel_offset
                compass.panel_size = widget_size

                added_widgets.update({widget_name: compass})

                widget_bounds = (
                    self.anchor_positions[0] + screen_offset[0] - half_size[0],
                    self.anchor_positions[0] + screen_offset[0] + half_size[0],
                    self.anchor_positions[1] + screen_offset[1] - half_size[1],
                    self.anchor_positions[1] + screen_offset[1] + half_size[1],
                    0.0,
                    0.0,
                )

                compass.GetRepresentation().GetPoint1Coordinate().SetValue(
                    widget_bounds[0], widget_bounds[2]
                )
                compass.GetRepresentation().GetPoint2Coordinate().SetValue(
                    widget_bounds[0] + half_size[0], widget_bounds[2] + half_size[1]
                )

            elif widget_type == 'value_changer':
                value_changer_size = np.asarray(widget_info["widget_size"])

                half_size = (
                    np.asarray([value_changer_size[0] / 2, value_changer_size[1] / 2]) * panel_width
                )

                assert panel_offset[0] + (value_changer_size[0] / 2) <= 1.0, (
                    f"Widget {widget_name} exceeds panel bounds: "
                    f"panel_offset {panel_offset}, value_changer_size {value_changer_size}"
                )

                assert panel_offset[0] - (value_changer_size[0] / 2) >= 0.0, (
                    f"Widget {widget_name} exceeds panel bounds: "
                    f"panel_offset {panel_offset}, value_changer_size {value_changer_size}"
                )

                widget_bounds = (
                    self.anchor_positions[0] + screen_offset[0] - half_size[0],
                    self.anchor_positions[0] + screen_offset[0] + half_size[0],
                    self.anchor_positions[1] + screen_offset[1] - half_size[1],
                    self.anchor_positions[1] + screen_offset[1] + half_size[1],
                    0.0,
                    0.0,
                )

                value_changer = ValueChangerWidget(
                    renderer,
                    interactor,
                    initial_value = widget_info["initial_value"],
                    min_value = widget_info["min_value"],
                    max_value = widget_info["max_value"],
                    step = widget_info["step"],
                    callback = widget_info["callback"],
                    position=[widget_bounds[0], widget_bounds[2]],
                    size=value_changer_size,
                    name=widget_name,
                    use_relative_position=True,
                    prepended_text=widget_info.get("prepended_text", None),
                    text_color=widget_info.get("text_color", text_color),
                    text_size=widget_info.get("text_size", 12),
                )

                value_changer.panel_offset = panel_offset
                value_changer.panel_size = value_changer_size

                added_widgets.update({widget_name: value_changer})

            elif widget_type == 'orientation_widget':
                from .specialists import CameraOrientationWidget

                orientation_widget = CameraOrientationWidget(
                    renderer,
                    interactor,
                    position=[widget_bounds[0], widget_bounds[2]],
                    size=widget_info["widget_size"],
                    name=widget_name,
                )
                # orientation_widget.panel_offset = panel_offset
                # orientation_widget.panel_size = widget_info["widget_size"]

                added_widgets.update({widget_name: orientation_widget})

            else:
                raise NotImplementedError(
                    f"{bcolors.FAIL}Widget type {widget_type} not recognized for widget {widget_name}{bcolors.ENDC}"
                )

        self.added_widgets = added_widgets

        # Initial call to set up button positions
        self.update_layout(None, None)


        # self.panel_background.AddObserver("ResizeEvent", partial(self.update_panel_elements, render=True))
        # self.panel_background.AddObserver("InteractionEvent", partial(self.update_panel_elements, render=True))
        self.ownObserver(
            self.panel_background, "EndInteractionEvent",
            partial(self.update_layout, render=True))
        # self.panel_background.AddObserver("ModifiedEvent", partial(self.update_panel_elements, render=True))
        # self.panel_background.AddObserver("OnDragEvent", partial(self.update_panel_elements, render=True))


        render_window = interactor.GetRenderWindow()
        self.ownObserver(
            render_window, "WindowResizeEvent", self.update_layout)

        if collapsed:
            self.collapse_panel()
            self.collapse_button.GetRepresentation().SetState(1)
            self.update_layout(None, None, render=True)


    def _layout_header(self):
        """Centre the title and collapse chevron in a themed header band.

        Runs after the background is redrawn and only moves the two header
        widgets *within* the panel; their stored layout bounds (used to size
        the panel) are left untouched, so the panel does not grow.
        """
        background = self.panel_background
        if not isinstance(background, VectorPanelBackground):
            return
        bounds = background.GetBounds()
        band, size_x, size_y, inset_x, title_inset = panel_header_metrics(
            self.interactor)
        window_width = max(1, self.interactor.GetRenderWindow().GetSize()[0])
        top = bounds[3]
        centre = top - band / 2.0
        if getattr(self, "_panel_collapsed", False):
            centre = (bounds[2] + bounds[3]) / 2.0   # centred on the pill
        background.header_height = band
        chevron_left = bounds[1] - inset_x - size_x
        button = getattr(self, "collapse_button", None)
        if isinstance(button, VectorButtonWidget):
            button.SetBounds(chevron_left, bounds[1] - inset_x,
                             centre - size_y / 2.0, centre + size_y / 2.0)
        title = getattr(self, "text_anchor", None)
        if isinstance(title, TextWidget):
            title_x = bounds[0] + title_inset
            title_width = max(0.001, chevron_left - 6.0 / window_width - title_x)
            text_height = panel_title_text_height(self.interactor)
            title_y = centre - text_height / 2.0
            # update_layout writes the representation directly, so set it
            # the same way (TextWidget.SetPosition skips "unchanged" moves).
            rep = title.GetRepresentation()
            rep.GetPositionCoordinate().SetValue(title_x, title_y)
            rep.GetPosition2Coordinate().SetValue(title_width, text_height)
            title._locked_position = (title_x, title_y)
            title._locked_size = (title_width, text_height)
            if title.elide_to_bounds:
                title._update_edit_display()
            rep.Modified()
            title.Modified()

    def engulf_widget_bounds(self, panel_bounds, widget_bounds):
        """
        Updates the panel bounds to encompass the widget bounds.
        This function adjusts the panel bounds to ensure that it fully contains
        the widget bounds. It modifies the panel bounds in-place by comparing
        each coordinate of the widget bounds with the corresponding coordinate
        of the panel bounds.
        Args:
            panel_bounds (list[float]): A list of four float values representing
                the current bounds of the panel in the format
                [left, right, top, bottom].
            widget_bounds (list[float]): A list of four float values representing
                the bounds of the widget in the format [left, right, top, bottom].
        Returns:
            list[float]: The updated panel bounds after encompassing the widget bounds.
        """

        if widget_bounds[0] < panel_bounds[0]:
            panel_bounds[0] = widget_bounds[0]
        if widget_bounds[1] > panel_bounds[1]:
            panel_bounds[1] = widget_bounds[1]
        if widget_bounds[2] < panel_bounds[2]:
            panel_bounds[2] = widget_bounds[2]
        if widget_bounds[3] > panel_bounds[3]:
            panel_bounds[3] = widget_bounds[3]

        return panel_bounds


    def redraw_panel_background(self, panel_bounds, buffer=0.01):
        """
        Adjusts and redraws the background panel with optional padding.
        This function recalculates the position and size of a panel's background
        based on the given panel bounds and an optional buffer. It updates the
        background representation's position and size accordingly.
        Args:
            panel_bounds (list): A list of four float values representing the
                bounds of the panel in the format [x_min, x_max, y_min, y_max].
            buffer (float, optional): An optional padding value to be added
                around the panel bounds. Defaults to 0.01.
        Side Effects:
            Updates the position and size of the `panel_background` object,
            including its `panel_bounds` and `panel_size` attributes.
        Note:
            This function assumes the existence of a `panel_background` object
            with a `GetRepresentation` method and `SetPosition`/`SetPosition2`
            methods for updating its position and size.
        """

        if panel_bounds is None:
            # A dock can temporarily disable every child while hidden. There
            # is then no enabled-widget union to redraw, but the last explicit
            # panel bounds remain valid for the subsequent unhide/layout pass.
            return

        BackgroundRepresentation = self.panel_background.GetRepresentation()

        width = panel_bounds[1] - panel_bounds[0]
        height = panel_bounds[3] - panel_bounds[2]

        padded_width = width + (2 * buffer)
        padded_height = height + (2 * buffer)
        padded_x = panel_bounds[0] - buffer
        padded_y = panel_bounds[2] - buffer

        if isinstance(self.panel_background, vtk.vtkBorderWidget):
            BackgroundRepresentation.SetPosition(padded_x, padded_y)
            BackgroundRepresentation.SetPosition2(padded_width, padded_height)

        elif isinstance(self.panel_background, VectorPanelBackground):
            self.panel_background.SetBounds(padded_x, padded_x + padded_width, padded_y, padded_y + padded_height)



        self.panel_background.panel_bounds = [
            padded_x,
            padded_x + padded_width,
            padded_y,
            padded_y + padded_height,
        ]
        self.panel_background.panel_size = [padded_width, padded_height]
        # Keep the panel's own hit-test rectangle in sync with the visible
        # background.  Widget layout can extend well beyond the small rectangle
        # supplied to the constructor (buttons commonly use negative Y offsets).
        # Leaving this at its initial value makes clicks on those controls look
        # like empty-scene clicks to the interactor, which clears the selection
        # before the control callback runs.
        self.panel_bounds = np.asarray(
            self.panel_background.panel_bounds, dtype=float)

    def update_layout(self, caller=None, event=None, render=False):
        """
        Updates the panel elements and their positions based on the caller's interaction
        and the current state of the panel. This function handles resizing,
        repositioning, and updating the bounds of various widgets within the panel.

        Widgets within VTK are annoyingly inconsistent in how they handle their bounds
        and positions. This function attempts to standardize the behavior of the widgets
        within the panel by recalculating their positions and sizes based on the current
        state of the panel and the interaction event.

        Args:
            caller: The object that triggered the event, typically a VTK widget.
            event: The event that occurred, triggering the update.
        Functionality:
            - Adjusts the panel's size and position based on user interactions.
            - Updates the bounds and positions of widgets (e.g., sliders, buttons, text
            widgets) within the panel.
            - Handles changes in panel aspect ratio and recalculates widget positions
            accordingly.
            - Ensures widgets are properly aligned and resized within the panels
            bounds.
            - Supports multiple widget types, including:
                - vtkSliderWidget
                - vtkCompassWidget
                - vtkTextWidget
                - vtkButtonWidget
            - Recalculates the panel's overall bounds to encompass all widgets.
            - Redraws the panel background to reflect the updated bounds.
        Raises:
            NotImplementedError: If an unrecognized widget type is encountered.
        Notes:
            - This function assumes the presence of global variables such as
            `panel_background`,
              `text_anchor`, `added_widgets`, `buffer`, `renderer`, and `interactor`.
            - The function relies on VTK and NumPy for widget manipulation and
            mathematical operations.
        """

        screenspace_widgets = _button_types()
        slider_widgets = _SliderAPI            # native and composite
        two_point_widgets = vtk.vtkCompassWidget
        position_widgets = (vtk.vtkTextWidget, ValueChangerWidget)
        pure_vtk_widgets = (vtk.vtkCameraOrientationWidget,)

        window_size = self.interactor.GetRenderWindow().GetSize()

        if isinstance(self.panel_background, vtk.vtkBorderWidget):

            anchor_positions = np.asarray(self.panel_background.GetRepresentation().GetPositionCoordinate().GetValue()) + np.asarray(
                [self.buffer, self.buffer, self.buffer]
            )
            panel_height = self.panel_background.GetRepresentation().GetPosition2Coordinate().GetValue()[1] - (2 * self.buffer)
            panel_width = self.panel_background.GetRepresentation().GetPosition2Coordinate().GetValue()[0] - (2 * self.buffer)

        elif isinstance(self.panel_background, VectorPanelBackground):

            bounds = self.panel_background.GetBounds()
            anchor_positions = np.asarray([bounds[0] + self.buffer, bounds[2] + self.buffer])
            panel_width = bounds[1] - bounds[0] - (2 * self.buffer)
            panel_height = bounds[3] - bounds[2] - (2 * self.buffer)

        anchor_positions[1] += panel_height

        new_panel_size = np.asarray([panel_width, panel_height])

        old_panel_size = self.panel_background.panel_size
        if old_panel_size is None:
            old_panel_size = np.asarray([panel_width, panel_height])

        old_panel_size -= np.asarray([2 * self.buffer, 2 * self.buffer])

        height_change = np.abs(old_panel_size[1] - new_panel_size[1])

        if self.keep_aspect_ratio and height_change > 0.01:

            old_aspect_ratio = old_panel_size[0] / old_panel_size[1]
            new_aspect_ratio = new_panel_size[0] / new_panel_size[1]
            aspect_ratio = old_aspect_ratio / new_aspect_ratio
            new_panel_size[0] = new_panel_size[0] * aspect_ratio

            panel_width = new_panel_size[0]
            panel_height = new_panel_size[1]

            self.panel_background.panel_size = new_panel_size


        for panel_element_name, panel_element in self.added_widgets.items():

            panel_offset = np.asarray(panel_element.panel_offset) * panel_width
            element_size = np.asarray(panel_element.panel_size) * panel_width

            half_size = (element_size[0] / 2, element_size[1] / 2)

            widget_bounds = np.asarray(
                [
                    anchor_positions[0] + panel_offset[0] - half_size[0],
                    anchor_positions[0] + panel_offset[0] + half_size[0],
                    anchor_positions[1] + panel_offset[1] - half_size[1],
                    anchor_positions[1] + panel_offset[1] + half_size[1],
                    0.0,
                    0.0,
                ]
            )

            if isinstance(panel_element, slider_widgets):
                slider_length = (widget_bounds[1] - widget_bounds[0])

                panel_slider = panel_element

                rep = panel_slider.GetRepresentation()
                rep.GetPoint1Coordinate().SetValue(widget_bounds[0], widget_bounds[2])
                rep.GetPoint2Coordinate().SetValue(
                    widget_bounds[0] + slider_length, widget_bounds[2]
                )

                rep.SetTubeWidth(0.05 * slider_length)
                rep.SetEndCapWidth(0.1 * slider_length)
                rep.SetSliderWidth(0.1 * slider_length)
                rep.SetTitleHeight(0.1 * slider_length)
                rep.SetLabelHeight(0.1 * slider_length)
                rep.SetSliderLength(0.05 * slider_length)

                panel_element.panel_bounds = widget_bounds

            elif isinstance(panel_element, two_point_widgets):

                two_point_widget = panel_element

                rep = two_point_widget.GetRepresentation()
                rep.GetPoint1Coordinate().SetValue(widget_bounds[0], widget_bounds[2])
                rep.GetPoint2Coordinate().SetValue(widget_bounds[1], widget_bounds[3])
                rep.GetPoint1Coordinate().SetCoordinateSystemToNormalizedDisplay()
                rep.GetPoint2Coordinate().SetCoordinateSystemToNormalizedDisplay()

                panel_element.panel_bounds = widget_bounds

            elif isinstance(panel_element, position_widgets):
                position_widget = panel_element
                rep = position_widget.GetRepresentation()
                rep.GetPositionCoordinate().SetValue(widget_bounds[0], widget_bounds[2])
                rep.GetPosition2Coordinate().SetValue(
                    widget_bounds[1] - widget_bounds[0],
                    widget_bounds[3] - widget_bounds[2],
                )
                rep.GetPositionCoordinate().SetCoordinateSystemToNormalizedDisplay()
                rep.GetPosition2Coordinate().SetCoordinateSystemToNormalizedDisplay()

                panel_element.panel_bounds = widget_bounds
                if isinstance(position_widget, TextWidget):
                    # Keep the stored geometry in step (ellipsis fitting and
                    # locking read it) and re-fit when the width changed.
                    new_size = (widget_bounds[1] - widget_bounds[0],
                                widget_bounds[3] - widget_bounds[2])
                    width_changed = abs(new_size[0] - position_widget._locked_size[0]) > 1e-6
                    position_widget._locked_position = (widget_bounds[0], widget_bounds[2])
                    position_widget._locked_size = new_size
                    if width_changed and position_widget.elide_to_bounds:
                        position_widget._update_edit_display()

                position_widget.Modified()

            elif isinstance(panel_element, screenspace_widgets):

                element_bounds = np.array(widget_bounds) * np.array([
                                window_size[0],
                                window_size[0],
                                window_size[1],
                                window_size[1],
                                0.0,
                                0.0,
                            ]
                )

                panel_element.GetRepresentation().PlaceWidget(element_bounds)
                panel_element.panel_bounds = widget_bounds

            elif isinstance(panel_element, pure_vtk_widgets):
                # Pure VTK widgets that manage their own positions
                continue

            elif isinstance(panel_element, VectorButtonWidget):

                keep_aspect_ratio = getattr(panel_element, "equal_aspect_ratio", True)

                element_bounds = np.array(widget_bounds)

                x0 = element_bounds[0]
                y0 = element_bounds[2]
                x1 = element_bounds[1]
                y1 = element_bounds[3]

                if keep_aspect_ratio:

                    # make it so the icons are actually square and not stretched when the panel is resized by adjusting the bounds to maintain the aspect ratio of the element size

                    window_width, window_height = self.interactor.GetRenderWindow().GetSize()

                    if window_width == 0:
                        window_width = 1
                    if window_height == 0:
                        window_height = 1


                    element_width = x1 - x0
                    element_height = y1 - y0

                    aspect_ratio = element_width / element_height
                    window_aspect_ratio = window_width / window_height

                    if aspect_ratio > window_aspect_ratio: # If the element is wider than the window aspect ratio, we need to reduce the width to maintain the aspect ratio
                        element_width = element_height * window_aspect_ratio
                        element_height = element_height * window_aspect_ratio

                    width_multiplier = aspect_ratio / window_aspect_ratio
                    # height_multiplier = window_aspect_ratio / aspect_ratio
                    height_multiplier = 1.0

                    x1 = x0 + (element_width * width_multiplier)
                    y1 = y0 + (element_height * height_multiplier)

                panel_element.SetBounds(x0, x1, y0, y1)
                panel_element.panel_bounds = widget_bounds

            elif isinstance(panel_element, ScrollablePanel):
                panel_element.SetBounds(
                    widget_bounds[0], widget_bounds[1],
                    widget_bounds[2], widget_bounds[3])
                panel_element.panel_bounds = widget_bounds

            elif isinstance(panel_element, ColorPaletteWidget):
                panel_element.SetBounds(
                    widget_bounds[0], widget_bounds[1],
                    widget_bounds[2], widget_bounds[3])

            else:
                logger.debug("%s %s", f"Widget type not recognised {panel_element_name}", type(panel_element))
                raise NotImplementedError


        new_panel_bounds = None

        new_panel_bounds = self.determine_panel_bounds()
        # A collapsed panel keeps its header-only bounds: growing them to the
        # layout's height (e.g. on a window resize) drew the header controls
        # over the next docked panel.
        if self.contentLayout() is not None and new_panel_bounds is not None \
                and not self._panel_collapsed:
            new_panel_bounds = self._bounds_with_layout(new_panel_bounds)

        self.redraw_panel_background(new_panel_bounds, buffer=self.buffer)
        self._layout_header()
        self._apply_content_layout()

        if render:
            self.interactor.GetRenderWindow().Render()




    def determine_panel_bounds(self, initial_bounds=None):
        """
        Determines the bounds of the panel based on the positions of the added widgets.
        This function iterates through all added widgets and calculates the minimum
        and maximum bounds to encompass all widgets
        within the panel. It returns the updated panel bounds as a list.

        """
        new_panel_bounds = initial_bounds

        for element_name, panel_element in self.added_widgets.items():

            enabled = panel_element.GetEnabled()

            if enabled == 0:
                continue

            widget_bounds = panel_element.panel_bounds

            if isinstance(panel_element, _SliderAPI):   # native or composite
                widget_bounds[2] -= (0.2 * (widget_bounds[1] - widget_bounds[0]))

            if new_panel_bounds is None:
                new_panel_bounds = widget_bounds
            else:
                new_panel_bounds = self.engulf_widget_bounds(new_panel_bounds, widget_bounds)

        return new_panel_bounds

    def embedded_child_resized(self, child):
        """Adopt a bottom-edge resize made by an embedded scroll viewport."""
        if child not in self.added_widgets.values():
            return
        panel_bounds = self.panel_background.GetBounds()
        panel_width = max(
            1e-9, panel_bounds[1] - panel_bounds[0] - 2 * self.buffer)
        anchor_x = panel_bounds[0] + self.buffer
        anchor_y = panel_bounds[3] - self.buffer
        child_bounds = child.GetBounds()
        old_height = float(child.panel_size[1]) * panel_width
        new_width = child_bounds[1] - child_bounds[0]
        new_height = child_bounds[3] - child_bounds[2]
        center_x = (child_bounds[0] + child_bounds[1]) / 2.0
        center_y = (child_bounds[2] + child_bounds[3]) / 2.0
        child.panel_size = np.asarray(
            [new_width / panel_width, new_height / panel_width])
        child.panel_offset = np.asarray(
            [(center_x - anchor_x) / panel_width,
             (center_y - anchor_y) / panel_width])

        height_delta = new_height - old_height
        if self.parent_pane is not None and abs(height_delta) > 1e-12:
            current = self.parent_pane._panel_heights.get(self)
            if current is not None:
                self.parent_pane._panel_heights[self] = max(
                    .06, current + height_delta)
            self.parent_pane.layout()
        else:
            self.update_layout(render=False)

    def is_within_bounds(self, x, y):
        """Check if a given position is within the panel bounds."""
        if not self._pane_visible:
            return False
        # Read the live background bounds so dragging/resizing a panel cannot
        # leave its input region behind.  Fall back to panel_bounds for older
        # background implementations.
        get_bounds = getattr(self.panel_background, "GetBounds", None)
        bounds = get_bounds() if get_bounds is not None else self.panel_bounds
        xmin, xmax, ymin, ymax = bounds
        return xmin <= x <= xmax and ymin <= y <= ymax

    def handle_mouse_wheel(self, x, y, direction):
        """Offer wheel input to the deepest scrollable child first."""
        if not self._pane_visible or not self.is_within_bounds(x, y):
            return False
        for child in reversed(tuple(self.added_widgets.values())):
            handler = getattr(child, 'handle_mouse_wheel', None)
            contains = getattr(child, 'is_within_bounds', None)
            if (handler is not None and
                    (contains is None or contains(x, y)) and
                    handler(x, y, direction)):
                return True
        return False


    def collapse_panel(self):


        """Execute the collapse panel operation."""
        for element_name, panel_element in self.added_widgets.items():
            if element_name == "panel_title":
                continue
            if element_name == "collapse_button":
                continue

            if isinstance(panel_element, _button_types()):
                rep = panel_element.GetRepresentation()


                rep.SetVisibility(False)

            panel_element.SetEnabled(False)

        self._panel_collapsed = True
        self._sync_layout_visibility()
        self.collapsedChanged.emit(True)
        if isinstance(self.panel_background, VectorPanelBackground):
            self.panel_background.set_collapsed_header(True)
        if self.parent_pane is not None:
            self.parent_pane.layout()

        # self.interactor.GetRenderWindow().Render()

    def expand_panel(self):


        """Execute the expand panel operation."""
        for element_name, panel_element in self.added_widgets.items():
            if element_name == "panel_title":
                continue
            if element_name == "collapse_button":
                continue

            if element_name in getattr(self, "suppressed_elements", ()):
                continue

            if isinstance(panel_element, _button_types()):
                rep = panel_element.GetRepresentation()


                rep.SetVisibility(True)

            panel_element.SetEnabled(True)

        self._panel_collapsed = False
        self._sync_layout_visibility()
        self._apply_content_layout()
        self.collapsedChanged.emit(False)
        if isinstance(self.panel_background, VectorPanelBackground):
            self.panel_background.set_collapsed_header(False)
        if self.parent_pane is not None:
            self.parent_pane.layout()


        # self.interactor.GetRenderWindow().Render()

    def toggle_panel(self, caller, event):
        """Toggle the visibility of the panel elements."""


        if caller.GetRepresentation().GetState() == 1:
            logger.debug(f"Collapsing panel {self.panel_title}")
            self.collapse_panel()
        else:
            logger.debug(f"Expanding panel {self.panel_title}")
            self.expand_panel()


        self.panel_bounds = self.determine_panel_bounds()



        self.redraw_panel_background(self.panel_bounds, buffer=self.buffer)

        self.update_layout(None, None, render=True)

        if self.parent_pane is not None:
            self.parent_pane.layout()

        self.interactor.GetRenderWindow().Render()

    def close_panel(self, caller=None, event=None):
        """Hide a floating panel; callers may show the same instance again."""
        self.SetVisibility(False)
        self.closed.emit()
        self.interactor.GetRenderWindow().Render()

    def handle_mouse_move(self, caller, event):
        """Handle mouse move events within the panel."""
        # mouse_pos = self.interactor.GetEventPosition()
        # normalized_x = mouse_pos[0] / self.interactor.GetRenderWindow().GetSize()[0]
        # normalized_y = mouse_pos[1] / self.interactor.GetRenderWindow().GetSize()[1]
        pass

    def handle_left_button_down(self, caller, event):
        """Handle left button down events within the panel."""
        pass

    def handle_left_button_up(self, caller, event):
        """Handle left button up events within the panel."""
        pass

    def handle_right_button_down(self, caller, event):
        """Handle right button down events within the panel."""
        pass

    def handle_right_button_up(self, caller, event):
        """Handle right button up events within the panel."""
        pass

    # -- content layouts ----------------------------------------------------
    #
    # A WidgetPanel may hold a layout (setLayout) instead of, or as well as,
    # name-keyed widgets positioned by panel_offset. The layout fills the
    # area below the header band, and the panel grows to the layout's size
    # hint (or, when docked, tells the dock its height via dockHeight()).

    def _header_band(self):
        return panel_header_metrics(self.interactor)[0]

    def _content_frac_rect(self):
        x0, x1, y0, y1 = self.panel_background.GetBounds()[:4]
        buffer = self.buffer
        return (x0 + buffer, x1 - buffer, y0 + buffer,
                y1 - self._header_band())

    def contentsRect(self):
        if self.contentLayout() is None:
            return super().contentsRect()
        x0, x1, y0, y1 = self._content_frac_rect()
        width, height = self.viewportExtent()
        scale = ui_scale()
        return (x0 * width / scale, y0 * height / scale,
                max(0.0, x1 - x0) * width / scale,
                max(0.0, y1 - y0) * height / scale)

    def _layout_height_frac(self):
        hint = self.contentLayout().sizeHint()[1]
        return hint * ui_scale() / self._window_height()

    def _window_height(self):
        return max(1, self.interactor.GetRenderWindow().GetSize()[1])

    def _bounds_with_layout(self, panel_bounds):
        """Extend shrink-wrapped bounds downward to fit the layout."""
        bounds = [float(value) for value in panel_bounds[:4]]
        top = bounds[3] + self.buffer              # background top edge
        bottom = top - self._header_band() - self._layout_height_frac() \
            - self.buffer
        bounds[2] = min(bounds[2], bottom + self.buffer)
        return bounds

    def dockHeight(self):
        """Height a dock should give this panel, or None for legacy sizing."""
        if self.contentLayout() is None:
            return None
        return (self._header_band() + self._layout_height_frac()
                + self.buffer)

    def sizeHint(self):
        layout = self.contentLayout()
        if layout is None:
            return super().sizeHint()
        width = self.geometry("px")[2]
        height = (self.dockHeight() * self._window_height()) / ui_scale()
        return (width, height)

    def _apply_content_layout(self):
        layout = self.contentLayout()
        if layout is None or self._panel_collapsed or not self._pane_visible:
            return
        rect = self.contentsRect()
        if rect is not None:
            layout._applying = True
            try:
                layout.setGeometry(rect)
            finally:
                layout._applying = False
        self._sync_layout_visibility()

    def layoutRequestEvent(self, layout):
        """Resize for the layout's new hint, then lay it out."""
        if self._panel_collapsed or not self._pane_visible:
            self._sync_layout_visibility()
            return
        if self.parent_pane is not None:
            self.parent_pane.layout()       # re-stacks and calls SetBounds
        else:
            self.update_layout(render=False)
        self.requestRender()

    def _sync_layout_visibility(self):
        """Make layout widgets' on-screen state follow the panel.

        The panel alone shows or hides layout widgets' actors: a widget is
        drawn and interactive only while the panel is visible and expanded,
        the widget is not explicitly hidden, and (for form labels) its field
        is not hidden. Widgets' own show()/hide() only record intent.
        """
        layout = self.contentLayout()
        if layout is None:
            return
        panel_shown = self._pane_visible and not self._panel_collapsed
        for item in layout.widgetItems():
            _set_shown_raw(item.widget,
                           panel_shown and not item.effectivelyHidden())

    def _show_layout_widgets(self, _shown=None):
        self._sync_layout_visibility()

    def setLayout(self, layout):
        super().setLayout(layout)
        if layout is not None:
            self._sync_layout_visibility()
            if self.parent_pane is not None:
                self.parent_pane.layout()
            else:
                self.update_layout(render=False)

    def GetBounds(self):
        """Return the panel's normalized-display bounds."""
        return tuple(self.panel_background.GetBounds())

    def SetBounds(self, x_min, x_max, y_min, y_max):
        """Place the panel using the common normalized layout interface."""
        managed_bounds = (float(x_min), float(x_max),
                          float(y_min), float(y_max))
        self.panel_background.SetBounds(*managed_bounds)
        self.update_layout(render=False)
        if self.parent_pane is not None:
            # Floating panels normally shrink-wrap their enabled children.
            # Dock rows instead fill the pane's assigned horizontal slot and
            # retain their ordered-list height.
            self.panel_background.SetBounds(*managed_bounds)
            self.panel_background.panel_bounds = list(managed_bounds)
            self.panel_background.panel_size = [
                managed_bounds[1] - managed_bounds[0],
                managed_bounds[3] - managed_bounds[2]]
            self.panel_bounds = np.asarray(managed_bounds)
            # The dock's height wins over the shrink-wrapped one: re-place the
            # header and let a bottom list fill the slack evenly.
            self._layout_header()
            self._install_fit_on_resize()
            self._fit_embedded_bottom()
            self._apply_content_layout()

    def _install_fit_on_resize(self):
        """Re-fit a bottom embedded list after window resizes.

        Low priority so it runs after the list's own resize handler; side
        margins scale with window width and the bottom one with height, so
        they drift apart unless refitted.
        """
        if getattr(self, "_fit_resize_installed", False):
            return
        self._fit_resize_installed = True

        def refit(_caller=None, _event=None):
            if self.parent_pane is not None:
                self._fit_embedded_bottom()

        self.ownObserver(self.interactor, "ConfigureEvent", refit, -10.0)
        self.ownObserver(
            self.interactor.GetRenderWindow(), "WindowResizeEvent", refit,
            -10.0)

    def _fit_embedded_bottom(self):
        """Give a bottom embedded list the same bottom margin as its sides."""
        if getattr(self, "_panel_collapsed", False):
            return
        outer = self.panel_background.GetBounds()
        lists = [element for element in self.added_widgets.values()
                 if isinstance(element, ScrollablePanel) and element.GetEnabled()]
        if not lists:
            return
        lowest = min(lists, key=lambda element: element.GetBounds()[2])
        others = [element.panel_bounds[2] for element in self.added_widgets.values()
                  if element is not lowest and element.GetEnabled()
                  and getattr(element, "panel_bounds", None) is not None]
        inner = lowest.GetBounds()
        if others and min(others) < inner[2]:
            return          # something else sits below the list
        width, height = self.interactor.GetRenderWindow().GetSize()
        side_px = (inner[0] - outer[0]) * max(1, width)
        target = outer[2] + side_px / max(1, height)
        if abs(target - inner[2]) * height > 1.0 and target < inner[3]:
            lowest.SetBounds(inner[0], inner[1], target, inner[3])

    def SetPosition(self, x, y):
        bounds = self.GetBounds()
        self.SetBounds(x, x + bounds[1] - bounds[0],
                       y, y + bounds[3] - bounds[2])

    def SetSize(self, width, height):
        bounds = self.GetBounds()
        self.SetBounds(bounds[0], bounds[0] + width,
                       bounds[2], bounds[2] + height)

    def set_element_shown(self, name, shown):
        """Show or hide one element independently of the panel; a hidden
        element stays hidden when the panel is shown or expanded."""
        suppressed = self.__dict__.setdefault("suppressed_elements", set())
        if shown:
            suppressed.discard(name)
        else:
            suppressed.add(name)
        element = self.added_widgets.get(name)
        if element is not None:
            element.SetEnabled(bool(shown) and self.GetEnabled()
                               and not self._panel_collapsed)
            return
        element = self.widget(name)            # moved into the layout
        if element is not None:
            element.setVisible(bool(shown))
            self._sync_layout_visibility()

    def SetVisibility(self, visible):
        """Show or hide the complete panel without changing collapsed state."""
        self._pane_visible = bool(visible)
        self.panel_background.SetVisibility(visible)
        self._sync_layout_visibility()
        if visible:
            # Bounds may have changed while hidden (e.g. docked under an
            # inactive tab), when content layout passes are skipped.
            self._apply_content_layout()
        suppressed = getattr(self, "suppressed_elements", ())
        for name, element in self.added_widgets.items():
            show = bool(visible) and name not in suppressed
            if self._panel_collapsed and name not in {
                    "panel_title", "collapse_button"}:
                show = False
            element.SetEnabled(show)
        if visible and self.parent_pane is not None:
            # Re-enabling restores a list's stored size; refit its margin.
            self._fit_embedded_bottom()

    def SetEnabled(self, enabled):
        self.SetVisibility(enabled)

    def GetEnabled(self):
        return int(self._pane_visible)

    def title(self):
        return self.panel_title

    def setTitle(self, title):
        self.panel_title = str(title)
        title_widget = self.added_widgets.get('panel_title')
        if title_widget is not None and hasattr(title_widget, 'setText'):
            title_widget.setText(self.panel_title)
        self.layoutChanged.emit()

    def isCollapsed(self):
        return self._panel_collapsed

    def setCollapsed(self, collapsed):
        if bool(collapsed) == self._panel_collapsed:
            return
        self.collapse_panel() if collapsed else self.expand_panel()

    def isClosable(self):
        return self.closable

    def setClosable(self, closable):
        self.closable = bool(closable)

    def widget(self, name):
        """Find a named element, including ones moved into the content layout.

        Elements taken out with ``removeWidget`` keep their name for lookup
        while this panel's layout manages them, so code that addresses
        elements by name keeps working after a panel is ported to layouts.
        """
        found = self.added_widgets.get(name)
        if found is not None:
            return found
        detached = getattr(self, "_detached_elements", {}).get(name)
        layout = self.contentLayout()
        if detached is not None and layout is not None and \
                detached in layout.widgets():
            return detached
        return None

    def addWidget(self, name, widget):
        if name in self.added_widgets:
            raise KeyError(f'widget {name!r} already exists')
        self.added_widgets[name] = widget
        if isinstance(widget, WidgetMixin):
            widget.setParent(self)
        if hasattr(widget, 'ui_z_order'):
            widget.ui_draw_scope = self   # draw-order checks are per panel
        self.update_layout(render=False)
        self.layoutChanged.emit()
        return widget

    def removeWidget(self, widget_or_name):
        name = (widget_or_name if isinstance(widget_or_name, str) else
                next((key for key, value in self.added_widgets.items()
                      if value is widget_or_name), None))
        if name is None:
            return None
        widget = self.added_widgets.pop(name, None)
        if widget is not None:
            self.__dict__.setdefault("_detached_elements", {})[name] = widget
        if isinstance(widget, WidgetMixin):
            widget.setParent(None)
        self.layoutChanged.emit()
        return widget

    def saveState(self):
        state = super().saveState()
        state.update({
            'title': self.panel_title,
            'collapsed': self._panel_collapsed,
            'closable': self.closable,
            'bounds': tuple(self.GetBounds()),
            'suppressedElements': sorted(
                getattr(self, 'suppressed_elements', ())),
            'widgets': {
                name: widget.saveState()
                for name, widget in self.added_widgets.items()
                if isinstance(widget, WidgetMixin)
            },
        })
        return state

    def restoreState(self, state):
        if not isinstance(state, dict):
            raise TypeError('panel state must be a dictionary')
        with self.signalBlocker():
            if 'title' in state:
                self.setTitle(state['title'])
            if 'closable' in state:
                self.setClosable(state['closable'])
            if 'bounds' in state:
                self.SetBounds(*state['bounds'])
            suppressed = set(state.get('suppressedElements', ()))
            for name in self.added_widgets:
                self.set_element_shown(name, name not in suppressed)
            child_states = state.get('widgets', {})
            for name, child_state in child_states.items():
                child = self.added_widgets.get(name)
                if isinstance(child, WidgetMixin):
                    child.restoreState(child_state)
            self.setCollapsed(state.get('collapsed', self._panel_collapsed))
            common = {key: state[key] for key in (
                'objectName', 'enabled', 'visible', 'toolTip', 'statusTip')
                if key in state}
            super().restoreState(common)
        self.update_layout(render=False)
        return True

    def Delete(self):
        self.observerRegistry().clear()
        for name, widget in list(self.added_widgets.items()):
            if name in {'panel_title', 'collapse_button'} or widget is not None:
                if hasattr(widget, 'close'):
                    widget.close()
                elif hasattr(widget, 'Delete'):
                    widget.Delete()
        self.added_widgets.clear()
        if self.panel_background is not None:
            self.panel_background.close()

    def __repr__(self):

        """Return the developer-facing representation."""
        panel_elements = ", ".join(self.panel_elements.keys())

        return f"<WidgetPanel title={self.panel_title}, position={self.panel_position}, width={self.panel_width}, elements=[{panel_elements}]>"


class DockPane(WidgetMixin):
    """Renderer-edge container for vertically stacked native UI panels.

    ``WidgetPanel`` instances retain their normal floating behaviour until
    added here.  The pane then supplies their normalized width and position,
    enables its scrollbar only when the stack exceeds the viewport, and can
    collapse to a small button on the selected renderer edge.
    """
    # Re-sorts its own drawables after creating children (see
    # register_ui_drawable), so late lower-z children are expected.
    ui_sorts_draw_order = True


    @ui_scoped
    def __init__(self, renderer, interactor, side="left", width=.18,
                 margin=.008, spacing=.008, panel_color=(1, 1, 1),
                 text_color=(0, 0, 0), opacity=.92,
                 pass_scroll_events=False):
        if side not in {"left", "right"}:
            raise ValueError("DockPane side must be 'left' or 'right'")
        self.renderer = renderer
        self.interactor = interactor
        self.initWidget(f'{side}_dock_pane')
        self.currentChanged = Signal(self)
        self.tabCloseRequested = Signal(self)
        self.dockLocationChanged = Signal(self)
        self.widthChanged = Signal(self)
        self.side = side
        self.panel_title = f"{side.title()} Dock Pane"
        self.added_widgets = {}
        # Lengths: bare numbers keep their historical meaning (viewport
        # fractions, with the width also scaled by the UI scale preference);
        # px()/frac()/"8px" values are resolved per axis on every use.
        self._width_spec = self._dock_length(width, scale_bare=True)
        self._margin_spec = self._dock_length(margin)
        self._spacing_spec = self._dock_length(spacing)
        self.panel_color = panel_color
        self.text_color = text_color
        self.panels = []
        self._panel_heights = {}
        self.scroll_offset = 0.0
        self._scroll_animation = None
        self._scroll_target = 0.0
        self.collapsed = False
        self.enabled = True
        self.pass_scroll_events = bool(pass_scroll_events)
        self.layout_observers = []
        # Vertical tab bar (VS Code style activity bar). Without tabs the
        # pane behaves exactly as before.
        self.tabs = []                 # [{"name", "icon", "tooltip", "button"}]
        self.active_tab = None
        self.content_collapsed = False
        self._panel_tab = {}
        self._explicit_heights = set()
        # WidgetPanel content scales with width, so their dock height does
        # too (height / available width, recorded when added).
        self._panel_aspect = {}
        self.tab_bar = None
        self._min_width_spec = self._dock_length(0.08)
        self._max_width_spec = self._dock_length(0.45)
        self._auto_collapsed = False   # collapsed for a narrow window
        DockPane._register(self)
        self.bounds = self._edge_bounds()


        if side == "left":
            slider_side = "right"
            slider_offset = -0.005
        elif side == "right":
            slider_side = "left"
            slider_offset = -0.005

        self.background = VectorPanelBackground(
            renderer, interactor, bounds=self.bounds,
            panel_color=panel_color, opacity=opacity, movable=False,
            resizable=False, corner_radius=0.0, ui_z_order=0,
            # No outline: it would seam the active tab off from the pane.
            border_width=0, border_color=panel_color,
            name=f"{side}_dock_pane")
        self.scroll_box = ScrollBox(
            renderer, interactor, self.bounds, row_height=.02,
            buffer=self._vertical(self._margin_spec), panel_color=panel_color,
            add_blinders=False,
            scroll_callback=self._scroll_callback, scrollbar_side=slider_side, scrollbar_padding=slider_offset)
        # Leave the pane's complete height available to its children, but
        # shorten only the visual scrollbar track below the corner control.
        self.scroll_box.scrollbar_top_inset = 0.0
        self.slider = self.scroll_box.slider


        # The existing vector chevrons are vertical; their two states still
        # provide an unambiguous open/closed edge control until dedicated
        # horizontal artwork is added.
        if side == "left":
            icons = ["chevron_left", "chevron_right"]
        elif side == "right":
            icons = ["chevron_right", "chevron_left"]
        elif side == "top":
            icons = ["chevron_up", "chevron_down"]
        elif side == "bottom":
            icons = ["chevron_down", "chevron_up"]
        self.collapse_button = VectorButtonWidget(
            renderer, interactor,
            input_data=[os.path.join(ICON_ROOT, "vtk_icons",
                                     f"{icon}.vtk") for icon in icons],
            icon_name=icons, initial_state=0, callback=self.toggle,
            bounds=(0, .02, .96, .99), color=text_color,
            name=f"{side}_dock_collapse")
        self.collapse_button.equal_aspect_ratio = True
        self._position_collapse_button()
        self.ownObserver(interactor.GetRenderWindow(),
                         "WindowResizeEvent", self._on_window_resize)
        self._init_resize_handle()

    TAB_BAR_PX = 92        # device pixels
    HANDLE_PX = 8          # grab strip on the pane's inner edge
    TAB_ICON_PX = 60
    TAB_PAD_PX = 14        # tab padding around its icon
    TAB_RADIUS_PX = 14     # tab corner / fillet radius

    # -- lengths -------------------------------------------------------------
    @staticmethod
    def _dock_length(value, scale_bare=False):
        from .units import Length, parse_length

        if isinstance(value, (int, float)) and not isinstance(value, bool):
            # A fraction of the window grows with its pixels already: only
            # the size preference applies, not the display density.
            factor = user_scale() if scale_bare else 1.0
            return Length(float(value) * factor, "frac")
        return parse_length(value, "frac", legacy=True)

    def _window_size(self):
        width, height = self.interactor.GetRenderWindow().GetSize()[:2]
        return max(1, width), max(1, height)

    def _horizontal(self, length):
        from .units import to_frac

        return to_frac(length, self._window_size()[0])

    def _vertical(self, length):
        from .units import to_frac

        return to_frac(length, self._window_size()[1])

    def _set_width_value(self, width):
        """Store a new width, keeping the unit the pane was created with."""
        from .units import Length, px

        if isinstance(width, Length) or isinstance(width, str):
            self._width_spec = self._dock_length(width)
        elif self._width_spec.unit == "px":
            pixels = float(width) * self._window_size()[0] / ui_scale()
            self._width_spec = px(pixels)
        else:
            self._width_spec = Length(float(width), "frac")

    @property
    def width(self):
        """Pane width as a fraction of the window width (at least the tab
        bar plus :attr:`MIN_CONTENT_PX` of content, so panels stay
        readable in a narrow window)."""
        window = max(1, self.interactor.GetRenderWindow().GetSize()[0])
        minimum = self._tab_bar_width() + self.MIN_CONTENT_PX * ui_scale() / window
        return min(1.0, max(self._horizontal(self._width_spec), minimum))

    @width.setter
    def width(self, value):
        self._set_width_value(value)

    @property
    def min_width(self):
        return self._horizontal(self._min_width_spec)

    @min_width.setter
    def min_width(self, value):
        self._min_width_spec = self._dock_length(value)

    @property
    def max_width(self):
        return self._horizontal(self._max_width_spec)

    @max_width.setter
    def max_width(self, value):
        self._max_width_spec = self._dock_length(value)

    @property
    def margin(self):
        """Horizontal margin (fraction of window width)."""
        return self._horizontal(self._margin_spec)

    @margin.setter
    def margin(self, value):
        self._margin_spec = self._dock_length(value)

    @property
    def vertical_margin(self):
        return self._vertical(self._margin_spec)

    @property
    def spacing(self):
        """Vertical gap between stacked panels (fraction of window height)."""
        return self._vertical(self._spacing_spec)

    @spacing.setter
    def spacing(self, value):
        self._spacing_spec = self._dock_length(value)

    MIN_CONTENT_PX = 220    # logical px of panel content, at least
    MIN_SCENE_PX = 200      # logical px left to the scene in narrow windows
    _panes = {}             # renderer -> [weakref to DockPane], in order

    @classmethod
    def _register(cls, pane):
        import weakref

        key = id(pane.renderer)
        refs = [ref for ref in cls._panes.get(key, []) if ref() is not None]
        refs.append(weakref.ref(pane))
        cls._panes[key] = refs

    def _siblings(self):
        """This renderer's panes, oldest first."""
        return [pane for pane in (ref() for ref in
                                  DockPane._panes.get(id(self.renderer), []))
                if pane is not None and pane.enabled]

    def _occupied_px(self, expanded):
        """Logical px of window width the pane covers, expanded or not."""
        window = max(1, self.interactor.GetRenderWindow().GetSize()[0])
        if expanded:
            fraction = self.width
        elif self.tabs:
            fraction = self._tab_bar_width()
        else:
            fraction = 0.0
        return fraction * window / ui_scale()

    def _fit_window(self):
        """On a window width change: collapse panes, newest first, while
        the scene would get under :attr:`MIN_SCENE_PX`; re-open the ones
        collapsed that way once there is room. Collapsing or expanding by
        hand in between is respected."""
        window = max(1, self.interactor.GetRenderWindow().GetSize()[0])
        panes = self._siblings()
        state = DockPane._panes.setdefault(("fit", id(self.renderer)), [None])
        if state[0] == (window, len(panes)):
            return
        state[0] = (window, len(panes))
        available = window / ui_scale()

        def scene(expanded):
            return available - sum(p._occupied_px(p in expanded)
                                   for p in panes)

        expanded = {p for p in panes if not p.isCollapsed()}
        for pane in panes:                       # re-open, oldest first
            if pane._auto_collapsed and pane not in expanded and \
                    scene(expanded | {pane}) >= self.MIN_SCENE_PX:
                expanded.add(pane)
                pane._auto_collapsed = False
                pane.setCollapsed(False)
        for pane in reversed(panes):              # collapse, newest first
            if scene(expanded) >= self.MIN_SCENE_PX:
                break
            if pane in expanded:
                expanded.discard(pane)
                pane.setCollapsed(True)
                pane._auto_collapsed = True

    def _tab_bar_width(self):
        if not self.tabs:
            return 0.0
        width = max(1, self.interactor.GetRenderWindow().GetSize()[0])
        return (self.TAB_BAR_PX * ui_scale()) / width

    def _edge_bounds(self):
        """Whole pane (tab bar + content), or just the tab bar when the
        content is collapsed."""
        width = (self._tab_bar_width() if (self.tabs and self.content_collapsed)
                 else self.width)
        if self.side == "left":
            return (0.0, width, 0.0, 1.0)
        return (1.0 - width, 1.0, 0.0, 1.0)

    def _content_bounds(self):
        tab = self._tab_bar_width()
        x0, x1, y0, y1 = self._edge_bounds()
        if self.side == "left":
            return (x0 + tab, x1, y0, y1)
        return (x0, x1 - tab, y0, y1)

    def _tab_bar_bounds(self):
        tab = self._tab_bar_width()
        if self.side == "left":
            return (0.0, tab, 0.0, 1.0)
        return (1.0 - tab, 1.0, 0.0, 1.0)

    def _handle_bounds(self):
        """Inner-edge grab strip (inside the pane margin)."""
        width = max(1, self.interactor.GetRenderWindow().GetSize()[0])
        strip = (self.HANDLE_PX * ui_scale()) / width
        x0, x1, y0, y1 = self._edge_bounds()
        if self.side == "left":
            return (x1 - strip, x1, y0, y1)
        return (x0, x0 + strip, y0, y1)

    # ---- tabs -----------------------------------------------------------
    def _tab_colors(self):
        theme = getattr(self.renderer, "theme", None)
        pane = tuple(self.panel_color)
        if theme is None:
            return tuple(c * 0.9 for c in pane), (0.1, 0.6, 1.0)
        if theme.dark_mode:
            bar = tuple(c * 0.75 for c in theme.pane_color)
        else:
            bar = tuple(p + (b - p) * 0.4 for p, b in
                        zip(theme.pane_color, theme.border_color))
        return bar, tuple(theme.accent_color_rgb)

    @ui_scoped
    def add_tab(self, name, icon, tooltip=None, align="top", keep_color=False):
        """Add a tab to the vertical tab bar; panels join it via add_panel.

        ``icon`` may be a library icon name or an explicit vector-data path.
        ``align="bottom"`` pins the tab to the bottom of the bar (as VS Code
        does for settings). ``keep_color`` shows the icon in colour even when
        inactive -- for status tabs whose icon carries meaning."""
        if self.tab_bar is None:
            bar_color, accent = self._tab_colors()
            self.tab_bar = VectorPanelBackground(
                self.renderer, self.interactor, bounds=self._tab_bar_bounds(),
                panel_color=bar_color, border_color=bar_color, opacity=1.0,
                border_width=0,   # a border would seam the tab into the pane
                movable=False, resizable=False, corner_radius=0.0,
                ui_z_order=1, name=f"{self.side}_tab_bar")
            # The active-tab indicator is drawn as a "well" in the accent.
            self.tab_bar.well_color = accent
            # Tabs replace the corner collapse chevron.
            self.collapse_button.SetEnabled(False)
        icon_path = (os.fspath(icon) if os.path.isfile(os.fspath(icon)) else
                     os.path.join(ICON_ROOT, "vtk_icons", f"{icon}.vtk"))
        icon_name = os.path.splitext(os.path.basename(icon_path))[0]
        button = VectorButtonWidget(
            self.renderer, self.interactor, input_data=[icon_path, icon_path],
            icon_name=[icon_name, icon_name],
            grayscale_states=[not keep_color, False],
            grayscale_brightness=0.35, initial_state=0,
            callback=lambda caller, event, tab=name: self.select_tab(tab),
            bounds=(0, .02, 0, .02), hover_text=tooltip or name.title(),
            name=f"{self.side}_tab_{name}")
        button.equal_aspect_ratio = True
        self.tabs.append({"name": name, "icon": icon, "tooltip": tooltip,
                          "button": button, "align": align})
        if self.active_tab is None:
            self.active_tab = name
        self._sync_tabs()
        self.layout()
        # The tab bar (z=1) and tab buttons are created after the resize
        # handle (UI_Z_PANEL_CONTROL); re-raise the handle above them.
        handle = getattr(self, "resize_handle", None)
        if handle is not None:
            enforce_ui_draw_order(self.renderer, [handle])
        return button

    def set_tab_icon(self, name, icon, tooltip=None):
        """Swap a tab's icon (e.g. a status tab); no-op for unknown tabs."""
        for tab in self.tabs:
            if tab["name"] != name:
                continue
            if tab["icon"] == icon and tooltip is None:
                return
            tab["icon"] = icon
            icon_path = (os.fspath(icon) if os.path.isfile(os.fspath(icon)) else
                         os.path.join(ICON_ROOT, "vtk_icons", f"{icon}.vtk"))
            icon_name = os.path.splitext(os.path.basename(icon_path))[0]
            button = tab["button"]
            button.input_states = [icon_path, icon_path]
            button.input_data = icon_path
            button.icon_name = [icon_name, icon_name]
            if tooltip is not None:
                tab["tooltip"] = tooltip
                button.hover_text = tooltip
            button.pd = None            # rebuild the icon geometry
            button.Modified()
            return

    def select_tab(self, name):
        """Show *name*'s panels; clicking the active tab collapses/expands."""
        self._auto_collapsed = False             # the user decided
        previous = self.active_tab
        if name == self.active_tab:
            self.content_collapsed = not self.content_collapsed
        else:
            self.active_tab = name
            self.content_collapsed = False
        self._stop_scroll_animation()
        self.scroll_offset = 0.0
        self._sync_tabs()
        self.layout(render=True)
        if previous != self.active_tab:
            self.currentChanged.emit(self.currentIndex())

    def count(self):
        return len(self.tabs)

    def currentIndex(self):
        return next((index for index, tab in enumerate(self.tabs)
                     if tab['name'] == self.active_tab), -1)

    def setCurrentIndex(self, index):
        index = int(index)
        if not 0 <= index < self.count():
            raise IndexError(index)
        name = self.tabs[index]['name']
        if name == self.active_tab and not self.content_collapsed:
            return
        previous = self.active_tab
        self.active_tab = name
        self.content_collapsed = False
        self._sync_tabs()
        self.layout(render=True)
        if previous != name:
            self.currentChanged.emit(index)

    def currentWidget(self):
        panels = self._tab_panels()
        return panels[0] if panels else None

    def widget(self, index):
        name = self.tabs[int(index)]['name']
        panels = [panel for panel in self.panels
                  if self._panel_tab.get(panel) == name]
        return panels[0] if panels else None

    def tabText(self, index):
        return self.tabs[int(index)]['name']

    def setTabText(self, index, text):
        tab = self.tabs[int(index)]
        old_name = tab['name']
        new_name = str(text)
        tab['name'] = new_name
        if self.active_tab == old_name:
            self.active_tab = new_name
        tab['button'].callback = (
            lambda caller, event, name=new_name: self.select_tab(name))
        for panel in self.panels:
            if self._panel_tab.get(panel) == old_name:
                self._panel_tab[panel] = new_name

    def tabToolTip(self, index):
        return self.tabs[int(index)].get('tooltip') or ''

    def setTabToolTip(self, index, tooltip):
        tab = self.tabs[int(index)]
        tab['tooltip'] = str(tooltip)
        tab['button'].setToolTip(tooltip)
        tab['button'].hover_text = str(tooltip)

    def requestCloseTab(self, index):
        index = int(index)
        if not 0 <= index < self.count():
            raise IndexError(index)
        self.tabCloseRequested.emit(index)

    def dockLocation(self):
        return self.side

    def setDockLocation(self, side):
        side = str(side).lower()
        if side not in {'left', 'right'}:
            raise ValueError("dock location must be 'left' or 'right'")
        if side == self.side:
            return
        self.side = side
        icons = (["chevron_left", "chevron_right"] if side == "left"
                 else ["chevron_right", "chevron_left"])
        self.collapse_button.input_states = [
            os.path.join(ICON_ROOT, "vtk_icons", f"{icon}.vtk")
            for icon in icons]
        self.collapse_button.icon_name = icons
        self.collapse_button.input_data = self.collapse_button.input_states[
            self.collapse_button.state % len(self.collapse_button.input_states)]
        self.collapse_button.pd = None
        self.layout(render=True)
        self.dockLocationChanged.emit(side)

    def dockWidth(self):
        return float(self.width)

    def setDockWidth(self, width):
        """Set the width: a window fraction, or a ``px()``/``frac()`` length."""
        from .units import Length

        if isinstance(width, (Length, str)):
            spec = self._dock_length(width)
            value = self._horizontal(spec)
            clamped = min(self.max_width, max(self.min_width, value))
            if not math.isclose(clamped, value, rel_tol=0.0, abs_tol=1e-12):
                spec = clamped
        else:
            spec = min(self.max_width, max(self.min_width, float(width)))
        previous = self.width
        self._set_width_value(spec)
        if math.isclose(self.width, previous, rel_tol=0.0, abs_tol=1e-12):
            return
        width = self.width
        self.layout(render=True)
        self.widthChanged.emit(width)

    def removeTab(self, index):
        index = int(index)
        tab = self.tabs.pop(index)
        tab['button'].close()
        if self.active_tab == tab['name']:
            self.active_tab = (self.tabs[min(index, len(self.tabs) - 1)]['name']
                               if self.tabs else None)
            self.currentChanged.emit(self.currentIndex())
        if self.active_tab is not None:
            for panel in self.panels:
                if self._panel_tab.get(panel) == tab['name']:
                    self._panel_tab[panel] = self.active_tab
        self._sync_tabs()
        self.layout(render=True)

    def isCollapsed(self):
        return self.collapsed or self.content_collapsed

    def setCollapsed(self, collapsed):
        collapsed = bool(collapsed)
        if self.tabs:
            self.content_collapsed = collapsed
            self._sync_tabs()
            self.layout(render=True)
        elif collapsed != self.collapsed:
            self.collapsed = collapsed
            self.background.SetVisibility(not collapsed)
            self.collapse_button.GetRepresentation().SetState(int(collapsed))
            self.layout(render=True)

    def _sync_tabs(self):
        for tab in self.tabs:
            active = tab["name"] == self.active_tab and not self.content_collapsed
            button = tab["button"]
            # Active icons keep their full size: the curved tab (drawn by
            # the tab bar) marks the selection, not an icon tile.
            button.GetRepresentation().SetState(int(active))
            button.background_style = None
            button.Modified()

    def _layout_tabs(self):
        if self.tab_bar is None:
            return
        window_width, window_height = self.interactor.GetRenderWindow().GetSize()
        window_width, window_height = max(1, window_width), max(1, window_height)
        bar = self._tab_bar_bounds()
        self.tab_bar.SetBounds(*bar)
        scale = ui_scale()
        # Too many tabs for the window's height: shrink them all alike so
        # the stack fits (icon, padding and fillet room).
        slot_px = (self.TAB_ICON_PX + 2 * self.TAB_PAD_PX +
                   2 * self.TAB_RADIUS_PX) * scale
        needed_px = len(self.tabs) * slot_px + 2 * self.TAB_RADIUS_PX * scale
        if self.tabs and needed_px > window_height:
            scale *= window_height / needed_px
        self._tab_scale = scale
        size_x = (self.TAB_ICON_PX * scale) / window_width
        size_y = (self.TAB_ICON_PX * scale) / window_height
        pad_x = (self.TAB_PAD_PX * scale) / window_width
        pad_y = (self.TAB_PAD_PX * scale) / window_height
        gap_y = 2.0 * (self.TAB_RADIUS_PX * scale) / window_height   # room for fillets
        outer_inset = 8.0 / window_width
        centre_x = (bar[0] + bar[1]) / 2.0
        top = 1.0 - gap_y
        bottom = gap_y
        indicator_w = 3.0 / window_width
        wells = []
        self.tab_bar.tab_shape = None
        slot = size_y + 2 * pad_y + gap_y
        # Top tabs stack downwards; bottom-aligned tabs stack upwards.
        ordered = ([t for t in self.tabs if t.get("align") != "bottom"] +
                   list(reversed([t for t in self.tabs if t.get("align") == "bottom"])))
        for tab in ordered:
            if tab.get("align") == "bottom":
                y0 = bottom + pad_y
                y1 = y0 + size_y
                bottom += slot
            else:
                y1, y0 = top - pad_y, top - pad_y - size_y
                top -= slot
            tab["button"].SetBounds(centre_x - size_x / 2.0, centre_x + size_x / 2.0, y0, y1)
            if tab["name"] == self.active_tab and not self.content_collapsed:
                # A tab in the pane's own colour that flows into the content.
                if self.side == "left":
                    tx0, tx1, content_side = bar[0] + outer_inset, bar[1], "right"
                else:
                    tx0, tx1, content_side = bar[0], bar[1] - outer_inset, "left"
                self.tab_bar.tab_shape = {
                    "x0": tx0, "x1": tx1, "y0": y0 - pad_y, "y1": y1 + pad_y,
                    "radius_px": (self.TAB_RADIUS_PX * scale), "color": tuple(self.panel_color),
                    "content_side": content_side}
                # Thin accent indicator on the tab's outer edge.
                edge = tx0 if self.side == "left" else tx1 - indicator_w
                wells.append((edge, edge + indicator_w, y0 + pad_y * 0.5, y1 - pad_y * 0.5))
        self.tab_bar.wells = wells
        self.tab_bar.Modified()

    def _tab_panels(self):
        if not self.tabs:
            return list(self.panels)
        return [panel for panel in self.panels
                if self._panel_tab.get(panel, self.tabs[0]["name"]) == self.active_tab]

    # ---- resize handle --------------------------------------------------
    @ui_scoped
    def _init_resize_handle(self):
        theme = getattr(self.renderer, "theme", None)
        self._grip_idle = (theme.muted_text_color if theme is not None
                           else (0.55, 0.55, 0.58))
        self._grip_active = (theme.accent_color_rgb if theme is not None
                             else (0.1, 0.6, 1.0))
        self.resize_handle = VectorPanelBackground(
            self.renderer, self.interactor, bounds=self._handle_bounds(),
            panel_color=self.panel_color, border_color=self.panel_color,
            # decorations_only never paints a fill; opacity applies to the grip
            opacity=1.0, movable=False, resizable=False, corner_radius=0.0,
            ui_z_order=UI_Z_PANEL_CONTROL, name=f"{self.side}_dock_resize",
            decorations_only=True)
        self.resize_handle.well_color = self._grip_idle
        self._handle_hover = False
        self._dragging = None            # (start_x_px, start_width) while dragging
        iren = self.interactor
        self._handle_tags = {
            "move": self.ownObserver(
                iren, "MouseMoveEvent", self._on_handle_move, 5.0),
            "press": self.ownObserver(
                iren, "LeftButtonPressEvent", self._on_handle_press, 5.0),
            "release": self.ownObserver(
                iren, "LeftButtonReleaseEvent", self._on_handle_release, 5.0),
        }
        self._layout_handle()

    def _layout_handle(self):
        handle = getattr(self, "resize_handle", None)
        if handle is None:
            return
        visible = self.enabled and not self.collapsed and not self.content_collapsed
        handle.SetVisibility(visible)
        bounds = self._handle_bounds()
        handle.SetBounds(*bounds)
        # A short grip pill centred on the strip.
        window_width, window_height = self.interactor.GetRenderWindow().GetSize()
        grip_w = 4.0 / max(1, window_width)
        grip_h = 46.0 / max(1, window_height)
        cx, cy = (bounds[0] + bounds[1]) / 2.0, (bounds[2] + bounds[3]) / 2.0
        handle.wells = [(cx - grip_w / 2, cx + grip_w / 2, cy - grip_h / 2, cy + grip_h / 2)]
        handle.well_color = (self._grip_active if (self._handle_hover or self._dragging)
                             else self._grip_idle)
        handle.Modified()

    def _pointer_on_handle(self):
        if not (self.enabled and not self.collapsed and not self.content_collapsed):
            return False
        width, height = self.interactor.GetRenderWindow().GetSize()
        x, y = self.interactor.GetEventPosition()
        x0, x1, y0, y1 = self._handle_bounds()
        slack = 3.0      # px of forgiveness either side
        return (x0 * width - slack <= x <= x1 * width + slack and
                y0 * height <= y <= y1 * height)

    def _abort(self, key):
        command = self.interactor.GetCommand(self._handle_tags[key])
        if command is not None:
            command.SetAbortFlag(1)

    def _set_cursor(self, resize):
        window = self.interactor.GetRenderWindow()
        window.SetCurrentCursor(vtk.VTK_CURSOR_SIZEWE if resize else vtk.VTK_CURSOR_DEFAULT)

    def _on_handle_move(self, caller=None, event=None):
        if self._dragging is not None:
            start_x, start_width = self._dragging
            window_width = max(1, self.interactor.GetRenderWindow().GetSize()[0])
            dx = (self.interactor.GetEventPosition()[0] - start_x) / window_width
            sign = 1.0 if self.side == "left" else -1.0
            minimum = max(self.min_width, self._tab_bar_width() + 0.06)
            width = min(self.max_width, max(minimum, start_width + sign * dx))
            if abs(width - self.width) * window_width >= 2.0:
                self.width = width
                self.layout(render=True)
            self._abort("move")
            return
        hover = self._pointer_on_handle()
        if hover != self._handle_hover:
            self._handle_hover = hover
            self._set_cursor(hover)
            self._layout_handle()
            self.interactor.GetRenderWindow().Render()

    def _on_handle_press(self, caller=None, event=None):
        if not self._pointer_on_handle():
            return
        self._dragging = (self.interactor.GetEventPosition()[0], self.width)
        self._layout_handle()
        self._abort("press")

    def _on_handle_release(self, caller=None, event=None):
        if self._dragging is None:
            return
        original_width = self._dragging[1]
        self._dragging = None
        self._handle_hover = self._pointer_on_handle()
        self._set_cursor(self._handle_hover)
        self._layout_handle()
        self.layout(render=True)
        if not math.isclose(original_width, self.width,
                            rel_tol=0.0, abs_tol=1e-12):
            self.widthChanged.emit(self.width)
        self._abort("release")

    def _position_collapse_button(self):
        window_width, window_height = self.interactor.GetRenderWindow().GetSize()
        button_width = 18.0 / max(1, window_width)
        button_height = 26.0 / max(1, window_height)
        if self.collapsed:
            x0 = 0.0 if self.side == "left" else 1.0 - button_width
        else:
            # Both panes place the control in their own top-right corner.
            # Previously the right pane used its inner (left) edge here.
            x0 = self.bounds[1] - button_width
        self.collapse_button.SetBounds(
            x0, x0 + button_width, 1.0 - button_height - self.vertical_margin,
            1.0 - self.vertical_margin)

    def add_panel(self, panel, height=None, tab=None):
        """Add a floating-compatible panel to the vertical dock stack.

        With tabs, *tab* names the tab the panel belongs to (default: the
        first tab)."""
        if tab is None and self.tabs:
            tab = self.tabs[0]['name']
        if tab is not None:
            if not any(candidate['name'] == tab for candidate in self.tabs):
                raise ValueError(f"unknown dock tab {tab!r}")
            self._panel_tab[panel] = tab
        if panel in self.panels:
            return panel
        if not all(hasattr(panel, name) for name in
                   ("GetBounds", "SetBounds", "SetVisibility")):
            getbounds = hasattr(panel, "GetBounds")
            setbounds = hasattr(panel, "SetBounds")
            setvisibility = hasattr(panel, "SetVisibility")
            widget_name = getattr(panel, "panel_title", panel.__class__.__name__)
            raise TypeError(f"Added widget '{widget_name}' must implement GetBounds, SetBounds, and SetVisibility, but got {getbounds=}, {setbounds=}, {setvisibility=}")
        bounds = panel.GetBounds()
        original_width = max(1e-9, float(bounds[1] - bounds[0]))
        available_width = max(
            1e-9, self.width - self._tab_bar_width() - 2 * self.margin)
        width_scale = available_width / original_width
        inferred = max(
            .06, float(bounds[3] - bounds[2]) * width_scale)
        self.panels.append(panel)
        self._panel_heights[panel] = inferred if height is None else float(height)
        if height is not None:
            self._explicit_heights.add(panel)
        if isinstance(panel, WidgetPanel):
            self._panel_aspect[panel] = self._panel_heights[panel] / available_width
        panel.parent_pane = self
        # A docked panel is the dock's child, so the router's hit chain,
        # theme refresh and dump_tree descend into it (a native widget in
        # a docked panel, such as a chart, then receives its events).
        if isinstance(panel, WidgetMixin):
            panel.setParent(self)
        panel.keep_aspect_ratio = False
        if hasattr(panel, "panel_background"):
            panel.panel_background.keep_aspect_ratio = False
            panel.panel_background.movable = False
            panel.panel_background.resizable = False
        self.layout()
        return panel

    def remove_panel(self, panel):
        if panel in self.panels:
            self.panels.remove(panel)
            self._panel_heights.pop(panel, None)
            self._panel_tab.pop(panel, None)
            self._explicit_heights.discard(panel)
            panel.parent_pane = None
            if isinstance(panel, WidgetMixin) and \
                    panel.parentWidget() is self:
                panel.setParent(None)
            self.layout()

    def _effective_height(self, panel):
        if (getattr(panel, "_panel_collapsed", False) or
                getattr(panel, "collapsed", False)):
            if theme_value(self.renderer, "title_color", None) is not None:
                # A pill exactly two corner radii tall.
                return collapsed_panel_height(self.interactor)
            return max(.045, self.width * .22)
        dock_height = getattr(panel, "dockHeight", None)
        height = dock_height() if callable(dock_height) else None
        if height is not None and panel not in self._explicit_heights:
            return height
        aspect = self._panel_aspect.get(panel)
        if aspect is not None:
            available = max(1e-9, self.width - self._tab_bar_width() - 2 * self.margin)
            return aspect * available
        return self._panel_heights[panel]

    def layout(self, render=False):
        """Size and position children, enabling scrolling only on overflow."""
        from .layouts import layout_pass

        # One hint cache for the whole pass: every panel's dockHeight() and
        # its content layout measure each widget once.
        with layout_pass():
            self._layout_pass(render)

    def _layout_pass(self, render):
        self._fit_window()          # cheap unless the width or panes changed
        self.bounds = self._edge_bounds()
        content = self._content_bounds()
        self._layout_tabs()
        self._layout_handle()
        if content[1] - content[0] > 1e-6:
            self.background.SetBounds(*content)
            self.scroll_box.SetBounds(*content)
        self.background.SetVisibility(
            self.enabled and not self.collapsed and not self.content_collapsed)
        self._position_collapse_button()
        window_height = max(
            1, self.interactor.GetRenderWindow().GetSize()[1])
        self.scroll_box.scrollbar_top_inset = (
            (0.0 if self.tabs else 26.0 / window_height) +
            self.vertical_margin + 4.0 / window_height)
        shown = self._tab_panels()
        for panel in self.panels:
            if panel not in shown:
                panel.SetVisibility(False)
        if self.collapsed or not self.enabled or self.content_collapsed:
            for panel in self.panels:
                panel.SetVisibility(False)
            self.slider.EnabledOff()
            # Dependants such as viewport-corner controls must update before
            # the collapse render, otherwise their new layout is not visible
            # until an unrelated resize or mouse event.
            self._notify_layout_observers()
            if render:
                self.interactor.GetRenderWindow().Render()
            return

        heights = [self._effective_height(panel) for panel in shown]
        content_height = (sum(heights) +
                          self.spacing * max(0, len(heights) - 1) +
                          2 * self.vertical_margin)
        viewport_height = 1.0
        maximum = max(0.0, content_height - viewport_height)
        self.scroll_offset = min(self.scroll_offset, maximum)
        self.scroll_box.scroll_offset = self.scroll_offset
        self.scroll_box.set_content_height(content_height, viewport_height)

        x0 = content[0] + self.margin
        x1 = content[1] - self.margin - (.008 if maximum else 0.0)
        cursor = content[3] - self.vertical_margin + self.scroll_offset
        for panel, height in zip(shown, heights):
            y1 = cursor
            y0 = y1 - height
            panel.SetBounds(x0, x1, y0, y1)
            panel.SetVisibility(y1 > self.bounds[2] and y0 < self.bounds[3])
            cursor = y0 - self.spacing
        self._notify_layout_observers()
        if render:
            self.interactor.GetRenderWindow().Render()

    def add_layout_observer(self, callback):
        """Call *callback* whenever the pane changes the visible viewport."""
        if callback not in self.layout_observers:
            self.layout_observers.append(callback)

    def _notify_layout_observers(self):
        for callback in tuple(self.layout_observers):
            callback(self)

    def _scroll_callback(self, caller, event=None):
        self._stop_scroll_animation()
        value = caller.GetRepresentation().GetValue()
        content = self.scroll_box.total_height
        self.scroll_offset = value * max(0.0, content - 1.0)
        self.layout(render=True)

    def handle_mouse_wheel(self, x, y, direction):
        """Route to a nested panel, then scroll the dock stack if necessary."""
        if not self.is_within_bounds(x, y):
            return False
        for panel in reversed(self._tab_panels()):
            handler = getattr(panel, 'handle_mouse_wheel', None)
            contains = getattr(panel, 'is_within_bounds', None)
            if (handler is not None and
                    (contains is None or contains(x, y)) and
                    handler(x, y, direction)):
                return True
        maximum = max(0.0, self.scroll_box.total_height - 1.0)
        if maximum <= 0.0:
            # With no active dock scrollbar, allow the renderer (or another
            # enclosing container) to receive the wheel event.
            return False
        step = max(0.06, 0.08 * maximum)
        # Notches that arrive while a scroll animates add to its target.
        animating = self._scroll_animation is not None and \
            self._scroll_animation.state() == "running"
        start = self._scroll_target if animating else self.scroll_offset
        new_offset = min(maximum, max(0.0, start - direction * step))
        if abs(new_offset - start) <= 1e-12:
            return not self.pass_scroll_events
        self.scrollTo(new_offset)
        return True

    # -- scrolling ------------------------------------------------------------------
    SCROLL_MS = 140

    def scrollOffset(self):
        """How far the stack is scrolled, in viewport heights."""
        return self.scroll_offset

    def setScrollOffset(self, offset, render=False):
        """Scroll to ``offset`` viewport heights now (clamped); ``render``
        renders at once instead of before the next frame."""
        maximum = max(0.0, self.scroll_box.total_height - 1.0)
        offset = min(maximum, max(0.0, float(offset)))
        if abs(offset - self.scroll_offset) <= 1e-12:
            return
        self.scroll_offset = offset
        self.scroll_box.scroll_offset = offset
        if maximum > 0:
            self.scroll_box.set_scroll_fraction(offset / maximum, 1.0)
        self.scroll_box.update_slider_geometry()
        self.layout(render=render)
        if not render:
            self.requestRender()

    def scrollTo(self, offset, animated=True):
        """Scroll to ``offset`` viewport heights, smoothly by default
        (instantly with animations off)."""
        from .animation import PropertyAnimation, animations_enabled

        maximum = max(0.0, self.scroll_box.total_height - 1.0)
        offset = min(maximum, max(0.0, float(offset)))
        self._stop_scroll_animation()
        self._scroll_target = offset
        if not animated or not animations_enabled():
            self.setScrollOffset(offset, render=True)     # as before W8
            return
        self._scroll_animation = PropertyAnimation(
            self, "scrollOffset", duration_ms=self.SCROLL_MS,
            easing="outCubic", end_value=offset, interactor=self.interactor,
            request_render=False)
        self._scroll_animation.start()

    def _stop_scroll_animation(self):
        animation = getattr(self, "_scroll_animation", None)
        if animation is not None:
            animation.stop()
        self._scroll_animation = None

    def toggle(self, caller, event=None):
        self._auto_collapsed = False             # the user decided
        self.collapsed = bool(caller.GetRepresentation().GetState())
        self.background.SetVisibility(not self.collapsed)
        self.layout(render=True)

    def _on_window_resize(self, caller=None, event=None):
        self.scroll_box.update_slider_geometry()
        self._position_collapse_button()
        self._fit_window()
        self.layout()

    def SetEnabled(self, enabled):
        self.enabled = bool(enabled)
        self.background.SetVisibility(self.enabled and not self.collapsed)
        self.collapse_button.SetEnabled(self.enabled and not self.tabs)
        if self.tab_bar is not None:
            self.tab_bar.SetVisibility(self.enabled)
            for tab in self.tabs:
                tab["button"].SetEnabled(self.enabled)
        self.layout()

    def GetEnabled(self):
        return int(self.enabled)

    def GetBounds(self):
        return self.bounds

    def raise_controls(self):
        """Re-add overlay controls after dock children to keep them clickable."""
        controls = [self.collapse_button, getattr(self, "resize_handle", None)]
        controls += [tab["button"] for tab in self.tabs]
        for control in controls:
            actor = getattr(control, "actor", None)
            if actor is not None:
                ui_layer(self.renderer).RemoveActor(actor)
                ui_layer(self.renderer).AddActor(actor)

    def is_within_bounds(self, x, y):
        if self.collapsed or not self.enabled:
            return False
        return (self.bounds[0] <= x <= self.bounds[1] and
                self.bounds[2] <= y <= self.bounds[3])

    def saveState(self):
        state = super().saveState()
        state.update({
            'side': self.side,
            'width': self.width,
            'widthSpec': self._width_spec.to_json(),
            'activeTab': self.active_tab,
            'collapsed': self.collapsed,
            'contentCollapsed': self.content_collapsed,
            'scrollOffset': self.scroll_offset,
            'panels': {
                panel.objectName(): panel.saveState()
                for panel in self.panels
                if isinstance(panel, WidgetMixin)
            },
        })
        return state

    def restoreState(self, state):
        if not isinstance(state, dict):
            raise TypeError('dock state must be a dictionary')
        with self.signalBlocker():
            if 'side' in state:
                self.setDockLocation(state['side'])
            if 'widthSpec' in state:
                from .units import Length

                self._width_spec = Length.from_json(state['widthSpec'])
            elif 'width' in state:
                self.width = min(
                    self.max_width, max(self.min_width, float(state['width'])))
            self.collapsed = bool(state.get('collapsed', self.collapsed))
            self.content_collapsed = bool(
                state.get('contentCollapsed', self.content_collapsed))
            active_tab = state.get('activeTab')
            if active_tab is None or any(
                    tab['name'] == active_tab for tab in self.tabs):
                self.active_tab = active_tab
            self._stop_scroll_animation()
            self.scroll_offset = max(
                0.0, float(state.get('scrollOffset', self.scroll_offset)))
            panel_states = state.get('panels', {})
            for panel in self.panels:
                if (isinstance(panel, WidgetMixin) and
                        panel.objectName() in panel_states):
                    panel.restoreState(panel_states[panel.objectName()])
            common = {key: state[key] for key in (
                'objectName', 'enabled', 'visible', 'toolTip', 'statusTip')
                if key in state}
            super().restoreState(common)
        self._sync_tabs()
        self.layout(render=False)
        return True

    def Delete(self):
        self.observerRegistry().clear()
        for panel in list(self.panels):
            if hasattr(panel, 'close'):
                panel.close()
        self.panels.clear()
        for widget in (self.collapse_button, self.resize_handle,
                       self.tab_bar, self.scroll_box, self.background):
            if widget is not None and hasattr(widget, 'close'):
                widget.close()
            elif widget is not None and hasattr(widget, 'Delete'):
                widget.Delete()


class PanelBackgroundWidget(vtk.vtkBorderWidget, WidgetMixin):
    """The native (``vtkBorderWidget``) panel background; the composite one
    is :class:`multipanel.composite.PanelBackgroundWidget`."""

    @property
    def native(self):
        """This widget (``None`` on composites)."""
        return self

    def __init__(self,
                renderer,
                interactor,
                panel_bounds,
                buffer=0.01,
                panel_color=(1.0, 1.0, 1.0),
                highlight_color=(0.8, 0.8, 1),
                border_color=(0, 0, 0),
                opacity=0.9,
                name="background_rectangle",
                radius=0.1,
                border_width=4,
                grabbable=False,
                place_factor=0.01,
                callback=None,
                ui_z_order=UI_Z_PANEL_BACKGROUND,
            ):
        """Initialize the instance."""
        super().__init__()
        self.initWidget(name)
        self.highlightedChanged = Signal(self)
        self.renderer = renderer
        self.interactor = interactor

        """Adds a panel background to a VTK renderer using a border widget to
        allow for UI elements to move together.

        Parameters
        ----------
        renderer : vtkRenderer
            The VTK renderer to which the panel background will be added.
        interactor : vtkRenderWindowInteractor
            The interactor associated with the renderer.
        panel_bounds : list or array-like
            The bounds of the panel in the format [xmin, xmax, ymin, ymax].
        buffer : float, optional
            The buffer to add around the panel bounds. Default is 0.01.
        panel_color : tuple, optional
            RGB color of the panel background as a tuple of floats (0 to 1).
            Default is (1, 1, 1).
        border_color : tuple, optional
            RGB color of the panel border as a tuple of floats (0 to 1).
            Default is (0, 0, 0).
        opacity : float, optional
            Opacity of the panel background (0 to 1). Default is 0.9.
        name : str, optional
            Name to identify the background widget. Default is 'background_rectangle'.
        radius : float, optional
            Corner radius strength for rounded corners. Default is 0.1.
        border_width : int, optional
            Thickness of the panel border. Default is 4.

        Notes
        -----
        - The function modifies the `renderer` object by adding a `widgets`
        attribute if it does not already exist.
        - The `widgets` attribute is a dictionary that stores the created border
        widget with the specified `name`.
        - The `buffer` value is also stored as an attribute of the returned border
        widget.
        """

        panel_bounds = np.asarray(panel_bounds)
        panel_bounds[0] = panel_bounds[0] - buffer
        panel_bounds[1] = panel_bounds[1] + buffer
        panel_bounds[2] = panel_bounds[2] - buffer
        panel_bounds[3] = panel_bounds[3] + buffer

        # Calculate position based on bounds
        width = panel_bounds[1] - panel_bounds[0]
        height = panel_bounds[3] - panel_bounds[2]

        self.width = width
        self.height = height
        self.buffer = buffer
        self.panel_bounds = panel_bounds
        self.radius = radius
        self.panel_color = panel_color
        self.border_color = border_color
        self.opacity = opacity
        self.border_width = border_width
        self.panel_size = [width, height]
        self.highlight_color = highlight_color
        self._panel_theme_role = (
            theme_role_for_color(
                renderer, panel_color, 'panel_background_color', 'pane_color')
            or ('panel_background_color'
                if tuple(panel_color[:3]) == (1.0, 1.0, 1.0) else None))
        self._border_theme_role = (
            theme_role_for_color(renderer, border_color, 'border_color')
            or ('border_color'
                if tuple(border_color[:3]) == (0.0, 0.0, 0.0) else None))
        self._highlight_theme_role = theme_role_for_color(
            renderer, highlight_color, 'accent_faint', 'accent_soft')
        self.grabbable = grabbable
        self.highlighted = False
        self.callback = callback
        self.ui_z_order = int(ui_z_order)

        self.rep = self.make_representation()

        self.SetInteractor(interactor)
        # Explicit renderer: On() would otherwise pick the poked (scene) one.
        self.SetDefaultRenderer(ui_layer(renderer))
        self.SetCurrentRenderer(ui_layer(renderer))
        self.SetRepresentation(self.rep)




        if not grabbable:
            self.SetSelectable(False)
            self.SetProcessEvents(False)
        else:
            self.SetSelectable(True)
            self.SetProcessEvents(True)


        if self.callback is not None:
            self.ownObserver(self, "InteractionEvent", self.callback)
            if grabbable:
                self.SetSelectable(False)
                self.SetProcessEvents(True)



        self.rep.SetPlaceFactor(place_factor)

        self.SetPriority(place_factor)
        if not hasattr(renderer, "widgets"):
            renderer.widgets = {}
        renderer.widgets.update({name: self})

        self.On()
        register_ui_drawable(renderer, self, self.ui_z_order, name)

    def make_representation(self):
        """Creates a vtkBorderRepresentation for the panel background."""
        rep = vtk.vtkBorderRepresentation()

        rep.SetPlaceFactor(1)
        rep.SetPosition(self.panel_bounds[0], self.panel_bounds[2])
        rep.SetPosition2(self.width, self.height)
        rep.SetCornerRadiusStrength(self.radius)
        rep.SetCornerResolution(4)
        new_panel_color = colormap_utils.color_to_RGB(self.panel_color)
        rep.SetPolygonColor(new_panel_color)
        rep.SetPolygonOpacity(self.opacity)

        rep.SetBorderColor(colormap_utils.color_to_RGB(self.border_color))
        rep.SetBorderThickness(self.border_width)

        if self.highlighted:
            rep.SetPolygonColor(self.highlight_color[0],
                               self.highlight_color[1],
                               self.highlight_color[2])
            rep.SetPolygonOpacity(1.0)

        return rep

    def SetPanelBounds(self, xmin, xmax, ymin, ymax):
        """Execute the set panel bounds operation."""
        self.panel_bounds = (xmin, xmax, ymin, ymax)
        self.make_representation()

        self.Modified()

    def SetPosition(self, x, y):
        """Execute the set position operation."""
        self.panel_bounds[0] = x
        self.panel_bounds[2] = y

        self.rep.SetPosition(x, y)


        self.Modified()

    def SetVisibility(self, visible):

        """Execute the set visibility operation."""
        if visible:
            self.On()
            if self.highlighted:
                self.rep.SetPolygonColor(self.highlight_color[0],
                                        self.highlight_color[1],
                                        self.highlight_color[2])
                self.rep.SetPolygonOpacity(1.0)
            else:
                self.rep.SetPolygonColor(colormap_utils.color_to_RGB(self.panel_color))
                self.rep.SetPolygonOpacity(self.opacity)

        else:
            self.Off()
        self.Modified()

    def SetSize(self, width, height):


        """Execute the set size operation."""
        self.panel_bounds[1] = self.panel_bounds[0] + width
        self.panel_bounds[3] = self.panel_bounds[2] + height
        self.width = width
        self.height = height
        self.rep.SetPosition2(width, height)

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
        self.rep.SetBorderColor(
            colormap_utils.color_to_RGB(self.border_color))
        color = self.highlight_color if self.highlighted else self.panel_color
        self.rep.SetPolygonColor(colormap_utils.color_to_RGB(color))
        self.rep.Modified()

    def Delete(self):
        """Execute the delete operation."""
        self.observerRegistry().clear()
        self.Off()
        # deletes itself from the renderer widgets
        del self

    def Highlight(self, highlight_on):
        old = self.highlighted
        """Execute the highlight operation."""
        if highlight_on:
            # self.rep.SetBorderColor(colormap_utils.color_to_RGB((1, 0, 0)))
            self.rep.SetPolygonColor(self.highlight_color[0],
                                    self.highlight_color[1],
                                    self.highlight_color[2])
            self.rep.SetPolygonOpacity(1.0)
            self.highlighted = True
        else:
            self.highlighted = False
            # self.rep.SetBorderColor(colormap_utils.color_to_RGB(self.border_color))
            self.rep.SetPolygonColor(colormap_utils.color_to_RGB(self.panel_color))
            self.rep.SetPolygonOpacity(self.opacity)

        self.Modified()
        if old != self.highlighted:
            self.highlightedChanged.emit(self.highlighted)








class ViewportDisplayPanel(WidgetMixin):
    """Top-right viewport controls positioned inside the visible scene area."""

    MODES = ('wireframe', 'material', 'textured')
    TEXTURE_NAMES = (
        'albedoTex', 'baseColorTex', 'normalTex', 'materialTex',
        'emissiveTex', 'ormTex', 'coatNormalTex')

    @ui_scoped
    def __init__(self, renderer, interactor, left_pane=None, right_pane=None,
                 panel_color=(0.12, 0.12, 0.14), text_color=(1, 1, 1),
                 initial_mode='textured', panel_title='Viewport Display',
                 corner_radius=0.05, opacity=0.0, panel_height=0.12, panel_width=0.24,
                 panel_buffer=8, show_projection_button=True):
        self.renderer = renderer
        self.interactor = interactor
        self.initWidget('viewport_display_panel')
        self.modeChanged = Signal(self)
        # Emitted with True (parallel) or False (perspective).
        self.projectionChanged = Signal(self)
        self.projection_listeners = []
        self.left_pane = left_pane
        self.right_pane = right_pane
        self.panel_color = panel_color
        self.text_color = text_color
        self.mode = initial_mode
        self.panel_height = panel_height
        self.panel_width = panel_width
        self.panel_buffer = panel_buffer
        self.bounds = (0.99 - self.panel_width, 0.99, 0.99 - self.panel_height, 0.99)
        self._actor_appearance = {}
        self.corner_radius = corner_radius
        self.opacity = opacity
        # Callables invoked with the new mode after every set_mode (used by
        # the Qt menu bar to mirror the in-scene buttons).
        self.mode_listeners = []
        self.controls_visible = True

        self.background = VectorPanelBackground(
            renderer, interactor, bounds=self.bounds,
            panel_color=panel_color, opacity=opacity, movable=False,
            resizable=False, corner_radius=corner_radius,
            name='viewport_display_panel')
        self.panel_title = panel_title
        # Imported lazily to keep the container module independent of the
        # specialist module during package initialisation.
        from .specialists import CameraOrientationWidget

        self.camera_widget = CameraOrientationWidget(
            renderer, interactor, position=(1-self.panel_height, 1-self.panel_height), size=(self.panel_height, self.panel_height))
        self.camera_widget.managed_by_viewport_panel = True
        icon_for_mode = {
            'wireframe': 'wireframe_blue',
            'material': 'shaded',
            'textured': 'textured',
        }
        self.buttons = {}
        for mode in self.MODES:
            icon_path = os.path.join(ICON_ROOT, 'vtk_icons', f'{icon_for_mode[mode]}.vtk')
            button = VectorButtonWidget(
                renderer, interactor, input_data=[icon_path, icon_path],
                color=None, grayscale_states=[True, False],
                grayscale_brightness=.12,
                initial_state=int(mode == initial_mode),
                callback=lambda caller, event, value=mode:
                    self.request_mode(value),
                bounds=(0, self.panel_height, 0, self.panel_height),
                grabbable=False, name=f'viewport_{mode}',
                hover_text=f'{mode.title()} viewport shading')
            button.equal_aspect_ratio = True
            self.buttons[mode] = button
        # Perspective / parallel ("orthographic") projection: the icon shows
        # the current projection; a click switches to the other one.
        self.projection_button = None
        camera = renderer.GetActiveCamera()
        self._parallel = bool(camera.GetParallelProjection())
        if show_projection_button:
            icons = [os.path.join(ICON_ROOT, 'vtk_icons', f'{name}.vtk')
                     for name in ('perspective', 'orthographic')]
            self.projection_button = VectorButtonWidget(
                renderer, interactor, input_data=icons, color=None,
                grayscale_states=[False, False],
                initial_state=int(self._parallel),
                callback=lambda caller, event: self.request_projection(
                    not self._parallel),
                bounds=(0, self.panel_height, 0, self.panel_height),
                grabbable=False, name='viewport_projection',
                hover_text=self._projection_hover_text())
            self.projection_button.equal_aspect_ratio = True
            # Follow projection changes made elsewhere (menus, scripts).
            self.ownObserver(renderer, 'StartEvent',
                             self._follow_camera_projection)
        for pane in (left_pane, right_pane):
            if pane is not None:
                pane.add_layout_observer(self._pane_layout_changed)
        self.ownObserver(interactor.GetRenderWindow(),
                         'WindowResizeEvent', self._window_resized)
        # Qt/VTK commonly reports interactive resizes as ConfigureEvent on the
        # interactor rather than WindowResizeEvent on the render window.
        self.ownObserver(interactor, 'ConfigureEvent', self._window_resized)
        self.layout()
        # Material-list construction may have styled actors before this
        # controller existed. Establish the requested representation as soon
        # as the controller is attached.
        self.set_mode(initial_mode, render=False)

    def _pane_layout_changed(self, pane=None):
        self.layout()

    def _restore_camera_viewport(self, caller=None, event=None):
        viewport = getattr(self, "_camera_viewport", None)
        if viewport is not None and caller is not None and \
                tuple(caller.GetViewport()) != tuple(viewport):
            caller.SetViewport(*viewport)

    def _window_resized(self, caller=None, event=None):
        self.layout()

    def _visible_horizontal_bounds(self):
        x0, x1 = 0.0, 1.0
        if (self.left_pane is not None and self.left_pane.enabled and
                not self.left_pane.collapsed):
            x0 = self.left_pane.GetBounds()[1]
        if (self.right_pane is not None and self.right_pane.enabled and
                not self.right_pane.collapsed):
            x1 = self.right_pane.GetBounds()[0]
        return x0, x1

    def layout(self):
        """Anchor the controls to the unobscured render viewport."""
        window_width, window_height = self.interactor.GetRenderWindow().GetSize()
        window_width, window_height = max(window_width, 1), max(window_height, 1)
        visible_x0, visible_x1 = self._visible_horizontal_bounds()

        # Logical px: the size preference times the display density.
        scale = ui_scale()
        buffer = self.panel_buffer * scale
        margin_x, margin_y = buffer / window_width, buffer / window_height

        button_size = 64 * scale

        slots = self._button_count() + 2         # buttons, then the camera
        panel_width = ((button_size * slots) + (4 * buffer)) / window_width
        available = (visible_x1 - visible_x0) - 2 * margin_x
        if panel_width > available > 0:
            # A narrow scene: shrink the buttons (and camera) to fit it
            # rather than spill over the docks.
            fit = max(0.25, (available * window_width - 4 * buffer)
                      / (button_size * slots))
            button_size *= min(1.0, fit)
            panel_width = ((button_size * slots) + (4 * buffer)) / window_width
        panel_height = ((button_size * 1.2) + (2 * buffer) )/ window_height
        x1 = visible_x1 -  margin_x
        x0 = max(visible_x0 + margin_x, x1 - panel_width)
        y1 = 1.0 - margin_y
        y0 = y1 - panel_height
        self.bounds = (x0, x1, y0, y1)
        self.background.SetBounds(*self.bounds)

        aspect_ratio = window_width / window_height

        base_height = panel_height - ((2 * buffer) / window_height)

        # Square buttons: the panel's inner height, as a width fraction.
        # (Portrait windows used to shrink them by the aspect ratio.)
        button_height = base_height
        button_width = base_height / aspect_ratio

        button_gap = 6 * scale / window_width
        bx = x0 + margin_x
        by = y1 - margin_y - button_height
        for button in self._row_buttons():
            button.SetBounds(bx, bx + button_width, by, by + button_height)
            bx += button_width + button_gap

        inner_height_pixels = panel_height * window_height - (2 * buffer)
        # The buttons occupy the left side of the panel. As the unobscured
        # viewport narrows, constrain the camera control to the actual space
        # remaining instead of allowing its old fixed size to overlap them.
        camera_left = bx + margin_x
        inner_width_pixels = max(0, (x1 - margin_x - camera_left) * window_width)
        # VTK's SetSize takes ints (a float raised TypeError in narrow
        # windows, once the padding scaled with the display).
        camera_pixels = int(max(2 * buffer, min(inner_height_pixels, inner_width_pixels)))
        camera_representation = self.camera_widget.GetRepresentation()
        camera_representation.AnchorToUpperRight()
        camera_padding = max(1, int(round(4 * scale)))
        camera_representation.SetPadding(camera_padding, camera_padding)
        camera_representation.SetSize(camera_pixels, camera_pixels)
        # vtkCameraOrientationWidget owns a non-interactive overlay renderer.
        # Its viewport, rather than representation padding, determines the
        # widget's screen corner in VTK 9.3. Resize that existing renderer to
        # the camera portion of this panel; do not create another renderer or
        # alter the scene renderer's viewport/camera.
        camera_renderer = self.camera_widget.GetCurrentRenderer()
        camera_region_pixels = camera_pixels + 2 * camera_padding
        camera_x1 = visible_x1 - (2 * margin_x)
        camera_y1 = 1.0 - margin_y
        camera_x0 = max(
            visible_x0, camera_x1 - camera_region_pixels / window_width)
        camera_y0 = max(
            0.0, camera_y1 - camera_region_pixels / window_height)
        self._camera_viewport = (camera_x0, camera_y0, camera_x1, camera_y1)
        camera_renderer.SetViewport(*self._camera_viewport)
        if getattr(self, "_camera_render_tag", None) is None:
            # vtkCameraOrientationWidget moves its renderer back to the
            # window's corner when it renders (over the right pane): put it
            # back where the layout placed it, after VTK has done so.
            self._camera_render_tag = camera_renderer.AddObserver(
                "StartEvent", self._restore_camera_viewport, -100.0)
        camera_renderer.Modified()
        camera_representation.Modified()
        camera_representation.BuildRepresentation()
        self.camera_widget.Modified()
        self.background.Modified()

    def _row_buttons(self):
        buttons = [self.buttons[mode] for mode in self.MODES]
        if self.projection_button is not None:
            buttons.append(self.projection_button)
        return buttons

    def _button_count(self):
        return len(self._row_buttons())

    # -- camera projection ---------------------------------------------------------------
    def _projection_hover_text(self):
        if self._parallel:
            return 'Orthographic (parallel) projection: click for perspective'
        return 'Perspective projection: click for orthographic'

    def _sync_projection_button(self):
        button = self.projection_button
        if button is None:
            return
        button.GetRepresentation().SetState(int(self._parallel))
        button.hover_text = self._projection_hover_text()

    def _follow_camera_projection(self, caller=None, event=None):
        parallel = bool(self.renderer.GetActiveCamera().GetParallelProjection())
        if parallel != self._parallel:
            self._parallel = parallel
            self._sync_projection_button()
            self._notify_projection()

    def _notify_projection(self):
        for listener in list(self.projection_listeners):
            listener(self._parallel)
        self.projectionChanged.emit(self._parallel)

    def isParallelProjection(self):
        return self._parallel

    def request_projection(self, parallel):
        """Button-requested projection change, without a nested render."""
        self.set_projection(parallel, render=False)
        self.interactor.GetRenderWindow().Modified()

    def set_projection(self, parallel, render=True):
        """Switch the scene camera between perspective and parallel
        projection, keeping what is at the focal point the same size on
        screen (the parallel scale matches the perspective view's height
        at the focal distance, and back)."""
        parallel = bool(parallel)
        camera = self.renderer.GetActiveCamera()
        changed = parallel != bool(camera.GetParallelProjection())
        if changed:
            half_angle = math.radians(camera.GetViewAngle()) / 2.0
            tangent = max(math.tan(half_angle), 1e-6)
            if parallel:
                camera.SetParallelScale(camera.GetDistance() * tangent)
            else:
                distance = max(camera.GetParallelScale() / tangent, 1e-6)
                focal = camera.GetFocalPoint()
                direction = camera.GetDirectionOfProjection()
                camera.SetPosition(*(f - d * distance
                                     for f, d in zip(focal, direction)))
            camera.SetParallelProjection(parallel)
            self.renderer.ResetCameraClippingRange()
        previous = self._parallel
        self._parallel = parallel
        self._sync_projection_button()
        if changed or previous != parallel:
            self._notify_projection()
        if render:
            self.interactor.GetRenderWindow().Render()

    def toggle_projection(self, render=True):
        self.set_projection(not self._parallel, render=render)

    def _leaf_actors(self):
        """Yield scene geometry, excluding 2D UI and helper actors."""
        actors = self.renderer.GetActors()
        actors.InitTraversal()
        seen = set()
        for _ in range(actors.GetNumberOfItems()):
            actor = actors.GetNextActor()
            if actor is None:
                continue
            identity = actor.GetAddressAsString('vtkProp')
            if identity in seen:
                continue
            seen.add(identity)
            if is_scene_actor(actor):    # see set_scene_actor_predicate
                yield actor

    def _remember_appearance(self, actor):
        identity = actor.GetAddressAsString('vtkProp')
        if identity not in self._actor_appearance:
            # Keep the importer's live property and every texture binding
            # intact. vtkGLTFImporter owns rendering resources associated with
            # this object, so replacing it or removing its textures is unsafe.
            original_property = actor.GetProperty()
            imported = getattr(actor, '_imported_textured_appearance', None)
            if not hasattr(actor, 'textured_color'):
                actor.textured_color = tuple(
                    imported['color'] if imported is not None
                    else original_property.GetColor())
            self._actor_appearance[identity] = {
                'property': original_property,
                'representation': (
                    imported['representation'] if imported is not None
                    else original_property.GetRepresentation()),
                'interpolation': (
                    imported['interpolation'] if imported is not None
                    else original_property.GetInterpolation()),
                'color': (imported['color'] if imported is not None
                          else original_property.GetColor()),
                'scalar_visibility': (
                    imported['scalar_visibility'] if imported is not None
                    else actor.GetMapper().GetScalarVisibility()),
            }
            if imported is not None:
                self._actor_appearance[identity].update(imported)
        return self._actor_appearance[identity]

    @staticmethod
    def _restore_appearance(actor, appearance):
        prop = appearance['property']
        prop.SetRepresentation(appearance['representation'])
        prop.SetInterpolation(appearance['interpolation'])
        color = tuple(getattr(actor, 'textured_color', appearance['color']))
        prop.SetColor(*color)
        prop.SetEdgeColor(*(component * 0.5 for component in color))
        for name, setter in (
                ('opacity', 'SetOpacity'),
                ('ambient', 'SetAmbient'),
                ('diffuse', 'SetDiffuse'),
                ('specular', 'SetSpecular'),
                ('specular_power', 'SetSpecularPower'),
                ('metallic', 'SetMetallic'),
                ('roughness', 'SetRoughness'),
                ('occlusion_strength', 'SetOcclusionStrength')):
            if name in appearance:
                method = getattr(prop, setter, None)
                if method is not None:
                    method(appearance[name])
        actor.GetMapper().SetScalarVisibility(
            appearance['scalar_visibility'])

    def _material_color(self, actor):
        material = actor_material(actor)    # see set_actor_material_resolver
        if not material:
            return actor.GetProperty().GetColor()
        # Allocate on first use so material mode colours every material,
        # including those that arrived with imported geometry.
        resolver = material_color_resolver()
        if resolver is None:
            return actor.GetProperty().GetColor()
        return resolver(self.renderer, material)

    def request_mode(self, mode):
        """Apply a button-requested mode immediately without a nested render."""
        if mode not in self.MODES:
            raise ValueError(f'Unknown viewport display mode: {mode}')
        self.set_mode(mode, render=False)
        # The active interaction will schedule its normal render. Marking the
        # window avoids a re-entrant Render() from inside the click callback.
        self.interactor.GetRenderWindow().Modified()

    def set_mode(self, mode, render=True):
        """Apply a Blender-style viewport representation to scene actors."""
        if mode not in self.MODES:
            raise ValueError(f'Unknown viewport display mode: {mode}')
        previous = self.mode
        self.mode = mode
        for name, button in self.buttons.items():
            button.GetRepresentation().SetState(int(name == mode))
        for actor in self._leaf_actors():
            appearance = self._remember_appearance(actor)
            prop = appearance['property']
            if mode == 'wireframe':
                prop.SetRepresentationToWireframe()
                prop.SetColor(*self._material_color(actor))
            elif mode == 'material':
                prop.SetRepresentationToSurface()
                # PBR is the path through which vtkGLTFImporter samples its
                # albedo/ORM maps. Phong presents the assigned uniform material
                # colour without deleting those maps, allowing a safe restore.
                prop.SetInterpolationToPhong()
                prop.SetColor(*self._material_color(actor))
            else:
                self._restore_appearance(actor, appearance)
            actor.Modified()
        for listener in list(self.mode_listeners):
            listener(mode)
        if previous != mode:
            self.modeChanged.emit(mode)
        if render:
            self.interactor.GetRenderWindow().Render()

    def set_controls_visible(self, visible, render=True):
        """Show or hide the in-scene shading buttons and orientation widget.

        The display mode itself keeps applying; only the overlay controls are
        hidden, and hidden controls no longer capture clicks.
        """
        visible = bool(visible)
        self.controls_visible = visible
        for button in self._row_buttons():
            button.SetVisibility(visible)
        self.background.SetVisibility(visible)
        self.camera_widget.SetEnabled(int(visible))
        if visible:
            self.layout()
        if render:
            self.interactor.GetRenderWindow().Render()

    def modeValue(self):
        return self.mode

    def setMode(self, mode):
        self.set_mode(mode)

    def availableModes(self):
        return self.MODES

    def controlsVisible(self):
        return self.controls_visible

    def setControlsVisible(self, visible):
        self.set_controls_visible(visible)

    def saveState(self):
        state = super().saveState()
        state.update({
            'mode': self.modeValue(),
            'controlsVisible': self.controlsVisible(),
            'parallelProjection': self.isParallelProjection(),
        })
        return state

    def restoreState(self, state):
        if 'mode' in state:
            self.set_mode(state['mode'], render=False)
        if 'parallelProjection' in state:
            self.set_projection(state['parallelProjection'], render=False)
        if 'controlsVisible' in state:
            self.set_controls_visible(
                state['controlsVisible'], render=False)
        return super().restoreState({
            key: state[key] for key in (
                'objectName', 'enabled', 'visible', 'toolTip', 'statusTip')
            if key in state})

    def Delete(self):
        self.observerRegistry().clear()
        for button in self._row_buttons():
            button.close()
        self.camera_widget.close()
        self.background.close()

    def GetBounds(self):
        return self.bounds

    def is_within_bounds(self, x, y):
        if not self.controls_visible:
            return False
        return (self.bounds[0] <= x <= self.bounds[1] and
                self.bounds[2] <= y <= self.bounds[3])



class Frame(WidgetMixin):
    """A plain container widget: geometry, children and an optional layout.

    The equivalent of a bare ``QWidget``/``QFrame``. Give it geometry with
    ``setGeometry`` (``px``/``frac`` lengths accepted) and children with
    ``setLayout``. ``background=True`` draws a rounded panel behind the
    children. Hiding the frame hides its children; showing it restores the
    children that were visible before.
    """

    def __init__(self, renderer, interactor, geometry=None, background=False,
                 panel_color=None, opacity=1.0, object_name="frame",
                 parent=None, ui_z_order=10):
        self.renderer = renderer
        self.interactor = interactor
        self.ui_z_order = int(ui_z_order)
        self._bounds = (0.0, 0.0, 0.0, 0.0)
        self._shown = True
        self.parent_pane = None
        self.initWidget(object_name, parent)
        self._background = None
        if background:
            tokens = getattr(getattr(renderer, "theme", None), "tokens", None)
            if panel_color is not None:
                color = panel_color
            elif tokens:
                color = tokens["panel"]
            else:
                color = theme_value(renderer, "panel_color", (0.95, 0.95, 0.95))
            border = tokens["border"] if tokens else None
            self._background = VectorPanelBackground(
                renderer, interactor, bounds=(0.0, 0.01, 0.0, 0.01),
                panel_color=color, border_color=border, opacity=opacity,
                movable=False, resizable=False, ui_z_order=ui_z_order,
                name=f"{object_name}/background")
        if geometry is not None:
            self.setGeometry(*geometry)

    def GetBounds(self):
        return self._bounds

    def SetBounds(self, x0, x1, y0, y1):
        bounds = (float(x0), float(x1), float(y0), float(y1))
        changed = bounds != self._bounds
        self._bounds = bounds
        if self._background is not None and x1 > x0 and y1 > y0:
            self._background.SetBounds(*self._bounds)
        layout = self.contentLayout()
        if changed and layout is not None and not layout._applying:
            # Containers such as DockPane place panels with SetBounds, which
            # emits no geometryChanged; lay the content out right away.
            layout._applying = True
            try:
                layout.setGeometry(self.contentsRect())
            finally:
                layout._applying = False
        self.requestRender()

    def dockHeight(self):
        """Height (window fraction) a DockPane should give this frame."""
        if self.contentLayout() is None:
            return None
        height = max(1, self.interactor.GetRenderWindow().GetSize()[1])
        return self.sizeHint()[1] * ui_scale() / height

    def layoutRequestEvent(self, layout):
        if self.parent_pane is not None:
            self.parent_pane.layout()
        rect = self.contentsRect()
        if rect is not None:
            layout.setGeometry(rect)
        self._sync_child_visibility()
        self.requestRender()

    def GetVisibility(self):
        return self._shown

    def SetVisibility(self, visible):
        visible = bool(visible)
        if visible == self._shown:
            return
        self._shown = visible
        if self._background is not None:
            self._background.SetVisibility(visible)
        self._sync_child_visibility()
        self.requestRender()

    def _sync_child_visibility(self):
        """Children are drawn only while the frame is shown.

        Only the children's actors are switched; their own show()/hide()
        state (and so their layout size) is left alone, as for WidgetPanel.
        """
        layout = self.contentLayout()
        if layout is not None:
            for item in layout.widgetItems():
                _set_shown_raw(item.widget,
                               self._shown and not item.effectivelyHidden())
            return
        for child in self.children():
            _set_shown_raw(child, self._shown and not child.isHidden())

    def sizeHint(self):
        layout = self.contentLayout()
        if layout is None:
            return super().sizeHint()
        left, top, right, bottom = self.contentsMargins()
        width, height = layout.sizeHint()
        return (width + left + right, height + top + bottom)

    def minimumSizeHint(self):
        layout = self.contentLayout()
        if layout is None:
            return (0.0, 0.0)
        left, top, right, bottom = self.contentsMargins()
        width, height = layout.minimumSize()
        return (width + left + right, height + top + bottom)

    def adjustSize(self):
        """Resize to the size hint, keeping the top-left corner fixed."""
        from .units import px

        geometry = self.geometry("px")
        width, height = self.sizeHint()
        if geometry is None:
            self.setGeometry(px(0), px(0), px(width), px(height))
            return
        x, y, _old_width, old_height = geometry
        self.setGeometry(px(x), px(y + old_height - height), px(width),
                         px(height))

    def close(self):
        background, self._background = self._background, None
        if background is not None:
            background.SetVisibility(False)
            closer = getattr(background, "close", None)
            if callable(closer):
                closer()
        return super().close()

__all__ = [
    "Frame",
    "DockPane",
    "PanelBackgroundWidget",
    "ScrollBox",
    "ScrollableElement",
    "ScrollablePanel",
    "ScrollableTextPanel",
    "ViewportDisplayPanel",
    "WidgetPanel",
]
