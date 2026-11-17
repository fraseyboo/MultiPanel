"""Quick start: a panel with controls and a chart, over a 3D scene.

Run interactively::

    python examples/quickstart.py

or render one frame off-screen to an image::

    python examples/quickstart.py --screenshot quickstart.png
"""
import argparse
import sys
from pathlib import Path

import numpy as np
import vtk

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from multipanel.chartview import ChartView, XYChart  # noqa: E402
from multipanel.config import theme  # noqa: E402
from multipanel.containers import Frame  # noqa: E402
from multipanel.layouts import VBoxLayout  # noqa: E402
from multipanel.router import EventRouter  # noqa: E402
from multipanel.standard import CheckBox, Label, PushButton  # noqa: E402
from multipanel.units import frac, px  # noqa: E402


def build(offscreen=False):
    renderer = vtk.vtkRenderer()
    renderer.theme = theme()                   # UI colour tokens
    renderer.SetBackground(0.12, 0.13, 0.15)
    window = vtk.vtkRenderWindow()
    window.SetOffScreenRendering(offscreen)
    window.SetSize(900, 600)
    window.AddRenderer(renderer)
    interactor = vtk.vtkRenderWindowInteractor()
    interactor.SetRenderWindow(window)
    interactor.SetInteractorStyle(
        vtk.vtkInteractorStyleTrackballCamera())
    EventRouter.install(interactor)            # routes input to the UI

    # Some 3D content.
    source = vtk.vtkSphereSource()
    source.SetThetaResolution(48)
    source.SetPhiResolution(48)
    mapper = vtk.vtkPolyDataMapper()
    mapper.SetInputConnection(source.GetOutputPort())
    sphere = vtk.vtkActor()
    sphere.SetMapper(mapper)
    renderer.AddActor(sphere)

    # A panel of controls and a chart, laid out like a Qt widget.
    panel = Frame(renderer, interactor, background=True,
                  geometry=(frac(0.02), frac(0.25), px(320), px(420)))
    title = Label(renderer, interactor, "Sphere", bold=True)
    wireframe = CheckBox(renderer, interactor, "Wireframe")
    wireframe.toggled.connect(lambda on: (
        sphere.GetProperty().SetRepresentation(1 if on else 2),
        window.Render()))
    chart = XYChart()
    x = np.linspace(0, 10, 200)
    chart.addLine(x, np.exp(-x / 3) * np.cos(2 * x), name="signal")
    chart.axisX().setTitle("Time (s)")
    view = ChartView(renderer, interactor, chart)
    view.setMinimumHeight(px(220))
    reset = PushButton(renderer, interactor, "Reset camera")
    reset.clicked.connect(lambda: (renderer.ResetCamera(), window.Render()))

    column = VBoxLayout(margins=(8, 8, 8, 8), spacing=6)
    column.addWidget(title)
    column.addWidget(wireframe)
    column.addWidget(view, stretch=1)
    column.addWidget(reset)
    panel.setLayout(column)
    renderer.ResetCamera()
    return window, interactor


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--screenshot", type=Path)
    args = parser.parse_args()
    window, interactor = build(offscreen=args.screenshot is not None)
    if args.screenshot:
        from multipanel.core import RenderScheduler

        window.Render()
        RenderScheduler.for_window(window, interactor).flush()
        window.Render()
        grab = vtk.vtkWindowToImageFilter()
        grab.SetInput(window)
        grab.ReadFrontBufferOff()
        writer = vtk.vtkPNGWriter()
        writer.SetFileName(str(args.screenshot))
        writer.SetInputConnection(grab.GetOutputPort())
        writer.Write()
        print(f"wrote {args.screenshot}")
        return
    window.Render()
    interactor.Initialize()
    interactor.Start()


if __name__ == "__main__":
    main()
