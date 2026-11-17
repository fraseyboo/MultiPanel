"""Charts as scene panels: a source energy spectrum (demo data).

Run interactively::

    python examples/chart_panel_demo.py [--dark]

or write one off-screen frame to an image::

    python examples/chart_panel_demo.py --screenshot charts.png [--dark]

The left dock's "Source" tab holds a spectrum chart panel; a second chart
floats over the scene. Wheel zooms a chart, left drag pans it, right drag
zooms a box, double-click (or Home) resets; the camera only moves when the
pointer is over the scene.
"""
import argparse
import sys
from pathlib import Path

import numpy as np
import vtk

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from multipanel.chartview import ChartPanel, XYChart  # noqa: E402
from multipanel.config import theme  # noqa: E402
from multipanel.containers import DockPane  # noqa: E402
from multipanel.router import EventRouter  # noqa: E402


def watt_spectrum(edges, a=0.988, b=2.249):
    """Bin probabilities of a Watt fission spectrum (U-235 thermal)."""
    energies = np.linspace(edges[0], edges[-1], 4000)
    density = np.exp(-energies / a) * np.sinh(np.sqrt(b * energies))
    cumulative = np.concatenate([[0.0], np.cumsum(
        (density[1:] + density[:-1]) / 2 * np.diff(energies))])
    at_edges = np.interp(edges, energies, cumulative)
    return np.diff(at_edges) / at_edges[-1]


def source_chart():
    """SDEF-like demo: a binned neutron spectrum and gamma lines."""
    chart = XYChart(title="Source energy spectrum")
    chart.axisX().setTitle("Energy (MeV)")
    chart.axisY().setTitle("Probability per bin")
    edges = np.concatenate([[0.0], np.geomspace(0.1, 10.0, 24)])
    bins = chart.addStep(edges, watt_spectrum(edges), name="Watt (SI1 H/SP1)",
                         fill=True)
    lines = chart.addStems([0.662, 1.173, 1.332], [0.085, 0.100, 0.100],
                           name="Gamma lines")
    # Drag bin tops and edges, and the lines (also sideways); Ctrl+Z undoes.
    bins.setEditable(True)
    lines.setEditable(True, move_x=True)
    return chart


def efficiency_chart():
    chart = XYChart(title="Detector response (demo)")
    chart.axisX().setTitle("Energy (MeV)")
    chart.axisY().setTitle("Efficiency")
    energy = np.linspace(0.05, 3.0, 60)
    chart.addLine(energy, 0.42 * np.exp(-energy / 1.3) + 0.04,
                  name="NaI 3x3 in", markers=True)
    chart.addLine(energy, 0.18 * np.exp(-energy / 2.1) + 0.02,
                  name="HPGe")
    return chart


def build(renderer, interactor):
    cube_source = vtk.vtkCubeSource()
    mapper = vtk.vtkPolyDataMapper()
    mapper.SetInputConnection(cube_source.GetOutputPort())
    cube = vtk.vtkActor()
    cube.SetMapper(mapper)
    cube.GetProperty().SetColor(0.45, 0.62, 0.85)
    renderer.AddActor(cube)
    renderer.ResetCamera()
    renderer._demo_source = cube_source          # keep the pipeline alive

    theme = renderer.theme
    dock = DockPane(renderer, interactor, side="left", width=0.36,
                    panel_color=theme.pane_color, text_color=theme.text_color)
    dock.add_tab("source", "add_shape", tooltip="Source")
    dock.add_tab("tools", "GRI", tooltip="Tools")
    spectrum = ChartPanel(renderer, interactor, source_chart(),
                          title="Source spectrum", chart_height=260)
    dock.add_panel(spectrum, tab="source")      # the first tab is active
    floating = ChartPanel(renderer, interactor, efficiency_chart(),
                          title="Detector response", position=(0.6, 0.5),
                          width=0.36, chart_height=200)
    return dock, spectrum, floating


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--screenshot", type=Path)
    parser.add_argument("--dark", action="store_true")
    args = parser.parse_args()
    renderer = vtk.vtkRenderer()
    renderer.theme = theme(dark_mode=args.dark)
    renderer.SetBackground(*renderer.theme.tokens["pane"])
    window = vtk.vtkRenderWindow()
    window.SetSize(1200, 720)
    window.AddRenderer(renderer)
    if args.screenshot:
        window.SetOffScreenRendering(True)
    interactor = vtk.vtkRenderWindowInteractor()
    interactor.SetRenderWindow(window)
    interactor.SetInteractorStyle(vtk.vtkInteractorStyleTrackballCamera())
    EventRouter.install(interactor)
    build(renderer, interactor)
    if args.screenshot:
        from multipanel.core import RenderScheduler

        window.Render()
        RenderScheduler.for_window(window, interactor).flush()
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
