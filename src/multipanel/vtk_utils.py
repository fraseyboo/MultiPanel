import vtk
from vtk.util import numpy_support
import math
from tqdm import tqdm, trange
import numpy as np
import warnings
import os
import logging

# import config
import sys

logger = logging.getLogger(__name__)

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__),"../GUI/")))

from . import interactor_utils
from . import colormap_utils

from . import config

_drop_file_handler = None


def set_drop_file_handler(handler):
    """Register ``handler(paths, renderer=...)`` for application file drops."""
    global _drop_file_handler
    _drop_file_handler = handler


from vtkmodules.vtkCommonCore import (
    VTK_VERSION_NUMBER,
    vtkVersion
)

logger.debug("VTK version: %s", vtkVersion.GetVTKVersion())

import matplotlib
from matplotlib import pyplot as plt

# from scipy.spatial import cKDTree as KDTree
from sklearn.neighbors import KDTree


# import GUI.widget_utils as widget_utils
# from . import interactor_utils

# try:
#     matplotlib.rcParams.update({
#         "pgf.texsystem": "pdflatex",
#         'font.family': 'serif',
#         'text.usetex': True,
#         'pgf.rcfonts': False,
#     })
# except:


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



conflicting_backends = ['QtAgg', 'Qt5Agg']


try:                                    # Matplotlib >= 3.9
    from matplotlib.backends import backend_registry
    available_backends = backend_registry.list_builtin()
except ImportError:
    available_backends = getattr(matplotlib.rcsetup, "all_backends", None)


if matplotlib.pyplot.get_backend() in conflicting_backends:
    try:
        matplotlib.use('GTK4Agg')
        logger.debug('backend set to GTK3Agg to avoid conflict with VTK plot')
    except:
        logger.warning('Tried to switch to GTK4, failed')
        logger.debug("%s %s", 'Currently using:', matplotlib.get_backend())


def block_e_key(interactor_obj, event):
    """Execute the block e key operation."""
    key = interactor_obj.GetKeySym()
    if key == 'e':
        # Prevent any further handling, including platform-specific exit
        interactor_obj.SetKeyCode("")  # Clear key code
        return  # Do not propagate
    elif key == '3':
        # Prevent any further handling, including platform-specific exit
        interactor_obj.SetKeyCode("")  # Clear key code
        return  # Do not propagate


@vtk.calldata_type(vtk.VTK_OBJECT)
def on_drop_callback(caller, event, calldata):
    """Handle drop callback."""
    files = vtk.vtkStringArray.SafeDownCast(calldata)

    logger.debug("Drop event received!")
    total_files = files.GetNumberOfValues()
    logger.debug("%s %s", 'Total files dropped:', total_files)

    file_list = []

    for i in range(files.GetNumberOfValues()):
        path = files.GetValue(i)

        logger.debug(f"File {i + 1}: {path}")

        file_list.append(path)

    renderer = caller.GetRenderWindow().GetRenderers().GetFirstRenderer()

    if _drop_file_handler is None:
        raise RuntimeError(
            "No file-drop handler is registered; call set_drop_file_handler()")
    _drop_file_handler(file_list, renderer=renderer)

    # we need to update the actor panel

    if hasattr(renderer, 'UI_panels') and 'actor_visibility' in renderer.UI_panels:


        actor_visibility_panel = renderer.UI_panels['actor_visibility']
        actor_visibility_panel.update_layout(update_actors=True)

    renderer.GetRenderWindow().Render()


def create_renderer(actors=None, use_ssao=False, 
                    window_name='Compton Visualiser',
                    dark_mode=True):
    # Create graphics stuff

    """Create renderer."""
    ren = vtk.vtkRenderer()
    # Saved Appearance preferences (shared with the Qt UI) override the
    # requested default; see LIBS/config.py.
    ren.theme = config.theme.from_preferences(default_dark=dark_mode)
    renWin = vtk.vtkRenderWindow()
    renWin.AddRenderer(ren)
    iren = vtk.vtkRenderWindowInteractor()
    iren.SetRenderWindow(renWin)

    if dark_mode:
        background_color = np.asarray((18, 19, 20)) / 255.0
    else:
        background_color = (1.0, 1.0, 1.0)

    # Add observer to interactor BEFORE setting the style
    # iren.AddObserver("KeyPressEvent", block_e_key, 1.0)  # priority=1.0 to run first


    ren.SetBackground(background_color[0], background_color[1], background_color[2])
    if len(background_color) > 3:
        ren.SetBackground2(background_color[3], background_color[4], background_color[5])
        ren.GradientBackgroundOn()
    ren.ResetCamera()
    ren.TwoSidedLightingOn()
    ren.ResetCameraClippingRange()
    ren.ResetCamera()

    if use_ssao:

        from sys import platform
        if platform == "linux" or platform == "linux2":
            ren = interactor_utils.set_passes(ren, use_ssao=True)
            # linux
        elif platform == "darwin":
            logger.debug('Enabling SSAO does not appear to be supported on MacOS, skipping (for now)')
            # ren = interactor_utils.set_passes(ren, use_ssao=True)
            pass
            # OS X
        elif platform == "win32":
            ren = interactor_utils.set_passes(ren, use_ssao=True)
            # Windows...

    if actors is not None:

        if isinstance(actors, list):
            for actor in actors:
                ren.AddActor(actor)
        elif isinstance(actors, vtk.vtkActorCollection):
            pass
        elif isinstance(actors, dict):
            for actor in actors.values:
                ren.AddActor(actor)


    # Enable image smoothing for better rendering quality
    renWin.SetMultiSamples(64)
    renWin.LineSmoothingOn()
    renWin.PointSmoothingOn()
    renWin.PolygonSmoothingOn()

    renWin.SetSize(1500, 1500)
    # macOS shrinks a window taller than its screen without VTK noticing:
    # ask for one that fits.
    from .display import fit_window_to_screen
    fit_window_to_screen(renWin)
    renWin.SetWindowName(window_name)

    iren.AddObserver(vtk.vtkCommand.DropFilesEvent, on_drop_callback)

    iren.Initialize()
    iren.SetInteractorStyle(interactor_utils.MyInteractorStyle(iren, ren.GetActiveCamera(), renWin, ren))

    return ren, renWin, iren

def set_camera(camera, position):
    """Set camera."""
    pos_dict = {'N': np.array([0, 1, 0]),
                'E': np.array([1, 0, 0]),
                'S': np.array([0, -1, 0]),
                'W': np.array([-1, 0, 0]),
                'Top': np.array([0, 0, 1]),
                'Bottom': np.array([0, 0, -1]),
                'NE': np.array([0.707, 0.707, 0]),
                'NW': np.array([0.707, -0.707, 0]),
                'SE': np.array([-0.707, 0.707, 0]),
                'SW': np.array([-0.707, -0.707, 0])}

    pos = np.asarray(camera.GetPosition())
    cent = np.asarray(camera.GetFocalPoint())


    rad = np.sqrt(np.sum(np.square(pos-cent)))

    new_pos = pos_dict[position]*rad

    camera.SetPosition(new_pos)
    up = np.asarray([0, 0, 1])
    # camera.SetViewUp(pos_dict[position])
    camera.SetViewUp(up)

class MyInteractorStyle(vtk.vtkInteractorStyleTrackballCamera):
    """[VTK class definitions to allow for more natural camera movement (trackpad style)
        and keybindings for extra functionality (camera movement, printscreens etc.)]

    Arguments:
      expects: renderWindowInteractor, render_camera, renderWindow
    """

    def __init__(self, parent, camera, renderer):
        """Initialize the instance."""
        self.parent = parent
        self.camera = camera
        self.renderer = renderer

        self.verbose = False
        self.auto_up = True
        # Kept alive from Python (see interactor_utils.keep_interactor_style_alive).
        interactor_utils.keep_interactor_style_alive(self)
        self.AddObserver("MiddleButtonPressEvent", self.middle_button_press_event)
        self.AddObserver("MiddleButtonReleaseEvent", self.middle_button_release_event)
        self.AddObserver("LeftButtonPressEvent", self.left_button_press_event)
        self.AddObserver("LeftButtonReleaseEvent", self.left_button_release_event)
        self.AddObserver("KeyPressEvent", self.keyPressEvent)

        # self.AutoAdjustCameraClippingRange(True)

    def release(self):
        """Let the style be garbage collected once it is no longer in use."""
        interactor_utils.release_interactor_style(self)

    def camera_zoom_in(self, step=2):

        """Execute the camera zoom in operation."""
        old = np.asarray(self.camera.GetPosition())

        new = old *0.9

        if self.auto_up:
            up = np.asarray([0, 0, 1])
            self.camera.SetViewUp(up)

        self.camera.SetPosition(tuple(new))


        # self.renderer.ResetCameraClippingRange()

        self.renderer.Render()
        return


    def camera_zoom_out(self, step=2):

        """Execute the camera zoom out operation."""
        old = np.asarray(self.camera.GetPosition())

        new = old * 1.1

        if self.auto_up:
            up = np.asarray([0, 0, 1])
            self.camera.SetViewUp(up)

        self.camera.SetPosition(tuple(new))

        # self.renderer.ResetCameraClippingRange()

        self.renderer.Render()
        return


    def rotate_clockwise(self, step=2):

        """Execute the rotate clockwise operation."""
        old = list(self.camera.GetPosition())

        x_coord = old[0]
        y_coord = old[1]

        if x_coord >= 0:
            if y_coord >= 0:
                x_sign = -1
                y_sign = 1
            else:
                x_sign = 1
                y_sign = 1
        elif y_coord >= 0:
            x_sign = -1
            y_sign = -1
        else:
            x_sign = 1
            y_sign = -1

        scale = 0.05

        del_x = np.abs(y_coord) * scale * x_sign
        del_y = np.abs(x_coord) * scale * y_sign
        hypot_1 = math.hypot(old[0], old[1])

        new_x =  old[0] + del_x
        new_y =  old[1] + del_y

        hypot_2 = math.hypot(new_x, new_y)

        rescale = hypot_1/hypot_2

        new = old
        new[0] = (new_x * rescale)
        new[1] = (new_y * rescale)

        if self.auto_up:
            up = np.asarray([0, 0, 1])
            self.camera.SetViewUp(up)

        self.camera.SetPosition(tuple(new))

        self.renderer.Render()
        return


    def rotate_anticlockwise(self):


        """Execute the rotate anticlockwise operation."""
        old = list(self.camera.GetPosition())

        x_coord = old[0]
        y_coord = old[1]

        if x_coord > 0:
            if y_coord > 0:
                x_sign = 1
                y_sign = -1
            else:
                x_sign = -1
                y_sign = -1
        elif y_coord > 0:
            x_sign = 1
            y_sign = 1
        else:
            x_sign = -1
            y_sign = 1

        scale = 0.05

        del_x = np.abs(y_coord) * scale * x_sign
        del_y = np.abs(x_coord) * scale * y_sign
        hypot_1 = math.hypot(old[0], old[1])

        new_x =  old[0] + del_x
        new_y =  old[1] + del_y

        hypot_2 = math.hypot(new_x, new_y)

        rescale = hypot_1/hypot_2

        new = old
        new[0] = (new_x * rescale)
        new[1] = (new_y * rescale)

        if self.auto_up:
            up = np.asarray([0, 0, 1])
            self.camera.SetViewUp(up)

        self.camera.SetPosition(tuple(new))

        self.renderer.Render()
        return


    def rotate_upclockwise(self):


        """Execute the rotate upclockwise operation."""
        old = list(self.camera.GetPosition())

        x_coord = old[0]
        y_coord = old[1]


        d_coord = math.hypot(x_coord, y_coord)

        z_coord = old[2]

        if z_coord >= 0:
           z_sign = 1
           d_sign = -1
        else:
            z_sign = 1
            d_sign = 1

        scale = 0.05

        del_z = np.abs(d_coord) * scale * z_sign
        del_d = np.abs(z_coord) * scale * d_sign
        hypot_1 = math.hypot(d_coord, z_coord)

        new_z =  z_coord + del_z
        new_d =  d_coord + del_d

        hypot_2 = math.hypot(new_z, new_d)
        rescale = hypot_1/hypot_2

        new = old
        new[2] = (new_z * rescale)
        new_d = (new_d * rescale)

        rescale_2 = new_d/d_coord

        new[0] = (x_coord * rescale_2)
        new[1] = (y_coord * rescale_2)

        if self.auto_up:
            up = np.asarray([0, 0, 1])
            self.camera.SetViewUp(up)

        self.camera.SetPosition(tuple(new))

        self.renderer.Render()
        return


    def rotate_downclockwise(self):

        """Execute the rotate downclockwise operation."""
        old = list(self.camera.GetPosition())

        x_coord = old[0]
        y_coord = old[1]

        d_coord = math.hypot(x_coord, y_coord)

        z_coord = old[2]

        if z_coord >= 0:
           z_sign = -1
           d_sign = +1
        else:
            z_sign = -1
            d_sign = -1

        scale = 0.05

        del_z = np.abs(d_coord) * scale * z_sign
        del_d = np.abs(z_coord) * scale * d_sign
        hypot_1 = math.hypot(d_coord, z_coord)

        new_z =  z_coord + del_z
        new_d =  d_coord + del_d

        hypot_2 = math.hypot(new_z, new_d)
        rescale = hypot_1/hypot_2

        new = old
        new[2] = (new_z * rescale)
        new_d = (new_d * rescale)

        rescale_2 = new_d/d_coord

        new[0] = (x_coord * rescale_2)
        new[1] = (y_coord * rescale_2)

        if self.auto_up:
            up = np.asarray([0, 0, 1])
            self.camera.SetViewUp(up)

        self.camera.SetPosition(tuple(new))

        self.renderer.Render()
        return


    def screenshot(self):

        """Execute the screenshot operation."""
        w2if = vtk.vtkWindowToImageFilter()
        w2if.SetScale(4)
        w2if.SetInput(self.renderer)
        w2if.Update()

        writer = vtk.vtkPNGWriter()
        writer.SetFileName("screenshot.png")
        writer.SetInputData(w2if.GetOutput())
        writer.Write()

    def keyPressEvent(self, obj, event):
        """Execute the key press event operation."""
        key = str(self.parent.GetKeySym())
        # check here for available keypresses supported by Qt & VTK
        # https://github.com/Kitware/VTK/blob/master/GUISupport/Qt/QVTKInteractorAdapter.cxx
        if key == 'Left':
            self.rotate_clockwise()
        if key == 'Right':
            self.rotate_anticlockwise()
        if key == 'Up':
            self.rotate_upclockwise()
        if key == 'Down':
            self.rotate_downclockwise()
        if key == 'c':
            self.screenshot()
        if key == 'equal':
            self.camera_zoom_in()
        if key == 'minus':
            self.camera_zoom_out()
        return


    def left_button_press_event(self, obj, event):
        """Execute the left button press event operation."""
        if self.verbose:
            logger.debug("left Button pressed")
        self.OnLeftButtonDown()
        return


    def left_button_release_event(self, obj, event):
        """Execute the left button release event operation."""
        if self.verbose:
            logger.debug("left Button released")
        self.OnLeftButtonUp()
        return


    def middle_button_press_event(self, obj, event):
        """Execute the middle button press event operation."""
        if self.verbose:
            logger.debug("Middle Button pressed")
        self.OnMiddleButtonDown()
        return


    def middle_button_release_event(self, obj, event):
        """Execute the middle button release event operation."""
        if self.verbose:
            logger.debug("Middle Button released")
        self.OnMiddleButtonUp()
        return


