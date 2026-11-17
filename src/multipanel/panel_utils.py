import sys
import vtk
import os
import logging

logger = logging.getLogger(__name__)


root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__),".."))

vtk_colors = vtk.vtkNamedColors()


sys.path.append(root_dir)

from . import vtk_utils


def create_3D_text_widget(text, rel_pos, text_size, follow_camera=False, color='black'):
    """Create 3 d text widget."""
    vector_text = vtk.vtkVectorText()
    vector_text.SetText(text)

    mapper = vtk.vtkPolyDataMapper()
    mapper.SetInputConnection(vector_text.GetOutputPort())

    if follow_camera:
        actor = vtk.vtkFollower()
    else:
        actor = vtk.vtkActor()

    actor.SetMapper(mapper)
    actor.SetScale(text_size, text_size, text_size)
    actor.GetProperty().SetColor(1, 1, 1)

    actor.SetPosition(rel_pos)
    actor.GetProperty().SetColor(vtk_colors.GetColor3d(color))

    return actor


# Example callback to handle slider interaction
def slider_callback(obj, event):
    """Handle the slider callback event."""
    value = obj.GetRepresentation().GetValue()
    # If you have a sphere_source, update its resolution here
    # sphere_source.SetThetaResolution(int(value))
    logger.debug(f"Slider value: {value}")

def create_3D_slider_widget(interactor, min_value=3.0, max_value=50.0, initial_value=32,
                            title="Slider Title", slider_position=(-4, 5.9, 0), slider_length=8,
                            text_color='black'):
    """Create 3 d slider widget."""
    slider_rep = vtk.vtkSliderRepresentation3D()
    slider_rep.SetMinimumValue(min_value)
    slider_rep.SetMaximumValue(max_value)
    # Assuming you have a sphere_source defined, otherwise replace with your source
    slider_rep.SetValue(initial_value)  # Replace 32 with your sphere_source.GetThetaResolution() if available
    slider_rep.SetTitleText("Sphere Resolution")
    slider_rep.SetTitleHeight(0.125)
    slider_rep.SetLabelHeight(0.055)
    slider_rep.GetPoint1Coordinate().SetCoordinateSystemToWorld()
    slider_rep.GetPoint1Coordinate().SetValue(slider_position[0], slider_position[1], slider_position[2])
    slider_rep.GetPoint2Coordinate().SetCoordinateSystemToWorld()
    slider_rep.GetPoint2Coordinate().SetValue(slider_position[0] + slider_length, slider_position[1], slider_position[2])
    slider_rep.SetSliderLength(0.075)
    slider_rep.SetSliderWidth(0.05)
    slider_rep.SetEndCapLength(0.05)


    slider_rep.slider_length = slider_length  # Store the length for later use

    slider_widget = vtk.vtkSliderWidget()
    slider_widget.SetInteractor(interactor)
    slider_widget.SetRepresentation(slider_rep)
    slider_widget.SetAnimationModeToJump()
    slider_widget.EnabledOn()

    # slider_rep.GetProperty().SetColor(vtk_colors.GetColor3d(text_color))
    # slider_rep.GetLabelProperty().SetColor(vtk_colors.GetColor3d(text_color))

    # slider_widget.AddObserver(vtk.vtkCommand.InteractionEvent, slider_callback)


    return slider_widget


def button_callback(widget, event, calldata=None):

    """Handle the button callback event."""
    rep = widget.GetRepresentation()
    state = rep.GetState()
    color = rep.GetButtonProp(state).GetProperty().GetColor()
    # self.Actor.GetProperty().SetColor(color)
    logger.debug(f"State: {state}")

