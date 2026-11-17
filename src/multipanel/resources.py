"""Package resource locations without importing the widget implementation."""

from pathlib import Path


PACKAGE_ROOT = Path(__file__).resolve().parent
ICON_ROOT = str(PACKAGE_ROOT / "icons")
FONT_ROOT = str(PACKAGE_ROOT / "fonts")

# One folder per icon format, side by side under an "icons" folder.
ICON_FORMATS = ("vtk", "svg", "png")

__all__ = ["FONT_ROOT", "ICON_FORMATS", "ICON_ROOT", "PACKAGE_ROOT",
           "icon_folder", "icon_sources"]


def icon_folder(fmt, root=ICON_ROOT):
    """The folder of one icon format, e.g. ``icons/svg_icons``."""
    if fmt not in ICON_FORMATS:
        raise ValueError(f"icon format must be one of {ICON_FORMATS}")
    return str(Path(root) / f"{fmt}_icons")


def icon_sources(path, formats=("svg", "png")):
    """Where the SVG/PNG source of icon ``path`` (typically a missing
    ``.vtk``) may be, in order of preference.

    Only the format folder and the extension change, never other parts
    of the path (a directory such as ``multipanel`` keeps its name):

    1. the matching folder next to the icon's: ``…/vtk_icons/x.vtk`` →
       ``…/svg_icons/x.svg``, then ``…/png_icons/x.png``;
    2. the icon's own folder: ``…/x.svg``;
    3. the package's icon folders (for paths from elsewhere).
    """
    path = Path(path)
    stem, folder = path.stem, path.parent
    in_format_folder = folder.name.endswith("_icons") and \
        folder.name[:-len("_icons")] in ICON_FORMATS
    candidates = []
    for fmt in formats:
        if in_format_folder:
            candidates.append(folder.parent / f"{fmt}_icons" / f"{stem}.{fmt}")
        candidates.append(folder / f"{stem}.{fmt}")
    for fmt in formats:
        candidates.append(Path(icon_folder(fmt)) / f"{stem}.{fmt}")
    seen, result = set(), []
    for candidate in candidates:
        if candidate != path and candidate not in seen:
            seen.add(candidate)
            result.append(str(candidate))
    return result