def cartoonify_actor(actor, add_edges=False, line_width=2):  
    """Execute the cartoonify actor operation."""
    actor.GetProperty().SetAmbient(0.6)
    actor.GetProperty().SetDiffuse(0.4)
    actor.GetProperty().SetSpecular(0.1)

    if add_edges:

        mesh_color = actor.GetProperty().GetColor()

        edge_color = [mesh_color[0] * 0.7, mesh_color[1] * 0.7, mesh_color[2] * 0.7]

        actor.GetProperty().SetEdgeVisibility(1)
        actor.GetProperty().SetEdgeColor(*edge_color)
        actor.GetProperty().SetLineWidth(line_width)


def add_contours(input_data,
                 renderer=None,
                 c_number=10,
                 c_range=None,
                 c_values=None,
                 spacing=(1, 1, 1),
                 opacity=1.0,
                 origin=None,
                 colormap='viridis',
                 name='contour',
                 shade=False,
                 passthrough=False,
                 color_override=None,
                 pickable=False,
                 enabled=True,
                 mesh_color=[0.9, 0.9, 0.9]):
    """[Adds contours of a volume to the current renderer]

    Arguments:
        input_data {[NUmpy array (x,y,z)]} -- [the volume to contour]
        renderer {[VTK renderer]} -- [the current VTK renderer]

    Keyword Arguments:
        c_number {int} -- [description] (default: {10})
        c_range {[type]} -- [description] (default: {None})
        spacing {tuple} -- [description] (default: {(1,1,1)})
        opacity {float} -- [description] (default: {0.5})
        origin {[type]} -- [description] (default: {None})
    """

    colors = vtk.vtkNamedColors()



    if type(input_data) is type(vtk.vtkImageData()):


        im = input_data
        try:
            c_range = im.GetPointData().GetArray("ImageScalars").GetValueRange()
        except AttributeError:
           c_range = [0,1] 

        # image_shape = im.GetDimensions()
        passthrough = True

        # LUT = colormap_utils.make_LUT(colormap=colormap, c_range=(c_range))

    elif type(input_data) is type(vtk.vtkStructuredPoints()):

        # im = input_data

        # c_range = im.GetPointData().GetArray().GetValueRange()

        # image_shape = im.GetDimensions()

        # LUT = colormap_utils.make_LUT(colormap=colormap, c_range=(c_range))
        passthrough = True
        c_range = [0,1]


    elif type(input_data) is type(vtk.vtkVolume()):
        input_data = input_data.GetMapper().GetInput()


        # LUT = colormap_utils.make_LUT(colormap=colormap, c_range=c_range)
        # LUT.SetSaturationRange(1.0, 1.0)
        # LUT.SetTableRange(0,1)
        passthrough = True

    else:


        # vol = vtk.vtkStructuredPoints()
        # vol.SetDimensions(input_data.shape[0], input_data.shape[1], input_data.shape[2])
        # if origin is None:
        #     vol.SetOrigin(spacing[0]*(-input_data.shape[0]/2), spacing[1]*(-input_data.shape[1]/2), (spacing[2]*(-input_data.shape[2]/2)))
        # else:
        #     vol.SetOrigin(origin)
        # vol.SetSpacing(spacing[0], spacing[1], spacing[2])

        scalars = vtk.vtkDoubleArray()
        scalars.SetNumberOfComponents(1)

        # ---------------------------------------------------------------------

        im = vtk.vtkImageData()
        im.SetDimensions(input_data.shape[0], input_data.shape[1], input_data.shape[2])

        im.AllocateScalars(numpy_support.get_vtk_array_type(input_data.dtype), 1)
        im.SetSpacing(spacing[0], spacing[1], spacing[2])

        if origin is None:
            im.SetOrigin((spacing[0]*(-input_data.shape[0]/2)), (spacing[1]*(-input_data.shape[1]/2)), 0)
        else:
            im.SetOrigin(origin)

        v_image = numpy_support.numpy_to_vtk(input_data.T.flat)

        im.GetPointData().SetScalars(v_image)

        if c_range is None:
            c_range = (0, np.max(input_data))

    # ---------------------------------------------------------------------


    contour = vtk.vtkContourFilter()
    contour.SetUseScalarTree(True)


    if shade:
        contour.SetComputeScalars(True)
        contour.SetComputeGradients(True)
        contour.SetComputeNormals(True)
    else:
        contour.SetComputeScalars(False)
        contour.SetComputeGradients(False)
        contour.SetComputeNormals(False)
    # contour = vtk.vtkmContour()
    contour.FastModeOn()

    single_value = False

    if c_values is not None:
        c_values = np.asarray(c_values)
        if np.ndim(c_values) == 0:
            contour.SetValue(0, float(c_values))
            single_value = True
            pass
        elif np.ndim(c_values) == 1:
            c_values.sort()
            for i in range(len(c_values)):
                contour.SetValue(i, float(c_values[i]))
    else:
        if c_number > 1:
            contour.GenerateValues(c_number, c_range[0], c_range[1])
        else:
            contour.SetValue(0, float(c_range[0]))

    if passthrough:
        contour.SetInputData(input_data)
    else:
        contour.SetInputData(im)


    volMapper = vtk.vtkPolyDataMapper()
    volActor = vtk.vtkActor()

    if single_value:
        volActor.GetProperty().SetColor(mesh_color[0], mesh_color[1], mesh_color[2])
        volMapper.ScalarVisibilityOff()
    else:
        contour.ComputeScalarsOn()
    contour.Update()


    # lut.SetTableRange(c_range[0], c_range[1])


    volMapper.SetInputConnection(contour.GetOutputPort())
    if color_override is not None:
        volActor.GetProperty().SetColor(colors.GetColor3d(color_override))
        volMapper.ScalarVisibilityOff()
    else:
        volMapper.ScalarVisibilityOn()
    if c_range is not None:
        lut = colormap_utils.make_LUT(colormap, c_range=c_range)
        volMapper.SetScalarRange(c_range)
        volMapper.SetLookupTable(lut)

        

    volActor.SetMapper(volMapper)
    volActor.GetProperty().EdgeVisibilityOff()
    volActor.GetProperty().SetOpacity(opacity)

    volActor.SetPickable(pickable)

    volActor.contour_filter = contour
    volActor.contour_value = c_range

    volActor.SetObjectName(name)
    volActor.Modified()

    if enabled:
        volActor.SetVisibility(True)
    else:
        volActor.SetVisibility(False)

    if not shade:
        volActor.GetProperty().LightingOff()

    if renderer is None:
        return volActor
    else:
        renderer.AddActor(volActor)
        logger.debug('Contours added')


def add_lines(locations,
              weights=None,
              use_euclidean_as_weight=True,
              renderer=None,
              opacity=1.0,
              color=None,
              colormap='viridis',
              render_type='line',
              tube_radius=0.2,
              tube_resolution=6,
              verbose=False):
    """[Adds a series of lines to the renderer in a similar manner to add_arrows(),
        The lines are rendered in 2D and are much faster to compute]

    Arguments:
        [edge_data] {Numpy 2D array, (N,6)} -- [a 2D array containing the starts & ends of all lines]
        [renderer] {VTK renderer} -- the renderer used by VTK
    Returns:
        [renderer] {VTK renderer} -- the same renderer with lines added

    """

    if locations.shape[1] == 3:
        locations = np.reshape(np.asarray([(x,y) for x,y in zip(locations[:-1], locations[1:])]), [-1, 6])

    colors = vtk.vtkNamedColors()

    linesPolyData = vtk.vtkPolyData()
    lines = vtk.vtkCellArray()
    iterator = 0
    pts = vtk.vtkPoints()
    if locations.shape[1] == 6:
        if verbose:
            logger.debug('Reading rowwise')
        for row in tqdm(locations, desc='Adding Lines', disable=not verbose):

            p0 = row[0:3]
            p1 = row[3:6]


            pts.InsertNextPoint(p0)
            pts.InsertNextPoint(p1)

            line = vtk.vtkLine()
            line.GetPointIds().SetId(0, iterator)

            line.GetPointIds().SetId(1, iterator+1)

            iterator += 2

            lines.InsertNextCell(line)

        linesPolyData.SetLines(lines)

        linesPolyData.SetPoints(pts)

        line_mapper = vtk.vtkPolyDataMapper()

        if vtk.VTK_MAJOR_VERSION <= 5:
            line_mapper.SetInput(linesPolyData)
        else:
            line_mapper.SetInputData(linesPolyData)

        if ((weights is None) and (use_euclidean_as_weight is True)):
            if verbose:
                logger.debug('Using Euclidean distance as weights')
            weights = np.linalg.norm(locations[:, :3]-locations[:, 3:], axis=1)

        if weights is not None:
            scalar_color = vtk.vtkFloatArray()
            scalar_color.SetNumberOfComponents(1)
            scalar_color.SetName("SignedDistances")

            for pointId in range(lines.GetNumberOfCells()):
                scalar_color.InsertNextValue(weights[pointId])

            linesPolyData.GetCellData().SetScalars(scalar_color)

            line_mapper.SetScalarRange(np.min(weights), np.max(weights))

        line_actor = vtk.vtkActor()
        line_actor.SetMapper(line_mapper)
        line_actor.GetProperty().SetOpacity(opacity)
        line_actor.GetProperty().SetLineWidth(tube_radius)

        if color is not None:
            line_actor.GetProperty().SetColor(colors.GetColor3d(color))
        else:
            lut = colormap_utils.make_LUT(colormap=colormap)
            line_mapper.SetLookupTable(lut)

        if render_type == 'tube':
            if verbose:
                logger.debug('Rendering as tubes, may take a while')
            tubefilter = vtk.vtkTubeFilter()
            tubefilter.SetInputData(linesPolyData)
            tubefilter.SetRadius(tube_radius)
            tubefilter.SetNumberOfSides(tube_resolution)
            tubemapper = vtk.vtkPolyDataMapper()
            tubemapper.SetInputConnection(tubefilter.GetOutputPort())

            if weights is not None:

                tubemapper.SetScalarRange(np.min(weights), np.max(weights))

            # else:
            if color is None:
                tubemapper.SetLookupTable(lut)

            line_actor = vtk.vtkActor()
            line_actor.SetMapper(tubemapper)
            line_actor.GetProperty().SetOpacity(opacity)
            if color is not None:
                line_actor.GetProperty().SetColor(colors.GetColor3d(color))
        if renderer is None:
            return line_actor
        else:
            renderer.AddActor(line_actor)

    else:
        if verbose:
            logger.debug("%s", locations.shape)
            logger.debug('Reading row pairwise')
        for i in range(locations.shape[0] - 1):
            arrow_start, arrow_end = locations[i, :], locations[(i + 1), :]
            arrow = add_line(arrow_start, arrow_end, return_line=True)
            renderer.AddActor(arrow)

    return renderer


