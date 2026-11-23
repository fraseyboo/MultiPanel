"""Gallery of every packaged MultiPanel icon.

Run interactively::

    python examples/icon_gallery.py [--dark]

or write one off-screen frame to an image::

    python examples/icon_gallery.py --screenshot icon_gallery.png [--dark]

The gallery discovers the package at runtime, so newly added PNG icons appear
without editing this example.  Click an entry to show which PNG, source SVG,
tintable SVG and VTK assets are available for that name.
"""
from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path
from types import SimpleNamespace

import vtk

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from multipanel.containers import Frame  # noqa: E402
from multipanel.core import RenderScheduler  # noqa: E402
from multipanel.layouts import VBoxLayout  # noqa: E402
from multipanel.models import TableModel  # noqa: E402
from multipanel.resources import ICON_ROOT  # noqa: E402
from multipanel.router import EventRouter  # noqa: E402
from multipanel.standard import Label  # noqa: E402
from multipanel.ui_theme import DARK, LIGHT, vtk_tokens  # noqa: E402
from multipanel.units import frac  # noqa: E402
from multipanel.views import TableView  # noqa: E402

COLUMNS = 6


def icon_inventory(root=ICON_ROOT):
    """Return ``[(name, formats), ...]`` for icons with a PNG preview."""
    root = Path(root)
    names = sorted(path.stem for path in (root / "png_icons").glob("*.png"))
    inventory = []
    for name in names:
        formats = {
            "PNG": (root / "png_icons" / f"{name}.png").is_file(),
            "SVG": (root / "svg_icons" / f"{name}.svg").is_file(),
            "tintable": (root / "tintable" / f"{name}.svg").is_file(),
            "VTK": (root / "vtk_icons" / f"{name}.vtk").is_file(),
        }
        inventory.append((name, formats))
    return inventory


def icon_model(inventory, columns=COLUMNS):
    """Lay the inventory down columns so alphabetical runs read vertically."""
    rows = math.ceil(len(inventory) / columns)
    cells = []
    for row in range(rows):
        line = []
        for column in range(columns):
            offset = column * rows + row
            if offset >= len(inventory):
                line.append({"display": "", "flags": ()})
                continue
            name, formats = inventory[offset]
            available = ", ".join(key for key, present in formats.items()
                                  if present)
            line.append({"display": name, "decoration": name,
                         "toolTip": f"{name} — {available}",
                         "user": (name, formats)})
        cells.append(line)
    return TableModel(cells, headers=[f"Icons {i + 1}" for i in range(columns)])


def build(renderer, interactor):
    inventory = icon_inventory()
    counts = {key: sum(formats[key] for _name, formats in inventory)
              for key in ("PNG", "SVG", "tintable", "VTK")}
    title = Label(renderer, interactor, "MultiPanel icon gallery", bold=True)
    summary = Label(
        renderer, interactor,
        f"{len(inventory)} previewable icons  •  "
        f"{counts['SVG']} SVG  •  {counts['tintable']} tintable  •  "
        f"{counts['VTK']} VTK",
        muted=True)
    status = Label(renderer, interactor,
                   "Click an icon to inspect its packaged formats", muted=True)

    model = icon_model(inventory)
    table = TableView(renderer, interactor, model=model,
                      selection_mode="single")
    table.setHeaderHidden(True)
    table.setStretchLastSection(True)

    def show_icon(index):
        value = index.data("user")
        if not value:
            return
        name, formats = value
        state = "  ".join(f"{key} {'✓' if present else '—'}"
                          for key, present in formats.items())
        status.setText(f"{name}    {state}")

    table.clicked.connect(show_icon)

    panel = Frame(renderer, interactor, background=True,
                  geometry=(frac(0.02), frac(0.025),
                            frac(0.96), frac(0.95)))
    panel.setContentsMargins(14, 12, 14, 10)
    layout = VBoxLayout(spacing=6)
    layout.addWidget(title)
    layout.addWidget(summary)
    layout.addWidget(table, stretch=1)
    layout.addWidget(status)
    panel.setLayout(layout)
    return panel, table, inventory


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
        panel, table, inventory = build(renderer, interactor)
        panel.contentLayout().activate()
        if inventory:
            table.setCurrentIndex(table.model().index(0, 0))
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
    panel, _table, _inventory = build(renderer, interactor)
    panel.contentLayout().activate()
    window.Render()
    interactor.Initialize()
    interactor.Start()


if __name__ == "__main__":
    main()
