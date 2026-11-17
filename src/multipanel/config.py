"""Renderer-level UI theme shared by the VTK widgets and the Qt front end."""
from __future__ import annotations

import os

from . import ui_theme


SCALE_RANGE = (0.75, 1.5)
# Where the Qt preferences (theme, accent, scale) are stored. Applications
# set their own name with set_settings_scope() before reading a theme.
_SETTINGS_SCOPE = ["MultiPanel", "MultiPanel"]


def set_settings_scope(organization, application=None):
    """Store and read the UI preferences under ``organization`` /
    ``application`` (``QSettings`` names; the application defaults to the
    organization). Call once at start-up, before the theme is read."""
    _SETTINGS_SCOPE[:] = [str(organization),
                          str(application or organization)]


def settings_scope():
    """``(organization, application)`` of the preference store."""
    return tuple(_SETTINGS_SCOPE)


def _clamp_scale(value):
    try:
        value = float(value)
    except (TypeError, ValueError):
        return 1.0
    return round(min(SCALE_RANGE[1], max(SCALE_RANGE[0], value)), 2)


def _settings():
    """The shared Qt preference store, or None when Qt is unavailable."""
    try:
        from PyQt5.QtCore import QSettings  # noqa: WPS433
    except ImportError:
        try:
            from PyQt6.QtCore import QSettings  # noqa: WPS433
        except ImportError:
            return None
    return QSettings(*settings_scope())


def save_preferences(dark_mode=None, accent_color=None, ui_scale=None):
    """Persist appearance preferences (same keys as the Qt Appearance menu).

    Returns True when they were written."""
    settings = _settings()
    if settings is None:
        return False
    if dark_mode is not None:
        settings.setValue("ui/theme_mode", ui_theme.DARK if dark_mode else ui_theme.LIGHT)
    if accent_color is not None:
        settings.setValue("ui/accent_color", accent_color)
    if ui_scale is not None:
        settings.setValue("ui/scale", _clamp_scale(ui_scale))
    settings.sync()
    return True


class theme:
    """Light/dark UI colours and type sizes for one renderer.

    Colours come from the shared design tokens (``LIBS/ui_theme.py``) so the
    VTK UI matches the Qt UI. Attributes are 0..1 RGB tuples:

    ``pane_color``           dock / pane background
    ``panel_background_color`` panel surface (kept for existing callers)
    ``title_color``          panel header band
    ``border_color``         hairline panel borders
    ``text_color`` / ``muted_text_color`` primary / secondary text
    ``accent_color_rgb``     accent; ``accent_soft`` / ``accent_faint`` are
                             the accent pre-blended over the panel colour
    ``row_hover_color``, ``input_color``

    plus ``body_font_size`` / ``title_font_size`` (VTK points).
    """

    BODY_FONT_SIZE = 13
    TITLE_FONT_SIZE = 14

    def __init__(self, dark_mode=True, accent_color=ui_theme.DEFAULT_ACCENT,
                 ui_scale=1.0):
        self.dark_mode = bool(dark_mode)
        # Interface size multiplier (shared "ui/scale" preference).
        self.ui_scale = _clamp_scale(ui_scale)
        # A colour saved from the Qt Appearance menu takes precedence.
        self.accent_color = accent_color
        self.body_font_size = self.BODY_FONT_SIZE
        self.title_font_size = self.TITLE_FONT_SIZE
        self.update()

    def update(self, dark_mode=None, accent_color=None):
        """Recompute every colour after a mode or accent change."""
        if dark_mode is not None:
            self.dark_mode = bool(dark_mode)
        if accent_color is not None:
            self.accent_color = accent_color
        mode = ui_theme.DARK if self.dark_mode else ui_theme.LIGHT
        tokens = ui_theme.vtk_tokens(mode, self.accent_color)
        self.mode = mode
        self.tokens = tokens
        self.pane_color = tokens["pane"]
        self.panel_background_color = tokens["panel"]
        self.title_color = tokens["title"]
        self.border_color = tokens["border"]
        self.text_color = tokens["text"]
        self.muted_text_color = tokens["muted"]
        self.accent_color_rgb = tokens["accent"]
        self.accent_soft = tokens["accent_soft"]
        self.accent_faint = tokens["accent_faint"]
        self.row_hover_color = tokens["row_hover"]
        self.input_color = tokens["input"]
        self.button_color = tokens["button"]
        self.button_hover_color = tokens["button_hover"]
        # Recessed list background: slightly darker than the panel in both
        # modes (the input colour is lighter than the panel in light mode).
        panel, pane = tokens["panel"], tokens["pane"]
        self.well_color = (tokens["input"] if self.dark_mode else
                           tuple(p + (q - p) * 0.45 for p, q in zip(panel, pane)))
        return self

    @classmethod
    def from_preferences(cls, default_dark=False,
                         default_accent=ui_theme.DEFAULT_ACCENT):
        """Theme from the Qt Appearance preferences when available.

        ``MULTIPANEL_UI_THEME`` (``light``/``dark``),
        ``MULTIPANEL_UI_ACCENT`` (``#RRGGBB``) and ``MULTIPANEL_UI_SCALE``
        override the saved choice; without Qt the defaults
        apply.
        """
        mode, accent, scale = None, None, 1.0
        settings = _settings()
        if settings is not None:
            mode = settings.value("ui/theme_mode", None)
            accent = settings.value("ui/accent_color", None)
            scale = settings.value("ui/scale", 1.0)
        mode = os.environ.get("MULTIPANEL_UI_THEME", mode)
        accent = os.environ.get("MULTIPANEL_UI_ACCENT", accent) or default_accent
        dark = (str(mode).lower() == ui_theme.DARK) if mode else default_dark
        try:
            ui_theme.hex_to_rgb(accent)
        except ValueError:
            accent = default_accent
        scale = os.environ.get("MULTIPANEL_UI_SCALE", scale)
        return cls(dark_mode=dark, accent_color=accent, ui_scale=scale)

    def __repr__(self):
        return f"theme(mode={self.mode!r}, accent={self.accent_color!r})"