def add_line(startPoint, endPoint, return_line=False, linewidth=1, linecolor='Black'):
    """[Creates a singular line actor or the linesource]

    Arguments:
        startPoint {[Numpy array (3)]} -- [start point of line]
        endPoint {[Numpy array (3)]} -- [end point of line]

    Keyword Arguments:
        return_line {bool} -- [returns the line as a source, used if multiple lines are added
                                see add_lines() for implementation] (default: {True})

    Returns:
        [actor] {VTK Actor} -- [A VTK actor for the line]
    """

    if return_line:

        pts = vtk.vtkPoints()
        pts.InsertNextPoint(startPoint)
        pts.InsertNextPoint(endPoint)

        line = vtk.vtkLine()
        line.GetPointIds().SetId(0, 0)
        line.GetPointIds().SetId(1, 1)

        return (line, pts)

    lineSource = vtk.vtkLineSource()
    lineSource.SetPoint1(startPoint)
    lineSource.SetPoint2(endPoint)
    lineSource.SetResolution(1)
    

    # Visualize
    colors = vtk.vtkNamedColors()

    mapper = vtk.vtkPolyDataMapper()
    mapper.SetInputConnection(lineSource.GetOutputPort())
    actor = vtk.vtkActor()
    actor.SetMapper(mapper)
    actor.GetProperty().SetLineWidth(linewidth)
    actor.GetProperty().SetColor(colors.GetColor3d(linecolor))

    return actor

 

def add_labels(locations, scalar_vals, precision=1, renderer=None, label_color=[1, 1, 1], text_color=[0, 0, 0], opacity=0.5):

    """Add labels."""
    points = vtk.vtkPoints()
    label = vtk.vtkStringArray()
    label.SetName('label')


    if scalar_vals.dtype == np.dtype('U24'):

        logger.debug('Labels appear to be text')

    for lnum, location in enumerate(locations):
        points.InsertNextPoint(location[0], location[1], location[2])
        try:
            label_val = round(scalar_vals[lnum], precision)
        except TypeError:
            label_val = scalar_vals[lnum]
        if precision == 0:
            label_val = int(label_val)
        label.InsertNextValue(str(label_val))

    polydata = vtk.vtkPolyData()
    polydata.SetPoints(points)
    polydata.GetPointData().AddArray(label)

    hier = vtk.vtkPointSetToLabelHierarchy()
    hier.SetInputData(polydata)
    hier.SetLabelArrayName('label')
    hier.GetTextProperty().SetColor(text_color)

    lmapper = vtk.vtkLabelPlacementMapper()
    lmapper.SetInputConnection(hier.GetOutputPort())

    lmapper.SetShapeToRoundedRect()
    lmapper.SetBackgroundColor(label_color)
    lmapper.SetBackgroundOpacity(opacity)
    lmapper.SetMargin(3)

    lactor = vtk.vtkActor2D()
    lactor.SetMapper(lmapper)

    if renderer is None:
        return lactor
    else:
        renderer.AddActor(lactor)


def add_axes(source_object=None,
              source_renderer=None,
              line_width=3,
              font_size=20,
              bounds=None,
              axes_type='cartesian',
              axes_units='m',
              tick_location='outside',
              minor_ticks=False,
              axes_placement='outer',
              grid_placement='outer',
              flat_labels=True,
              sticky_axes=False,
              draw_grid_planes=False,
              color=[0.1,0.1,0.1],
              name='widgets/axes'):
    """[Adds axes to an actor]

    Arguments:
        source_object {VTK Actor} -- [The actor you want the Axes to be bound to]
        source_renderer {VTK renderer} -- [the renderer used in VTK]

    Returns:
        Axes {VTK widget} -- [The axes specified]
    """

    if axes_type == 'cartesian':
        cubeAxesActor = vtk.vtkCubeAxesActor()

        if source_object is not None:
            cubeAxesActor.SetBounds(source_object.GetBounds())
        else:
            cubeAxesActor.SetBounds(bounds)

        
        if source_renderer is not None:
            cubeAxesActor.SetCamera(source_renderer.GetActiveCamera())

        cubeAxesActor.GetProperty().SetColor(* color)

        cubeAxesActor.SetXTitle('X-Axis')
        cubeAxesActor.SetXUnits(axes_units)
        cubeAxesActor.GetXAxesLinesProperty().SetColor(* color)
        cubeAxesActor.GetTitleTextProperty(0).SetColor(* color)
        cubeAxesActor.GetLabelTextProperty(0).SetColor(* color)

        cubeAxesActor.SetYTitle('Y-Axis')
        cubeAxesActor.SetYUnits(axes_units)
        cubeAxesActor.GetYAxesLinesProperty().SetColor(* color)
        cubeAxesActor.GetTitleTextProperty(1).SetColor(* color)
        cubeAxesActor.GetLabelTextProperty(1).SetColor(* color)

        cubeAxesActor.SetZTitle('Z-Axis')
        cubeAxesActor.SetZUnits(axes_units)
        # cubeAxesActor.GetZAxesLinesProperty().SetColor(* color)
        # cubeAxesActor.GetTitleTextProperty(2).SetColor(* color)
        # cubeAxesActor.GetLabelTextProperty(2).SetColor(* color)

        cubeAxesActor.GetZAxesLinesProperty().SetColor(0,0,0)
        cubeAxesActor.GetTitleTextProperty(2).SetColor(0,0,0)
        cubeAxesActor.GetLabelTextProperty(2).SetColor(0,0,0)

        cubeAxesActor.DrawXGridlinesOn()
        cubeAxesActor.DrawYGridlinesOn()
        cubeAxesActor.DrawZGridlinesOn()

        cubeAxesActor.SetUseBounds(True)

        cubeAxesActor.GetXAxesGridlinesProperty().SetColor(* color)
        cubeAxesActor.GetYAxesGridlinesProperty().SetColor(* color)
        cubeAxesActor.GetZAxesGridlinesProperty().SetColor(* color)

        cubeAxesActor.GetXAxesGridlinesProperty().SetLineWidth(line_width)
        cubeAxesActor.GetYAxesGridlinesProperty().SetLineWidth(line_width)
        cubeAxesActor.GetZAxesGridlinesProperty().SetLineWidth(line_width)

        cubeAxesActor.SetCoordinateSystemToPhysical()

        if vtk.VTK_MAJOR_VERSION > 5:
            if grid_placement == 'outer':
                cubeAxesActor.SetGridLineLocation(cubeAxesActor.VTK_GRID_LINES_FURTHEST)
            elif grid_placement == 'inner':
                cubeAxesActor.SetGridLineLocation(cubeAxesActor.VTK_GRID_LINES_CLOSEST)
            elif grid_placement == 'all':
                cubeAxesActor.SetGridLineLocation(cubeAxesActor.VTK_GRID_LINES_ALL)

        if minor_ticks:
            cubeAxesActor.XAxisMinorTickVisibilityOn()
            cubeAxesActor.YAxisMinorTickVisibilityOn()
            cubeAxesActor.ZAxisMinorTickVisibilityOn()

        else:
            cubeAxesActor.XAxisMinorTickVisibilityOff()
            cubeAxesActor.YAxisMinorTickVisibilityOff()
            cubeAxesActor.ZAxisMinorTickVisibilityOff()

        if tick_location == 'inside':
            cubeAxesActor.SetTickLocationToInside()
        elif tick_location == 'outside':
            cubeAxesActor.SetTickLocationToOutside()
        elif tick_location == 'both':
            cubeAxesActor.SetTickLocationToBoth()

        if axes_placement == 'outer':
            cubeAxesActor.SetFlyModeToOuterEdges()
            cubeAxesActor.SetTickLocationToOutside()
        elif axes_placement == 'inner':
            cubeAxesActor.SetFlyModeToClosestTriad()
        elif axes_placement == 'furthest':
            cubeAxesActor.SetFlyModeToFurthestTriad()
        elif axes_placement == 'all':
            cubeAxesActor.SetFlyModeToStaticEdges()

        # cubeAxesActor.SetUse2DMode(flat_labels)
        # cubeAxesActor.SetUseTextActor3D(True)
        cubeAxesActor.SetStickyAxes(sticky_axes)
        cubeAxesActor.SetCenterStickyAxes(False)

        cubeAxesActor.GetProperty().SetLineWidth(line_width)
        # cubeAxesActor.Update()
        cubeAxesActor.GetProperty().RenderLinesAsTubesOn()
        # cubeAxesActor.GetProperty().SetEdgeVisibility(True)
        # cubeAxesActor.GetProperty().SetInterpolationToPhong()
        # cubeAxesActor.GetProperty().VertexVisibilityOn()
        # cubeAxesActor.SetUse2DMode(True)


        x_properties = cubeAxesActor.GetTitleTextProperty(0)



        x_properties.BoldOn()
        x_properties.ItalicOn()
        x_properties.SetFontSize(font_size)
        x_properties.SetLineOffset(50)
        x_properties.SetVerticalJustificationToTop()
        x_properties.Modified()


        y_properties = cubeAxesActor.GetTitleTextProperty(1)
        y_properties.BoldOn()
        y_properties.ItalicOn()
        y_properties.SetFontSize(font_size)
        y_properties.SetLineOffset(50)
        y_properties.Modified()

        z_properties = cubeAxesActor.GetTitleTextProperty(2)
        z_properties.BoldOn()
        z_properties.ItalicOn()
        z_properties.SetFontSize(font_size)
        z_properties.SetLineOffset(50)
        z_properties.Modified()
    

        if draw_grid_planes:
            cubeAxesActor.DrawXGridpolysOn()
            cubeAxesActor.DrawYGridpolysOn()
            cubeAxesActor.DrawZGridpolysOn()


        # cubeAxesActor.SetUseTextActor3D(2)
        # cubeAxesActor.SetUseTextActor3D(1)
        # cubeAxesActor.SetUseTextActor3D(0)
        # cubeAxesActor.SetUse2DMode(False)
        cubeAxesActor.Modified()
        if name is None:
            name = 'cubeAxes-%i' % np.random.randint(100000)
        cubeAxesActor.SetObjectName(name)

        return cubeAxesActor

    elif axes_type == 'polar':
        # pole = [0, 0, 0]
        polaxes = vtk.vtkPolarAxesActor()
        polaxes.SetMinimumAngle(0.)
        polaxes.SetMaximumAngle(360.)
        polaxes.SetSmallestVisiblePolarAngle(1.)
        polaxes.SetUse2DMode(flat_labels)

        polaxes.SetAutoSubdividePolarAxis(True)
        if source_renderer is not None:
            polaxes.SetCamera(source_renderer.GetActiveCamera())
        polaxes.SetPolarLabelFormat("%6.1f")
        polaxes.GetSecondaryRadialAxesProperty().SetColor(1., 0., 0.)
        polaxes.GetSecondaryRadialAxesTextProperty().SetColor(0., 0., 1.)
        polaxes.GetPolarArcsProperty().SetColor(1., 0., 0.)
        polaxes.GetSecondaryPolarArcsProperty().SetColor(0., 0., 1.)
        polaxes.GetPolarAxisProperty().SetColor(0., 0, 0.)
        polaxes.GetPolarAxisTitleTextProperty().SetColor(0., 0., 0.)
        polaxes.GetPolarAxisLabelTextProperty().SetColor(0., 0., 0.)
        polaxes.SetEnableDistanceLOD(True)
        if name is None:
            name = 'polarAxes-%i' % np.random.randint(100000)
        polaxes.SetObjectName(name)

        if minor_ticks:
            polaxes.SetAxisMinorTickVisibility(1)

        polaxes.SetScreenSize(6.)

        if source_object is not None:
            object_bounds = np.asarray(source_object.GetBounds())
            del_x = object_bounds[1] - object_bounds[0]
            del_y = object_bounds[3] - object_bounds[2]

            max_bound = max(del_x, del_y)
            polaxes.SetMaximumRadius(max_bound/2)

        else:
            polaxes.SetBounds(bounds)

        return polaxes


