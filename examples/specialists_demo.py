"""Scene specialist widget demo (moved out of ``multipanel.specialists``).

Requires the ``scientific`` extra. Run with ``python examples/specialists_demo.py``.
"""
from vtkmodules.vtkRenderingAnnotation import vtkAnnotatedCubeActor

from multipanel import vtk_utils
from multipanel.colormap_utils import color_to_RGB
from multipanel.controls import TextWidget, ValueChangerWidget


def main():
    """Execute the main operation."""
    actor = vtkAnnotatedCubeActor()
    actor.GetCubeProperty().SetColor(color_to_RGB("PeachPuff"))

    renderer, renderWindow, renderWindowInteractor = vtk_utils.create_renderer(
        use_ssao=True
    )

    # add_compass_widget(renderer, renderWindowInteractor)

    sliding_value_widget = ValueChangerWidget(
        renderer=renderer,
        interactor=renderWindowInteractor,
        min_value=0.0,
        max_value=100.0,
        initial_value=50.0,
        position=(0.5, 0.1),
        # position=(10, 10),
        # size=(200, 50),
        # name='widgets/sliding_value_widget'
    )

    # text_widget = TextWidget(
    #     renderer=renderer,
    #     interactor=renderWindowInteractor,
    #     text="Hello, VTK!",
    #     position=(0.1, 0.8),
    #     size=(0.2, 0.1),
    #     # position=(300, 300),
    #     # size=(200, 100),
    #     # name='widgets/text_widget'
    # )

    text_widget = TextWidget(
        renderer=renderer,
        interactor=renderWindowInteractor,
        text="Edit me!",
        # position=text_position,
        # size=(self.Representation.size[0] - (2 * self.Representation.size[1]), self.Representation.size[1]),
        # grabbable=False,
        # editable=True,
        # force_to_float=True,
        # end_of_edit_callback=end_of_edit_callback,
        text_color=(0, 1, 0)
    )

    bounds = text_widget
    print('Text widget bounds:', bounds)

    renderer.AddActor(actor)
    renderer.SetBackground(color_to_RGB("MidnightBlue"))
    renderer.ResetCamera()

    renderWindow.SetSize(640, 480)
    renderWindow.SetWindowName("CompassWidget")

    renderWindow.Render()

    renderWindowInteractor.Start()


if __name__ == "__main__":
    main()
