"""Item views in a splitter: a 10,000-row list, a scene tree and a table.

Run interactively::

    python examples/views_demo.py [--dark]

or write one off-screen frame to an image::

    python examples/views_demo.py --screenshot views.png [--dark]

Click, Ctrl-click and Shift-click select; the arrow keys move (Right/Left
open and close tree branches); the wheel scrolls; drag a table header
edge to resize a column; drag the bars between the views to resize them.
Selecting materials in the list shows them in
the status line.
"""
import argparse
import sys
from pathlib import Path
from types import SimpleNamespace

import vtk

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from multipanel.containers import Frame  # noqa: E402
from multipanel.hierarchy import HierarchyNode  # noqa: E402
from multipanel.layouts import VBoxLayout  # noqa: E402
from multipanel.models import (  # noqa: E402
    CHECKED, UNCHECKED, ListModel, TableModel, TreeModel,
)
from multipanel.router import EventRouter  # noqa: E402
from multipanel.splitter import Splitter  # noqa: E402
from multipanel.standard import Label  # noqa: E402
from multipanel.ui_theme import DARK, LIGHT, vtk_tokens  # noqa: E402
from multipanel.units import frac, px  # noqa: E402
from multipanel.views import ListView, TableView, TreeView  # noqa: E402

MATERIALS = ["Air", "Water", "Lead", "Tungsten", "Concrete", "Polyethylene",
             "Steel 304", "Aluminium", "Copper", "Graphite"]
COLOURS = [(0.62, 0.80, 0.95), (0.25, 0.55, 0.90), (0.45, 0.47, 0.55),
           (0.30, 0.30, 0.36), (0.70, 0.68, 0.62), (0.90, 0.88, 0.80),
           (0.60, 0.63, 0.68), (0.80, 0.82, 0.86), (0.85, 0.50, 0.30),
           (0.20, 0.20, 0.22)]


def material_model(count=10000):
    rows = []
    for i in range(count):
        name = MATERIALS[i % len(MATERIALS)]
        rows.append({"display": f"{name} #{i}", "user": i,
                     "decoration": COLOURS[i % len(COLOURS)],
                     "checkState": CHECKED if i % 4 == 0 else UNCHECKED,
                     "toolTip": f"{name}, material {i}"})
    return ListModel(rows)


def scene_model():
    cells = HierarchyNode("Cells", expanded_by_default=True, children=[
        HierarchyNode(f"Cell {i}", value=i) for i in range(1, 7)])
    surfaces = HierarchyNode("Surfaces", children=[
        HierarchyNode(name) for name in ("Plane", "Sphere", "Cylinder")])
    lead = HierarchyNode("Lead", expanded_by_default=True, children=[
        HierarchyNode("Pb-206"), HierarchyNode("Pb-207"),
        HierarchyNode("Pb-208")])
    materials = HierarchyNode("Materials", expanded_by_default=True,
                              children=[lead, HierarchyNode("Water")])
    model = TreeModel([cells, surfaces, materials])
    model.setData(model.index(0), "atom", "decoration")
    model.setData(model.index(2), "array", "decoration")
    return model


def cell_model():
    rows = [(f"Cell {i}", MATERIALS[i % len(MATERIALS)],
             round(0.5 + 1.37 * i, 2), f"importance n=1, region {i % 3}")
            for i in range(1, 61)]
    return TableModel(rows, headers=("Cell", "Material", "Density",
                                     "Comment"))


def build(renderer, interactor):
    panel = Frame(renderer, interactor, background=True,
                  geometry=(frac(0.03), frac(0.04), frac(0.94), frac(0.92)))
    panel.setContentsMargins(12, 12, 12, 12)
    materials = material_model()
    status = Label(renderer, interactor, "10,000 materials")

    # The three columns sit in a splitter: drag the bars between them.
    columns = Splitter(renderer, interactor, "horizontal")
    columns.setHandleWidth(12)
    views = []
    for title, view in (
            ("Materials (10,000 rows)",
             ListView(renderer, interactor, model=materials)),
            ("Scene", TreeView(renderer, interactor, model=scene_model())),
            ("Cells", TableView(renderer, interactor, model=cell_model()))):
        column = VBoxLayout(spacing=6)
        column.addWidget(Label(renderer, interactor, title, bold=True))
        column.addWidget(view, stretch=1)
        holder = Frame(renderer, interactor)
        holder.setMinimumSize(px(120), px(80))
        holder.setLayout(column)
        columns.addWidget(holder)
        views.append(view)
    columns.setSizes([1, 1, 2])
    columns.setStretchFactor(2, 1)

    def show_selection(*_args):
        rows = views[0].selectedIndexes()
        names = ", ".join(index.data() for index in rows[:3])
        more = f" and {len(rows) - 3} more" if len(rows) > 3 else ""
        status.setText(f"Selected: {names}{more}" if rows
                       else "10,000 materials")

    views[0].selectionChanged.connect(show_selection)
    outer = VBoxLayout(spacing=10)
    outer.addWidget(columns, stretch=1)
    outer.addWidget(status)
    panel.setLayout(outer)
    return panel, views


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
    window.SetSize(980, 560)
    window.AddRenderer(renderer)
    if args.screenshot:
        window.SetOffScreenRendering(True)
    interactor = vtk.vtkRenderWindowInteractor()
    interactor.SetRenderWindow(window)
    interactor.SetInteractorStyle(vtk.vtkInteractorStyleTrackballCamera())
    EventRouter.install(interactor)
    panel, (materials, tree, table) = build(renderer, interactor)
    panel.contentLayout().activate()
    if args.screenshot:
        model = materials.model()
        materials.selectionModel().select(
            [model.index(row) for row in (2, 3, 4, 9)])
        materials.selectionModel().setCurrentIndex(model.index(9))
        tree.setCurrentIndex(tree.model().index(2, 0, tree.model().index(0)))
        table.setCurrentIndex(table.model().index(4, 0))
        tree.setFocus(reason="mouse")
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