# def remesh(mesh, subdivisions=1, n_clusters=2000, pre_subdivide=False, max_iter=20, iso_try=1000, verbose=False):

#     # print(type(mesh))

#     if type(mesh) is type(vtk.vtkActor()):

#         if pre_subdivide:

#             subdivider = vtk.vtkAdaptiveSubdivisionFilter()
#             subdivider.SetMaximumNumberOfPasses(subdivisions)
#             subdivider.SetInputData(mesh.GetMapper().GetInput())
#             subdivider.Update()

#             mesh_2 = subdivider.GetOutput()

#             edge_data = mesh_2.GetPolys().GetData()
#             point_data = mesh_2.GetPoints().GetData()

#         else:

#             mesh_2 = mesh.GetMapper().GetInput()
#             edge_data = mesh_2.GetPolys().GetData()
#             point_data = mesh_2.GetPoints().GetData()

#         faces = numpy_support.vtk_to_numpy(edge_data)
#         points = numpy_support.vtk_to_numpy(point_data)

#         faces = faces.reshape(-1,4)

#         npoints = mesh_2.GetNumberOfPoints()

#     if faces.dtype != np.int32:
#         faces = faces.astype(np.int32) 


#     # init steps?
#     return_weighted = True

#     weights = np.array([])

#     if points.dtype == np.float64:
#         weighted_point_func = _clustering.weighted_points_double
#     else:
#         weighted_point_func = _clustering.weighted_points_float

#     _area, _wcent = weighted_point_func(points, faces, weights, return_weighted)

#     _neigh, _nneigh = _clustering.neighbors_from_faces(npoints, faces)

#     _edges = _clustering.edge_id(_neigh, _nneigh)
#     # init end?


#     #subdivision step?
#     """Perform a linear subdivision of a mesh"""
#     new_faces = np.copy(faces)
#     if new_faces.dtype != np.int32:
#         new_faces = new_faces.astype(np.int32)

#     new_points = np.copy(points)
#     if new_points.dtype != np.double:
#         new_points = new_points.astype(np.double)

#     for _ in range(subdivisions):
#         new_points, new_faces = _clustering.subdivision(new_points, new_faces)


#     if verbose:


#     sub_mesh = pv.PolyData(new_points, new_faces)
#     sub_mesh.clean(inplace=True)

#     new_points = sub_mesh.points
#     new_faces = sub_mesh.faces.reshape(-1, 4)

#     if verbose:



#     # re-init?
#     return_weighted = True
#     weights = np.array([])

#     if new_faces.dtype != np.int32:
#         new_faces = new_faces.astype(np.int32)

#     if new_points.dtype == np.float64:
#         weighted_point_func = _clustering.weighted_points_double
#     else:
#         weighted_point_func = _clustering.weighted_points_float

#     new_npoints = new_points.shape[0]

#     _area, _wcent = weighted_point_func(new_points, new_faces, weights, return_weighted)
#     _neigh, _nneigh = _clustering.neighbors_from_faces(new_npoints, new_faces)
#     _edges = _clustering.edge_id(_neigh, _nneigh)

#     # clustering step?

#     clusters, _, nclus = _clustering.cluster(_neigh, _nneigh, n_clusters, _area, _wcent, _edges, max_iter, verbose, iso_try)


#     # begin create mesh? 

#     cnorm = None

#     # begin cluster_centroid

#     null_clusters = np.any(clusters == -1)
#     if null_clusters:
#         clusters = clusters.copy()
#         clusters[clusters == -1] = clusters.max() + 1

#     wval = new_points * _area.reshape(-1, 1)
#     cweight = np.bincount(clusters, weights=_area)
#     cweight[cweight == 0] = 1

#     cval = np.vstack((np.bincount(clusters, weights=wval[:, 0]),
#                       np.bincount(clusters, weights=wval[:, 1]),
#                       np.bincount(clusters, weights=wval[:, 2]))) / cweight

#     if null_clusters:
#         # print('clusters are NULL')
#         cval[:, -1] = np.inf

#     # end cluster_centroid


#     ccent = np.ascontiguousarray(cval.T)

#     rng = np.arange(new_faces.shape[0]).reshape((-1, 1))
#     a = np.hstack((rng, rng, rng)).ravel()
#     b = clusters[new_faces[:, 1:]].ravel()
#     c = np.ones(len(a), dtype='bool')

#     boolmatrix = sparse.csr_matrix((c, (a, b)), dtype='bool')


#     nadjclus = boolmatrix.sum(1)
#     adj = np.array(nadjclus == 3).nonzero()[0]
#     idx = boolmatrix[adj].nonzero()[1]

#     # Append these points and faces
#     new_points = ccent
#     f = idx.reshape((-1, 3))

#     # Remove duplicate faces
#     a = np.sort(f, 1)

#     b = np.ascontiguousarray(a).view(np.dtype((np.void, a.dtype.itemsize * a.shape[1])))
#     _, idx = np.unique(b, return_index=True)

#     f = f[idx]

#     # Create vtk surface
#     triangles = np.empty((f.shape[0], 4), dtype=f.dtype)
#     triangles[:, -3:] = f
#     triangles[:, 0] = 3

#     # end create_mesh

#     new_mesh = add_polyhedron(new_points, triangles[:,1:])

#     return new_mesh


def add_colorbar(actor,
                 interactor=None,
                 title='Values',
                 orientation='vertical',
                 return_widget=True,
                 total_ticks=10,
                 background=True,
                 opacity=1.0):
    """[Adds a colorbar to the interactor]

    Arguments:
        interactor {[VTK Interactor]} -- [the interactor used by VTK]
        title {[string]} -- [the title of the colorbar]
        mapper {[VTK mapper]} -- [the VTK mapper used to grab color values]

    Keyword Arguments:
        orientation {str} -- [orientation of the colorbar] (default: {'vertical'})
        return_widget {bool} -- [returns the colorbar as a widget instead] (default: {True})

    Returns:
        [type] -- [description]
    """

    if isinstance(actor, vtk.vtkScalarBarActor):

        scalar_bar = actor

    else:

        scalar_bar = vtk.vtkScalarBarActor()
        scalar_bar.SetLookupTable(actor.GetMapper().GetLookupTable())
        scalar_bar.GetLabelTextProperty().SetColor(0.0, 0.0, 0.0)
        scalar_bar.GetLabelTextProperty().SetFontFamilyToArial()
        scalar_bar.GetLabelTextProperty().ItalicOff()
        # scalar_bar.GetLabelTextProperty().ShadowOff()
        # scalar_bar.GetLabelTextProperty().FrameOn()
        scalar_bar.GetLabelTextProperty().SetShadowOffset(0,0)
        scalar_bar.GetLabelTextProperty().GetShadowColor((1,1,1))#.SetValue(1,1,1)
        # scalar_bar.GetLabelTextProperty().SetBackgroundOpacity(0.5)
        # scalar_bar.GetLabelTextProperty().SetBackgroundColor(1.0, 1.0, 1.0)

        scalar_bar.SetTitle(title)
        scalar_bar.GetTitleTextProperty().SetColor(0.0, 0.0, 0.0)
        # scalar_bar.SetUnconstrainedFontSize(40)
        scalar_bar.GetTitleTextProperty().SetFontFamilyToArial()
        scalar_bar.GetTitleTextProperty().ShadowOff()
        scalar_bar.GetTitleTextProperty().ItalicOff()
        scalar_bar.AnnotationTextScalingOn()
        scalar_bar.SetVerticalTitleSeparation(10)

        if orientation == 'Horizontal':
            scalar_bar.SetOrientationToHorizontal()
        else:
            scalar_bar.SetOrientationToVertical()
        # scalar_bar.SetWidth(width)
        # scalar_bar.SetHeight(0.1)
        scalar_bar.SetVisibility(1)
        scalar_bar.SetNumberOfLabels(total_ticks)
        scalar_bar.UseOpacityOn()
        if background:
            scalar_bar.DrawBackgroundOn()
            scalar_bar.GetBackgroundProperty().SetOpacity(opacity)
        # scalar_bar.SetWidth(10)
        scalar_bar.SetBarRatio(0.85)


        # scalar_bar.GetPositionCoordinate().SetValue(0.05, 0.01)

    # create the scalar_bar_widget
    if return_widget:
        scalar_bar_widget = vtk.vtkScalarBarWidget()
        scalar_bar_widget.SetInteractor(interactor)
        scalar_bar_widget.SetScalarBarActor(scalar_bar)
        scalar_bar_widget.On()
        scalar_bar_widget.ResizableOn()

        return scalar_bar_widget

    return scalar_bar


def generate_delaunay_space(reference_actor, opacity=0.5, mesh_color='blue'):

    """Execute the generate delaunay space operation."""
    colors = vtk.vtkNamedColors()

    clean_filter = vtk.vtkCleanPolyData()
    clean_filter.SetInputData(reference_actor.GetMapper().GetInput())

    del_filter = vtk.vtkDelaunay3D()
    del_filter.SetInputConnection(clean_filter.GetOutputPort())
    del_mapper = vtk.vtkDataSetMapper()
    del_mapper.SetInputConnection(del_filter.GetOutputPort())
    
    del_actor = vtk.vtkActor()
    del_actor.SetMapper(del_mapper)
    del_actor.GetProperty().SetColor(colors.GetColor3d(mesh_color))
    del_actor.GetProperty().SetOpacity(opacity)

    return del_actor


