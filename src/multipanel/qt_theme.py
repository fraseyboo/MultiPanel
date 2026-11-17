"""Light/dark theming with a configurable accent colour for the Qt panels.

Everything colour-related for the classic Qt UI is defined here so the panels
themselves only carry object names (``panelFrame``, ``titleBar`` ...). The
theme is applied in three layers:

* the Fusion style, so native widgets render the same on every platform;
* a ``QPalette`` derived from the theme, which Fusion uses for inputs,
  trees, scrollbars, focus rings and selection highlights;
* one stylesheet on the main window for the custom panel chrome.

``ThemeManager`` owns the current :class:`PanelTheme`, re-applies it on
change, persists it with ``QSettings`` and can install an *Appearance* menu.

UI scale
--------
``PanelTheme.scale`` multiplies every text size in the stylesheet and every
pixel metric registered through :func:`set_metrics` (fixed button sizes,
list heights, icon sizes ...). Widgets register their *unscaled* metrics
once; :func:`rescale_registered_widgets` re-applies them whenever the scale
changes, so scaling is live and needs no restart.
"""
from __future__ import annotations

import sys
import weakref
from dataclasses import dataclass, replace

if sys.platform == 'darwin':
    from PyQt5.QtCore import QObject, QSettings, pyqtSignal
    from PyQt5.QtCore import QSize
    from PyQt5.QtGui import QColor, QIcon, QKeySequence, QPalette, QPixmap
    from PyQt5.QtWidgets import (
        QAction, QActionGroup, QApplication, QColorDialog, QStyleFactory)
else:
    from PyQt6.QtCore import QObject, QSettings, QSize, pyqtSignal
    from PyQt6.QtGui import (
        QAction, QActionGroup, QColor, QIcon, QKeySequence, QPalette, QPixmap)
    from PyQt6.QtWidgets import QApplication, QColorDialog, QStyleFactory

from .scene_theme import apply_scene_theme
from .core import refresh_renderer_theme
from . import ui_theme as _shared_theme

LIGHT = "light"
DARK = "dark"
DEFAULT_ACCENT = "#037CF6"

ACCENT_PRESETS = {
    "Blue": "#037CF6",
    "Teal": "#0F9D9A",
    "Green": "#2E9E4F",
    "Amber": "#D98A00",
    "Red": "#D64545",
    "Purple": "#8A4FD8",
}


def _settings_scope():
    from .config import settings_scope

    return settings_scope()


_KEY_MODE = "ui/theme_mode"
_KEY_ACCENT = "ui/accent_color"
_KEY_SCALE = "ui/scale"

SCALE_PRESETS = (0.75, 0.9, 1.0, 1.1, 1.25, 1.5)
MIN_SCALE, MAX_SCALE = SCALE_PRESETS[0], SCALE_PRESETS[-1]

# Unscaled text sizes in px. All panel text uses BODY so sizes match across
# panels; only glyph-only controls (chevrons, step arrows) use GLYPH.
_FONT_BODY = 12
_FONT_GLYPH = 9


# ---------------------------------------------------------------------------
# UI scale: global factor plus a registry of widgets with pixel metrics
# ---------------------------------------------------------------------------

_current_scale = 1.0
_registered = weakref.WeakSet()


def ui_scale() -> float:
    """Return the active UI scale factor."""
    return _current_scale


def scaled(px) -> int:
    """Scale an unscaled pixel value by the active UI scale."""
    return max(1, int(round(float(px) * _current_scale)))


def _apply_metrics(widget):
    metrics = getattr(widget, "_ui_base_metrics", None) or {}
    if "fixed_size" in metrics:
        w, h = metrics["fixed_size"]
        widget.setFixedSize(scaled(w), scaled(h))
    if "fixed_width" in metrics:
        widget.setFixedWidth(scaled(metrics["fixed_width"]))
    if "fixed_height" in metrics:
        widget.setFixedHeight(scaled(metrics["fixed_height"]))
    if "min_width" in metrics:
        widget.setMinimumWidth(scaled(metrics["min_width"]))
    if "min_height" in metrics:
        widget.setMinimumHeight(scaled(metrics["min_height"]))
    if "max_height" in metrics:
        widget.setMaximumHeight(scaled(metrics["max_height"]))
        widget.updateGeometry()
    if "icon_size" in metrics:
        w, h = metrics["icon_size"]
        widget.setIconSize(QSize(scaled(w), scaled(h)))


