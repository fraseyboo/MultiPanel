"""Chart gallery: every chart type, live or as images.

Open the interactive gallery (all charts side by side as scene panels)::

    python examples/chart_gallery.py [--dark]

Lines, histogram with error bars, error-bar scatter (x and y), log axis,
bars, composition bars, box plots, a 2D histogram, a pie chart, an
editable spectrum, clickable bars, two charts with a linked x axis and a
table bound to a chart. Hover for tooltips, wheel to
zoom, drag to pan, right-drag to zoom a box, double-click to reset. The
spectrum tile is editable (drag bins, edges and lines; Ctrl+Z undoes),
bars in the "click" tile highlight when clicked, and the table tile shares
its selection with its chart. T switches theme.

Write every scene in both themes to a folder instead::

    python examples/chart_gallery.py out/ [--scale 2]

``render(theme, scene)`` returns one scene as ``vtkImageData``; the chart
screenshot tests compare it with references in ``tests/screenshots``.
"""
import argparse
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from multipanel.chart_export import export_chart, render_chart  # noqa: E402
from multipanel.chartview import (  # noqa: E402
    Histogram2DChart, PieChart, XYChart,
)
from multipanel.ui_theme import DARK, LIGHT, vtk_tokens  # noqa: E402

SIZE = (560, 380)


def lines():
    """Lines (one with markers) and a scatter, legend top right."""
    chart = XYChart(title="Lines and points")
    chart.axisX().setTitle("Time (s)")
    chart.axisY().setTitle("Signal")
    t = np.linspace(0.0, 10.0, 60)
    chart.addLine(t, np.sin(t) + 2.0, name="sine")
    chart.addLine(t[::5], np.cos(t[::5]) + 2.0, name="cosine",
                  markers=True)
    chart.addScatter(t[::3], 0.4 * np.sin(2 * t[::3]) + 0.6, name="samples")
    return chart


def histogram():
    """A filled histogram with error bars and discrete lines (stems)."""
    chart = XYChart(title="Spectrum")
    chart.axisX().setTitle("Energy (MeV)")
    chart.axisY().setTitle("Counts per bin")
    edges = np.array([0.0, 0.25, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0])
    counts = np.array([120.0, 340.0, 410.0, 260.0, 150.0, 70.0, 20.0])
    step = chart.addStep(edges, counts, name="measured", fill=True)
    centres = (edges[:-1] + edges[1:]) / 2
    chart.addErrorBars(centres, counts, np.sqrt(counts) * 3, of=step,
                       name="measured error")
    chart.addStems([0.662, 1.173, 1.332], [380.0, 300.0, 290.0],
                   name="lines")
    return chart


def logarithmic():
    """A log y axis over five decades (the curves fall away from the legend)."""
    chart = XYChart(title="Attenuation")
    chart.axisX().setTitle("Depth (cm)")
    chart.axisY().setTitle("Relative flux")
    chart.axisY().setLogScale(True)
    chart.setLegendPosition("top-right")
    depth = np.linspace(0.0, 30.0, 40)
    chart.addLine(depth, np.exp(-depth / 2.6), name="water")
    chart.addLine(depth, np.exp(-depth / 6.0), name="concrete")
    return chart


def bars():
    """Bars with the legend hidden."""
    chart = XYChart(title="Doses by organ")
    chart.axisX().setTitle("Organ")
    chart.axisY().setTitle("Dose (mGy)")
    chart.setLegendVisible(False)
    chart.addBars([1, 2, 3, 4, 5], [4.2, 2.8, 6.1, 1.4, 3.3], name="dose")
    return chart


