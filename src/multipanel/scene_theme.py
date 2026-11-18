"""Light/dark colours for the 3D scene, matched to the Qt panel theme.

Qt-free so it can be driven from ``GUI.qt_theme.ThemeManager`` or any other
front end. Only theme-neutral scene chrome is recoloured: the background,
the reference grid and in-scene progress text. Semantic colours (gizmo
axes, selection highlight, material colours) are deliberately untouched.
"""
from __future__ import annotations

# Background gradients: VTK's Background is the bottom colour, Background2
# the top.
_BACKGROUND = {
    False: {"bottom": (1.0, 1.0, 1.0), "top": (0.905, 0.925, 0.950)},
    True: {"bottom": (0.071, 0.078, 0.090), "top": (0.150, 0.163, 0.184)},
}
# How strongly the accent tints each grid layer over the background.
_GRID_MIX = {
    False: {"major": 0.30, "major_edge": 0.42, "minor": 0.25},
    True: {"major": 0.38, "major_edge": 0.50, "minor": 0.22},
}


def _parse_hex(color: str) -> tuple[float, float, float]:
    value = color.strip().lstrip("#")
    if len(value) != 6:
        raise ValueError(f"expected #RRGGBB colour, got {color!r}")
    return tuple(int(value[i:i + 2], 16) / 255.0 for i in (0, 2, 4))


def _mix(base, tint, amount):
    return tuple(b + (t - b) * amount for b, t in zip(base, tint))


def scene_palette(dark: bool, accent: str) -> dict:
    """Return the scene colours (0..1 RGB tuples) for a mode and accent."""
    dark = bool(dark)
    accent_rgb = _parse_hex(accent)
    background = _BACKGROUND[dark]
    # Tint toward the lighter end of the gradient in dark mode so the grid
    # stays visible against the darkest pixels.
    grid_base = background["top"] if dark else background["bottom"]
    mix = _GRID_MIX[dark]
    return {
        "dark": dark,
        "accent": accent_rgb,
        "background_bottom": background["bottom"],
        "background_top": background["top"],
        "grid_major": _mix(grid_base, accent_rgb, mix["major"]),
        "grid_major_edge": _mix(grid_base, accent_rgb, mix["major_edge"]),
        "grid_minor": _mix(grid_base, accent_rgb, mix["minor"]),
        "text": (0.90, 0.91, 0.93) if dark else (0.12, 0.14, 0.16),
        "progress_background": ((0.16, 0.17, 0.19) if dark
                                else (0.86, 0.88, 0.91)),
    }


def register_reference_grid(renderer, major_actor, minor_actor):
    """Record the reference-grid actors so a theme can recolour them."""
    renderer.reference_grid_actors = {"major": major_actor, "minor": minor_actor}


# Dithered background textures, one per (bottom, top) colour pair.
_BACKGROUND_TEXTURES = {}
_TEXTURE_SIZE = (256, 2048)      # (width, height) texels


def dithered_gradient_texture(bottom, top, size=_TEXTURE_SIZE, seed=7):
    """Vertical gradient texture with triangular ±1 LSB dither.

    The dark gradient spans only ~20 of the 256 levels per channel, so an
    undithered gradient bands visibly. VTK (9.3 onwards) dithers its own
    gradient background (``vtkRenderer.SetDitherGradient``, on by default),
    which :func:`apply_scene_theme` now uses; this texture is the older
    alternative (``dither="texture"``), kept for comparison and for
    renderers without that option.
    """
    import numpy as np
    import vtk
    from vtkmodules.util.numpy_support import numpy_to_vtk

    width, height = size
    key = (tuple(round(c, 5) for c in bottom), tuple(round(c, 5) for c in top), size)
    texture = _BACKGROUND_TEXTURES.get(key)
    if texture is not None:
        return texture
    t = np.linspace(0.0, 1.0, height)[:, None, None]          # row 0 = bottom
    ramp = (np.asarray(bottom)[None, None, :] * (1.0 - t) +
            np.asarray(top)[None, None, :] * t) * 255.0
    rng = np.random.default_rng(seed)
    noise = (rng.random((height, width, 1)) + rng.random((height, width, 1)) - 1.0)
    pixels = np.clip(np.rint(ramp + noise), 0, 255).astype(np.uint8)
    image = vtk.vtkImageData()
    image.SetDimensions(width, height, 1)
    scalars = numpy_to_vtk(pixels.reshape(-1, 3), deep=True,
                           array_type=vtk.VTK_UNSIGNED_CHAR)
    scalars.SetNumberOfComponents(3)
    image.GetPointData().SetScalars(scalars)
    texture = vtk.vtkTexture()
    texture.SetInputData(image)
    texture.InterpolateOff()     # keep the dither per pixel, not smeared
    texture.RepeatOff()
    texture.EdgeClampOn()
    _BACKGROUND_TEXTURES[key] = texture
    return texture


DITHER_MODES = ("vtk", "texture", "off")


def background_dither_mode(dither=True):
    """``"vtk"``, ``"texture"`` or ``"off"`` for :func:`apply_scene_theme`'s
    ``dither`` argument. ``MULTIPANEL_BACKGROUND_DITHER`` overrides the
    default (``True``, VTK's own dithering)."""
    import os

    if dither is True:
        dither = os.environ.get("MULTIPANEL_BACKGROUND_DITHER", "vtk")
    if dither is False or dither is None:
        return "off"
    mode = str(dither).strip().lower()
    return mode if mode in DITHER_MODES else "vtk"


def apply_scene_theme(renderer, dark: bool, accent: str, render: bool = True,
                      dither=True):
    """Recolour the scene chrome of *renderer*; returns the palette used.

    The background is a vertical gradient. ``dither`` removes its banding:
    ``True``/``"vtk"`` uses VTK's dithered gradient, ``"texture"`` a
    pre-dithered texture (:func:`dithered_gradient_texture`), and
    ``False``/``"off"`` a plain gradient.
    """
    palette = scene_palette(dark, accent)
    renderer.SetBackground(*palette["background_bottom"])
    renderer.SetBackground2(*palette["background_top"])
    mode = background_dither_mode(dither)
    if mode == "texture":
        renderer.SetBackgroundTexture(dithered_gradient_texture(
            palette["background_bottom"], palette["background_top"]))
        renderer.GradientBackgroundOff()
        renderer.TexturedBackgroundOn()
    else:
        renderer.TexturedBackgroundOff()
        renderer.GradientBackgroundOn()
        if hasattr(renderer, "SetDitherGradient"):
            renderer.SetDitherGradient(mode == "vtk")

    grid = getattr(renderer, "reference_grid_actors", None) or {}
    major = grid.get("major")
    if major is not None:
        major.GetProperty().SetColor(*palette["grid_major"])
        major.GetProperty().SetEdgeColor(*palette["grid_major_edge"])
    minor = grid.get("minor")
    if minor is not None:
        minor.GetProperty().SetColor(*palette["grid_minor"])

    # Read lazily by in-scene overlays such as VTKProgressReporter.
    renderer.scene_palette = palette
    if render:
        window = renderer.GetRenderWindow()
        if window is not None:
            window.Render()
    return palette
