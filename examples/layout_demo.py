"""Layouts demo: a material panel built with Frame + Form/VBox/HBox layouts.

Run interactively::

    python examples/layout_demo.py

or render one frame off-screen to an image::

    python examples/layout_demo.py --screenshot layout.png
"""
import argparse
import sys
from pathlib import Path

import numpy as np
import vtk

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from multipanel.containers import Frame  # noqa: E402
from multipanel.controls import (  # noqa: E402
    SliderWidget,
    TextWidget,
    ValueChangerWidget,
    VectorButtonWidget,
)
from multipanel.layouts import FormLayout, HBoxLayout, VBoxLayout  # noqa: E402
from multipanel.router import EventRouter  # noqa: E402
from multipanel.units import frac, px  # noqa: E402


def icon(kind):
    if kind == "play":
        return np.asarray(((0.2, 0.15), (0.85, 0.5), (0.2, 0.85)))
    return np.asarray(((0.2, 0.2), (0.8, 0.2), (0.8, 0.8), (0.2, 0.8)))


def build(renderer, interactor):
    frame = Frame(renderer, interactor, background=True,
                  panel_color=(0.93, 0.94, 0.96),
                  geometry=(frac(0.04), frac(0.45), px(340), px(250)))

    title = TextWidget(renderer, interactor, text="Material", bold=True,
                       scale_text_to_widget=False, text_size=16)
    name = TextWidget(renderer, interactor, text="Lead (Pb)", editable=True,
                      scale_text_to_widget=False, text_size=13)
    density = ValueChangerWidget(renderer, interactor, 11.35, 0.0, 30.0,
                                 step=0.05)
    temperature = ValueChangerWidget(renderer, interactor, 293.0, 0.0,
                                     3000.0, step=1.0)
    fraction = SliderWidget(renderer, interactor, min_value=0, max_value=1,
                            initial_value=0.5, callback=lambda *_: None,
                            show_value=False, title="")
    fraction.apply_flat_style()
    apply_button = VectorButtonWidget(renderer, interactor,
                                      input_data=[icon("play")],
                                      color=(0.2, 0.45, 0.85))
    stop_button = VectorButtonWidget(renderer, interactor,
                                     input_data=[icon("stop")],
                                     color=(0.55, 0.55, 0.6))

    form = FormLayout(spacing=6)
    form.addRow("Name", name)
    form.addRow("Density", density)
    form.addRow("Temperature", temperature)
    form.addRow("Fraction", fraction)

    buttons = HBoxLayout(spacing=8)
    buttons.addStretch()
    buttons.addWidget(stop_button)
    buttons.addWidget(apply_button)

    column = VBoxLayout(margins=(12, 12, 12, 12), spacing=10)
    column.addWidget(title)
    column.addLayout(form)
    column.addStretch()
    column.addLayout(buttons)
    frame.setLayout(column)
    return frame


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--screenshot", type=Path)
    args = parser.parse_args()

    renderer = vtk.vtkRenderer()
    renderer.SetBackground(0.18, 0.2, 0.24)
    window = vtk.vtkRenderWindow()
    window.SetSize(900, 600)
    window.AddRenderer(renderer)
    if args.screenshot:
        window.SetOffScreenRendering(True)
    interactor = vtk.vtkRenderWindowInteractor()
    interactor.SetRenderWindow(window)
    interactor.SetInteractorStyle(vtk.vtkInteractorStyleTrackballCamera())
    EventRouter.install(interactor)

    frame = build(renderer, interactor)
    frame.contentLayout().activate()
    window.Render()

    if args.screenshot:
        grab = vtk.vtkWindowToImageFilter()
        grab.SetInput(window)
        grab.ReadFrontBufferOff()
        grab.Update()
        writer = vtk.vtkPNGWriter()
        writer.SetFileName(str(args.screenshot))
        writer.SetInputConnection(grab.GetOutputPort())
        writer.Write()
        print(f"wrote {args.screenshot}")
        return
    interactor.Initialize()
    interactor.Start()


if __name__ == "__main__":
    main()
