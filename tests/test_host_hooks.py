"""The former package name, and the hooks that keep host specifics out."""
import os
import subprocess
import sys
from pathlib import Path

import pytest
import vtk

SRC = Path(__file__).resolve().parents[1] / "src"


def test_old_package_name_is_an_alias_with_a_warning():
    code = (
        "import warnings\n"
        "with warnings.catch_warnings(record=True) as caught:\n"
        "    warnings.simplefilter('always')\n"
        "    import vtk_2d_ui\n"
        "    from vtk_2d_ui.controls import TextWidget\n"
        "    import vtk_2d_ui.chartview as old_chartview\n"
        "import multipanel, multipanel.controls, multipanel.chartview\n"
        "assert vtk_2d_ui is multipanel\n"
        "assert TextWidget is multipanel.controls.TextWidget\n"
        "assert old_chartview is multipanel.chartview\n"
        "assert any(issubclass(w.category, DeprecationWarning) and\n"
        "           'multipanel' in str(w.message) for w in caught)\n"
        "print('ok')\n")
    env = dict(os.environ, PYTHONPATH=str(SRC))
    result = subprocess.run([sys.executable, "-c", code], env=env,
                            capture_output=True, text=True, timeout=120)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "ok"


def test_settings_scope_is_configurable():
    from multipanel import config

    before = config.settings_scope()
    try:
        assert before == ("MultiPanel", "MultiPanel")
        config.set_settings_scope("Example Org", "Example App")
        assert config.settings_scope() == ("Example Org", "Example App")
        config.set_settings_scope("Solo")
        assert config.settings_scope() == ("Solo", "Solo")
    finally:
        config.set_settings_scope(*before)


def actor(**attributes):
    mapper = vtk.vtkPolyDataMapper()
    mapper.SetInputData(vtk.vtkPolyData())
    result = vtk.vtkActor()
    result.SetMapper(mapper)
    for name, value in attributes.items():
        setattr(result, name, value)
    return result


def test_scene_actor_and_material_hooks():
    from multipanel import _widget_support as support

    plain, ui = actor(), actor(IsUI=True)
    helper = actor()
    helper.PickableOff()
    assert support.is_scene_actor(plain)
    assert not support.is_scene_actor(ui)
    assert not support.is_scene_actor(helper)
    assert support.actor_material(actor(material="lead")) == "lead"
    try:
        support.set_scene_actor_predicate(
            lambda a: hasattr(a, "cell_properties"))
        support.set_actor_material_resolver(
            lambda a: getattr(getattr(a, "cell_properties", None),
                              "material", None))
        tagged = actor(cell_properties=type("P", (), {"material": "air"}))
        assert support.is_scene_actor(tagged)
        assert not support.is_scene_actor(plain)
        assert support.actor_material(tagged) == "air"
    finally:
        support.set_scene_actor_predicate(None)
        support.set_actor_material_resolver(None)
    assert support.is_scene_actor(plain)


def test_add_logo_needs_an_existing_image():
    from multipanel.specialists import add_logo
    from multipanel.testing import UiHarness

    with UiHarness(size=(400, 300)) as ui:
        with pytest.raises(FileNotFoundError):
            add_logo(ui.renderer, ui.interactor, "no-such-logo")
        add_logo(ui.renderer, ui.interactor, "cube")   # a bundled icon
        ui.render()


def test_only_licensed_image_folders_ship():
    icons = SRC / "multipanel" / "icons"
    folders = {path.name for path in icons.iterdir() if path.is_dir()}
    assert folders <= {"png_icons", "svg_icons", "tintable", "vtk_icons"}
