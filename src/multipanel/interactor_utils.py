import math

import numpy as np
import vtk
import logging

logger = logging.getLogger(__name__)


class MyInteractorStyle(vtk.vtkInteractorStyleTrackballCamera):
    """[VTK class definitions to allow for more natural camera movement (trackpad style)
        and keybindings for extra functionality (camera movement, printscreens etc.)]

    Arguments:
      expects: renderWindowInteractor, render_camera, renderWindow
    """

    def __init__(self, interactor, camera, render_window, renderer):
        """Initialize the instance."""
        self.interactor = interactor
        super().__init__()
        # self.interactor = self.GetInteractor()
        self.camera = camera
        self.render_window = render_window
        self.renderer = renderer
        self.locators = {}
        self.picker = None

        self.camera_frozen = False
        self.text_edit_mode = False

        self.verbose = False
        self.auto_up = True
        self.AddObserver("LeftButtonPressEvent", self.left_button_press_event)
        self.AddObserver("LeftButtonReleaseEvent", self.left_button_release_event)
        self.AddObserver("MiddleButtonPressEvent", self.middle_button_press_event)
        self.AddObserver("MiddleButtonReleaseEvent", self.middle_button_release_event)
        self.AddObserver("RightButtonPressEvent", self.right_button_press_event)
        self.AddObserver("RightButtonReleaseEvent", self.right_button_release_event)
        self.AddObserver("KeyPressEvent", self.keyPressEvent)
        self.AddObserver("MouseMoveEvent", self.onMouseMove)
 
        # self.AddObserver('AnnotationChangedEvent', selectionCallback)
        # self.AutoAdjustCameraClippingRange(True)

    def camera_zoom_in(self, step=2):
        """Execute the camera zoom in operation."""
        old = np.asarray(self.camera.GetPosition())

        new = old * 0.9

        if self.auto_up:
            up = np.asarray([0, 0, 1])
            self.camera.SetViewUp(up)

        self.camera.SetPosition(tuple(new))


        # self.render_window.ResetCameraClippingRange()

        self.render_window.Render()

    def camera_zoom_out(self, step=2):
        """Execute the camera zoom out operation."""
        old = np.asarray(self.camera.GetPosition())

        new = old * 1.1

        if self.auto_up:
            up = np.asarray([0, 0, 1])
            self.camera.SetViewUp(up)

        self.camera.SetPosition(tuple(new))

        # self.render_window.ResetCameraClippingRange()

        self.render_window.Render()

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

        new_x = old[0] + del_x
        new_y = old[1] + del_y

        hypot_2 = math.hypot(new_x, new_y)

        rescale = hypot_1 / hypot_2

        new = old
        new[0] = new_x * rescale
        new[1] = new_y * rescale

        if self.auto_up:
            up = np.asarray([0, 0, 1])
            self.camera.SetViewUp(up)

        self.camera.SetPosition(tuple(new))
        self.renderer.ResetCamera()

        self.render_window.Render()

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

        new_x = old[0] + del_x
        new_y = old[1] + del_y

        hypot_2 = math.hypot(new_x, new_y)

        rescale = hypot_1 / hypot_2

        new = old
        new[0] = new_x * rescale
        new[1] = new_y * rescale

        if self.auto_up:
            up = np.asarray([0, 0, 1])
            self.camera.SetViewUp(up)

        self.camera.SetPosition(tuple(new))
        self.renderer.ResetCamera()

        self.render_window.Render()

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

        new_z = z_coord + del_z
        new_d = d_coord + del_d

        hypot_2 = math.hypot(new_z, new_d)
        rescale = hypot_1 / hypot_2

        new = old
        new[2] = new_z * rescale
        new_d = new_d * rescale

        rescale_2 = new_d / d_coord

        new[0] = x_coord * rescale_2
        new[1] = y_coord * rescale_2

        if self.auto_up:
            up = np.asarray([0, 0, 1])
            self.camera.SetViewUp(up)

        self.camera.SetPosition(tuple(new))
        self.renderer.ResetCamera()

        self.render_window.Render()

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

        new_z = z_coord + del_z
        new_d = d_coord + del_d

        hypot_2 = math.hypot(new_z, new_d)
        rescale = hypot_1 / hypot_2

        new = old
        new[2] = new_z * rescale
        new_d = new_d * rescale

        rescale_2 = new_d / d_coord

        new[0] = x_coord * rescale_2
        new[1] = y_coord * rescale_2

        if self.auto_up:
            up = np.asarray([0, 0, 1])
            self.camera.SetViewUp(up)

        self.camera.SetPosition(tuple(new))
        self.renderer.ResetCamera()

        self.render_window.Render()

    def screenshot(self):

        """Execute the screenshot operation."""
        w2if = vtk.vtkWindowToImageFilter()
        w2if.SetScale(4)
        w2if.SetInput(self.render_window)
        w2if.Update()

        writer = vtk.vtkPNGWriter()
        writer.SetFileName("screenshot.png")
        writer.SetInputData(w2if.GetOutput())
        writer.Write()

    def keyPressEvent(self, obj, event):

        
        """Execute the key press event operation."""
        key = str(self.interactor.GetKeySym())
        # check here for available keypresses supported by Qt & VTK
        # https://github.com/Kitware/VTK/blob/master/GUISupport/Qt/QVTKInteractorAdapter.cxx
        if self.text_edit_mode:
            logger.debug("%s %s", "In text edit mode, ignoring key press:", key)
            return
        
        return

        if key == "Left":
            self.rotate_clockwise()
        elif key == "Right":
            self.rotate_anticlockwise()
        elif key == "Up":
            self.rotate_upclockwise()
        elif key == "Down":
            self.rotate_downclockwise()
        elif key == "c":
            self.screenshot()
        elif key == "equal":
            self.camera_zoom_in()
        elif key == "minus":
            self.camera_zoom_out()
        elif key == "o":
            self.switch_rendering_mode()
        elif key == "v":
            self.probe_event()
        elif key == "m":
            self.probe_event()
            # Do your custom behavior here
            # Return without calling parent method to block default 'e' behavior
        else:
            # For other keys, fall back to default behavior
            self.OnKeyPress()

    def probe_event(self):
        """Execute the probe event operation."""
        actor = self.get_actor()
        if actor:
            pos3D, probe_val = self.probe_actor(actor)

    def left_button_press_event(self, obj, event):
        """Execute the left button press event operation."""
        if self.verbose:
            logger.debug("left Button pressed")
        self.OnLeftButtonDown()

    def left_button_release_event(self, obj, event):
        """Execute the left button release event operation."""
        # if self.verbose:
        self.camera_frozen = False
        self.OnLeftButtonUp()

    def middle_button_press_event(self, obj, event):
        """Execute the middle button press event operation."""
        if self.verbose:
            logger.debug("Middle Button pressed")
        self.OnMiddleButtonDown()

    def middle_button_release_event(self, obj, event):
        """Execute the middle button release event operation."""
        if self.verbose:
            logger.debug("Middle Button released")
        self.OnMiddleButtonUp()

    def right_button_press_event(self, obj, event):
        """Execute the right button press event operation."""
        if self.verbose:
            logger.debug("Right Button pressed")
        self.OnRightButtonDown()
        # actor = self.get_actor()
        # if actor:
        #     pos3D, probe_val = self.probe_actor(actor)

    def right_button_release_event(self, obj, event):
        """Execute the right button release event operation."""
        if self.verbose:
            logger.debug("Right Button released")
        self.OnRightButtonUp()

    def get_actor(self):
        """Return actor."""
        x, y = self.interactor.GetEventPosition()
        self.render_window = self.interactor.FindPokedRenderer(x, y)
        if not self.picker:
            self.picker = vtk.vtkPropPicker()

        self.picker.PickProp(x, y, self.render_window)

        return self.picker.GetProp3D()

        return actor

    def onMouseMove(self, obj, event):

        """Execute the on mouse move operation."""
        if self.verbose:
            logger.debug("Mouse move event")

        if self.camera_frozen:
            # self.renderer.Render()
            return
        

        return super().OnMouseMove()
    

    # def probe_actor(self, actor):

    #     picked3d = np.array(self.picker.GetPickPosition())
    #     if isinstance(actor, vtk.vtkActor):
    #         actor_name = actor.GetObjectName()

    #         locator = self.locators.get(actor_name)
    #         if locator is None:
    #             locator = widget_utils.build_locator(actor, method='kd_point')
    #             self.locators.update({actor_name: locator})

    #         ID = locator.FindClosestPoint(picked3d)
    #         point_data = actor.GetMapper().GetInput().GetPointData()
    #         point_array = point_data.GetScalars('Overlaps')

    #         if point_array is not None:
    #             point_val = int(point_array.GetTuple(ID)[0])
    #             return picked3d, point_val

    #         else:
    #             return picked3d, 0
    #     else:
    #         return picked3d, 0

    
    def switch_rendering_mode(self):
        """Execute the switch rendering mode operation."""
        projection_mode = self.camera.GetParallelProjection()
        if projection_mode == 1:
            self.camera.SetParallelProjection(False)
            projection_mode = self.camera.GetParallelProjection()
            logger.debug("Camera set to Perspective Projection")
        else:
            self.camera.SetParallelProjection(True)
            projection_mode = self.camera.GetParallelProjection()
            logger.debug("Camera set to Parallel Projection")

        self.render_window.Render()


