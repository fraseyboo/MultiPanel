"""Shared implementation support for MultiPanel widgets.

This is an internal module. Public applications should import from controls,
containers, specialists, or the compatibility widgets namespace.
"""

import math
import logging

# noinspection PyUnresolvedReferences
# noinspection PyUnresolvedReferences
from functools import partial
# from panel import widget
from vtkmodules.vtkCommonCore import vtkMath
from vtkmodules.vtkRenderingAnnotation import vtkAnnotatedCubeActor

# from GUI.icon_converter import read_vtk_icon_file

try:
    from vtkmodules.vtkInteractionWidgets import (
        vtkCompassRepresentation,
        vtkCompassWidget,
    )
except ImportError:
    from vtkmodules.vtkGeovisCore import vtkCompassRepresentation, vtkCompassWidget

import os
import colorsys
import time
import numpy as np
import vtk
from vtkmodules.util.numpy_support import numpy_to_vtk, vtk_to_numpy
from .render_profiler import profiled_paint
from .core import SizePolicy, Signal, WidgetMixin
from vtk.util import numpy_support

import contextlib
import functools
import warnings

import uuid

logger = logging.getLogger(__name__)

from .optional import import_optional
from .resources import FONT_ROOT, ICON_ROOT, PACKAGE_ROOT

MODULE_ROOT = str(PACKAGE_ROOT)
_material_color_resolver = None


def set_material_color_resolver(resolver):
    """Register ``resolver(renderer, material_name)`` for host material colours."""
    global _material_color_resolver
    _material_color_resolver = resolver


def material_color_resolver():
    """Return the host material-colour callback, if one is registered."""
    return _material_color_resolver


def _default_scene_actor(actor):
    """Scene geometry: a mapped, pickable actor that is not UI and counts
    towards the scene bounds."""
    return (actor.GetMapper() is not None and
            not getattr(actor, 'IsUI', False) and
            bool(actor.GetUseBounds()) and bool(actor.GetPickable()))


def _default_actor_material(actor):
    return getattr(actor, 'material', None)


_scene_actor_predicate = _default_scene_actor
_actor_material_resolver = _default_actor_material


def set_scene_actor_predicate(predicate=None):
    """Register ``predicate(actor) -> bool``: which actors are scene
    geometry (restyled by the viewport display modes). ``None`` restores
    the default (mapped, pickable, non-UI actors that count for bounds)."""
    global _scene_actor_predicate
    _scene_actor_predicate = predicate or _default_scene_actor


def is_scene_actor(actor):
    return bool(_scene_actor_predicate(actor))


def set_actor_material_resolver(resolver=None):
    """Register ``resolver(actor) -> material name or None`` (used with the
    material-colour resolver by the "material" display mode). ``None``
    restores the default, the actor's ``material`` attribute."""
    global _actor_material_resolver
    _actor_material_resolver = resolver or _default_actor_material


def actor_material(actor):
    return _actor_material_resolver(actor)

from . import colormap_utils
from .hierarchy import HierarchyNode
from .vtk_compat import add_actor_2d, remove_actor_2d


def ui_layer(renderer):
    """The renderer that draws the 2D UI for *renderer*: its full-window
    ``ui_overlay`` when it has one (see GUI.UI.install_ui_overlay), else the
    renderer itself. Scene queries keep using the scene renderer."""
    overlay = getattr(renderer, "ui_overlay", None)
    return renderer if overlay is None else overlay


def _icon_converter():
    return import_optional(
        ".icon_converter", package=__package__, extra="icons",
        purpose="converting SVG or raster icons")


def _vtk_utils():
    return import_optional(
        ".vtk_utils", package=__package__, extra="scientific",
        purpose="scientific VTK utilities")


def _mpl_utils():
    return import_optional(
        ".mpl_utils", package=__package__, extra="scientific",
        purpose="Matplotlib plotting")


UI_Z_PANEL_BACKGROUND = 10
UI_Z_SCROLL_ROWS = 20
UI_Z_BLINDER = 30
UI_Z_PANEL_TITLE = 40

# Scroll masks ("blinders") over rows sliding past a list's edges. Disabled:
# rows that are not fully inside the viewport are hidden anyway, and the
# masks caused colour/size artefacts. Set True to bring them back.
ENABLE_SCROLL_BLINDERS = False


def theme_value(renderer, name, default):
    """Read a colour/size from ``renderer.theme`` (LIBS/config.py).

    Falls back to *default* -- the widget's historical value -- when the
    renderer has no theme or the theme lacks the attribute.
    """
    theme = getattr(renderer, "theme", None)
    value = getattr(theme, name, None) if theme is not None else None
    return default if value is None else value


def theme_role_for_color(renderer, color, *roles):
    """Return the theme role currently represented by *color*, if any."""
    theme = getattr(renderer, "theme", None)
    if theme is None or color is None:
        return None
    try:
        value = tuple(float(component) for component in color[:3])
    except (TypeError, ValueError):
        return None
    for role in roles:
        themed = getattr(theme, role, None)
        if themed is not None and np.allclose(value, themed, atol=1e-6):
            return role
    return None


