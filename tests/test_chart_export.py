"""Chart export: images, vector files and CSV (charts proposal C6)."""
import csv
import io

import numpy as np
import pytest
import vtk

from multipanel._widget_support import set_ui_scale, ui_scale, user_scale
from multipanel.chart_export import (
    CSV_COLUMNS, chart_rows, export_chart, image_array, render_chart,
)
from multipanel.chartview import ChartView, XYChart, _DEFAULT_TOKENS
from multipanel.config import theme
from multipanel.router import EventRouter
from multipanel.testing import UiHarness
from multipanel.units import px


def sample():
    chart = XYChart(title="Sample")
    chart.axisX().setTitle("Energy (MeV)")
    step = chart.addStep([0, 1, 2, 4], [3, 5, 2], name="bins", fill=True)
    chart.addErrorBars([0.5, 1.5, 3], [3, 5, 2], [0.3, 0.5, 0.2], of=step,
                       name="bins error")
    chart.addLine([0, 4], [1, 4], name="fit")
    chart.addStems([2.5], [6], name="line")
    hidden = chart.addScatter([1], [1], name="hidden")
    hidden.setVisible(False)
    return chart


def colour_of(token):
    return np.array([round(255 * c) for c in _DEFAULT_TOKENS[token]])


def test_rendered_image_is_the_chart_on_the_panel_colour():
    image = image_array(render_chart(sample(), size=(400, 280)))
    assert image.shape[:2] == (280, 400)
    corner = image[2, 2, :3].astype(int)
    assert np.abs(corner - colour_of("panel")).max() <= 2
    assert len(np.unique(image.reshape(-1, image.shape[2]), axis=0)) > 30


def test_scale_multiplies_the_size():
    chart = sample()
    small = image_array(render_chart(chart, size=(300, 200)))
    large = image_array(render_chart(chart, size=(300, 200), scale=2))
    assert large.shape[:2] == (400, 600) and small.shape[:2] == (200, 300)


@pytest.mark.parametrize("suffix", [".png", ".jpg", ".tif", ".svg", ".pdf",
                                    ".eps"])
def test_files_are_written(tmp_path, suffix):
    path = export_chart(sample(), tmp_path / f"chart{suffix}",
                        size=(320, 240))
    assert path.exists() and path.stat().st_size > 500
    assert list(tmp_path.iterdir()) == [path]
    if suffix == ".svg":
        text = path.read_text()
        assert "<svg" in text and ">Energy (MeV)<" in text
    if suffix == ".pdf":
        assert path.read_bytes().startswith(b"%PDF")


def test_png_matches_render(tmp_path):
    chart = sample()
    path = export_chart(chart, tmp_path / "chart.png", size=(320, 240))
    reader = vtk.vtkPNGReader()
    reader.SetFileName(str(path))
    reader.Update()
    written = image_array(reader.GetOutput())[:, :, :3].astype(int)
    rendered = image_array(render_chart(chart, size=(320, 240)))[:, :, :3]
    assert np.abs(written - rendered.astype(int)).max() <= 1


def test_unknown_formats_are_refused(tmp_path):
    with pytest.raises(ValueError, match="unsupported"):
        export_chart(sample(), tmp_path / "chart.bmpx")


def test_csv_rows():
    chart = sample()
    rows = chart_rows(chart)
    assert set(rows[0]) == set(CSV_COLUMNS)
    kinds = [row["kind"] for row in rows]
    assert kinds == ["histogram"] * 3 + ["error"] * 3 + ["line"] * 2 + \
        ["lines"]
    assert rows[1] == {"series": "bins", "kind": "histogram", "x": "1",
                       "x_low": "", "x_high": "2", "y": "5", "y_low": "",
                       "y_high": ""}
    assert (rows[4]["y_low"], rows[4]["y_high"]) == ("4.5", "5.5")
    parsed = list(csv.DictReader(io.StringIO(chart.toCsv())))
    assert len(parsed) == len(rows) and parsed[-1]["series"] == "line"
    assert all(row["series"] != "hidden" for row in parsed)


def test_csv_file(tmp_path):
    path = sample().export(tmp_path / "chart.csv")
    assert path.read_text().splitlines()[0] == ",".join(CSV_COLUMNS)


@pytest.fixture
def ui():
    previous = user_scale()
    set_ui_scale(1.0)
    with UiHarness(size=(900, 600)) as harness:
        harness.renderer.theme = theme(dark_mode=True)
        harness.interactor.SetInteractorStyle(
            vtk.vtkInteractorStyleTrackballCamera())
        EventRouter.install(harness.interactor)
        yield harness
        EventRouter.uninstall(harness.interactor)
    set_ui_scale(previous)


def test_export_from_a_view_keeps_the_view_working(ui, tmp_path):
    chart = sample()
    view = ChartView(ui.renderer, ui.interactor, chart)
    view.setGeometry(*(px(v) for v in (300, 100, 420, 300)))
    ui.render()
    x, y, w, h = view.geometry("display")
    ui.wheel((x + w / 2, y + h / 2), steps=2)          # zoom in
    zoomed = chart.axisX().range()
    image = image_array(render_chart(chart))
    assert image.shape[:2] == (300, 420)                # the view's size
    dark_panel = np.array([round(255 * c) for c in
                           ui.renderer.theme.tokens["panel"]])
    assert np.abs(image[2, 2, :3].astype(int) - dark_panel).max() <= 2
    assert chart.axisX().range() == pytest.approx(zoomed)
    assert chart.vtkChart().GetScene() is view._actor.GetScene()
    label = chart.axisX().vtkAxis().GetLabelProperties()
    assert label.GetColor() == pytest.approx(
        ui.renderer.theme.tokens["muted"])
    ui.wheel((x + w / 2, y + h / 2), steps=-2)         # still interactive
    assert chart.axisX().range() != pytest.approx(zoomed)
    chart.export(tmp_path / "view.png", scale=2)
    reader = vtk.vtkPNGReader()
    reader.SetFileName(str(tmp_path / "view.png"))
    reader.Update()
    assert reader.GetOutput().GetDimensions()[:2] == (840, 600)