def composition():
    """Horizontal bars with category labels (a material's elements)."""
    chart = XYChart(title="Soft tissue (ICRU-44)")
    chart.axisX().setTitle("Weight fraction (%)")
    chart.setLegendVisible(False)
    elements = ["O", "C", "H", "N", "Na", "P", "S", "Cl", "K"]
    percent = [71.1, 14.3, 10.1, 3.4, 0.1, 0.2, 0.3, 0.2, 0.3]
    order = sorted(range(len(elements)), key=lambda i: -percent[i])
    positions = list(range(len(order), 0, -1))       # largest at the top
    chart.addBars(positions, [percent[i] for i in order], name="weight",
                  horizontal=True)
    chart.axisY().setTickLabels(positions, [elements[i] for i in order])
    return chart


def error_scatter():
    """Points with x and y error bars (capped)."""
    chart = XYChart(title="Measurements with errors")
    chart.axisX().setTitle("Thickness (mm)")
    chart.axisY().setTitle("Transmission")
    thickness = np.array([1.0, 2.0, 3.5, 5.0, 7.0, 9.0])
    transmission = np.exp(-thickness / 4.0)
    chart.addErrorScatter(thickness, transmission,
                          errors=0.04 + 0.05 * transmission,
                          x_errors=np.full(6, 0.25), name="measured",
                          size=8.0)
    model = np.linspace(0.0, 10.0, 60)
    chart.addLine(model, np.exp(-model / 4.0), name="model")
    return chart


def heatmap():
    """A 2D histogram (dose map) on a log colour scale."""
    x = np.linspace(-1.0, 1.0, 48)
    y = np.linspace(-1.0, 1.0, 36)
    xx, yy = np.meshgrid(x, y)
    dose = 100.0 * np.exp(-((xx - 0.2) ** 2 + yy ** 2) / 0.08) + \
        5.0 * np.exp(-((xx + 0.5) ** 2 + (yy - 0.4) ** 2) / 0.02) + 0.05
    chart = Histogram2DChart(dose, x_range=(-10, 10), y_range=(-7.5, 7.5),
                             title="Dose map", log=True,
                             value_title="Dose (mGy)")
    chart.axisX().setTitle("x (cm)")
    chart.axisY().setTitle("y (cm)")
    return chart


def pie():
    """A pie chart: mass by material."""
    return PieChart(["Concrete", "Steel", "Water", "Lead", "Air"],
                    [62.0, 21.0, 9.0, 6.5, 1.5], title="Mass by material")


def boxes():
    """Box plots with category labels and outliers."""
    rng = np.random.default_rng(7)
    chart = XYChart(title="Dose spread by organ")
    chart.axisY().setTitle("Dose (mGy)")
    chart.setLegendVisible(False)
    groups = [rng.normal(4.0, 0.8, 40), rng.normal(6.5, 1.6, 40),
              np.r_[rng.normal(2.5, 0.5, 40), 6.4, 7.1],
              rng.normal(5.0, 1.1, 40)]
    chart.addBoxes(groups, labels=["Lung", "Liver", "Bone", "Skin"],
                   name="dose")
    return chart


SCENES = {"lines": lines, "histogram": histogram, "log": logarithmic,
          "bars": bars, "composition": composition, "errors": error_scatter,
          "heatmap": heatmap, "pie": pie, "boxes": boxes}


def theme_tokens(theme):
    return vtk_tokens(DARK if theme == "dark" else LIGHT)


def render(theme="light", scene="lines", scale=1.0):
    """One scene as ``vtkImageData``."""
    if scene not in SCENES:
        raise ValueError(f"scene must be one of {sorted(SCENES)}")
    return render_chart(SCENES[scene](), size=SIZE, scale=scale,
                        tokens=theme_tokens(theme), dark=theme == "dark")


# -- the interactive gallery ---------------------------------------------------------------
def editable_spectrum():
    """A source spectrum to drag: bin tops and edges, and the lines."""
    chart = XYChart(title="Editable spectrum (drag; Ctrl+Z)")
    chart.axisX().setTitle("Energy (MeV)")
    chart.axisY().setTitle("Weight")
    edges = np.array([0.0, 0.3, 0.6, 1.0, 1.5, 2.2, 3.0])
    bins = chart.addStep(edges, [0.05, 0.18, 0.3, 0.22, 0.12, 0.04],
                         name="bins", fill=True)
    lines = chart.addStems([0.662, 1.173, 1.332], [0.28, 0.24, 0.24],
                           name="lines")
    bins.setEditable(True)
    lines.setEditable(True, move_x=True, x_minimum=0.001)
    return chart