def rounded_rect_polydata(x, y, width, height, radii, rgba, resolution=6):
    """Filled rounded rectangle in pixels with per-corner radii.

    *radii* is ``(bottom_left, bottom_right, top_right, top_left)`` in px;
    *rgba* is 0..255. Returns polydata with cell colours for
    ``vtkContext2D.DrawPolyData``.
    """
    width, height = max(0.0, width), max(0.0, height)
    limit = min(width, height) / 2.0
    bl, br, tr, tl = (max(0.0, min(float(r), limit)) for r in radii)
    corners = (
        (x + bl, y + bl, bl, np.pi, 1.5 * np.pi),
        (x + width - br, y + br, br, 1.5 * np.pi, 2.0 * np.pi),
        (x + width - tr, y + height - tr, tr, 0.0, 0.5 * np.pi),
        (x + tl, y + height - tl, tl, 0.5 * np.pi, np.pi),
    )
    points = vtk.vtkPoints()
    polygon = vtk.vtkPolygon()
    for cx, cy, radius, a0, a1 in corners:
        steps = resolution if radius > 0 else 1
        for angle in np.linspace(a0, a1, steps):
            polygon.GetPointIds().InsertNextId(points.InsertNextPoint(
                cx + radius * np.cos(angle), cy + radius * np.sin(angle), 0.0))
    cells = vtk.vtkCellArray()
    cells.InsertNextCell(polygon)
    colors = vtk.vtkUnsignedCharArray()
    colors.SetNumberOfComponents(4)
    colors.InsertNextTuple4(*(int(c) for c in rgba))
    polydata = vtk.vtkPolyData()
    polydata.SetPoints(points)
    polydata.SetPolys(cells)
    polydata.GetCellData().SetScalars(colors)
    return polydata


def disc_icon_polydata(sides=48, radius=0.42):
    """Filled unit-square disc icon (e.g. colour swatches); recoloured by
    VectorButtonWidget's ``color``."""
    source = vtk.vtkRegularPolygonSource()
    source.SetNumberOfSides(int(sides))
    source.SetRadius(radius)
    source.SetCenter(0.5, 0.5, 0.0)
    source.GeneratePolygonOn()
    source.GeneratePolylineOff()
    source.Update()
    disc = vtk.vtkPolyData()
    disc.DeepCopy(source.GetOutput())
    colors = vtk.vtkUnsignedCharArray()
    colors.SetNumberOfComponents(4)
    for _ in range(disc.GetNumberOfCells()):
        colors.InsertNextTuple4(255, 255, 255, 255)
    disc.GetCellData().SetScalars(colors)
    return disc


def tab_shape_polydata(x0, x1, y0, y1, radius, rgba, content_side="right",
                       resolution=8):
    """Browser-style tab (pixels) joining a pane edge, triangulated.

    The tab spans ``[x0, x1] x [y0, y1]`` with convex rounded corners on
    the side away from the content and concave fillets of *radius* where it
    meets the content edge (``x1`` for ``content_side="right"``, else
    ``x0``), so it flows into the pane like a sideways browser tab.
    """
    r = max(0.0, min(float(radius), (x1 - x0) / 2.0, (y1 - y0) / 2.0))
    edge = x1                       # build for content on the right ...
    left = x0

    def arc(cx, cy, a0, a1):
        return [(cx + r * np.cos(a), cy + r * np.sin(a))
                for a in np.linspace(a0, a1, resolution)]

    outline = []
    outline += arc(edge - r, y1 + r, 0.0, -0.5 * np.pi)          # top concave fillet
    outline += arc(left + r, y1 - r, 0.5 * np.pi, np.pi)         # top outer corner
    outline += arc(left + r, y0 + r, np.pi, 1.5 * np.pi)         # bottom outer corner
    outline += arc(edge - r, y0 - r, 0.5 * np.pi, 0.0)           # bottom concave fillet
    if content_side != "right":     # ... and mirror for content on the left
        outline = [(x0 + x1 - x, y) for x, y in reversed(outline)]
    points = vtk.vtkPoints()
    polygon = vtk.vtkPolygon()
    for x, y in outline:
        polygon.GetPointIds().InsertNextId(points.InsertNextPoint(x, y, 0.0))
    cells = vtk.vtkCellArray()
    cells.InsertNextCell(polygon)
    shape = vtk.vtkPolyData()
    shape.SetPoints(points)
    shape.SetPolys(cells)
    # The outline is concave (fillets): triangulate rather than rely on the
    # 2D painter filling a concave polygon.
    triangles = vtk.vtkTriangleFilter()
    triangles.SetInputData(shape)
    triangles.Update()
    result = vtk.vtkPolyData()
    result.DeepCopy(triangles.GetOutput())
    colors = vtk.vtkUnsignedCharArray()
    colors.SetNumberOfComponents(4)
    for _ in range(result.GetNumberOfCells()):
        colors.InsertNextTuple4(*(int(c) for c in rgba))
    result.GetCellData().SetScalars(colors)
    return result


def _rgba255(color, opacity=1.0):
    return (int(color[0] * 255), int(color[1] * 255), int(color[2] * 255),
            int(opacity * 255))


# Interface size multiplier (the shared "ui/scale" preference), set once at
# start-up via set_ui_scale(), and the display's pixel density (device
# pixels per point: 2 on a Retina display), kept current by
# multipanel.display.DisplayWatcher from the window's DPI.
_UI_SCALE = 1.0
_DEVICE_SCALE = 1.0


def set_ui_scale(scale):
    global _UI_SCALE
    _UI_SCALE = min(1.5, max(0.75, float(scale)))


def user_scale():
    """The size preference alone."""
    return _UI_SCALE


def device_scale():
    """Device pixels per point of the window's display (window DPI / 72)."""
    return _DEVICE_SCALE


def set_device_scale(scale):
    global _DEVICE_SCALE
    _DEVICE_SCALE = min(4.0, max(0.5, float(scale)))