def reconstruct_surface(points, nbr_sz=None, sample_spacing=None, se_type='contour'):

    # vtkpoints = numpy_support.numpy_to_vtk(points)
    """Execute the reconstruct surface operation."""
    vtkpoints = vtk.vtkPoints()
    for point in points:
        vtkpoints.InsertNextPoint(point)

    
    polydata = vtk.vtkPolyData()
    polydata.SetPoints(vtkpoints)

    clean = False

    if clean:
        cleaner = vtk.vtkCleanPolyData()
        cleaner.SetInputData(polydata)
        cleaner.Update()
        polydata = cleaner.GetOutput()

    logger.debug('Reconstructing surface')

    if se_type == 'poisson':
        normals = vtk.vtkPCANormalEstimation()
        normals.SetInputData(polydata)
        sample_size = int(points.shape[0]/1000)
        if sample_size < 10:
            sample_size = 10
        normals.SetSampleSize(sample_size)
        normals.SetNormalOrientationToGraphTraversal()
        normals.FlipNormalsOff()
        alg = vtk.vtkPoissonReconstruction()
        alg.SetDepth(12)
        alg.SetSetInputConnection(normals.GetOutputPort())

    elif se_type == 'ball':


        bins = 32
        N = points.shape[0]

        distance = vtk.vtkSignedDistance()
        f = 0.1
        x0, x1, y0, y1, z0, z1 = polydata.GetBounds()
        distance.SetBounds(x0-(x1-x0)*f, x1+(x1-x0)*f,
                        y0-(y1-y0)*f, y1+(y1-y0)*f,
                        z0-(z1-z0)*f, z1+(z1-z0)*f)
        if polydata.GetPointData().GetNormals():
            distance.SetInputData(polydata)
        else:
            normals = vtk.vtkPCANormalEstimation()
            normals.SetInputData(polydata)
            normals.SetSampleSize(int(500))
            normals.SetNormalOrientationToGraphTraversal()
            distance.SetInputConnection(normals.GetOutputPort())
            logger.debug("%s %s %s %s", "Recalculating normals for", N, "Points, sample size=", int(N / 50))

        b = polydata.GetBounds()
        diagsize = np.sqrt((b[1] - b[0]) ** 2 + (b[3] - b[2]) ** 2 + (b[5] - b[4]) ** 2)
        radius = diagsize / bins * 5
        distance.SetRadius(radius)
        distance.SetDimensions(bins, bins, bins)
        distance.Update()

        logger.debug("%s %s", "Calculating mesh from points with R =", radius)
        surface = vtk.vtkExtractSurface()
        surface.SetRadius(radius * 0.99)
        surface.HoleFillingOn()
        surface.ComputeNormalsOff()
        surface.ComputeGradientsOff()
        surface.SetInputConnection(distance.GetOutputPort())
        surface.Update()

        logger.debug("%s", surface)
        
        surface_actor = vtk.vtkActor()
        mapper = vtk.vtkPolyDataMapper()
        mapper.SetInputConnection(surface.GetOutputPort())
        mapper.Modified()
        surface_actor.SetMapper(mapper)
        surface_actor.Modified()

        logger.debug("%s", surface_actor)

        return surface_actor

    alg = vtk.vtkSurfaceReconstructionFilter()
    alg.SetInputData(polydata)
    if nbr_sz is not None:
        alg.SetNeighborhoodSize(nbr_sz)
    if sample_spacing is not None:
        alg.SetSampleSpacing(sample_spacing)
    alg.Update()

    logger.debug('Surface reconstructed')

    # connect using ports as this will be slightly faster
    if se_type == 'cubes':
        se = vtk.vtkMarchingCubes()
        se.SetComputeNormals(False)
        se.SetComputeScalars(False)
        se.SetComputeGradients(False)
        se.SetInputConnection(alg.GetOutputPort())
        se.SetValue(0, 0.0)

    elif se_type == 'contour':
        se = vtk.vtkContourFilter()
        se.SetInputConnection(alg.GetOutputPort())
        se.SetValue(0, 0.0)

    elif se_type == 'powercrust':
        se = vtk.vtkPowerCrustSurfaceReconstruction()
        se.SetInputConnection(alg.GetOutputPort())

    surface_actor = vtk.vtkActor()
    mapper = vtk.vtkPolyDataMapper()
    mapper.SetInputConnection(se.GetOutputPort())
    mapper.Modified()
    surface_actor.SetMapper(mapper)
    surface_actor.GetProperty().SetOpacity(0.5)
    surface_actor.Modified()

    return surface_actor


def delaunay2D(input_points, original_points, opacity=1, use_kd_tree=True, delete_weird_triangles=True):

    """Execute the delaunay2 d operation."""
    def check_edge_ratio(cell, area_cutoff=0.01, distance_cutoff=0.8, threshold_type='radius'):

        # edge_1 = cell.GetEdge(0)
        # edge_2 = cell.GetEdge(1)
        # edge_3 = cell.GetEdge(2)

        """Check edge ratio."""
        points = numpy_support.vtk_to_numpy(cell.GetPoints().GetData())

        if threshold_type == 'edge_ratio':

            r1 = np.linalg.norm(points[0,:] - points[1,:])
            r2 = np.linalg.norm(points[0,:] - points[2,:])
            r3 = np.linalg.norm(points[1,:] - points[2,:])

            edge_lengths = np.asarray([r1, r2, r3])

            # min_edge = np.min(edge_lengths)
            max_edge = np.max(edge_lengths)

            if max_edge > distance_cutoff:
                return False
            else:
                return True

        elif threshold_type == 'radius':

            p1 = np.linalg.norm(points[0,:])
            p2 = np.linalg.norm(points[1,:])
            p3 = np.linalg.norm(points[2,:])

            r1 = np.abs(p1-p2)
            r2 = np.abs(p1-p3)
            r3 = np.abs(p2-p3)

            radii = np.asarray([r1, r2, r3])

            max_delta = np.max(radii)

            if max_delta > distance_cutoff:
                return False

            else:
                return True
            
        elif threshold_type == 'area':

            norm = np.cross(points[1,:] - points[0,:], points[2,:] - points[0,:])

            area = np.linalg.norm(norm) / 2

            if area > area_cutoff:
                return False

            else:
                return True
            


    def delete_long_faces(polydata):

        """Delete long faces."""
        total_deletions = 0
        original_size = polydata.GetNumberOfCells()

        cell_array = polydata.GetPolys()
        cell_array.InitTraversal()

        bad_triangles = vtk.vtkCellArray()

        for i in tqdm(range(cell_array.GetNumberOfCells()), desc='Deleting large cells'):
 
            trial_cell = polydata.GetCell(i)


            valid = check_edge_ratio(trial_cell, distance_cutoff=0.8)
            if not valid:

                bad_triangles.InsertNextCell(trial_cell)
                total_deletions += 1

        bad_polydata =  vtk.vtkPolyData()

        # Add the geometry and topology to the polydata
        bad_polydata.SetPolys(bad_triangles)
        bad_polydata.Modified()


        deleter = vtk.vtkRemovePolyData()
        deleter.SetInputData(polydata)
        deleter.AddInputData(bad_polydata)
        deleter.Update()

        polydata2 = deleter.GetOutput()

        logger.debug("%s %s %s %s", 'Original size:', original_size, 'new size:', original_size-total_deletions)

        return polydata2

    input_points = input_points.astype(np.float32)
    original_points = original_points.astype(np.float32)

    vtkpoints = vtk.vtkPoints()
    for point in tqdm(input_points, desc='Inserting points'):
        vtkpoints.InsertNextPoint(point[0], point[1], 0)
    
    polydata = vtk.vtkPolyData()
    polydata.SetPoints(vtkpoints)


    logger.debug('Performing 2D (mercator) Delaunay Triangulation (may take a while)')

    delaunay = vtk.vtkDelaunay2D()
    delaunay.SetInputData(polydata)
    delaunay.Update()

    logger.debug('surface reconstructed')

    surface = vtk.vtkDataSetSurfaceFilter()
    surface.SetInputData(delaunay.GetOutput())
    surface.Update()

    meshpoints = numpy_support.vtk_to_numpy(surface.GetOutput().GetPoints().GetData())
 
    resorted_vtkpoints = vtk.vtkPoints()
    # resorted_points = np.zeros(input_points.shape)
    scalars = np.zeros(meshpoints.shape[0])

    if use_kd_tree:

        logger.debug('using kd-tree for indexing')

        tree = KDTree(input_points)

        logger.debug('tree built, now indexing')
        # i, mp in enumerate(tqdm(meshpoints, desc='Reordering points')):
        distances, indices = tree.query(meshpoints[:,:2], 1)

        for i, index in enumerate(tqdm(indices, desc='Reordering points')):
            resorted_vtkpoints.InsertNextPoint(*original_points[int(index),:])
            scalars[i] = np.linalg.norm(original_points[int(index), :])
            # reordered_positions[i,:] = original_points[mi[0], :]
        

    else:

        for i, mp in enumerate(tqdm(meshpoints, desc='Reordering points')):
            # if np.all(np.isclose(mp, input_points[i,:], rtol=0.0001)):
            #     resorted_vtkpoints.InsertNextPoint(*original_points[i, :])
            #     continue
            # else:
            mi = np.argwhere(np.all(np.isclose(input_points,mp[:2],rtol=0.0001), axis=1))

            if mi.size == 1:
                resorted_vtkpoints.InsertNextPoint(*original_points[mi[0], :])
                scalars[i] = np.linalg.norm(original_points[mi[0], :])
                # reordered_positions[i,:] = original_points[mi[0], :]
            elif mi.size > 1:
                distances  = np.linalg.norm(np.squeeze(original_points[mi]) - mp, axis=1)
                best_match = np.argmin(distances)
                resorted_vtkpoints.InsertNextPoint(*original_points[mi[best_match], :])
                scalars[i] = np.linalg.norm(original_points[mi[best_match], :])
                # reordered_positions[i,:] = original_points[mi[0], :]
            else:
                logger.debug("%s %s", mi, 'no candidates')

    new_mesh = surface.GetOutput()

    new_mesh.SetPoints(resorted_vtkpoints)


    # c_range = (np.nanmin(scalars), np.nanmax(scalars))
    # lut = make_LUT(c_range=c_range)

    new_mesh.GetPointData().SetScalars(numpy_support.numpy_to_vtk(scalars))

    if delete_weird_triangles:
        new_mesh = delete_long_faces(new_mesh)


    mapper = vtk.vtkPolyDataMapper()
    mapper.SetInputData(new_mesh)

 

    mapper.Modified()


    surface_actor = vtk.vtkActor()
    surface_actor.SetMapper(mapper)
    surface_actor.GetProperty().SetOpacity(opacity)
    surface_actor.GetProperty().SetEdgeVisibility(1)
    surface_actor.Modified()


    return surface_actor


def check_cell_validity(cell_bounds, theta=0.0785, phi=0.0785, angle_multiplier=8.0, radial_multiplier=16.0):


    """Check cell validity."""
    cell_size = np.asarray([(cell_bounds[1] - cell_bounds[0]), (cell_bounds[3] - cell_bounds[2]), (cell_bounds[5] - cell_bounds[4])])
    cell_centre = np.asarray([(cell_bounds[1] + cell_bounds[0]), (cell_bounds[3] + cell_bounds[2]), (cell_bounds[5] + cell_bounds[4])])/2
  
    r = np.linalg.norm(cell_centre)
    
    transverse_constraint = np.sqrt((r * (np.sin(theta)))**2 + (r * (np.sin(phi)))**2)

    # radial_constraint = transverse_constraint * radial_multiplier
    
    angle_constraints = transverse_constraint * angle_multiplier

    if np.all(cell_size < angle_constraints):
        return True
    else:

        return False


def make_cone(cone_verts, cone_apex, name='cone', include_end=False, calculate_normals=False, opacity=0.5, mesh_color='purple'):

    """Create cone."""
    face_points = np.zeros((cone_verts.shape[0]+1,3))

    polys = vtk.vtkCellArray()
    if include_end:
        fil = vtk.vtkIdList()

    for c, cone_vert in enumerate(cone_verts):

        face_points[0,:] = cone_apex

        v_id = c + 1
        face_points[v_id,:] = cone_vert
        if include_end:
            fil.InsertNextId(v_id)

        if v_id > 1:
            vil = vtk.vtkIdList()
            vil.InsertNextId(0)
            vil.InsertNextId(v_id)
            vil.InsertNextId(v_id-1)
            polys.InsertNextCell(vil)
    
    vil = vtk.vtkIdList()
    vil.InsertNextId(0)
    vil.InsertNextId(v_id)
    vil.InsertNextId(1)

    polys.InsertNextCell(vil)
    if include_end:
        polys.InsertNextCell(fil)

    cone = vtk.vtkPolyData()
    points = vtk.vtkPoints()
    points.SetData(numpy_support.numpy_to_vtk(face_points))

    cone.SetPoints(points)
    cone.SetPolys(polys)

    cleaner = vtk.vtkCleanPolyData()
    cleaner.SetInputData(cone)
    cleaner.Update()

    triangulation = vtk.vtkTriangleFilter()
    triangulation.SetInputData(cleaner.GetOutput())
    triangulation.Update()

    mapper = vtk.vtkPolyDataMapper()

    if calculate_normals:
        norms = vtk.vtkPolyDataNormals()
        norms.SetInputData(triangulation.GetOutput())
        norms.Update()
        mapper.SetInputData(norms.GetOutput())

    else:
        mapper.SetInputData(triangulation.GetOutput())

    actor = vtk.vtkActor()
    actor.SetObjectName(name)
    actor.SetMapper(mapper)
    actor.GetProperty().SetOpacity(opacity)
    actor.GetProperty().SetColor(vtk.vtkNamedColors().GetColor3d(mesh_color))

    return actor