def set_metrics(widget, **metrics):
    """Register unscaled pixel metrics on *widget* and apply them now.

    Accepted keys: ``fixed_size=(w, h)``, ``fixed_width``, ``fixed_height``,
    ``min_width``, ``min_height``, ``max_height``, ``icon_size=(w, h)``.
    """
    base = dict(getattr(widget, "_ui_base_metrics", None) or {})
    base.update(metrics)
    widget._ui_base_metrics = base
    _registered.add(widget)
    _apply_metrics(widget)
    return widget


def rescale_registered_widgets():
    """Re-apply every registered widget's metrics at the active scale."""
    for widget in list(_registered):
        try:
            _apply_metrics(widget)
        except RuntimeError:  # C++ object already deleted
            _registered.discard(widget)


def _clamp_scale(value) -> float:
    try:
        value = float(value)
    except (TypeError, ValueError):
        return 1.0
    return min(MAX_SCALE, max(MIN_SCALE, value))

# Neutral surfaces per mode, shared with the VTK UI (LIBS/ui_theme.py).
_BASE = _shared_theme.BASE


def _hex(color: QColor) -> str:
    return color.name().upper()


def _rgba(color: QColor, alpha: float) -> str:
    return (f"rgba({color.red()}, {color.green()}, {color.blue()}, "
            f"{int(round(alpha * 255))})")


def _contrast_text(color: QColor) -> str:
    """Return black or white, whichever reads better on *color*."""
    def channel(value):
        value /= 255.0
        return value / 12.92 if value <= 0.03928 else ((value + 0.055) / 1.055) ** 2.4
    luminance = (0.2126 * channel(color.red()) + 0.7152 * channel(color.green())
                 + 0.0722 * channel(color.blue()))
    return "#000000" if luminance > 0.45 else "#FFFFFF"


@dataclass(frozen=True)
class PanelTheme:
    """A UI mode plus accent colour; everything else is derived."""

    mode: str = DARK
    accent: str = DEFAULT_ACCENT
    scale: float = 1.0

    def __post_init__(self):
        if self.mode not in (LIGHT, DARK):
            raise ValueError(f"mode must be {LIGHT!r} or {DARK!r}")
        if not QColor(self.accent).isValid():
            raise ValueError(f"invalid accent colour {self.accent!r}")
        if not MIN_SCALE <= float(self.scale) <= MAX_SCALE:
            raise ValueError(
                f"scale must be between {MIN_SCALE} and {MAX_SCALE}")

    @property
    def is_dark(self) -> bool:
        return self.mode == DARK

    def tokens(self) -> dict:
        """Return the named colours used by the palette and stylesheet."""
        tokens = dict(_BASE[self.mode])
        accent = QColor(self.accent)
        tokens["accent"] = _hex(accent)
        tokens["accent_hover"] = _hex(
            accent.lighter(115) if self.is_dark else accent.darker(110))
        tokens["accent_pressed"] = _hex(
            accent.lighter(130) if self.is_dark else accent.darker(125))
        tokens["accent_text"] = _contrast_text(accent)
        tokens["accent_soft"] = _rgba(accent, 0.28 if self.is_dark else 0.18)
        tokens["accent_faint"] = _rgba(accent, 0.14 if self.is_dark else 0.09)
        tokens["font"] = max(8, int(round(_FONT_BODY * self.scale)))
        tokens["font_glyph"] = max(6, int(round(_FONT_GLYPH * self.scale)))
        return tokens


