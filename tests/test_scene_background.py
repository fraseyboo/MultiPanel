"""The scene background gradient and its dithering."""
import numpy as np
import pytest
import vtk
from vtkmodules.util.numpy_support import vtk_to_numpy

from multipanel.scene_theme import apply_scene_theme, background_dither_mode


def make_renderer(size=(200, 400)):
    window = vtk.vtkRenderWindow()
    window.SetOffScreenRendering(True)
    window.SetSize(*size)
    renderer = vtk.vtkRenderer()
    window.AddRenderer(renderer)
    return window, renderer


def grab(window):
    window.Render()
    grab = vtk.vtkWindowToImageFilter()
    grab.SetInput(window)
    grab.ReadFrontBufferOff()
    grab.Update()
    width, height = window.GetSize()
    data = vtk_to_numpy(grab.GetOutput().GetPointData().GetScalars())
    return data.reshape(height, width, -1)[:, :, :3].astype(float)


@pytest.mark.parametrize("dither, mode", [
    (True, "vtk"), ("vtk", "vtk"), ("texture", "texture"),
    (False, "off"), ("off", "off"), ("nonsense", "vtk")])
def test_dither_modes(dither, mode, monkeypatch):
    monkeypatch.delenv("MULTIPANEL_BACKGROUND_DITHER", raising=False)
    assert background_dither_mode(dither) == mode


def test_environment_chooses_the_default(monkeypatch):
    monkeypatch.setenv("MULTIPANEL_BACKGROUND_DITHER", "texture")
    assert background_dither_mode() == "texture"
    assert background_dither_mode(False) == "off"     # explicit wins


@pytest.mark.parametrize("dither", [True, "texture", False])
def test_background_settings(dither, monkeypatch):
    monkeypatch.delenv("MULTIPANEL_BACKGROUND_DITHER", raising=False)
    _window, renderer = make_renderer()
    apply_scene_theme(renderer, True, "#037CF6", render=False, dither=dither)
    textured = dither == "texture"
    assert bool(renderer.GetTexturedBackground()) == textured
    assert bool(renderer.GetGradientBackground()) == (not textured)
    if not textured:
        assert bool(renderer.GetDitherGradient()) == (dither is True)


def test_vtk_dithering_breaks_up_the_bands(monkeypatch):
    """Without dithering each row of the dark gradient is one flat level,
    so the ramp shows as bands; dithered rows mix neighbouring levels."""
    monkeypatch.delenv("MULTIPANEL_BACKGROUND_DITHER", raising=False)
    noise = {}
    for dither in (False, True):
        window, renderer = make_renderer()
        apply_scene_theme(renderer, True, "#037CF6", render=False,
                          dither=dither)
        luminance = grab(window).mean(axis=2)
        noise[dither] = float(luminance.std(axis=1).mean())
    assert noise[False] < 0.05
    assert noise[True] > 0.1