def delaunay3D(input_points, original_points, opacity=1, use_kd_tree=True):


    """Execute the delaunay3 d operation."""
    def check_edge_ratio(cell, ratio_cutoff=8, distance_cutoff=0.1, threshold_type='radius'):

        # edge_1 = cell.GetEdge(0)
        # edge_2 = cell.GetEdge(1)
        # edge_3 = cell.GetEdge(2)

        """Check edge ratio."""
        if threshold_type == 'edge_ratio':

            points = numpy_support.vtk_to_numpy(cell.GetPoints().GetData())

            r1 = np.linalg.norm(points[0,:] - points[1,:])
            r2 = np.linalg.norm(points[0,:] - points[2,:])
            r3 = np.linalg.norm(points[1,:] - points[2,:])

            edge_lengths = np.asarray([r1, r2, r3])

            # min_edge = np.min(edge_lengths)
            max_edge = np.max(edge_lengths)

            if max_edge > distance_cutoff:
                return False
            else:
                return True

        elif threshold_type == 'radius':

            points = numpy_support.vtk_to_numpy(cell.GetPoints().GetData())


            p1 = np.linalg.norm(points[0,:])
            p2 = np.linalg.norm(points[1,:])
            p3 = np.linalg.norm(points[2,:])

            r1 = np.abs(p1-p2)
            r2 = np.abs(p1-p3)
            r3 = np.abs(p2-p3)

            radii = np.asarray([r1, r2, r3])

            min_radius = np.min(radii)

            if min_radius > distance_cutoff:
                return False

            else:
                return True


    def delete_long_faces(polydata):

        """Delete long faces."""
        total_deletions = 0
        original_size = polydata.GetNumberOfCells()

        for i in tqdm(range(polydata.GetNumberOfCells()), desc='Deleting large cells'):
            trial_cell = polydata.GetCell(i)
            valid = check_edge_ratio(trial_cell)
            # cell_bounds = trial_cell.GetBounds()
            # valid = check_cell_validity(cell_bounds, theta, phi)
            if not valid:
                polydata.DeleteCell(i)
                total_deletions += 1
        polydata.RemoveDeletedCells()

        logger.debug("%s %s %s %s", 'Original size:', original_size, 'new size:', original_size-total_deletions)

            # cell_center = trial_cell.EvaluateLocation()


    input_points = input_points.astype(np.float32)
    original_points = original_points.astype(np.float32)

    vtkpoints = vtk.vtkPoints()
    for point in tqdm(input_points, desc='Inserting points'):
        vtkpoints.InsertNextPoint(point)
    
    polydata = vtk.vtkPolyData()
    polydata.SetPoints(vtkpoints)


    logger.debug('Performing Delaunay Triangulation (may take a while)')

    delaunay = vtk.vtkDelaunay3D()
    delaunay.SetInputData(polydata)
    # delaunay.SetAlpha(alpha)
    delaunay.Update()

    logger.debug('surface reconstructed')

    surface = vtk.vtkDataSetSurfaceFilter()
    surface.SetInputData(delaunay.GetOutput())
    surface.Update()

    meshpoints = numpy_support.vtk_to_numpy(surface.GetOutput().GetPoints().GetData())
 
    logger.debug("%s %s %s", meshpoints.shape, input_points.shape, original_points.shape)
    resorted_vtkpoints = vtk.vtkPoints()
    # resorted_points = np.zeros(input_points.shape)
    scalars = np.zeros(meshpoints.shape[0])
    # reordered_positions = np.zeros((meshpoints.shape[0],3))

    if use_kd_tree:

        logger.debug('using kd-tree for indexing')

        tree = KDTree(input_points)

        logger.debug('tree built, now indexing')
        # i, mp in enumerate(tqdm(meshpoints, desc='Reordering points')):
        distances, indices = tree.query(meshpoints[:,:2], 1)

        for i, index in enumerate(tqdm(indices, desc='Reordering points')):
            resorted_vtkpoints.InsertNextPoint(*original_points[int(index),:])
            scalars[i] = np.linalg.norm(original_points[int(index), :])
            # reordered_positions[i,:] = original_points[mi[0], :]
        

    else:

        for i, mp in enumerate(tqdm(meshpoints, desc='Reordering points')):

            mi = np.argwhere(np.all(np.isclose(input_points,mp,rtol=0.0001), axis=1))

            if mi.size == 1:
                resorted_vtkpoints.InsertNextPoint(*original_points[mi[0], :])
                scalars[i] = np.linalg.norm(original_points[mi[0], :])
                # reordered_positions[i,:] = original_points[mi[0], :]
            elif mi.size > 1:
                distances  = np.linalg.norm(np.squeeze(original_points[mi]) - mp, axis=1)
                best_match = np.argmin(distances)
                resorted_vtkpoints.InsertNextPoint(*original_points[mi[best_match], :])
                scalars[i] = np.linalg.norm(original_points[mi[best_match], :])
                # reordered_positions[i,:] = original_points[mi[0], :]
            else:
                logger.debug("%s %s", mi, 'no candidates')

    new_mesh = surface.GetOutput()

    new_mesh.SetPoints(resorted_vtkpoints)

    mapper = vtk.vtkPolyDataMapper()
    mapper.SetInputData(new_mesh)

 
    c_range = (np.nanmin(scalars), np.nanmax(scalars))
    lut = colormap_utils.make_LUT(c_range=c_range)
    mapper.SetLookupTable(lut)
    mapper.SetScalarRange(c_range)
    # mapper.SetInterpolateBeforeMapping(True)
    new_mesh.GetPointData().SetScalars(numpy_support.numpy_to_vtk(scalars))

    delete_long_faces(new_mesh)

    surface_actor = vtk.vtkActor()

    mapper.Modified()
    surface_actor.SetMapper(mapper)
    surface_actor.GetProperty().SetOpacity(opacity)
    surface_actor.GetProperty().SetEdgeVisibility(1)
    surface_actor.Modified()


    return surface_actor


def display_graph(input_graph, z_scale=1, show_edge_weights=False, show_vertex_labels=False, color_vertices=True, color_edges=True, passthrough=False, representation='3D', background_colors=[[0.7,0.7,0.7,], [0.9,0.9,0.9]], colormap='viridis', vertex_scale_name="Vertex Levels", edge_weight_name='Edge Weights'):


    """Execute the display graph operation."""
    if passthrough:

        strategy = vtk.vtkPassThroughLayoutStrategy()

    else:

        strategy = vtk.vtkSpanTreeLayoutStrategy()
        # strategy = vtk.vtkConeLayoutStrategy()
        # strategy = vtk.vtkCircularLayoutStrategy()


    # strategy = vtk.vtkSimple2DLayoutStrategy()  # some other layout options that seem to work well
    # strategy = vtk.vtkCircularLayoutStrategy()
    # strategy = vtk.vtkFast2DLayoutStrategy()
    # strategy = vtk.vtkClustering2DLayoutStrategy()
    # strategy = vtk.vtkConeLayoutStrategy()

    strategy.SetEdgeWeightField(edge_weight_name)
    strategy.SetWeightEdges(True)

    layout = vtk.vtkGraphLayout()
    layout.SetInputData(input_graph)
    layout.SetLayoutStrategy(strategy)
    layout.SetZRange(z_scale)

    graphLayoutView = vtk.vtkGraphLayoutView()
    theme = vtk.vtkViewTheme()


    graphLayoutView.AddRepresentationFromInput(input_graph)
    graphLayoutView.SetVertexLabelVisibility(show_vertex_labels)
    graphLayoutView.SetLayoutStrategyToPassThrough()
    graphLayoutView.SetEdgeLayoutStrategyToPassThrough()
    graphLayoutView.AddRepresentationFromInputConnection(layout.GetOutputPort())
    # graphLayoutView.SetEdgeLabelArrayName("Edge Labels")
    graphLayoutView.SetEdgeLabelArrayName(edge_weight_name)

    graphLayoutView.SetEdgeLabelVisibility(show_edge_weights)

    if color_vertices:

        graphLayoutView.SetVertexColorArrayName(vertex_scale_name)
        graphLayoutView.SetColorVertices(True)
        vertex_scalar_range = input_graph.GetVertexData().GetArray(vertex_scale_name).GetValueRange()

        vertex_LUT = colormap_utils.make_LUT(c_range=vertex_scalar_range, colormap=colormap)
        theme.SetPointLookupTable(vertex_LUT)

    if color_edges:
        graphLayoutView.SetEdgeColorArrayName(edge_weight_name)
        graphLayoutView.SetColorEdges(color_edges)
        edge_scalar_range = input_graph.GetEdgeData().GetArray(edge_weight_name).GetValueRange()

        edge_LUT = colormap_utils.make_LUT(c_range=edge_scalar_range, colormap=colormap)
        theme.SetCellLookupTable(edge_LUT)
        # theme.SetEdgeLabelColor(edge_LUT)


    def selectionCallback(caller, event):

        """Execute the selection callback operation."""
        sel = caller.GetCurrentSelection()
        node0 = sel.GetNode(0)
        node0_field_type = node0.GetFieldType()
        sel_list0 = caller.GetCurrentSelection().GetNode(0).GetSelectionList()
        node1 = sel.GetNode(1)
        node1_field_type = node1.GetFieldType()
        sel_list1 = caller.GetCurrentSelection().GetNode(1).GetSelectionList()


        if (sel_list0.GetNumberOfTuples() > 0):
            printFieldType(node0_field_type)
            for ii in range(sel_list0.GetNumberOfTuples()):
                logger.debug("%s %s", '\t', sel_list0.GetValue(ii))

        if (sel_list1.GetNumberOfTuples() > 0):
            printFieldType(node1_field_type)
            for ii in range(sel_list1.GetNumberOfTuples()):
                logger.debug("%s %s", '\t', sel_list1.GetValue(ii))

    def printFieldType(field_type):
        """Execute the print field type operation."""
        if field_type == 3:
            logger.debug('Vertices Selected:')
        elif field_type == 4:
            logger.debug('Edges Selected:')
        else:
            logger.debug('Unknown type:')


    # lookupTable = vtk_utils.make_LUT(colormap=colormap, c_range=[np.nanmin(edge_weights), np.nanmax(edge_weights)], nan_color=(0,1,0,1))


    # theme.SetCellLookupTable(lookupTable)
        

    theme.SetVertexLabelColor(0,0,0)
    theme.SetEdgeLabelColor(0,0,0)
    theme.SetLineWidth(3)
    theme.SetPointSize(10)
    theme.SetOutlineColor(vtk.vtkNamedColors().GetColor3d('Black'))
    theme.SetSelectedCellColor(vtk.vtkNamedColors().GetColor3d('Red'))
    theme.SetSelectedPointColor(vtk.vtkNamedColors().GetColor3d('Red'))
    theme.SetPointHueRange(0, 1.0)
    theme.SetPointSaturationRange(0.0, 1.0)
    theme.SetBackgroundColor(background_colors[0])
    theme.SetBackgroundColor2(background_colors[1])


    graphLayoutView.ApplyViewTheme(theme)
    graphLayoutView.SetVertexLabelArrayName("Vertex Labels")
    # graphLayoutView.SetVertexLabelVisibility(show_vertex_IDs)

    graphLayoutView.Update()

    graphLayoutView.ResetCamera()
    if representation == '3D':
        graphLayoutView.SetInteractionModeTo3D()
    elif representation == '2D':
        graphLayoutView.SetInteractionModeTo2D()

    graphLayoutView.GetRenderWindow().SetWindowName('3D Graph Display')

    graphLayoutView.GetRenderWindow().SetLineSmoothing(True)
    graphLayoutView.GetRenderWindow().SetPointSmoothing(True)
    graphLayoutView.GetRenderWindow().SetPolygonSmoothing(True)
    # graphLayoutView.GetRenderWindow().SetFullScreen(True)
    graphLayoutView.GetRenderWindow().SetStereoTypeToSplitViewportHorizontal()
    graphLayoutView.GetRenderWindow().SetForceMakeCurrent()
    graphLayoutView.GetRenderWindow().MakeCurrent()

    graphLayoutView.GetRenderWindow().SetMultiSamples(8)
    
    rep = graphLayoutView.GetRepresentation(0)
    link = rep.GetAnnotationLink()
    link.AddObserver('AnnotationChangedEvent', selectionCallback)

    graphLayoutView.Render()
    graphLayoutView.ResetCamera()
    logger.debug('Tree rendered')
    graphLayoutView.GetInteractor().Start()