def clickable_bars():
    """Bars that report clicks; the clicked one is highlighted."""
    chart = XYChart(title="Click a bar")
    chart.axisX().setTitle("Cell")
    chart.axisY().setTitle("Volume (cm³)")
    chart.setLegendVisible(False)
    bars = chart.addBars([1, 2, 3, 4, 5, 6], [12.0, 30.0, 7.5, 21.0, 16.0,
                                              9.0], name="volume")
    bars.setClickable()
    chart.clicked.connect(lambda series, index: series.setHighlighted(
        [] if series.highlighted() == [index] else [index]))
    return chart


TILES = (lines, histogram, error_scatter, logarithmic, bars, composition,
         boxes, heatmap, pie, editable_spectrum, clickable_bars)


def _linked_grid_tile(renderer, interactor):
    """Two spectra over one energy axis: zoom or pan either."""
    from multipanel.chart_grid import ChartGrid

    energy = np.linspace(0.05, 3.0, 300)
    grid = ChartGrid(renderer, interactor, columns=1, link="x", spacing=4)
    for name, peaks in (("Detector A", (0.662, 1.173, 1.332)),
                        ("Detector B", (0.511, 1.275))):
        counts = 40 * np.exp(-energy / 0.8)
        for peak in peaks:
            counts += 300 * np.exp(-((energy - peak) / 0.02) ** 2)
        chart = XYChart()
        chart.setLegendVisible(False)
        chart.axisY().setTitle(name)
        chart.addLine(energy, counts, name=name)
        grid.addChart(chart, minimum_height=80)
    grid.charts()[-1].axisX().setTitle("Energy (MeV)")
    return _tile(renderer, interactor, "Linked x axes (zoom either)", grid)


def _tile(renderer, interactor, caption, *widgets):
    """A card: a bold caption over its widgets (the last one stretches)."""
    from multipanel.containers import Frame
    from multipanel.layouts import VBoxLayout
    from multipanel.standard import Label

    card = Frame(renderer, interactor, background=True)
    column = VBoxLayout(margins=(8, 6, 8, 8), spacing=4)
    column.addWidget(Label(renderer, interactor, caption, bold=True))
    for widget in widgets[:-1]:
        column.addWidget(widget)
    column.addWidget(widgets[-1], stretch=1)
    card.setLayout(column)
    return card


def _chart_tile(renderer, interactor, chart):
    from multipanel.chartview import ChartView

    caption = chart.title()
    chart.setTitle("")             # the card's caption names it
    return _tile(renderer, interactor, caption,
                 ChartView(renderer, interactor, chart))


def _bound_table_tile(renderer, interactor):
    """A table and a chart on one model, sharing the selection."""
    from multipanel.chart_models import bind_series
    from multipanel.chartview import ChartView
    from multipanel.models import TableModel
    from multipanel.units import px
    from multipanel.views import TableView

    model = TableModel([(float(d), round(100 * np.exp(-d / 4.0), 2))
                        for d in range(0, 21, 2)],
                       headers=("Depth (cm)", "Dose (%)"))
    table = TableView(renderer, interactor)
    table.setModel(model)
    table.setMinimumHeight(px(150))
    table.setMaximumHeight(px(150))
    chart = XYChart()
    chart.setLegendVisible(False)
    chart.axisX().setTitle("Depth (cm)")
    chart.axisY().setTitle("Dose (%)")
    points = chart.addLine([], [], name="dose", markers=True)
    view = ChartView(renderer, interactor, chart)
    tile = _tile(renderer, interactor,
                 "Table and chart, one selection", table, view)
    tile._binding = bind_series(points, model,
                                selection=table.selectionModel())
    return tile


