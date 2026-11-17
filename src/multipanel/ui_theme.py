"""Toolkit-independent design tokens shared by the Qt and VTK user interfaces.

Both front ends draw from the same light/dark neutral palettes and derive
their accent shades the same way, so the two UIs look like one product.
``GUI/qt_theme.py`` turns these tokens into a QPalette and stylesheet; the
VTK widgets read them as 0..1 RGB tuples through :func:`vtk_tokens`.
"""
from __future__ import annotations

LIGHT = "light"
DARK = "dark"
DEFAULT_ACCENT = "#037CF6"

# Neutral surfaces per mode; the accent is layered on top of these.
BASE = {
    LIGHT: {
        "pane": "#E4E7EC",
        "panel": "#FAFBFC",
        "title": "#EEF0F4",
        "border": "#C8CDD5",
        "text": "#1F2328",
        "muted": "#5F6772",
        "disabled": "#A0A6AF",
        "input": "#FFFFFF",
        "input_border": "#BFC5CE",
        "button": "#F1F3F6",
        "button_hover": "#E5E8ED",
        "row_hover": "#EDF0F4",
        "tooltip": "#FFFFFF",
    },
    DARK: {
        "pane": "#17191C",
        "panel": "#22252A",
        "title": "#2A2E34",
        "border": "#383D45",
        "text": "#E4E7EB",
        "muted": "#9AA3AD",
        "disabled": "#5C636C",
        "input": "#1B1D21",
        "input_border": "#454B54",
        "button": "#2E3238",
        "button_hover": "#383D44",
        "row_hover": "#2C3036",
        "tooltip": "#2A2E34",
    },
}

# Unscaled type scale in px shared by both UIs.
FONT_BODY = 12
FONT_TITLE = 12        # titles use the body size, in bold
FONT_GLYPH = 9


def hex_to_rgb(color: str) -> tuple[float, float, float]:
    value = color.strip().lstrip("#")
    if len(value) == 3:
        value = "".join(ch * 2 for ch in value)
    if len(value) != 6:
        raise ValueError(f"expected #RRGGBB colour, got {color!r}")
    return tuple(int(value[i:i + 2], 16) / 255.0 for i in (0, 2, 4))


def rgb_to_hex(rgb) -> str:
    return "#" + "".join(f"{max(0, min(255, round(c * 255))):02X}" for c in rgb[:3])


def lighter(rgb, factor):
    """``QColor.lighter(factor)`` on a 0..1 RGB tuple (Qt's HSV algorithm)."""
    import colorsys
    h, s, v = colorsys.rgb_to_hsv(*rgb)
    v = v * factor / 100.0
    if v > 1.0:
        # Qt moves the overflow into reduced saturation.
        s = max(0.0, s - (v - 1.0))
        v = 1.0
    return colorsys.hsv_to_rgb(h, s, v)


def darker(rgb, factor):
    """``QColor.darker(factor)`` on a 0..1 RGB tuple (Qt's HSV algorithm)."""
    import colorsys
    h, s, v = colorsys.rgb_to_hsv(*rgb)
    return colorsys.hsv_to_rgb(h, s, v * 100.0 / factor)


def contrast_text(rgb) -> str:
    """Black or white, whichever reads better on *rgb*."""
    def channel(value):
        return value / 12.92 if value <= 0.03928 else ((value + 0.055) / 1.055) ** 2.4
    luminance = (0.2126 * channel(rgb[0]) + 0.7152 * channel(rgb[1])
                 + 0.0722 * channel(rgb[2]))
    return "#000000" if luminance > 0.45 else "#FFFFFF"


def accent_tokens(mode: str, accent: str) -> dict:
    """Accent-derived shades for *mode* as hex strings plus alpha values."""
    dark = mode == DARK
    rgb = hex_to_rgb(accent)
    return {
        "accent": rgb_to_hex(rgb),
        "accent_hover": rgb_to_hex(lighter(rgb, 115) if dark else darker(rgb, 110)),
        "accent_pressed": rgb_to_hex(lighter(rgb, 130) if dark else darker(rgb, 125)),
        "accent_text": contrast_text(rgb),
        "accent_soft_alpha": 0.28 if dark else 0.18,
        "accent_faint_alpha": 0.14 if dark else 0.09,
    }


def hex_tokens(mode: str, accent: str) -> dict:
    """All colour tokens for *mode* as hex strings (Qt stylesheet form)."""
    if mode not in BASE:
        raise ValueError(f"mode must be {LIGHT!r} or {DARK!r}")
    tokens = dict(BASE[mode])
    tokens.update(accent_tokens(mode, accent))
    return tokens


def vtk_tokens(mode: str = LIGHT, accent: str = DEFAULT_ACCENT) -> dict:
    """All colour tokens as 0..1 RGB tuples (VTK form).

    Adds ``accent_soft``/``accent_faint``: the accent pre-blended over the
    panel colour, since most VTK 2D props take an opaque colour.
    """
    tokens = {}
    for key, value in hex_tokens(mode, accent).items():
        tokens[key] = hex_to_rgb(value) if isinstance(value, str) else value
    panel = tokens["panel"]
    accent_rgb = tokens["accent"]
    for name in ("soft", "faint"):
        alpha = tokens[f"accent_{name}_alpha"]
        tokens[f"accent_{name}"] = tuple(
            p + (a - p) * alpha for p, a in zip(panel, accent_rgb))
    return tokens