def threshold_polydata(polydata, threshold_value=0.0, threshold_type='above', field_name='Overlaps', invert=False,
                       name='widgets/mesh_thresholded', colormap='viridis', enabled=True, opacity=1):
    """[Thresholds a polydata object based on a scalar field]

    Arguments:
        polydata {[vtkPolyData]} -- [the polydata to threshold]
        threshold_value {[float]} -- [the value to threshold at]
        field_name {[str]} -- [the name of the scalar field to use for thresholding]

    Keyword Arguments:
        invert {bool} -- [whether to invert the threshold] (default: {False})

    Returns:
        [vtkPolyData] -- [the thresholded polydata]
    """

    # THRESHOLD_BETWEEN:'ThresholdType'
    # THRESHOLD_LOWER:'ThresholdType'
    # THRESHOLD_UPPER:'ThresholdType'

    thresh = vtk.vtkThreshold()

    if isinstance(polydata, vtk.vtkActor):
        polydata = polydata.GetMapper().GetInput()

    thresh.SetInputData(polydata)


    if not polydata.GetPointData().HasArray(field_name):

        logger.warning(f" {bcolors.WARNING} Field '{field_name}' not found in polydata. Available fields: {bcolors.ENDC}")
        total_fields = polydata.GetPointData().GetNumberOfArrays()
        for i in range(total_fields):
            field = polydata.GetPointData().GetArray(i)
            logger.debug(f"Field {i}: {field.GetName()}")
            logger.debug(f"Field {i} range: {field.GetRange()}")
            logger.debug(f"Field {i} type: {field.GetDataType()}")
            logger.debug(f"Field {i} number of components: {field.GetNumberOfComponents()}")

        # raise ValueError(f"Field '{field_name}' not found in polydata")
        field_name = polydata.GetPointData().GetArray(0).GetName()  # Use the first available field if not found
        logger.debug(f"Using default field '{field_name}' for thresholding")
    
    else:
        # field_array = polydata.GetPointData().GetArray(field_name)
        pass
    
    


    thresh.SetInputArrayToProcess(0, 0, 0, vtk.vtkDataObject.FIELD_ASSOCIATION_POINTS, field_name)

    full_range = polydata.GetPointData().GetArray(field_name).GetRange()

    if threshold_type == 'above':
        thresh.SetThresholdFunction(vtk.vtkThreshold.THRESHOLD_UPPER)
        thresh.SetUpperThreshold(threshold_value)
    elif threshold_type == 'below':
        thresh.SetThresholdFunction(vtk.vtkThreshold.THRESHOLD_LOWER)
        thresh.SetLowerThreshold(threshold_value)
    elif threshold_type == 'between':
        thresh.SetThresholdFunction(vtk.vtkThreshold.THRESHOLD_BETWEEN)
        assert isinstance(threshold_value, (list, tuple)) and len(threshold_value) == 2, "Threshold value must be a list or tuple of two values for 'between' threshold_type"
        assert threshold_value[0] < threshold_value[1], "Lower threshold must be less than upper threshold for 'between' threshold_type"
        thresh.SetLowerThreshold(threshold_value[0])
        thresh.SetUpperThreshold(threshold_value[1])

    if invert:
        thresh.InvertOn()
    else:
        thresh.InvertOff()

    thresh.Update()


    grid_to_poly = vtk.vtkGeometryFilter()
    grid_to_poly.SetMerging(True)
    grid_to_poly.SetInputData(thresh.GetOutput())
    grid_to_poly.Update()

    cleaner = vtk.vtkCleanPolyData()
    cleaner.SetInputConnection(grid_to_poly.GetOutputPort())
    cleaner.Update()

    filter_mapper = vtk.vtkDataSetMapper()
    filter_mapper.SetInputConnection(cleaner.GetOutputPort())
    filter_mapper.GetInput().GetPointData().SetActiveScalars(field_name)
    filter_actor = vtk.vtkActor()
    filter_actor.SetMapper(filter_mapper)
    filter_actor.SetObjectName(name)
    filter_actor.GetProperty().SetOpacity(opacity)

    c_values = filter_mapper.GetInput().GetPointData().GetArray(field_name)

    if c_values is None:

        c_range = (0, 1)  # Default range if field is not found
    else:


        c_range = filter_mapper.GetInput().GetPointData().GetArray(field_name).GetRange()

    lut = colormap_utils.make_LUT(colormap=colormap, c_range=c_range, nan_color=(0,0,1,1))

    filter_mapper.SetLookupTable(lut)
    filter_mapper.SetScalarRange(c_range)




    filter_actor.threshold_filter = thresh
    filter_actor.field_name = field_name
    filter_actor.threshold_value = threshold_value
    filter_actor.threshold_type = threshold_type
    filter_actor.current_range = c_range
    filter_actor.full_range = full_range
    filter_actor.invert = invert

    if enabled:
        filter_actor.SetVisibility(True)
    else:
        filter_actor.SetVisibility(False)


    return filter_actor


def divide_polydata_into_regions(polydata):
    
        # Ensure input is vtkPolyData

    """Execute the divide polydata into regions operation."""
    if isinstance(polydata, vtk.vtkActor):
        polydata = polydata.GetMapper().GetInput()

    # if not isinstance(polydata, vtk.vtkPolyData):
    #     raise ValueError("Input must be a vtkPolyData object.")

    # Create connectivity filter to find disconnected regions

    if isinstance(polydata, vtk.vtkPolyData):

        polydata_copy = vtk.vtkPolyData()
        polydata_copy.DeepCopy(polydata)
    elif isinstance(polydata, vtk.vtkUnstructuredGrid):

        polydata_copy = vtk.vtkUnstructuredGrid()
        polydata_copy.ShallowCopy(polydata)

        grid_to_poly = vtk.vtkGeometryFilter()
        grid_to_poly.SetMerging(True)
        grid_to_poly.SetInputData(polydata_copy)
        grid_to_poly.Update()

        cleaner = vtk.vtkCleanPolyData()
        cleaner.SetInputConnection(grid_to_poly.GetOutputPort())
        cleaner.Update()
        polydata_copy = cleaner.GetOutput()

        

    connectivity_filter = vtk.vtkConnectivityFilter()
    connectivity_filter.SetInputData(polydata_copy)
    connectivity_filter.SetExtractionModeToAllRegions()
    connectivity_filter.ColorRegionsOn()
    connectivity_filter.Update()

    # Assign a different color to each region using a lookup table
    region_array = connectivity_filter.GetOutput().GetCellData().GetArray("RegionId")
    num_regions = int(region_array.GetRange()[1]) + 1 if region_array else 1

    lut = vtk.vtkLookupTable()
    lut.SetNumberOfTableValues(num_regions)
    lut.Build()
    for i in range(num_regions):
        color = matplotlib.cm.get_cmap("tab20")(i % 20)  # cycle through tab20 colormap
        lut.SetTableValue(i, color[0], color[1], color[2], 1.0)


    
    num_regions = connectivity_filter.GetNumberOfExtractedRegions()
    logger.debug(f"Number of connected regions: {num_regions}")

    bounds = connectivity_filter.GetOutput().GetBounds()  # Returns (xmin, xmax, ymin, ymax, zmin, zmax)
    logger.debug(f"Bounds of the polydata: {bounds}")
    # Visualize
    mapper = vtk.vtkDataSetMapper()
    mapper.SetInputConnection(connectivity_filter.GetOutputPort())

    mapper.SetLookupTable(lut)
    mapper.SetScalarModeToUseCellFieldData()
    mapper.SelectColorArray("RegionId")
    mapper.SetScalarRange(0, num_regions - 1)


    mapper.Update()

    actor = vtk.vtkActor()
    actor.SetMapper(mapper)


    # Extract bounds for each region
    bounds_list = []
    for region_id in range(num_regions):

        threshold = vtk.vtkThreshold()
        threshold.SetInputData(connectivity_filter.GetOutput())
        threshold.SetThresholdFunction(vtk.vtkThreshold.THRESHOLD_BETWEEN)
        threshold.SetLowerThreshold(region_id)
        threshold.SetUpperThreshold(region_id)
  
        threshold.SetInputArrayToProcess(
            0, 0, 0, vtk.vtkDataObject.FIELD_ASSOCIATION_CELLS, "RegionId"
        )
        threshold.Update()

        # Convert to polydata (since vtkThreshold outputs vtkUnstructuredGrid)
        geometry_filter = vtk.vtkGeometryFilter()
        geometry_filter.SetInputData(threshold.GetOutput())
        geometry_filter.Update()

        region_polydata = geometry_filter.GetOutput()

        # Now get the bounds of this specific region
        bounds = region_polydata.GetBounds()
        bounds_list.append(list(bounds))

    connected_bounds = merge_bounds(bounds_list)

    bounds_actors = []

    for i, bounds in enumerate(connected_bounds):
        # Create a cube for each connected region
        cube = vtk.vtkCubeSource()
        cube.SetBounds(bounds)
        cube.Update()
        cube_mapper = vtk.vtkPolyDataMapper()
        cube_mapper.SetInputData(cube.GetOutput())
        cube_actor = vtk.vtkActor()
        cube_actor.SetMapper(cube_mapper)
        cube_actor.GetProperty().SetColor(np.random.rand(3))  # Random color for each cube
        cube_actor.GetProperty().SetOpacity(0.5)
        # cube_actor.GetProperty().SetRepresentationToWireframe()
        bounds_actors.append(cube_actor)


    return actor, bounds_actors

