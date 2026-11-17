"""Finding an icon's SVG/PNG source when its .vtk is missing."""
import shutil
from pathlib import Path

import pytest

from multipanel.resources import ICON_ROOT, icon_folder, icon_sources


def test_only_the_format_folder_and_extension_change():
    # "vtk" also appears in the package and project folder names.
    path = "/home/me/my_vtk_app/multipanel/icons/vtk_icons/add_shape.vtk"
    sources = icon_sources(path)
    assert sources[:4] == [
        "/home/me/my_vtk_app/multipanel/icons/svg_icons/add_shape.svg",
        "/home/me/my_vtk_app/multipanel/icons/vtk_icons/add_shape.svg",
        "/home/me/my_vtk_app/multipanel/icons/png_icons/add_shape.png",
        "/home/me/my_vtk_app/multipanel/icons/vtk_icons/add_shape.png",
    ]
    assert all("my_vtk_app/multipanel" in s for s in sources[:4])
    # then the package's own folders
    assert sources[-2:] == [str(Path(ICON_ROOT) / "svg_icons" / "add_shape.svg"),
                            str(Path(ICON_ROOT) / "png_icons" / "add_shape.png")]


def test_icons_outside_format_folders_look_beside_themselves():
    sources = icon_sources("/data/vtk/custom/logo.vtk")
    assert sources[:2] == ["/data/vtk/custom/logo.svg",
                           "/data/vtk/custom/logo.png"]


def test_icon_folder():
    assert icon_folder("png") == str(Path(ICON_ROOT) / "png_icons")
    with pytest.raises(ValueError):
        icon_folder("jpg")


def test_a_missing_vtk_icon_is_built_from_its_svg(tmp_path):
    pytest.importorskip("multipanel.icon_converter")
    from multipanel.controls import VectorButtonWidget
    from multipanel.testing import UiHarness

    icons = tmp_path / "vtk_project" / "icons"     # "vtk" in the path
    (icons / "svg_icons").mkdir(parents=True)
    (icons / "vtk_icons").mkdir()
    shutil.copy(Path(ICON_ROOT) / "svg_icons" / "add_shape.svg",
                icons / "svg_icons" / "fallback_test.svg")
    missing = icons / "vtk_icons" / "fallback_test.vtk"
    with UiHarness(size=(400, 300)) as ui:
        button = VectorButtonWidget(ui.renderer, ui.interactor,
                                    input_data=[str(missing)],
                                    icon_name=["fallback_test"],
                                    bounds=(0.1, 0.3, 0.1, 0.3))
        assert button.polydata.GetNumberOfPoints() > 0
    assert missing.exists()                         # cached for next time