def ui_scale():
    """Display pixels per logical pixel: the size preference times the
    display's pixel density. Use it for geometry (sizes, padding, line
    widths); font point sizes take :func:`font_scale`."""
    return _UI_SCALE * _DEVICE_SCALE


def font_scale():
    """Multiplier for font *point* sizes: VTK already turns points into
    pixels at the window's DPI, so only the size preference applies."""
    return _UI_SCALE


# One corner radius for every panel (fraction of the window's smaller side,
# as VectorPanelBackground interprets values <= 1).
PANEL_CORNER_RADIUS = 0.01


def panel_corner_radius_px(interactor):
    width, height = interactor.GetRenderWindow().GetSize()
    return PANEL_CORNER_RADIUS * min(max(1, width), max(1, height))


def collapsed_panel_height(interactor):
    """Normalized height of a collapsed panel: exactly two corner radii, so
    the collapsed bar is a pill with semicircular ends."""
    height = max(1, interactor.GetRenderWindow().GetSize()[1])
    return 2.0 * panel_corner_radius_px(interactor) / height


def panel_header_metrics(interactor):
    """Shared header band geometry (normalized) for every VTK panel.

    Returns ``(band_height, chevron_w, chevron_h, inset_x, title_inset_x)``.
    The band is a little over twice the title text height so the bold
    title and the collapse chevron sit centred on one line.
    """
    width, height = interactor.GetRenderWindow().GetSize()
    width, height = max(1, width), max(1, height)
    # The title size is in points; the band is in device pixels.
    band_px = round(panel_title_text_size(interactor) * 2.1 * _DEVICE_SCALE)
    scale = ui_scale()
    control = 18.0 * scale
    return (band_px / height, control / width, control / height,
            8.0 * scale / width, 10.0 * scale / width)


_TITLE_HEIGHT_CACHE = {}


def text_line_height(interactor, size, bold=False):
    """Rendered height (normalized) of one text line ("Hg") at *size*.

    With fixed-size fonts vtkTextRepresentation shrinks its box to the
    text, so layouts that centre text place a text-high box at the centre
    instead of relying on vertical justification inside a taller box.
    """
    window = interactor.GetRenderWindow()
    height = max(1, window.GetSize()[1])
    dpi = max(1, window.GetDPI())
    key = (int(size), bool(bold), dpi)
    if key not in _TITLE_HEIGHT_CACHE:
        prop = vtk.vtkTextProperty()
        prop.SetFontSize(int(size))
        apply_ui_font(prop, bold=bold)
        box = [0, 0, 0, 0]
        vtk.vtkTextRenderer.GetInstance().GetBoundingBox(prop, "Hg", box, dpi)
        _TITLE_HEIGHT_CACHE[key] = max(1, box[3] - box[2] + 1)
    return _TITLE_HEIGHT_CACHE[key] / height


def panel_title_text_height(interactor):
    """Rendered height (normalized) of a bold panel title line."""
    return text_line_height(interactor, panel_title_text_size(interactor), True)


def text_width(interactor, widget):
    """Rendered width (normalized) of a TextWidget's current text."""
    window = interactor.GetRenderWindow()
    width = max(1, window.GetSize()[0])
    box = [0, 0, 0, 0]
    vtk.vtkTextRenderer.GetInstance().GetBoundingBox(
        widget.text_actor.GetTextProperty(),
        widget.text_actor.GetInput() or " ", box, max(1, window.GetDPI()))
    return max(1, box[1] - box[0] + 1) / width


def place_text_centred(widget, x, centre_y, width, height, centre_x=False):
    """Put a TextWidget's text-high box at (*x*, centred on *centre_y*).

    With ``centre_x`` the box is instead centred horizontally in
    ``[x, x + width]`` using the measured text width (fixed-size text boxes
    shrink to the text, so justification alone cannot centre it).
    Writes the representation directly (as panel layouts do) and keeps the
    widget's locked geometry in step.
    """
    if centre_x:
        measured = min(width, text_width(widget.interactor, widget))
        x = x + (width - measured) / 2.0
        width = measured
    y = centre_y - height / 2.0
    rep = widget.GetRepresentation()
    rep.GetPositionCoordinate().SetValue(x, y)
    rep.GetPosition2Coordinate().SetValue(width, height)
    widget._locked_position = (x, y)
    widget._locked_size = (width, height)
    rep.Modified()
    widget.Modified()


def panel_title_text_size(interactor):
    """Shared bold title size for every VTK panel (device-pixel aware).

    A few steps above the tree-row text (for a standard 0.02-high row) and
    bold, so panel titles read as headings.
    """
    window_height = interactor.GetRenderWindow().GetSize()[1]
    # A font size in points: VTK scales it by the DPI, so take the row
    # height in points (device pixels / density).
    row_points = max(1, round(0.02 * _UI_SCALE * window_height
                              / _DEVICE_SCALE))
    return max(10, min(36, round(row_points * 0.55) + 1))
UI_Z_SCROLLBAR = 45
UI_Z_PANEL_CONTROL = 50

ENABLE_HOVER_TEXT = True