def build_gallery(renderer, interactor):
    """Every tile in a grid five wide, filling the window."""
    from multipanel.containers import Frame
    from multipanel.layouts import GridLayout
    from multipanel.units import frac

    root = Frame(renderer, interactor)
    root.setGeometry(frac(0), frac(0), frac(1), frac(1))
    grid = GridLayout(margins=(10, 10, 10, 10), spacing=10)
    tiles = [_chart_tile(renderer, interactor, build()) for build in TILES]
    tiles.append(_linked_grid_tile(renderer, interactor))
    tiles.append(_bound_table_tile(renderer, interactor))
    columns = 5
    rows = -(-len(tiles) // columns)
    for index, tile in enumerate(tiles):
        row, column = divmod(index, columns)
        grid.addWidget(tile, row, column)
    for column in range(columns):
        grid.setColumnStretch(column, 1)
    for row in range(rows):
        grid.setRowStretch(row, 1)
    root.setLayout(grid)
    root._tiles = tiles
    return root


def show_gallery(dark=False, screenshot=None, size=(2000, 1200)):
    import vtk

    from multipanel.config import theme
    from multipanel.core import RenderScheduler, refresh_renderer_theme
    from multipanel.router import EventRouter

    renderer = vtk.vtkRenderer()
    renderer.theme = theme(dark_mode=dark)
    renderer.SetBackground(*renderer.theme.tokens["pane"])
    window = vtk.vtkRenderWindow()
    window.SetSize(*size)
    if not screenshot:
        from multipanel.display import fit_window_to_screen
        fit_window_to_screen(window)
    window.SetWindowName("MultiPanel chart gallery (T: theme)")
    window.AddRenderer(renderer)
    if screenshot:
        window.SetOffScreenRendering(True)
    interactor = vtk.vtkRenderWindowInteractor()
    interactor.SetRenderWindow(window)
    interactor.SetInteractorStyle(vtk.vtkInteractorStyleUser())
    EventRouter.install(interactor)
    gallery = build_gallery(renderer, interactor)

    def switch_theme(caller, _event):
        if caller.GetKeySym() not in ("t", "T"):
            return
        renderer.theme.update(dark_mode=not renderer.theme.dark_mode)
        renderer.SetBackground(*renderer.theme.tokens["pane"])
        refresh_renderer_theme(renderer)
        window.Render()

    interactor.AddObserver("KeyPressEvent", switch_theme)
    window.Render()
    RenderScheduler.for_window(window, interactor).flush()
    window.Render()
    if screenshot:
        grab = vtk.vtkWindowToImageFilter()
        grab.SetInput(window)
        grab.ReadFrontBufferOff()
        grab.Update()
        writer = vtk.vtkPNGWriter()
        writer.SetFileName(str(screenshot))
        writer.SetInputConnection(grab.GetOutputPort())
        writer.Write()
        print(f"wrote {screenshot}")
        return gallery
    interactor.Initialize()
    interactor.Start()
    return gallery


def main():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("folder", type=Path, nargs="?",
                        help="write PNGs of every scene here instead")
    parser.add_argument("--scale", type=float, default=1.0)
    parser.add_argument("--dark", action="store_true")
    parser.add_argument("--screenshot", type=Path,
                        help="write the interactive gallery to an image")
    args = parser.parse_args()
    if args.folder is None:
        show_gallery(dark=args.dark, screenshot=args.screenshot)
        return
    args.folder.mkdir(parents=True, exist_ok=True)
    for theme in ("light", "dark"):
        for scene, build in SCENES.items():
            path = args.folder / f"{theme}_{scene}.png"
            export_chart(build(), path, size=SIZE, scale=args.scale,
                         tokens=theme_tokens(theme), dark=theme == "dark")
            print(f"wrote {path}")


if __name__ == "__main__":
    main()