def build_palette(theme: PanelTheme) -> QPalette:
    """Return a Fusion palette matching *theme*."""
    t = theme.tokens()
    palette = QPalette()
    roles = QPalette.ColorRole if hasattr(QPalette, "ColorRole") else QPalette
    groups = QPalette.ColorGroup if hasattr(QPalette, "ColorGroup") else QPalette

    def put(role_name, color, group=None):
        role = getattr(roles, role_name, None)
        if role is None:  # e.g. PlaceholderText on older Qt
            return
        if group is None:
            palette.setColor(role, QColor(color))
        else:
            palette.setColor(group, role, QColor(color))

    put("Window", t["pane"])
    put("WindowText", t["text"])
    put("Base", t["input"])
    put("AlternateBase", t["row_hover"])
    put("Text", t["text"])
    put("Button", t["button"])
    put("ButtonText", t["text"])
    put("BrightText", "#FFFFFF")
    put("ToolTipBase", t["tooltip"])
    put("ToolTipText", t["text"])
    put("PlaceholderText", t["muted"])
    put("Highlight", t["accent"])
    put("HighlightedText", t["accent_text"])
    put("Link", t["accent"])
    put("Light", t["button_hover"])
    put("Midlight", t["button"])
    put("Mid", t["border"])
    put("Dark", t["border"])
    put("Shadow", "#000000")
    disabled = groups.Disabled
    for role_name in ("WindowText", "Text", "ButtonText"):
        put(role_name, t["disabled"], disabled)
    put("Highlight", t["border"], disabled)
    return palette


def build_stylesheet(theme: PanelTheme) -> str:
    """Return the stylesheet for the custom panel chrome."""
    t = theme.tokens()
    return f"""
QWidget {{ font-size: {t['font']}px; }}
QMainWindow, QDockWidget {{ background: {t['pane']}; }}
/* The pane handles resize the docks; hide Qt's own dock separator so there
   is a single drag bar per pane. */
QMainWindow::separator {{ width: 0px; height: 0px; }}
QWidget#paneContainer {{ background: {t['pane']}; }}
QScrollArea#paneScroll {{ background: {t['pane']}; border: none; }}

QFrame#panelFrame {{
    background: {t['panel']};
    border: 1px solid {t['border']};
    border-radius: 6px;
}}
QWidget#titleBar {{
    background: {t['title']};
    border: none;
    border-bottom: 1px solid {t['border']};
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
}}
QFrame#panelFrame[collapsed="true"] QWidget#titleBar {{
    border-bottom: none;
    border-radius: 6px;
}}
QWidget#panelBody {{ background: transparent; }}
QFrame#panelFrame QLabel {{ color: {t['text']}; background: transparent; }}
QLabel#panelTitle {{
    color: {t['text']};
    font-weight: 600;
}}
QLabel#mutedLabel, QLabel[textRole="secondary"] {{ color: {t['muted']}; }}
QLabel[textRole="mono"] {{ font-family: "Menlo", "Consolas", "DejaVu Sans Mono", monospace; }}
QPushButton#collapseButton {{
    background: transparent;
    border: none;
    color: {t['muted']};
    font-size: {t['font_glyph']}px;
    padding: 0;
}}
QPushButton#collapseButton:hover {{ color: {t['accent']}; }}

QPushButton {{
    background: {t['button']};
    color: {t['text']};
    border: 1px solid {t['input_border']};
    border-radius: 4px;
    padding: 3px 10px;
}}
QPushButton:hover {{ background: {t['button_hover']}; border-color: {t['accent']}; }}
QPushButton:pressed {{ background: {t['accent_soft']}; }}
QPushButton:checked {{
    background: {t['accent']};
    color: {t['accent_text']};
    border-color: {t['accent']};
}}
QPushButton:disabled {{
    color: {t['disabled']};
    background: {t['panel']};
    border-color: {t['border']};
}}
QPushButton#primaryButton {{
    background: {t['accent']};
    color: {t['accent_text']};
    border-color: {t['accent']};
}}
QPushButton#primaryButton:hover {{ background: {t['accent_hover']}; }}
QPushButton#primaryButton:pressed {{ background: {t['accent_pressed']}; }}
QPushButton#primaryButton:disabled {{
    color: {t['disabled']};
    background: {t['panel']};
    border-color: {t['border']};
}}

QPushButton#iconButton {{
    background: {t['button']};
    border: 1px solid {t['border']};
    border-radius: 6px;
    padding: 2px;
}}
QPushButton#iconButton:hover {{ border-color: {t['accent']}; background: {t['button_hover']}; }}
QPushButton#iconButton:checked {{
    background: {t['accent_soft']};
    border-color: {t['accent']};
}}
QPushButton#stepButton, QPushButton#rowToggle {{
    background: transparent;
    border: none;
    color: {t['muted']};
    padding: 0;
}}
QPushButton#stepButton {{ font-size: {t['font_glyph']}px; }}
QPushButton#stepButton:hover, QPushButton#rowToggle:hover {{ color: {t['accent']}; }}
QPushButton#rowToggle:checked {{ color: {t['accent']}; background: transparent; }}

QWidget#listRow {{ background: transparent; border-radius: 3px; }}
QWidget#listRow:hover {{ background: {t['row_hover']}; }}
QWidget#listContainer {{ background: {t['input']}; }}
QScrollArea#listScroll {{
    background: {t['input']};
    border: 1px solid {t['border']};
    border-radius: 4px;
}}
QLineEdit#actorName {{
    background: transparent;
    border: none;
    border-radius: 3px;
    padding: 1px 3px;
    color: {t['text']};
}}
QLineEdit#actorName[selected="true"] {{ background: {t['accent_soft']}; }}

QToolTip {{
    background: {t['tooltip']};
    color: {t['text']};
    border: 1px solid {t['border']};
    padding: 3px;
}}
"""


