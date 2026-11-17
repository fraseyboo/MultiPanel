"""A scroll area inside a panel: clipped content, scroll bar, wheel.

Run interactively::

    python examples/scroll_demo.py [--dark]

or write one off-screen frame (scrolled part-way) to an image::

    python examples/scroll_demo.py --screenshot scroll.png [--dark]
"""
import argparse
import sys
from pathlib import Path
from types import SimpleNamespace

import vtk

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from multipanel.containers import Frame  # noqa: E402
from multipanel.layouts import HBoxLayout, VBoxLayout  # noqa: E402
from multipanel.router import EventRouter  # noqa: E402
from multipanel.scrollarea import ScrollArea  # noqa: E402
from multipanel.standard import CheckBox, ComboBox, Label, PushButton  # noqa: E402
from multipanel.ui_theme import DARK, LIGHT, vtk_tokens  # noqa: E402
from multipanel.units import frac, px  # noqa: E402

MATERIALS = ["Air", "Water", "Lead", "Tungsten", "Concrete", "Polyethylene",
             "Borated polyethylene", "Steel 304", "Aluminium", "Copper",
             "Graphite", "Uranium dioxide", "Zirconium", "Cadmium", "Boron",
             "Lithium fluoride", "Iron", "Nickel", "Titanium", "Glass"]


def build(renderer, interactor):
    panel = Frame(renderer, interactor, background=True,
                  geometry=(frac(0.05), frac(0.12), px(300), px(420)))
    panel.setContentsMargins(12, 12, 12, 12)
    area = ScrollArea(renderer, interactor)
    content = Frame(area.contentRenderer(), interactor)
    rows = VBoxLayout(spacing=6)
    for index, name in enumerate(MATERIALS):
        rows.addWidget(CheckBox(area.contentRenderer(), interactor, name,
                                checked=index % 3 == 0))
    shape = ComboBox(area.contentRenderer(), interactor)
    shape.addItems(["Sphere", "Box", "Cylinder"])
    rows.addWidget(shape)
    content.setLayout(rows)
    area.setWidget(content)

    buttons = HBoxLayout(spacing=8)
    buttons.addStretch()
    buttons.addWidget(PushButton(renderer, interactor, "Apply", default=True))
    column = VBoxLayout(spacing=10)
    column.addWidget(Label(renderer, interactor, "Materials in scene",
                           bold=True))
    column.addWidget(area, stretch=1)
    column.addLayout(buttons)
    panel.setLayout(column)
    return panel, area


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--screenshot", type=Path)
    parser.add_argument("--dark", action="store_true")
    args = parser.parse_args()
    if args.screenshot:
        from multipanel.animation import set_animations_enabled

        set_animations_enabled(False)
    tokens = vtk_tokens(DARK if args.dark else LIGHT)
    renderer = vtk.vtkRenderer()
    renderer.theme = SimpleNamespace(tokens=tokens)
    renderer.SetBackground(*tokens["pane"])
    window = vtk.vtkRenderWindow()
    window.SetSize(700, 520)
    window.AddRenderer(renderer)
    if args.screenshot:
        window.SetOffScreenRendering(True)
    interactor = vtk.vtkRenderWindowInteractor()
    interactor.SetRenderWindow(window)
    interactor.SetInteractorStyle(vtk.vtkInteractorStyleTrackballCamera())
    EventRouter.install(interactor)
    panel, area = build(renderer, interactor)
    panel.contentLayout().activate()
    if args.screenshot:
        from multipanel.core import RenderScheduler

        RenderScheduler.for_window(window, interactor).flush()
        area.scrollTo(130, animated=False)
        window.Render()
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
    window.Render()
    interactor.Initialize()
    interactor.Start()


if __name__ == "__main__":
    main()