def create_3D_button_widget(iren, textures, button_type='elliptical', button_size=1,
                            button_position=(2, 2, 0), colors='red', follow_camera=False):
    

    """Create 3 d button widget."""
    def _create_3D_button_actor(texture_file, button_type='elliptical', button_size=1,
                        button_position=(2, 2, 0), color='red'):
        

        """Create 3 d button actor."""
        if not os.path.exists(texture_file):
            raise FileNotFoundError(f"Texture file does not exist: {texture_file}")
        reader_factory = vtk.vtkImageReader2Factory()
        image_reader = reader_factory.CreateImageReader2(texture_file)

        if not image_reader:
            raise RuntimeError(f"Could not create image reader for file: {texture_file}")
        image_reader.SetFileName(texture_file)
        image_reader.Update()

        dims = image_reader.GetOutput().GetDimensions()

        aspect = float(dims[0]) / float(dims[1])

        texture = vtk.vtkTexture()
        texture.SetInputConnection(image_reader.GetOutputPort())

        if button_type == 'elliptical':
            
            button_source = vtk.vtkEllipticalButtonSource()
            button_source.SetCircumferentialResolution(50)
            button_source.SetShoulderResolution(10)
            button_source.SetTextureResolution(10)
            button_source.SetRadialRatio(1.0)
            button_source.SetShoulderTextureCoordinate(0.0, 0.0)
            button_source.SetTextureDimensions(dims[0], dims[1])
            button_source.SetTextureStyleToProportional()
            button_source.SetWidth(aspect * button_size)
            button_source.SetHeight(button_size)
            button_source.SetDepth(button_size * 0.1)
            button_source.SetCenter(* button_position)

        elif button_type == 'rectangular':
            
            button_source = vtk.vtkRectangularButtonSource()
            button_source.SetShoulderTextureCoordinate(0.0, 0.0)
            button_source.SetTextureDimensions(dims[0], dims[1])
            button_source.SetTextureStyleToProportional()
            button_source.SetWidth(aspect * button_size)
            button_source.SetHeight(button_size)
            button_source.SetBoxRatio(1)
            button_source.SetTextureHeightRatio(1.1)
            button_source.SetDepth(0.1 * button_size)
            button_source.SetCenter( * button_position)
            button_source.SetTwoSided(True)

        button_mapper = vtk.vtkPolyDataMapper()
        button_mapper.SetInputConnection(button_source.GetOutputPort())


        button_actor = vtk.vtkActor()
        button_actor.SetDragable(False)
        button_actor.SetMapper(button_mapper)
        button_actor.SetTexture(texture)
        button_actor.GetProperty().SetColor(vtk_colors.GetColor3d(color))
        button_actor.GetProperty().SetAmbient(0.9)
        button_actor.GetProperty().SetDiffuse(0.1)
        button_actor.GetProperty().SetSpecular(0.1)


        return button_actor

    # Create the widget and its representation.

    total_states = len(textures)

    button_representation = vtk.vtkProp3DButtonRepresentation()
    button_representation.SetNumberOfStates(total_states)

    if not isinstance(colors, list):
        colors = [colors] * total_states

    for state, texture_file in enumerate(textures):
        if not os.path.exists(texture_file):
            raise FileNotFoundError(f"Texture file does not exist: {texture_file}")
        button_actor = _create_3D_button_actor(texture_file, button_type=button_type,
                                                button_size=button_size,
                                                button_position=button_position,
                                                color=colors[state])
        button_representation.SetButtonProp(state, button_actor)


    if follow_camera:
        button_representation.FollowCameraOn()
    else:
        button_representation.FollowCameraOff()



    button_representation.HighlightStateType = vtk.vtkProp3DButtonRepresentation.HighlightHovering

    button_representation.Modified()

    button_widget = vtk.vtkButtonWidget()
    button_widget.SetInteractor(iren)
    button_widget.SetRepresentation(button_representation)
    button_widget.AddObserver(vtk.vtkCommand.StateChangedEvent, button_callback)
    button_widget.SetEnabled(1)

    return button_widget