def add_indicator_cube(interactor):
    """Add indicator cube."""
    colors = vtk.vtkNamedColors()

    axes_actor = vtk.vtkAnnotatedCubeActor()
    axes_actor.SetXPlusFaceText("L")
    axes_actor.SetXMinusFaceText("R")
    axes_actor.SetYMinusFaceText("I")
    axes_actor.SetYPlusFaceText("S")
    axes_actor.SetZMinusFaceText("P")
    axes_actor.SetZPlusFaceText("A")
    axes_actor.GetTextEdgesProperty().SetColor(colors.GetColor3d("White"))
    axes_actor.GetTextEdgesProperty().SetLineWidth(2)
    axes_actor.GetCubeProperty().SetColor(colors.GetColor3d("Blue"))
    marker = vtk.vtkOrientationMarkerWidget()
    marker.SetOrientationMarker(axes_actor)
    marker.SetInteractor(interactor)
    marker.EnabledOn()
    marker.InteractiveOn()
    marker.SetViewport(0.9, 0.0, 1.0, 0.1)

    return marker


def add_camera_widget(render_window):
    """Add camera widget."""
    cam_orient_manipulator = vtk.vtkCameraOrientationWidget()
    cam_orient_manipulator.SetParentRenderer(render_window)
    # Enable the widget.
    cam_orient_manipulator.On()
    return cam_orient_manipulator


