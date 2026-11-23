"""Trace PNG icon silhouettes and build MultiPanel SVG/VTK derivatives.

The PNG alpha channel defines the geometry.  RGB values in transparent edge
pixels are deliberately ignored, which makes this suitable for antialiased
AI-generated or hand-painted monochrome masters.

Usage::

    python tools/convert_png_icons.py open copy paste

For each name this writes ``svg_icons/<name>.svg``, regenerates the tintable
SVG, and writes ``vtk_icons/<name>.vtk`` using MultiPanel's established SVG
converter.  Existing outputs are replaced only for explicitly named icons.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ICONS = ROOT / "src" / "multipanel" / "icons"
PNG_DIR = ICONS / "png_icons"
SVG_DIR = ICONS / "svg_icons"
VTK_DIR = ICONS / "vtk_icons"

ALPHA_THRESHOLD = 32
SIMPLIFY_FACTOR = 0.00075


def _fmt(value: float) -> str:
    return f"{value:.3f}".rstrip("0").rstrip(".")


def trace_png(source: Path, target: Path) -> tuple[int, str]:
    """Trace *source* alpha contours into one even-odd compound SVG path."""
    import cv2
    import numpy as np

    image = cv2.imread(str(source), cv2.IMREAD_UNCHANGED)
    if image is None:
        raise ValueError(f"could not read {source}")
    if image.ndim != 3 or image.shape[2] != 4:
        raise ValueError(f"{source} is not RGBA")

    height, width = image.shape[:2]
    alpha = image[:, :, 3]
    mask = np.where(alpha >= ALPHA_THRESHOLD, 255, 0).astype(np.uint8)
    contours, hierarchy = cv2.findContours(
        mask, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
    if hierarchy is None or not contours:
        raise ValueError(f"{source} contains no visible contours")

    commands: list[str] = []
    kept = 0
    for contour in contours:
        if abs(cv2.contourArea(contour)) < 4.0:
            continue
        epsilon = max(0.15, SIMPLIFY_FACTOR * cv2.arcLength(contour, True))
        points = cv2.approxPolyDP(contour, epsilon, True).reshape(-1, 2)
        if len(points) < 3:
            continue
        commands.append("M" + " L".join(
            f"{_fmt(float(x))},{_fmt(float(y))}" for x, y in points) + " Z")
        kept += 1

    visible = alpha >= 128
    if not np.any(visible):
        visible = alpha >= ALPHA_THRESHOLD
    # OpenCV is BGRA.  Median suppresses coloured antialias fringes.
    bgr = np.median(image[:, :, :3][visible], axis=0).round().astype(int)
    colour = f"#{bgr[2]:02x}{bgr[1]:02x}{bgr[0]:02x}"
    svg = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" '
        f'height="{height}" viewBox="0 0 {width} {height}">\n'
        f'  <!-- Traced from png_icons/{source.name} by '
        'tools/convert_png_icons.py. -->\n'
        f'  <path fill="{colour}" fill-rule="evenodd" d="'
        + " ".join(commands) + '"/>\n</svg>\n')
    target.write_text(svg, encoding="utf-8")
    return kept, colour


def write_vtk(svg_path: Path, vtk_path: Path) -> None:
    from multipanel.icon_converter import (convert_svg_to_triangles,
                                           save_shapes_as_polydata)

    shapes = convert_svg_to_triangles(
        str(svg_path), plot=False, triangulate_opts="pq10")
    if not shapes:
        raise ValueError(f"no VTK geometry produced for {svg_path}")
    save_shapes_as_polydata(shapes, str(vtk_path))
    _normalize_text(vtk_path)


def _normalize_text(path: Path) -> None:
    """Remove writer-introduced trailing spaces and excess final lines."""
    lines = path.read_text(encoding="utf-8").splitlines()
    path.write_text("\n".join(line.rstrip() for line in lines).rstrip() + "\n",
                    encoding="utf-8")


def main(names: list[str]) -> int:
    if not names:
        print("provide one or more icon names", file=sys.stderr)
        return 2

    sys.path.insert(0, str(ROOT / "src"))
    SVG_DIR.mkdir(parents=True, exist_ok=True)
    VTK_DIR.mkdir(parents=True, exist_ok=True)
    for name in names:
        png_path = PNG_DIR / f"{name}.png"
        if not png_path.is_file():
            print(f"missing: {png_path}", file=sys.stderr)
            return 1
        svg_path = SVG_DIR / f"{name}.svg"
        contours, colour = trace_png(png_path, svg_path)
        write_vtk(svg_path, VTK_DIR / f"{name}.vtk")
        print(f"wrote {name}: {contours} contour(s), {colour}")

    subprocess.run(
        [sys.executable, str(ROOT / "tools" / "make_tintable_icons.py"),
         *names], check=True)
    for name in names:
        _normalize_text(SVG_DIR / f"{name}.svg")
        _normalize_text(ICONS / "tintable" / f"{name}.svg")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
