"""Screenshot tests from ``examples/gallery.py`` (W10).

Two kinds of check, in both themes:

* structural checks that hold on any machine (theme colours where they
  belong; menus, message boxes and the focus ring drawn on top);
* comparison with the reference images in ``tests/screenshots``, made
  with the VTK version recorded in ``versions.json``. Text rasterising
  differs between VTK versions, so other versions skip the comparison.
  Regenerate the references with ``MULTIPANEL_UPDATE_SCREENSHOTS=1``.
"""
import json
import os
import sys
from pathlib import Path

import numpy as np
import pytest
import vtk
from vtkmodules.util.numpy_support import vtk_to_numpy

from multipanel.ui_theme import DARK, LIGHT, vtk_tokens

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "examples"))

import gallery  # noqa: E402

REFERENCES = Path(__file__).resolve().parent / "screenshots"
VERSIONS = REFERENCES / "versions.json"
UPDATE = os.environ.get("MULTIPANEL_UPDATE_SCREENSHOTS", "") not in ("", "0")
THEMES = ("light", "dark")
# A pixel "differs" when a channel moves by more than this; a screenshot
# matches when at most MAX_DIFFERENT of its pixels differ.
CHANNEL_TOLERANCE = 40
MAX_DIFFERENT = 0.003

_cache = {}


def shot(theme, scene):
    key = (theme, scene)
    if key not in _cache:
        image = gallery.render(theme, scene)
        width, height, _ = image.GetDimensions()
        pixels = vtk_to_numpy(image.GetPointData().GetScalars())
        _cache[key] = (image, pixels.reshape(height, width, -1)[:, :, :3]
                       .astype(int))
    return _cache[key]


def pixels(theme, scene):
    return shot(theme, scene)[1]


def rgb(theme, token):
    tokens = vtk_tokens(DARK if theme == "dark" else LIGHT)
    return np.array([round(255 * c) for c in tokens[token]])


def near(pixel, colour, tolerance=3):
    return np.abs(pixel - colour).max() <= tolerance


def changed(a, b, region, tolerance=8):
    """Fraction of pixels in ``region`` (x0, x1, y0, y1; y up) that differ."""
    x0, x1, y0, y1 = region
    delta = np.abs(a[y0:y1, x0:x1] - b[y0:y1, x0:x1]).max(axis=2)
    return float((delta > tolerance).mean())


@pytest.mark.parametrize("theme", THEMES)
def test_theme_colours_are_where_they_belong(theme):
    image = pixels(theme, "plain")
    assert near(image[300, 800], rgb(theme, "pane"))           # background
    assert near(image[200, 360], rgb(theme, "panel"))          # panel margin
    # The panel is not empty: its controls draw text and shapes.
    panel = image[190:570, 40:360]
    assert len(np.unique(panel.reshape(-1, 3), axis=0)) > 50


@pytest.mark.parametrize("theme", THEMES)
def test_menu_and_submenu_draw_over_the_scene(theme):
    plain, menu = pixels(theme, "plain"), pixels(theme, "menu")
    # (> 0.6: where a menu lies over a same-coloured background, nothing
    # changes)
    assert changed(plain, menu, (432, 570, 440, 515)) > 0.6    # the menu
    assert changed(plain, menu, (578, 672, 358, 432)) > 0.6    # submenu
    assert changed(plain, menu, (0, 420, 0, 620)) == 0         # rest intact


@pytest.mark.parametrize("theme", THEMES)
def test_message_box_draws_in_front(theme):
    plain, message = pixels(theme, "plain"), pixels(theme, "message")
    # The scrim dims everything; the box itself differs from the dimmed
    # scene around it.
    assert changed(plain, message, (0, 900, 0, 620)) > 0.9
    box = changed(plain, message, (360, 540, 260, 360), tolerance=0)
    assert box > 0.9


@pytest.mark.parametrize("theme", THEMES)
def test_focus_ring_appears_after_tab(theme):
    plain, focus = pixels(theme, "plain"), pixels(theme, "focus")
    accent = rgb(theme, "accent")
    accent_px = lambda image: int(  # noqa: E731
        (np.abs(image - accent).max(axis=2) <= 12).sum())
    assert accent_px(focus) > accent_px(plain) + 40
    assert changed(plain, focus, (0, 900, 0, 620)) < 0.02     # just the ring


# -- reference images ----------------------------------------------------------------------
def _versions():
    if VERSIONS.exists():
        return json.loads(VERSIONS.read_text())
    return {}


def _read_png(path):
    reader = vtk.vtkPNGReader()
    reader.SetFileName(str(path))
    reader.Update()
    image = reader.GetOutput()
    width, height, _ = image.GetDimensions()
    data = vtk_to_numpy(image.GetPointData().GetScalars())
    return data.reshape(height, width, -1)[:, :, :3].astype(int)


@pytest.mark.parametrize("scene", gallery.SCENES)
@pytest.mark.parametrize("theme", THEMES)
def test_matches_reference_screenshot(theme, scene):
    reference = REFERENCES / f"{theme}_{scene}.png"
    vtk_version = vtk.vtkVersion.GetVTKVersion()
    if UPDATE:
        REFERENCES.mkdir(exist_ok=True)
        writer = vtk.vtkPNGWriter()
        writer.SetFileName(str(reference))
        writer.SetInputData(shot(theme, scene)[0])
        writer.Write()
        VERSIONS.write_text(json.dumps({"vtk": vtk_version}, indent=2) + "\n")
        return
    recorded = _versions().get("vtk")
    if not reference.exists():
        pytest.skip("no reference image; set MULTIPANEL_UPDATE_SCREENSHOTS=1")
    if recorded != vtk_version:
        pytest.skip(f"references made with VTK {recorded}, "
                    f"running {vtk_version}")
    expected, actual = _read_png(reference), pixels(theme, scene)
    assert expected.shape == actual.shape
    delta = np.abs(expected - actual).max(axis=2)
    different = float((delta > CHANNEL_TOLERANCE).mean())
    if different > MAX_DIFFERENT:
        failed = REFERENCES / f"{theme}_{scene}.actual.png"
        writer = vtk.vtkPNGWriter()
        writer.SetFileName(str(failed))
        writer.SetInputData(shot(theme, scene)[0])
        writer.Write()
        pytest.fail(f"{different:.2%} of pixels differ from {reference.name}"
                    f" (written to {failed.name})")