def _ui_render_props(drawable):
    """Return renderer props used internally by a native/custom UI object."""
    props = []
    for attribute in ('actor', 'text_actor', '_thumb_actor',
                      'overlay_track_actor', 'overlay_actor',
                      '_shortcut_text_actor'):
        prop = getattr(drawable, attribute, None)
        if prop is not None:
            props.append(prop)
    get_representation = getattr(drawable, 'GetRepresentation', None)
    representation = get_representation() if get_representation else None
    if representation is not None:
        # vtkWidget adds its representation itself as a renderer prop. Its
        # internal actors are useful for custom representations, but moving
        # only those does not alter the vtkWidget draw order.
        if isinstance(representation, vtk.vtkProp):
            props.append(representation)
        for method_name in ('GetActors', 'GetActors2D'):
            method = getattr(representation, method_name, None)
            if method is None:
                continue
            collection = vtk.vtkPropCollection()
            method(collection)
            collection.InitTraversal()
            for _ in range(collection.GetNumberOfItems()):
                prop = collection.GetNextProp()
                if prop is not None:
                    props.append(prop)
    unique = []
    identities = set()
    for prop in props:
        identity = prop.GetAddressAsString('vtkProp')
        if identity not in identities:
            identities.add(identity)
            unique.append(prop)
    return unique


# UI z orders are layers *within* a container (panel background < rows <
# blinders < title < scrollbar < controls); each container re-sorts only its
# own drawables. A container pushes itself as the stacking scope while it
# creates children, and the late-insertion check compares a drawable only with
# drawables of the same scope. Otherwise every panel created after another
# would "violate" the earlier panel's higher layers, which is not an error.
_UI_STACKING_SCOPES = []


@contextlib.contextmanager
def ui_stacking_scope(owner):
    """Register drawables created inside the block under *owner*'s scope."""
    _UI_STACKING_SCOPES.append(owner)
    try:
        yield owner
    finally:
        _UI_STACKING_SCOPES.pop()


def ui_scoped(method):
    """Run a container method with the container as the stacking scope."""
    @functools.wraps(method)
    def wrapper(self, *args, **kwargs):
        with ui_stacking_scope(self):
            return method(self, *args, **kwargs)
    return wrapper


def current_ui_stacking_scope():
    return _UI_STACKING_SCOPES[-1] if _UI_STACKING_SCOPES else None


def register_ui_drawable(renderer, drawable, z_order, name=None, scope=None):
    """Register a declared UI order and warn about late lower-layer items.

    Only drawables in the same stacking scope (the container that created
    them, see :func:`ui_stacking_scope`; or *scope* if given) are compared.
    """
    drawable.ui_z_order = int(z_order)
    drawable.ui_draw_name = name or getattr(
        drawable, 'name', drawable.__class__.__name__)
    if scope is None:
        scope = current_ui_stacking_scope()
    drawable.ui_draw_scope = scope
    drawables = getattr(renderer, '_ui_drawables', [])
    later_layers = [item for item in drawables
                    if item is not drawable
                    and getattr(item, 'ui_draw_scope', None) is scope
                    and getattr(item, 'ui_z_order', UI_Z_SCROLL_ROWS) >
                    drawable.ui_z_order]
    if later_layers and not getattr(scope, 'ui_sorts_draw_order', False):
        warning_key = (
            drawable.ui_draw_name, drawable.ui_z_order,
            tuple(sorted({getattr(item, 'ui_z_order', 0)
                          for item in later_layers})))
        warned = getattr(renderer, '_ui_order_warnings', set())
        if warning_key not in warned:
            warnings.warn(
                f"UI element {drawable.ui_draw_name!r} "
                f"(z={drawable.ui_z_order}) was inserted after higher-z "
                f"element(s): {', '.join(getattr(item, 'ui_draw_name', item.__class__.__name__) for item in later_layers)}. "
                "The renderer order will be corrected.",
                RuntimeWarning, stacklevel=2)
            warned.add(warning_key)
            renderer._ui_order_warnings = warned
    if drawable not in drawables:
        drawables.append(drawable)
    renderer._ui_drawables = drawables


def enforce_ui_draw_order(renderer, drawables):
    """Reinsert UI props in declared back-to-front order."""
    renderer = ui_layer(renderer)
    ordered = sorted(drawables, key=lambda item: item.ui_z_order)
    for drawable in ordered:
        for prop in _ui_render_props(drawable):
            if renderer.HasViewProp(prop):
                renderer.RemoveViewProp(prop)
                renderer.AddViewProp(prop)

# VTK_FONT_FILE = 'GUI/Brave Seasons.ttf'
# VTK_FONT_FILE = 'GUI/ZalandoSans-CondensedMedium.ttf'
# UI typeface: Inter (SIL OFL), 18pt optical size for small UI text. VTK's
# font-file mode draws exactly the file it is given (bold/italic flags are
# ignored), so each style has its own file; apply_ui_font picks it.
_FONT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         "fonts", "inter", "static")
UI_FONT_FILES = {
    (False, False): "Inter_18pt-Regular.ttf",
    (True, False): "Inter_18pt-Bold.ttf",
    (False, True): "Inter_18pt-Italic.ttf",
    (True, True): "Inter_18pt-BoldItalic.ttf",
}
UI_FONT_FILES = {style: os.path.join(_FONT_DIR, name)
                 for style, name in UI_FONT_FILES.items()}
if not all(os.path.isfile(path) for path in UI_FONT_FILES.values()):
    _fallback = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             "open-sans.regular.ttf")
    logger.warning(
        "Inter font files not found in %s; falling back to Open Sans",
        _FONT_DIR)
    UI_FONT_FILES = {style: _fallback for style in UI_FONT_FILES}
VTK_FONT_FILE = UI_FONT_FILES[(False, False)]


