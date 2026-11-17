"""In-scene 3D panel demo (moved out of ``multipanel.panel_utils``).

Run with ``python examples/panel_3d_demo.py``.
"""
import vtk

from multipanel import vtk_utils
from multipanel.panel_utils import PanelDragInteractorStyle, create_3D_panel


def add_test_actor(ren):


    """Add test actor."""
    source = vtk.vtkSuperquadricSource()
    source.SetPhiResolution(64)
    source.SetThetaResolution(64)
    source.SetThetaRoundness(1.5)
    source.SetThickness(1.5)
    source.SetSize(2)
    source.Update()

    mapper = vtk.vtkPolyDataMapper()
    mapper.SetInputConnection(source.GetOutputPort())

    actor = vtk.vtkActor()
    actor.SetMapper(mapper)

    actor.GetProperty().SetOpacity(0.5)

    ren.AddActor(actor)


def main():




    """Execute the main operation."""
    renderer, render_window, interactor = vtk_utils.create_renderer(background_color=[0.03, 0.03, 0.15])
# renderer, render_window, interactor = vtk_utils.create_renderer(use_ssao=True, background_color=[0.6, 0.6, 0.6, 0.9, 0.9, 0.9])

    add_test_actor(renderer)


    panel_actor = create_3D_panel(renderer, interactor, panel_size=(0.1, 0.1, 0.02))




    # # Set interactor style
    style = PanelDragInteractorStyle(panel_actor)
    interactor.SetInteractorStyle(style)



    renderer.AddActor(panel_actor)
    # Start
    renderer.ResetCamera()
    renderer.Render()
    render_window.Render()
    interactor.Start()


if __name__ == "__main__":

    main()
