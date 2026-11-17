"""Chart screenshot tests from ``examples/chart_gallery.py`` (charts C6).

As for the widget gallery: structural checks on any machine, and
comparison with references in ``tests/screenshots`` (``chart_<theme>_
<scene>.png``) made with the VTK version in ``versions.json``; other
versions skip the comparison. Regenerate with
``MULTIPANEL_UPDATE_SCREENSHOTS=1``.
"""
import json
import os
import sys
from pathlib import Path

import numpy as np
import pytest
import vtk

from multipanel.chart_export import image_array
from multipanel.chartview import palette

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "examples"))

import chart_gallery  # noqa: E402

REFERENCES = Path(__file__).resolve().parent / "screenshots"
VERSIONS = REFERENCES / "versions.json"
UPDATE = os.environ.get("MULTIPANEL_UPDATE_SCREENSHOTS", "") not in ("", "0")
THEMES = ("light", "dark")
CHANNEL_TOLERANCE = 40
MAX_DIFFERENT = 0.003

_cache = {}


def shot(theme, scene):
    if (theme, scene) not in _cache:
        image = chart_gallery.render(theme, scene)
        _cache[theme, scene] = (image,
                                image_array(image)[:, :, :3].astype(int))
    return _cache[theme, scene]


def token_rgb(theme, token):
    tokens = chart_gallery.theme_tokens(theme)
    return np.array([round(255 * c) for c in tokens[token]])


def count_near(image, colour, tolerance=24):
    return int((np.abs(image - colour).max(axis=2) <= tolerance).sum())


@pytest.mark.parametrize("theme", THEMES)
@pytest.mark.parametrize("scene", sorted(chart_gallery.SCENES))
def test_charts_draw_on_the_panel_colour(theme, scene):
    image = shot(theme, scene)[1]
    width, height = chart_gallery.SIZE
    assert image.shape[:2] == (height, width)
    assert np.abs(image[3, 3] - token_rgb(theme, "panel")).max() <= 2
    # Axis labels in the muted text colour (a pie has none), and the first
    # series in the theme's palette colour (a 2D histogram uses a colour
    # map instead).
    if scene != "pie":
        assert count_near(image, token_rgb(theme, "muted")) > 40
    if scene != "heatmap":
        first = np.array([round(255 * c)
                          for c in palette(theme == "dark")[0]])
        assert count_near(image, first) > 150


def test_themes_differ():
    light, dark = shot("light", "lines")[1], shot("dark", "lines")[1]
    assert np.abs(light - dark).max(axis=2).mean() > 50


def _read_png(path):
    reader = vtk.vtkPNGReader()
    reader.SetFileName(str(path))
    reader.Update()
    return image_array(reader.GetOutput())[:, :, :3].astype(int)


def _write_png(image, path):
    writer = vtk.vtkPNGWriter()
    writer.SetFileName(str(path))
    writer.SetInputData(image)
    writer.Write()


@pytest.mark.parametrize("scene", sorted(chart_gallery.SCENES))
@pytest.mark.parametrize("theme", THEMES)
def test_matches_reference_screenshot(theme, scene):
    reference = REFERENCES / f"chart_{theme}_{scene}.png"
    vtk_version = vtk.vtkVersion.GetVTKVersion()
    if UPDATE:
        REFERENCES.mkdir(exist_ok=True)
        _write_png(shot(theme, scene)[0], reference)
        VERSIONS.write_text(json.dumps({"vtk": vtk_version}, indent=2) + "\n")
        return
    recorded = (json.loads(VERSIONS.read_text()).get("vtk")
                if VERSIONS.exists() else None)
    if not reference.exists():
        pytest.skip("no reference image; set MULTIPANEL_UPDATE_SCREENSHOTS=1")
    if recorded != vtk_version:
        pytest.skip(f"references made with VTK {recorded}, "
                    f"running {vtk_version}")
    expected, actual = _read_png(reference), shot(theme, scene)[1]
    assert expected.shape == actual.shape
    different = float((np.abs(expected - actual).max(axis=2)
                       > CHANNEL_TOLERANCE).mean())
    if different > MAX_DIFFERENT:
        failed = REFERENCES / f"chart_{theme}_{scene}.actual.png"
        _write_png(shot(theme, scene)[0], failed)
        pytest.fail(f"{different:.2%} of pixels differ from {reference.name}"
                    f" (written to {failed.name})")


def test_the_interactive_gallery_builds(tmp_path):
    from multipanel.chartview import ChartView

    path = tmp_path / "gallery.png"
    gallery = chart_gallery.show_gallery(screenshot=path, size=(1200, 800))
    assert path.exists() and path.stat().st_size > 10_000
    assert len(gallery._tiles) == 13

    def views_in(widget):
        for child in widget.children():
            if isinstance(child, ChartView):
                yield child
            else:
                yield from views_in(child)

    views = [view for tile in gallery._tiles for view in views_in(tile)]
    assert len(views) == 14 and all(v.isVisible() for v in views)