def apply_ui_font(text_property, bold=None, italic=None):
    """Use the UI typeface on *text_property*, in the file matching its
    bold/italic flags (optionally setting them first)."""
    if bold is not None:
        text_property.SetBold(bool(bold))
    if italic is not None:
        text_property.SetItalic(bool(italic))
    path = UI_FONT_FILES[(bool(text_property.GetBold()),
                          bool(text_property.GetItalic()))]
    if os.path.isfile(path):
        text_property.SetFontFamily(vtk.VTK_FONT_FILE)
        text_property.SetFontFile(path)
    return text_property


class bcolors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

if not os.path.isfile(VTK_FONT_FILE):
    logger.warning("VTK font file %s not found; using default font",
                   VTK_FONT_FILE)

try:
    from numba_progress import ProgressBar
    progressbar_supported = True
except ImportError:
    progressbar_supported = False
    logger.debug("numba_progress is unavailable; reconstruction progress bars disabled")


# from ../vtk_utils import color_to_RGB, color_to_RGB_255

# from .import vtk_utils


def add_light_widget(iren, renderer=None):
    """
    Adds a light widget to the specified interactor and optionally associates it with a
    renderer.
    This function creates a VTK light widget with a positional light representation and
    attaches itto the provided interactor. If a renderer is provided, the widget is
    tored in therenderers `widgets` attribute for future reference.
    Args:
        iren (vtkRenderWindowInteractor): The interactor to which the light widget will
        be attached.
        renderer (vtkRenderer, optional): The renderer to associate the light widget
        with. If provided,
            the widget will be added to the `widgets` attribute of the renderer.
            Defaults to None.
    Returns:
        vtkLightWidget: The created light widget instance.
    """

    lightRep = vtk.vtkLightRepresentation()
    lightRep.SetPositional(True)
    lightRep.SetLightColor([1, 1, 1])

    lightWidget = vtk.vtkLightWidget()
    lightWidget.SetInteractor(iren)
    lightWidget.SetRepresentation(lightRep)
    lightWidget.On()

    # lightRep2 = vtk.vtkLightRepresentation()
    # lightRep2.SetLightColor([1,1,1])

    # lightWidget2 = vtk.vtkLightWidget()
    # lightWidget2.SetInteractor(iren)
    # lightWidget2.SetRepresentation(lightRep2)
    # lightWidget2.On()

    if renderer is not None:
        if not hasattr(renderer, "widgets"):
            renderer.widgets = {}
        renderer.widgets.update({"light_widget": lightWidget})

    return lightWidget


def add_camera_frame_widget(iren):
    """
    Creates and initializes a VTK camera widget with a specified interactor.
    This function sets up a VTK camera widget with a camera representation
    and a specified number of frames. The widget is activated and ready to
    interact with the provided interactor.
    Args:
        iren (vtkRenderWindowInteractor): The interactor to associate with the camera
        widget.
    Returns:
        vtkCameraWidget: The initialized and activated camera widget.
    """

    rep = vtk.vtkCameraRepresentation()
    rep.SetNumberOfFrames(2400)

    widget = vtk.vtkCameraWidget()
    widget.SetInteractor(iren)
    widget.SetRepresentation(rep)
    widget.On()

    return widget


def add_indicator_cube(interactor):
    """
    Adds an orientation marker widget to the given VTK interactor.
    This function creates an annotated cube actor with labeled faces to represent
    anatomical directions (Left, Right, Inferior, Superior, Posterior, Anterior).
    The cube is displayed as an orientation marker in the interactor window.
    Args:
        interactor (vtkRenderWindowInteractor): The VTK interactor to which the
            orientation marker widget will be added.
    Returns:
        vtkOrientationMarkerWidget: The orientation marker widget that was added
        to the interactor.
    """

    axes_actor = vtk.vtkAnnotatedCubeActor()
    axes_actor.SetXPlusFaceText("L")
    axes_actor.SetXMinusFaceText("R")
    axes_actor.SetYMinusFaceText("I")
    axes_actor.SetYPlusFaceText("S")
    axes_actor.SetZMinusFaceText("P")
    axes_actor.SetZPlusFaceText("A")
    axes_actor.GetTextEdgesProperty().SetColor(colormap_utils.color_to_RGB("White"))
    axes_actor.GetTextEdgesProperty().SetLineWidth(2)
    axes_actor.GetCubeProperty().SetColor(colormap_utils.color_to_RGB("Blue"))
    marker = vtk.vtkOrientationMarkerWidget()
    marker.SetOrientationMarker(axes_actor)
    marker.SetInteractor(interactor)
    marker.EnabledOn()
    marker.InteractiveOn()
    marker.SetViewport(0.9, 0.0, 1.0, 0.1)

    return marker


def add_camera_widget(render_window):
    """
    Adds a camera orientation widget to the specified render window.
    This function creates a vtkCameraOrientationWidget, sets its parent
    renderer to the provided render window, and enables the widget.
    Args:
        render_window: The render window (vtkRenderWindow) to which the
                       camera orientation widget will be added.
    Returns:
        vtkCameraOrientationWidget: The created and enabled camera orientation widget.
    """

    cam_orient_manipulator = vtk.vtkCameraOrientationWidget()
    cam_orient_manipulator.SetParentRenderer(render_window)
    # Enable the widget.
    cam_orient_manipulator.On()
    return cam_orient_manipulator