def merge_bounds(bounds_list, buffer=0.1):

    """Connects regions in a vtkPolyData object and returns the bounds of each region."""


    logger.debug(f"Number of isolated regions: {len(bounds_list)}")

    def determine_bounds_overlap(bounds1, bounds2, buffer=0.1):

        """given two bounds of size 6, determine if they overlap within a tollerance buffer."""

        def check_overlap(left_base_1, right_base_1, left_base_2, right_base_2, buffer=0.1, verbose=False):
            """Check overlap."""
            if right_base_1 + buffer < left_base_2: # p1 is to the left of p2
                if verbose:
                    logger.debug("%s", bcolors.OKGREEN + "bound 1 is to the left of bound 2" + bcolors.ENDC)
                return False
            
            elif right_base_2 + buffer < left_base_1: # p2 is to the left of p1
                if verbose:
                    logger.debug("%s", bcolors.OKGREEN + "bound 1 is to the right of bound 2" + bcolors.ENDC)
                return False
            
            elif (left_base_1 - buffer) <= left_base_2 and (right_base_1 + buffer) >= left_base_2:
                if verbose:
                    logger.debug("%s", bcolors.WARNING + "bound 1 right side overlaps with bound 2 left side" + bcolors.ENDC)
                return True # p2 left base is inside p1 (or right base of p1 is inside p2)
            
            elif (left_base_2 - buffer)  <= left_base_1 and (right_base_2 + buffer) >= left_base_1:
                if verbose:
                    logger.debug("%s", bcolors.WARNING + "bound 1 left side overlaps with bound 2 right side" + bcolors.ENDC)
                return True # p1 left base is inside p2 (or right base of p2 is inside p1)
            
            elif (left_base_1 - buffer) <= left_base_2 and (right_base_1 + buffer) >= right_base_2:
                if verbose:
                    logger.debug("%s", bcolors.WARNING + "bound 1 is fully surrounds bound 2" + bcolors.ENDC)
                return True # p2 is fully inside p1
            
            elif (left_base_2 - buffer) <= left_base_1 and (right_base_2 + buffer) >= right_base_1:
                if verbose:
                    logger.debug("%s", bcolors.WARNING + "bound 1 is fully inside Peak bound 2" + bcolors.ENDC)
                return True # p1 is fully inside p2

        x_overlap = check_overlap(bounds1[0], bounds1[1], bounds2[0], bounds2[1], buffer=buffer)
        y_overlap = check_overlap(bounds1[2], bounds1[3], bounds2[2], bounds2[3], buffer=buffer)
        z_overlap = check_overlap(bounds1[4], bounds1[5], bounds2[4], bounds2[5], buffer=buffer)

        if x_overlap and y_overlap and z_overlap:
            return True
        else:
            return False

    def iterative_merge(bounds_list, buffer=0.1, shuffle=True):

        """Merges bounds in a list of bounds, returning a new list of merged bounds."""

        merged_bounds = []
        used_indices = set()

        if shuffle:
            np.random.shuffle(bounds_list)

        for i, bounds1 in enumerate(bounds_list):
            if i in used_indices:
                continue

            merged_bound = bounds1


            for j, bounds2 in enumerate(bounds_list):
                if j <= i or j in used_indices:
                    continue

                if determine_bounds_overlap(merged_bound, bounds2, buffer=buffer):
                    # Merge the bounds
                    merged_bound[0] = min(merged_bound[0], bounds2[0])
                    merged_bound[1] = max(merged_bound[1], bounds2[1])
                    merged_bound[2] = min(merged_bound[2], bounds2[2])
                    merged_bound[3] = max(merged_bound[3], bounds2[3])
                    merged_bound[4] = min(merged_bound[4], bounds2[4])
                    merged_bound[5] = max(merged_bound[5], bounds2[5])

                    used_indices.add(j)

            merged_bounds.append(merged_bound)

        return merged_bounds
    
    merged_bounds = iterative_merge(bounds_list, buffer=buffer)
    merged_bounds = iterative_merge(merged_bounds, buffer=buffer)
    merged_bounds = iterative_merge(merged_bounds, buffer=buffer)
    merged_bounds = iterative_merge(merged_bounds, buffer=buffer)
    merged_bounds = iterative_merge(merged_bounds, buffer=buffer)
    merged_bounds = iterative_merge(merged_bounds, buffer=buffer)
    merged_bounds = iterative_merge(merged_bounds, buffer=buffer)
    merged_bounds = iterative_merge(merged_bounds, buffer=buffer)
    merged_bounds = iterative_merge(merged_bounds, buffer=buffer)
    merged_bounds = iterative_merge(merged_bounds, buffer=buffer)
    merged_bounds = iterative_merge(merged_bounds, buffer=buffer)

    logger.debug(f"Total merged bounds: {len(merged_bounds)}")

    return merged_bounds


    


# def main():

#     filepath = folderpath + os.sep + filename

#     compton_array = np.loadtxt(filepath)

#     compton_array = compton_array.reshape(160,160,80)


#     volume = add_volume(compton_array)

#     ren, renwin, iren = create_renderer()

#     ren.AddActor(volume)
#     ren.ResetCamera()
#     renwin.Render()
#     iren.Start()


# def callback_func(caller, timer_event):
#     polyactor.RotateZ(1)
#     renwin.Render()


# if __name__ == "__main__":
#     main()

    


_VOLUME_MAPPERS = {
    "smart": vtk.vtkSmartVolumeMapper,
    "GPU": vtk.vtkGPUVolumeRayCastMapper,
    "CPU": vtk.vtkFixedPointVolumeRayCastMapper,
    "openGL": vtk.vtkOpenGLGPUVolumeRayCastMapper,
}
_VOLUME_BLEND_MODES = {
    "composite": "SetBlendModeToComposite",
    "maximum": "SetBlendModeToMaximumIntensity",
    "minimum": "SetBlendModeToMinimumIntensity",
    "average": "SetBlendModeToAverageIntensity",
    "Additive": "SetBlendModeToAdditive",
    "iso": "SetBlendModeToIsoSurface",
    "slice": "SetBlendModeToSlice",
}


def add_volume(volume, renderer=None, spacing=(1, 1, 1), c_range=None,
               opacity_range=(0, 1), outline=False, colormap='viridis',
               clip_to_range=False, shade=False, blend_mode='composite',
               render_mode='smart', origin=(0, 0, 0), name='Field',
               verbose=False, enabled=True):
    """Volume-render a 3D numpy array (or ``vtkImageData``).

    Colour and opacity ramp linearly over ``c_range`` (default ``0..nanmax``)
    and ``opacity_range``; ``clip_to_range`` clips the values to ``c_range``
    first (on a copy). ``render_mode`` picks the mapper (``smart``, ``GPU``,
    ``CPU``, ``openGL``) and ``blend_mode`` its blending (``composite``,
    ``maximum``, ``minimum``, ``average``, ``Additive``, ``iso``,
    ``slice``). With ``outline`` a black bounding outline is also made.

    Returns the ``vtkVolume`` (``[volume, outline_actor]`` with ``outline``)
    when *renderer* is None; otherwise adds them to *renderer*.

    The Box/Lasso reconstructions and the reconstruction refresh build their
    Compton volumes with it.
    """
    if render_mode not in _VOLUME_MAPPERS:
        raise ValueError(f"render_mode must be one of {sorted(_VOLUME_MAPPERS)}, got {render_mode!r}")
    if blend_mode not in _VOLUME_BLEND_MODES:
        raise ValueError(f"blend_mode must be one of {sorted(_VOLUME_BLEND_MODES)}, got {blend_mode!r}")

    if isinstance(volume, vtk.vtkImageData):
        image = volume
        image.SetSpacing(spacing)
        image.SetOrigin(origin)
        if c_range is None:
            c_range = (0, image.GetScalarRange()[1])
    else:
        volume = np.asarray(volume)
        if clip_to_range and c_range is not None:
            volume = np.clip(volume, c_range[0], c_range[1])
        if c_range is None:
            c_range = (0, np.nanmax(volume))
        image = vtk.vtkImageData()
        image.SetSpacing(spacing)
        image.SetOrigin(origin)
        image.SetDimensions(volume.shape[0], volume.shape[1], volume.shape[2])
        image.GetPointData().SetScalars(numpy_support.numpy_to_vtk(volume.T.ravel(), deep=True))
    logger.debug("add_volume %s: range %s", name, c_range)

    opacity = vtk.vtkPiecewiseFunction()
    opacity.AddPoint(c_range[0], opacity_range[0])
    opacity.AddPoint(c_range[1], opacity_range[1])
    colors = vtk.vtkColorTransferFunction()
    for value, red, green, blue in colormap_utils.make_colormap(c_range=c_range, color=colormap)[:, :4]:
        colors.AddRGBPoint(value, red, green, blue)

    volume_property = vtk.vtkVolumeProperty()
    volume_property.SetColor(colors)
    volume_property.SetScalarOpacity(opacity)
    volume_property.SetShade(bool(shade))
    volume_property.SetInterpolationTypeToNearest()

    mapper = _VOLUME_MAPPERS[render_mode]()
    if render_mode == 'CPU':
        mapper.AutoAdjustSampleDistancesOn()
    getattr(mapper, _VOLUME_BLEND_MODES[blend_mode])()
    mapper.SetInputData(image)

    actor = vtk.vtkVolume()
    actor.SetMapper(mapper)
    actor.SetProperty(volume_property)
    actor.SetObjectName(name)
    actor.SetPickable(False)
    actor.SetVisibility(bool(enabled))

    outline_actor = None
    if outline:
        geometry = vtk.vtkImageDataGeometryFilter()
        geometry.SetInputData(image)
        outline_filter = vtk.vtkOutlineFilter()
        outline_filter.SetInputConnection(geometry.GetOutputPort())
        outline_mapper = vtk.vtkPolyDataMapper()
        outline_mapper.SetInputConnection(outline_filter.GetOutputPort())
        outline_actor = vtk.vtkActor()
        outline_actor.GetProperty().SetColor(0, 0, 0)
        outline_actor.SetMapper(outline_mapper)

    if renderer is None:
        return [actor, outline_actor] if outline else actor
    renderer.AddVolume(actor)
    if outline:
        renderer.AddActor(outline_actor)
    return None


def load_gltf(filename, renderer=None, render_window=None, override_lighting=False,
              opacity=1.0, specular=0.3, ambient=0.5, diffuse=0.5, specular_power=50.0,
              scale=(1, 1, 1), translate=None, rotate=(0, 0, 0), name=None,
              import_method='vtkGLTFImporter'):
    """Load a glTF/GLB file.

    ``import_method='vtkGLTFImporter'`` (needs *render_window*) imports the
    whole scene into the window's first renderer and returns ``{name: actor}``
    for the new, non-empty actors -- named ``name + index`` when *name* is
    given -- with *opacity* (and, with ``override_lighting``, the lighting
    values) applied and, when *translate* is given, a scale / X-Y-Z rotate /
    translate transform. ``'vtkGLTFReader'`` merges the file into one actor,
    returned, or added to *renderer* when one is given.

    The radiation markers are loaded with it.
    """
    import_methods = ('vtkGLTFReader', 'vtkGLTFImporter')
    if import_method not in import_methods:
        raise ValueError(f'import_method must be one of {import_methods}, got {import_method!r}')
    custom_name = name is not None
    if name is None:
        name = os.path.basename(filename)

    if import_method == 'vtkGLTFImporter':
        if render_window is None:
            raise ValueError('render_window must be given when using vtkGLTFImporter')
        logger.debug("Reading %s", filename)
        existing = render_window.GetRenderers().GetFirstRenderer().GetActors()
        existing_actors = [existing.GetItemAsObject(i) for i in range(existing.GetNumberOfItems())]

        importer = vtk.vtkGLTFImporter()
        importer.SetFileName(filename)
        importer.SetRenderWindow(render_window)
        importer.Update()

        actors = importer.GetRenderer().GetActors()
        actor_dict = dict()
        index = 0
        for i in range(actors.GetNumberOfItems()):
            actor = actors.GetItemAsObject(i)
            if actor is None or actor in existing_actors:
                continue
            actor.SetDragable(False)
            actor.GetProperty().SetOpacity(opacity)
            if override_lighting:
                actor.GetProperty().SetSpecular(specular)
                actor.GetProperty().SetSpecularPower(specular_power)
                actor.GetProperty().SetAmbient(ambient)
                actor.GetProperty().SetDiffuse(diffuse)
                actor.GetProperty().SetInterpolationToGouraud()
            if actor.GetMapper().GetInput().GetNumberOfPoints() == 0:
                continue                     # empty node
            if translate is not None:
                transform = vtk.vtkTransform()
                transform.PostMultiply()
                transform.Scale(scale)
                transform.RotateX(rotate[0])
                transform.RotateY(rotate[1])
                transform.RotateZ(rotate[2])
                transform.Translate(translate)       # after the rotation
                actor.SetUserTransform(transform)
            if custom_name:
                actor.SetObjectName(name + str(index))
                actor_dict[name + str(index)] = actor
            else:
                actor_dict[filename + str(index)] = actor
            index += 1
        return actor_dict

    reader = vtk.vtkGLTFReader()
    reader.SetFileName(filename)
    reader.Update()
    geometry = vtk.vtkCompositeDataGeometryFilter()
    geometry.SetInputConnection(reader.GetOutputPort())
    mapper = vtk.vtkPolyDataMapper()
    mapper.SetInputConnection(geometry.GetOutputPort())
    actor = vtk.vtkActor()
    actor.SetMapper(mapper)
    actor.GetProperty().SetOpacity(opacity)
    actor.GetProperty().SetSpecular(specular)
    actor.GetProperty().SetSpecularPower(80.0)
    actor.GetProperty().SetAmbient(ambient)
    actor.GetProperty().SetInterpolationToGouraud()
    if custom_name:
        actor.SetObjectName(name)
    if renderer is None:
        return actor
    renderer.AddActor(actor)
    return None


# Re-exported for compatibility until 1.0; new code imports from radiation.
from .radiation import add_GEANT4_tracks  # noqa: E402