def set_passes(render_window, use_ssao=False):
    """Set passes."""
    lightsP = vtk.vtkLightsPass()
    opaqueP = vtk.vtkOpaquePass()
    translucentP = vtk.vtkTranslucentPass()
    volumeP = vtk.vtkVolumetricPass()

    collection = vtk.vtkRenderPassCollection()
    overlayP = vtk.vtkOverlayPass()

    # opaque passes
    if use_ssao:
        bounds = np.asarray(render_window.ComputeVisiblePropBounds())

        b_r = np.linalg.norm(
            [bounds[1] - bounds[0], bounds[3] - bounds[2], bounds[5] - bounds[4]]
        )

        occlusion_radius = b_r * 0.1
        occlusion_bias = b_r * 0.001

        ssaoCamP = vtk.vtkCameraPass()
        ssaoCamP.SetDelegatePass(opaqueP)
        ssaoP = vtk.vtkSSAOPass()
        ssaoP.SetRadius(occlusion_radius)
        ssaoP.SetDelegatePass(ssaoCamP)
        ssaoP.SetBias(occlusion_bias)
        ssaoP.SetBlur(True)
        ssaoP.SetKernelSize(256)

        collection.AddItem(ssaoCamP)
        collection.AddItem(ssaoP)

    collection.AddItem(overlayP)
    collection.AddItem(lightsP)
    collection.AddItem(opaqueP)

    # translucent and volumic passes
    ddpP = vtk.vtkDualDepthPeelingPass()
    ddpP.SetTranslucentPass(translucentP)
    ddpP.SetVolumetricPass(volumeP)
    collection.AddItem(ddpP)

    sequence = vtk.vtkSequencePass()
    sequence.SetPasses(collection)

    fxaaP = vtk.vtkOpenGLFXAAPass()
    fxaaP.SetDelegatePass(sequence)

    camP = vtk.vtkCameraPass()
    camP.SetDelegatePass(fxaaP)

    # overlayP.SetDelegatePass(fxaaP)

    render_window.SetPass(camP)

    return render_window