def add_camera_path_widget(iren, renderer=None):
    """
    Creates and initializes a vtkCameraPathWidget with a vtkCameraPathRepresentation.

    This function sets up a camera path widget for use with a VTK interactor.
    The widget allows for the visualization and manipulation of camera paths
    in a 3D scene.

    Args:
        iren (vtkRenderWindowInteractor): The VTK render window interactor
            to which the camera path widget will be attached.
        renderer (vtkRenderer, optional): The VTK renderer to which the widget
            will be associated. If provided, the widget will be added to the
            renderer's widgets list. Defaults to None.

    Returns:
        vtkCameraPathWidget: The initialized camera path widget.
    """

    rep = vtk.vtkCameraPathRepresentation()
    rep.SetDirectional(True)
    # rep.SetNumberOfFrames(2400)

    widget = vtk.vtkCameraPathWidget()
    widget.SetInteractor(iren)
    widget.SetRepresentation(rep)
    widget.On()

    if renderer is not None:
        if not hasattr(renderer, "widgets"):
            renderer.widgets = {}
        renderer.widgets.update({"camera_path_widget": widget})

    return widget


def camera_perspective_callback(widget, event=None):
    """Callback function to switch the camera to perspective view."""

    value = widget.GetRepresentation().GetState()
    camera = widget.GetCurrentRenderer().GetActiveCamera()
    # camera.SetViewAngle(30)
    # camera.SetPosition(0, 0, 100)
    # camera.SetFocalPoint(0, 0, 0)

    if value == 0:
        camera.SetParallelProjection(False)
    else:
        camera.SetParallelProjection(True)

    # widget.GetCurrentRenderer().ResetCamera()
    widget.GetCurrentRenderer().GetRenderWindow().Render()

class rep_test(vtk.vtkPlaybackRepresentation):
    def __init__(self):
        """Initialize the instance."""
        self.SetShowBorderToOff()
        # self.EnforceNormalizedViewportBoundsOff()
        self.ProportionalResizeOn()
        self.MovingOn()
        self.Modified()
        self.BuildRepresentation()
        logger.debug("initialised test rep")
        logger.debug("%s", self)

    def Play(self):
        """Execute the play operation."""
        logger.debug("play")

    def Stop(self):
        """Execute the stop operation."""
        logger.debug("Stop")

    def ForwardOneFrame(self):
        """Execute the forward one frame operation."""
        logger.debug("Forward 1")

    def BackwardOneFrame(self):
        """Execute the backward one frame operation."""
        logger.debug("Backward 1")

    def JumpToBeginning(self):
        """Execute the jump to beginning operation."""
        logger.debug("Jump to Beginning")

    def JumpToEnd(self):
        """Execute the jump to end operation."""
        logger.debug("Jump to End")


def add_playback_widget(render_window_interactor, renderer=None):
    """
    Adds a playback widget to a VTK render window interactor.
    This function creates and configures a VTK playback widget, which provides
    playback controls such as play, stop, forward, backward, and jump to the
    beginning or end. The widget is associated with the provided render window
    interactor and optionally linked to a renderer.
    Args:
        render_window_interactor (vtkRenderWindowInteractor): The interactor
            associated with the render window where the playback widget will
            be added.
        renderer (vtkRenderer, optional): An optional renderer to which the
            playback widget will be linked. If provided, the widget will be
            stored in the `widgets` attribute of the renderer.
    Returns:
        vtkPlaybackWidget: The configured playback widget instance.
    """

    # Create the playback widget
    playback_widget = vtk.vtkPlaybackWidget()

    # Set up the playback widget
    playback_rep = rep_test()
    playback_widget.SetRepresentation(playback_rep)
    playback_widget.SetInteractor(render_window_interactor)
    playback_widget.PickingManagedOn()
    playback_widget.ProcessEventsOn()
    playback_widget.SetEnabled(True)
    playback_widget.DebugOn()

    playback_widget.On()

    playback_widget.Modified()

    playback_widget.GetRepresentation().Play()
    playback_widget.GetRepresentation().Stop()
    playback_widget.GetRepresentation().ForwardOneFrame()
    playback_widget.GetRepresentation().BackwardOneFrame()
    playback_widget.GetRepresentation().JumpToBeginning()
    playback_widget.GetRepresentation().JumpToEnd()

    logger.debug("%s %s", playback_rep, sorted(dir(playback_rep)))

    logger.debug("%s %s", playback_widget, sorted(dir(playback_widget)))

    state = playback_widget.GetRepresentation().GetInteractionState()

    logger.debug("%s %s", "STATE", state)

    if renderer is not None:
        if not hasattr(renderer, "widgets"):
            renderer.widgets = {}
        renderer.widgets.update({"playback_widget": playback_widget})

    return playback_widget


def CompassWidgetValueChangedCallback(widget, event):
    """Callback to set the camera position according to the position parameters
    given by the vtkCompassWidget.
    """
    try:
        camera = widget.GetCurrentRenderer().GetActiveCamera()
    except AttributeError:
        return

    # calculate new camera position from compass widget parameters
    distance = widget.GetDistance()
    tilt = widget.GetTilt()
    heading = widget.GetHeading()

    x = (
        distance
        * math.cos(vtkMath.RadiansFromDegrees(heading))
        * math.cos(vtkMath.RadiansFromDegrees(tilt))
    )
    y = (
        distance
        * math.sin(vtkMath.RadiansFromDegrees(heading))
        * math.cos(vtkMath.RadiansFromDegrees(tilt))
    )
    z = distance * math.sin(vtkMath.RadiansFromDegrees(tilt))

    # camera.SetPosition(x, y, z)
    # camera.SetFocalPoint(0, 0, 0)
    current_camera_position = camera.GetPosition()
    camera.SetFocalPoint(
        current_camera_position[0] + x,
        current_camera_position[1] + y,
        current_camera_position[2] + z,
    )
    camera.SetViewUp(0, 0, 1)
    # camera.SetClippingRange(0.1, distance + 1)

    widget.GetCurrentRenderer().Render()