def unormalise_panel_positions(coordinates, panel_actor, delta=0.001):

    """Execute the unormalise panel positions operation."""
    panel_x_bounds = panel_actor.GetBounds()[0:2]
    panel_y_bounds = panel_actor.GetBounds()[2:4]
    panel_z_bounds = panel_actor.GetBounds()[4:6]

    panel_x_size = panel_x_bounds[1] - panel_x_bounds[0]
    panel_y_size = panel_y_bounds[1] - panel_y_bounds[0]

    normalised_coordinates = []
    for coord in coordinates:
        x = coord[0] * panel_x_size + panel_x_bounds[0]
        y = coord[1] * panel_y_size + panel_y_bounds[0]
        z = panel_z_bounds[1] + delta
        normalised_coordinates.append((x, y, z))
    return normalised_coordinates


def create_3D_panel(renderer, interactor, panel_size=(0.1, 0.1, 0.005), panel_position=(0, 0, 0)):


    """Create 3D panel."""
    panel_source = vtk.vtkCubeSource()
    panel_source.SetXLength(panel_size[0])
    panel_source.SetYLength(panel_size[1])
    panel_source.SetZLength(panel_size[2])
    panel_source.SetCenter(panel_position[0], panel_position[1], panel_position[2])

    panel_mapper = vtk.vtkPolyDataMapper()
    panel_mapper.SetInputConnection(panel_source.GetOutputPort())

    panel_actor = vtk.vtkActor()
    panel_actor.SetObjectName("Interactive3DPanel")
    panel_actor.SetMapper(panel_mapper)
    panel_actor.GetProperty().SetColor(0.8, 0.8, 0.8)
    panel_actor.GetProperty().SetAmbient(0.9)
    panel_actor.GetProperty().SetDiffuse(0.1)
    panel_actor.GetProperty().SetSpecular(0.1)


    # Button positions relative to panel center
    # relative_button_positions = [(0.1, 0.5, 0.02), (0.5, 0.5, 0.02), (0.8, 0.5, 0.02)]
    relative_button_positions = [(0.8, 0.2, 0.15), (0.8, 0.5, 0.15), (0.8, 0.8, 0.15)]
    # relative_text_positions = [(-1.5, 1.6, 0.15), (0.0, 1.6, 0.15), (1.5, 1.6, 0.15)]
    relative_text_positions = [(0.1, 0.2, 0.15), (0.1, 0.5, 0.15), (0.1, 0.8, 0.15)]

    relative_slider_positions = [(-1.5, 0.1, 0.15)]


    relative_button_positions = unormalise_panel_positions(relative_button_positions, panel_actor)
    relative_text_positions = unormalise_panel_positions(relative_text_positions, panel_actor)
    relative_slider_positions = unormalise_panel_positions(relative_slider_positions, panel_actor)

    

    # buttons = []
    panel_widgets = []

    for rel_pos in relative_button_positions:
        # button, actor = create_3D_button_widget(interactor)


        button_widget = create_3D_button_widget(interactor,
            textures=[
                os.path.join(os.path.dirname(__file__), "icons", "png_icons",
                             f"{name}.png")
                for name in ("cube", "sphere", "cylinder")
            ],
            button_type='rectangular',
            button_size=panel_size[0] * 0.1,
            
            button_position=rel_pos,
            colors=['red', 'green', 'blue'],
            follow_camera=False
        )


        # buttons.append(button)
        panel_widgets.append((button_widget, rel_pos))

    # for rel_pos in relative_slider_positions:
    #     # Create a slider widget
    #     slider = create_3D_slider_widget(interactor, min_value=3.0, max_value=50.0, initial_value=32,
    #                                 title="Sphere Resolution", slider_position=rel_pos, slider_length=2)

    #     panel_widgets.append((slider, rel_pos))

    # Text creation


    for i, rel_pos in enumerate(relative_text_positions):
        text = create_3D_text_widget(f"Button {i+1}", rel_pos, text_size=0.1 * panel_size[0])
        panel_widgets.append((text, rel_pos))
        renderer.AddActor(text)

    # Transform for the panel
    panel_transform = vtk.vtkTransform()
    panel_actor.SetUserTransform(panel_transform)

    panel_actor.panel_elements = panel_widgets
    panel_actor.panel_transform = panel_transform


    return panel_actor


