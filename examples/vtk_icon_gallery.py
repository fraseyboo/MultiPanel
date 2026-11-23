"""Interactive gallery of every packaged VTK vector icon.

Each asset is rendered by the same :class:`VectorButtonWidget` used by
MultiPanel applications, rather than through a raster preview.  Run with::

    python examples/vtk_icon_gallery.py [--dark]

or write one off-screen frame to an image::

    python examples/vtk_icon_gallery.py --screenshot vtk_icons.png [--dark]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from types import SimpleNamespace

import vtk

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from multipanel.containers import Frame  # noqa: E402
from multipanel.controls import VectorButtonWidget  # noqa: E402
from multipanel.core import RenderScheduler  # noqa: E402
from multipanel.layouts import GridLayout, VBoxLayout  # noqa: E402
from multipanel.resources import ICON_ROOT  # noqa: E402
from multipanel.router import EventRouter  # noqa: E402
from multipanel.scrollarea import ScrollArea  # noqa: E402
from multipanel.standard import Label  # noqa: E402
from multipanel.ui_theme import DARK, LIGHT, vtk_tokens  # noqa: E402
from multipanel.units import frac  # noqa: E402

COLUMNS = 6


def vtk_icon_inventory(root=ICON_ROOT):
    """Return the VTK icon paths in stable, alphabetical order."""
    return sorted(Path(root).joinpath("vtk_icons").glob("*.vtk"),
                  key=lambda path: path.stem)


def build(renderer, interactor, columns=COLUMNS):
    icons = vtk_icon_inventory()
    title = Label(renderer, interactor, "MultiPanel VTK icon gallery",
                  bold=True)
    summary = Label(
        renderer, interactor,
        f"{len(icons)} vector assets  •  rendered with VectorButtonWidget",
        muted=True)
    status = Label(renderer, interactor,
                   "Click a vector button to inspect its asset name",
                   muted=True)

    area = ScrollArea(renderer, interactor, object_name="vtk_icon_scroll")
    content_renderer = area.contentRenderer()
    content = Frame(content_renderer, interactor)
    grid = GridLayout(margins=(8, 8, 8, 8), spacing=10)
    buttons = []

    def select(name):
        status.setText(f"Selected: {name}    ({name}.vtk)")

    for index, path in enumerate(icons):
        row, column = divmod(index, columns)
        tile = Frame(content_renderer, interactor)
        button = VectorButtonWidget(
            content_renderer, interactor, input_data=str(path),
            icon_name=path.stem, name=f"icon/{path.stem}",
            hover_text=path.stem, show_background=True)
        button.setFixedSize(42, 42)
        button.clicked.connect(lambda name=path.stem: select(name))
        label = Label(content_renderer, interactor, path.stem,
                      alignment="center", muted=True)
        tile_layout = VBoxLayout(margins=(5, 5, 5, 5), spacing=3)
        tile_layout.addWidget(button, alignment="center")
        tile_layout.addWidget(label)
        tile.setLayout(tile_layout)
        grid.addWidget(tile, row, column)
        buttons.append(button)

    for column in range(columns):
        grid.setColumnStretch(column, 1)
        grid.setColumnMinimumWidth(column, 150)
    content.setLayout(grid)
    area.setWidget(content)

    panel = Frame(renderer, interactor, background=True,
                  geometry=(frac(0.02), frac(0.025),
                            frac(0.96), frac(0.95)))
    panel.setContentsMargins(14, 12, 14, 10)
    layout = VBoxLayout(spacing=6)
    layout.addWidget(title)
    layout.addWidget(summary)
    layout.addWidget(area, stretch=1)
    layout.addWidget(status)
    panel.setLayout(layout)
    panel._icon_buttons = buttons
    return panel, area, icons


def _window(theme, size=(1280, 860), offscreen=False):
    tokens = vtk_tokens(DARK if theme == "dark" else LIGHT)
    renderer = vtk.vtkRenderer()
    renderer.theme = SimpleNamespace(tokens=tokens)
    renderer.SetBackground(*tokens["pane"])
    window = vtk.vtkRenderWindow()
    window.SetSize(*size)
    window.AddRenderer(renderer)
    if offscreen:
        window.SetOffScreenRendering(True)
    interactor = vtk.vtkRenderWindowInteractor()
    interactor.SetRenderWindow(window)
    interactor.SetInteractorStyle(vtk.vtkInteractorStyleTrackballCamera())
    EventRouter.install(interactor)
    return renderer, window, interactor


def render(theme="light", size=(1280, 860)):
    """Render one off-screen gallery frame and return ``vtkImageData``."""
    from multipanel.animation import animations_enabled, set_animations_enabled

    animated = animations_enabled()
    set_animations_enabled(False)
    window = interactor = None
    try:
        renderer, window, interactor = _window(theme, size, offscreen=True)
        panel, _area, _icons = build(renderer, interactor)
        panel.contentLayout().activate()
        RenderScheduler.for_window(window, interactor).flush()
        window.Render()
        grab = vtk.vtkWindowToImageFilter()
        grab.SetInput(window)
        grab.ReadFrontBufferOff()
        grab.Update()
        image = vtk.vtkImageData()
        image.DeepCopy(grab.GetOutput())
        return image
    finally:
        set_animations_enabled(animated)
        if interactor is not None:
            EventRouter.uninstall(interactor)
        if window is not None:
            window.Finalize()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--screenshot", type=Path)
    parser.add_argument("--dark", action="store_true")
    args = parser.parse_args()
    theme = "dark" if args.dark else "light"

    if args.screenshot:
        writer = vtk.vtkPNGWriter()
        writer.SetFileName(str(args.screenshot))
        writer.SetInputData(render(theme))
        writer.Write()
        print(f"wrote {args.screenshot}")
        return

    renderer, window, interactor = _window(theme)
    panel, _area, _icons = build(renderer, interactor)
    panel.contentLayout().activate()
    window.Render()
    interactor.Initialize()
    interactor.Start()


if __name__ == "__main__":
    main()