class ThemeManager(QObject):
    """Apply, change and persist the Qt UI theme."""

    theme_changed = pyqtSignal(object)
    # (old_scale, new_scale), emitted after metrics have been re-applied.
    scale_changed = pyqtSignal(float, float)

    def __init__(self, main_window, theme: PanelTheme, renderer=None,
                 persist: bool = True):
        super().__init__(main_window)
        self.main_window = main_window
        self.renderer = renderer
        self.persist = persist
        self.theme = theme
        self._mode_actions = {}
        self._scale_actions = {}

    # ---- construction --------------------------------------------------
    @classmethod
    def from_settings(cls, main_window, renderer=None, default_mode=DARK,
                      default_accent=DEFAULT_ACCENT, default_scale=1.0):
        """Create a manager from saved settings, falling back to defaults."""
        settings = QSettings(*_settings_scope())
        mode = str(settings.value(_KEY_MODE, default_mode) or default_mode)
        accent = str(settings.value(_KEY_ACCENT, default_accent) or default_accent)
        scale = _clamp_scale(settings.value(_KEY_SCALE, default_scale))
        try:
            theme = PanelTheme(mode=mode, accent=accent, scale=scale)
        except ValueError:
            theme = PanelTheme(mode=default_mode, accent=default_accent,
                               scale=_clamp_scale(default_scale))
        return cls(main_window, theme, renderer=renderer)

    # ---- application ---------------------------------------------------
    def apply(self):
        """Apply the current theme to the application and main window."""
        global _current_scale
        old_scale = _current_scale
        _current_scale = float(self.theme.scale)
        app = QApplication.instance()
        if app is not None:
            fusion = QStyleFactory.create("Fusion")
            if fusion is not None and app.style().objectName().lower() != "fusion":
                app.setStyle(fusion)
            app.setPalette(build_palette(self.theme))
            # Dialogs and popups outside the main window follow the scale too.
            font = app.font()
            font.setPixelSize(self.theme.tokens()["font"])
            app.setFont(font)
        self.main_window.setStyleSheet(build_stylesheet(self.theme))
        rescale_registered_widgets()
        self.main_window.setProperty("themeMode", self.theme.mode)
        # Keep the VTK-side theme object in step for code that reads it.
        legacy = getattr(self.renderer, "theme", None)
        if legacy is not None:
            if hasattr(legacy, "update"):
                legacy.update(dark_mode=self.theme.is_dark,
                              accent_color=self.theme.accent)
            else:
                legacy.dark_mode = self.theme.is_dark
                legacy.accent_color = self.theme.accent
        if self.renderer is not None:
            refresh_renderer_theme(self.renderer)
            # 3D background, reference grid and in-scene overlays.
            apply_scene_theme(self.renderer, self.theme.is_dark,
                              self.theme.accent)
        self._sync_actions()
        self.theme_changed.emit(self.theme)
        if old_scale != _current_scale:
            self.scale_changed.emit(old_scale, _current_scale)

    def set_theme(self, theme: PanelTheme):
        self.theme = theme
        if self.persist:
            settings = QSettings(*_settings_scope())
            settings.setValue(_KEY_MODE, theme.mode)
            settings.setValue(_KEY_ACCENT, theme.accent)
            settings.setValue(_KEY_SCALE, float(theme.scale))
        self.apply()

    def set_mode(self, mode: str):
        self.set_theme(replace(self.theme, mode=mode))

    def set_accent(self, accent: str):
        self.set_theme(replace(self.theme, accent=QColor(accent).name().upper()))

    def set_scale(self, scale: float):
        self.set_theme(replace(self.theme, scale=_clamp_scale(scale)))

    def step_scale(self, direction: int):
        """Move to the next larger (+1) or smaller (-1) scale preset."""
        current = float(self.theme.scale)
        if direction > 0:
            options = [s for s in SCALE_PRESETS if s > current + 1e-6]
            target = options[0] if options else MAX_SCALE
        else:
            options = [s for s in SCALE_PRESETS if s < current - 1e-6]
            target = options[-1] if options else MIN_SCALE
        self.set_scale(target)

    def choose_custom_accent(self):
        color = QColorDialog.getColor(
            QColor(self.theme.accent), self.main_window, "Accent colour")
        if color.isValid():
            self.set_accent(color.name())

    # ---- menu ----------------------------------------------------------
    def install_menu(self, menu_bar=None, title="Appearance"):
        """Add an Appearance menu with mode and accent choices."""
        menu_bar = menu_bar or self.main_window.menuBar()
        menu = menu_bar.addMenu(title)
        modes = QActionGroup(menu)
        modes.setExclusive(True)
        for mode, label in ((LIGHT, "Light mode"), (DARK, "Dark mode")):
            action = QAction(label, menu)
            action.setCheckable(True)
            action.triggered.connect(lambda _checked=False, m=mode: self.set_mode(m))
            modes.addAction(action)
            menu.addAction(action)
            self._mode_actions[mode] = action
        menu.addSeparator()
        accent_menu = menu.addMenu("Accent colour")
        for name, color in ACCENT_PRESETS.items():
            action = QAction(_swatch_icon(color), name, accent_menu)
            action.triggered.connect(
                lambda _checked=False, c=color: self.set_accent(c))
            accent_menu.addAction(action)
        accent_menu.addSeparator()
        custom = QAction("Custom…", accent_menu)
        custom.triggered.connect(self.choose_custom_accent)
        accent_menu.addAction(custom)

        scale_menu = menu.addMenu("UI scale")
        for direction, label, keys in (
                (1, "Larger", QKeySequence.StandardKey.ZoomIn
                 if hasattr(QKeySequence, "StandardKey") else QKeySequence.ZoomIn),
                (-1, "Smaller", QKeySequence.StandardKey.ZoomOut
                 if hasattr(QKeySequence, "StandardKey") else QKeySequence.ZoomOut)):
            action = QAction(label, scale_menu)
            action.setShortcut(QKeySequence(keys))
            action.triggered.connect(
                lambda _checked=False, d=direction: self.step_scale(d))
            scale_menu.addAction(action)
        reset = QAction("Actual size", scale_menu)
        reset.setShortcut(QKeySequence("Ctrl+0"))
        reset.triggered.connect(lambda _checked=False: self.set_scale(1.0))
        scale_menu.addAction(reset)
        scale_menu.addSeparator()
        scales = QActionGroup(scale_menu)
        scales.setExclusive(True)
        for value in SCALE_PRESETS:
            action = QAction(f"{int(round(value * 100))}%", scale_menu)
            action.setCheckable(True)
            action.triggered.connect(
                lambda _checked=False, v=value: self.set_scale(v))
            scales.addAction(action)
            scale_menu.addAction(action)
            self._scale_actions[value] = action
        self._sync_actions()
        return menu

    def _sync_actions(self):
        for mode, action in self._mode_actions.items():
            action.setChecked(mode == self.theme.mode)
        for value, action in self._scale_actions.items():
            action.setChecked(abs(value - float(self.theme.scale)) < 1e-6)


def _swatch_icon(color: str) -> QIcon:
    pixmap = QPixmap(14, 14)
    pixmap.fill(QColor(color))
    return QIcon(pixmap)