class CameraOrientationObserver:
    """
    A class to observe and update the orientation of a camera in relation to a compass
    widget.This class is designed to synchronize the camera's orientation with a compass
    widget,updating the widget's heading, tilt, and distance based on the cameras
    position, focal point, and view direction.
    Attributes:
        compass_widget: The compass widget to be updated.
        camera: The camera whose orientation is being observed. If not provided, the
        activecamera from the compass widget's current renderer is used.
    Methods:
        __call__(caller, ev):
            Callback method triggered by an event. Updates the compass widget based on
            the cameras orientation.
        update_compass_widget(compassWidget):
            Computes the camera's heading, tilt, and distance, and updates the compass
            widget accordingly.
    """

    def __init__(self, compass_widget, camera=None):
        """Initialize the instance."""
        self.compass_widget = compass_widget

        if camera is None:
            camera = compass_widget.GetCurrentRenderer().GetActiveCamera()
        else:
            self.camera = camera

    def __call__(self, caller, ev):
        """Execute the call operation."""
        self.update_compass_widget(self.compass_widget)

    def update_compass_widget(self, compassWidget):
        """Update compass widget."""
        camera = compassWidget.GetCurrentRenderer().GetActiveCamera()

        position = camera.GetPosition()
        focal_point = camera.GetFocalPoint()
        # view_up = camera.GetViewUp()

        # Compute heading, tilt, and distance
        direction = [focal_point[i] - position[i] for i in range(3)]
        distance = vtk.vtkMath.Normalize(direction)

        heading = vtk.vtkMath.DegreesFromRadians(np.arctan2(direction[1], direction[0]))

        tilt = vtk.vtkMath.DegreesFromRadians(np.arcsin(direction[2]))

        compassWidget.SetHeading(heading)
        compassWidget.SetTilt(tilt)
        compassWidget.SetDistance(distance)

        compassWidget.Modified()


def _attach_camera_orientation_observer(compass_widget, camera):
    """Keep exactly one camera observer owned by a compass widget."""
    previous = getattr(compass_widget, '_camera_observer', None)
    if previous is not None:
        previous_camera, previous_tag = previous
        previous_camera.RemoveObserver(previous_tag)
    tag = camera.AddObserver(
        "ModifiedEvent", CameraOrientationObserver(compass_widget, camera))
    compass_widget._camera_observer = (camera, tag)
    return tag


def add_compass_widget(renderer, renderWindowInteractor):
    """
    Adds a compass widget to the specified renderer and render window interactor.
    The compass widget provides a visual representation of orientation and distance
    within the 3D scene. It is interactive and can respond to user input.
    Args:
        renderer (vtkRenderer): The renderer to which the compass widget will be added.
        renderWindowInteractor (vtkRenderWindowInteractor): The interactor for handling
            user input and interaction with the widget.
    Behavior:
        - The compass widget is configured with a draggable representation.
        - The widget observes interaction events and updates accordingly.
        - The widget's distance and tilt speed are set to predefined values.
        - The active camera of the renderer is observed for orientation changes, which
          are reflected in the compass widget.
    Notes:
        - The widget is enabled by default.
        - The renderer is extended with a `widgets` attribute (if not already present)
          to keep track of added widgets.
    """

    compassRepresentation = vtkCompassRepresentation()

    compassRepresentation.SetUseBounds(True)
    compassRepresentation.DragableOn()

    compassWidget = vtkCompassWidget()
    compassWidget.SetInteractor(renderWindowInteractor)
    compassWidget.SetRepresentation(compassRepresentation)

    compassWidget.AddObserver("InteractionEvent", CompassWidgetValueChangedCallback)

    compassRepresentation.SetMinimumDistance(2)
    compassRepresentation.SetMaximumDistance(10)
    compassWidget.SetDistance(5)
    compassWidget.SetTiltSpeed(45)
    compassWidget.SetDistanceSpeed(2)

    compassRepresentation.GetLabelProperty().SetColor(0.0, 0.0, 0.0)
    compassRepresentation.GetRingProperty().SetColor(0.0, 0.0, 0.0)
    compassRepresentation.GetSelectedProperty().SetColor(0.0, 0.0, 0.0)
    compassRepresentation.GetSelectedProperty().SetLineWidth(2)

    compassWidget.EnabledOn()
    compassWidget.ProcessEventsOff()

    collection = vtk.vtkPropCollection()

    compassRepresentation.GetActors(collection)

    background = collection.GetItemAsObject(0)
    background.GetProperty().SetOpacity(0.0)


    for i in range(collection.GetNumberOfItems()):
        actor = collection.GetItemAsObject(i)

        actor.GetProperty().SetColor(0.0, 0.0, 0.0)
        actor.GetProperty().SetPointSize(5)
        actor.GetProperty().SetLineWidth(10)
        if i != 0:
            actor.GetProperty().SetOpacity(1)

        # actor.SetPickable(False)
        # actor.SetVisibility(True)

    # actors_2D = vtk.vtkPropCollection()

    # compassRepresentation.GetActors2D(actors_2D)

    # compassRepresentation.RingActor().GetProperty().SetColor(0.0, 0.0, 0.0)
    compassRepresentation.Highlight(1)

    compassWidget.Modified()

    camera = renderer.GetActiveCamera()
    _attach_camera_orientation_observer(compassWidget, camera)

    if not hasattr(renderer, "widgets"):
        renderer.widgets = {}

    renderer.widgets.update({"compass_widget": compassWidget})

    return compassWidget