def update_attached_elements(panel_actor):

    """Update attached elements."""
    panel_widgets = panel_actor.panel_elements
    panel_transform = panel_actor.panel_transform


    for widget, rel_pos in panel_widgets:
        pos = panel_transform.TransformPoint(rel_pos)
        rot = panel_transform.GetOrientation()

        if isinstance(widget, vtk.vtkButtonWidget):
            rep = widget.GetRepresentation()
            for state in range(10):
                prop = rep.GetButtonProp(state)
                if prop:
                    prop.SetPosition(pos)
                    prop.SetOrientation(rot)
                else:
                    break
        elif isinstance(widget, vtk.vtkSliderWidget):
            rep = widget.GetRepresentation()
            if isinstance(rep, vtk.vtkSliderRepresentation3D):
                slider_length = rep.slider_length
                rep.GetPoint1Coordinate().SetValue(pos[0], pos[1], pos[2])
                pos2 = panel_transform.TransformPoint(rel_pos[0] + slider_length, rel_pos[1], rel_pos[2])
                rep.GetPoint2Coordinate().SetValue(pos2[0], pos2[1], pos2[2])


            else:
                logger.warning(f"Unexpected representation type: {type(rep)}")
        elif hasattr(widget, "SetOrientation") and hasattr(widget, "SetPosition"):
            widget.SetPosition(pos)
            widget.SetOrientation(rot)
        else:
            widget.SetPosition(pos)


class PanelDragInteractorStyle(vtk.vtkInteractorStyleTrackballCamera):
    def __init__(self, panel):
        """Initialize the instance."""
        self.AddObserver("LeftButtonPressEvent", self.on_press)
        self.AddObserver("LeftButtonReleaseEvent", self.on_release)
        self.AddObserver("MouseMoveEvent", self.on_move)
        self.AddObserver("KeyPressEvent", self.on_key_press)
        self.dragging = False
        self.last_pos = None
        self.panel_transform = panel.panel_transform
        self.panel_actor = panel

    def on_press(self, obj, event):
        """Handle press."""
        click_pos = self.GetInteractor().GetEventPosition()
        self.last_pos = click_pos
        self.dragging = True
        self.OnLeftButtonDown()
        return
    
    def on_key_press(self, obj, event):
        """Handle key press."""
        key = self.GetInteractor().GetKeySym()
        t = vtk.vtkTransform()
        
        t.DeepCopy(self.panel_transform)

        if key == "Left":
            t.RotateY(-10)
        elif key == "Right":
            t.RotateY(10)
        elif key == "Up":
            t.Translate(0, 0.2, 0)
        elif key == "Down":
            t.Translate(0, -0.2, 0)
        elif key == "a":
            t.Translate(-0.2, 0, 0)
        elif key == "d":
            t.Translate(0.2, 0, 0)
        elif key == "w":
            t.Translate(0, 0, -0.2)
        elif key == "s":
            t.Translate(0, 0, 0.2)

        
        self.panel_transform.SetMatrix(t.GetMatrix())
        update_attached_elements(self.panel_actor)
        # render_window.Render()


    def on_release(self, obj, event):
        """Handle release."""
        self.dragging = False
        # self.OnLeftButtonUp()
        return

    def on_move(self, obj, event):
        """Handle move."""
        if not self.dragging:
            return

        last_x, last_y = self.last_pos
        x, y = self.GetInteractor().GetEventPosition()
        

        dx = (x - last_x) * 0.01
        dy = (y - last_y) * 0.01

        # Move panel
        t = vtk.vtkTransform()
        t.DeepCopy(self.panel_transform)
        t.Translate(dx, dy, 0)

        self.panel_transform.SetMatrix(t.GetMatrix())
        update_attached_elements(self.panel_actor)

        self.last_pos = (x, y)
        self.GetInteractor().GetRenderWindow().GetRenderers().GetFirstRenderer().ResetCameraClippingRange()
        self.GetInteractor().GetRenderWindow().Render()
        return