def add_pointcloud_widget(
    points,
    iren,
    renderer=None,
    use_hardware_picking=True,
    use_highlighting=False,
    return_actor=True,
):
    """
    Adds a VTK point cloud widget to the specified interactor.
    This function creates a point cloud widget using the provided points and interactor.
    It allows for interaction with the point cloud, such as selecting points and
    retrieving their coordinates and scalar values.
    Args:
        points (vtk.vtkPolyData or vtk.vtkActor): The point cloud data or actor to be
        visualized.
        iren (vtk.vtkRenderWindowInteractor): The interactor to which the widget will be
        added.
        renderer (vtk.vtkRenderer, optional): The renderer to which the widget will be
        associated.
            If provided, the widget will be added to the `widgets` attribute of the
            renderer.
            Defaults to None.
        use_hardware_picking (bool, optional): If True, enables hardware-based point
        picking.
            Defaults to True.
        use_highlighting (bool, optional): If True, enables highlighting of selected
        points.
            Defaults to False.
        return_actor (bool, optional): If True, returns the actor associated with the
        point cloud.
            Defaults to True.
    Returns:
        tuple: A tuple containing:
            - pcWidget (vtk.vtkPointCloudWidget): The created point cloud widget.
            - actor (vtk.vtkActor, optional): The actor associated with the point cloud,
              if `return_actor` is True.
    Notes:
        - The widget listens for "WidgetActivateEvent" to trigger the OnClickCallback
        function.
        - If `use_highlighting` is enabled, it may interfere with the "fly command"
        (key 'f').
        - The function prints information about selected points, including their
        coordinates and scalar values, to the console.
    """

    # def SelectPoint(widget, event_string):
    #     pcWidget, rep

    def OnClickCallback(widget, event_string):
        """Execute the on click callback operation."""
        pId = rep.GetPointId()
        logger.debug(f"Selected Point Id {rep.GetPointId()}: ")
        if isinstance(points, vtk.vtkActor):
            point_data = points.GetMapper().GetInput().GetPointData()
            actor_points = points.GetMapper().GetInput()
            point_location = actor_points.GetPoints().GetPoint(pId)

            x = point_location[0]
            y = point_location[1]
            z = point_location[2]

            logger.debug(f"Point Coordinates: X={x:.2f}, Y={y:.2f}, Z={z:.2f}")
            logger.debug("%s %s", "Scalar value:", point_data.GetScalars().GetTuple(pId))
        else:
            point_location = points.GetPoints().GetPoint(pId)
            x = point_location[0]
            y = point_location[1]
            z = point_location[2]
            logger.debug(f"Point Coordinates:  X={x:.2f}, Y={y:.2f}, Z={z:.2f}")

    # Conveniently the representation creates an actor/mapper
    # to render the point cloud.
    rep = vtk.vtkPointCloudRepresentation()
    rep.SetPlaceFactor(1.0)
    rep.PlacePointCloud(points)
    if use_hardware_picking:
        rep.SetPickingModeToHardware()
    else:
        rep.SetPickingModeToSoftware()

    if use_highlighting:
        logger.debug("Using highlighting, may break fly command (f)")
        rep.HighlightingOn()
    else:
        logger.debug("Not using highlighting")
        rep.HighlightingOff()

    pcWidget = vtk.vtkPointCloudWidget()
    pcWidget.SetManagesCursor(False)
    pcWidget.SetInteractor(iren)
    pcWidget.SetRepresentation(rep)
    pcWidget.SetPriority(0.5)
    # pcWidget.AddObserver("PickEvent",SelectPoint)
    pcWidget.AddObserver("WidgetActivateEvent", OnClickCallback)
    pcWidget.On()

    prop_collection = vtk.vtkPropCollection()
    rep.GetActors(prop_collection)

    if renderer is not None:
        if not hasattr(renderer, "widgets"):
            renderer.widgets = []
        renderer.widgets.append(pcWidget)

    if return_actor:
        actor = prop_collection.GetItemAsObject(0)

        return pcWidget, actor


    return pcWidget


def _pill_polydata(x0, x1, y0, y1, radius, corner_segments=6):
    """Filled rounded rectangle polygon in display pixels (slider overlay)."""
    radius = max(0.0, min(float(radius), (x1 - x0) / 2.0, (y1 - y0) / 2.0))
    points = vtk.vtkPoints()
    corners = ((x1 - radius, y1 - radius, 0.0), (x0 + radius, y1 - radius, 0.5),
               (x0 + radius, y0 + radius, 1.0), (x1 - radius, y0 + radius, 1.5))
    for cx, cy, start in corners:
        for k in range(corner_segments + 1):
            angle = np.pi * (start + 0.5 * k / corner_segments)
            points.InsertNextPoint(cx + radius * np.cos(angle),
                                   cy + radius * np.sin(angle), 0.0)
    polygon = vtk.vtkPolygon()
    count = points.GetNumberOfPoints()
    polygon.GetPointIds().SetNumberOfIds(count)
    for index in range(count):
        polygon.GetPointIds().SetId(index, index)
    cells = vtk.vtkCellArray()
    cells.InsertNextCell(polygon)
    polydata = vtk.vtkPolyData()
    polydata.SetPoints(points)
    polydata.SetPolys(cells)
    return polydata




# Internal implementation modules deliberately import private helpers too.
__all__ = [name for name in globals() if not name.startswith("__")]
