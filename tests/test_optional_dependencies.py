import subprocess
import sys
from pathlib import Path

import pytest

from multipanel import optional


def test_common_controls_import_without_optional_scientific_stack():
    source_root = Path(__file__).parents[1] / "src"
    script = f"""
import importlib.abc
import sys

sys.path.insert(0, {str(source_root)!r})
blocked = {{'cv2', 'matplotlib', 'scipy', 'shapely', 'sklearn',
           'svgpathtools', 'tqdm'}}

class BlockOptional(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.partition('.')[0] in blocked:
            raise ModuleNotFoundError(fullname)
        return None

sys.meta_path.insert(0, BlockOptional())
from multipanel import ICON_ROOT
from multipanel.controls import SliderWidget, TextWidget
print(ICON_ROOT, SliderWidget.__name__, TextWidget.__name__)
"""
    result = subprocess.run(
        [sys.executable, "-c", script], check=False,
        capture_output=True, text=True)

    assert result.returncode == 0, result.stderr
    assert "SliderWidget TextWidget" in result.stdout


def test_resource_import_does_not_load_widget_implementation():
    source_root = Path(__file__).parents[1] / "src"
    script = f"""
import sys
sys.path.insert(0, {str(source_root)!r})
from multipanel.resources import ICON_ROOT
assert 'multipanel.widgets' not in sys.modules
print(ICON_ROOT)
"""
    result = subprocess.run(
        [sys.executable, "-c", script], check=False,
        capture_output=True, text=True)

    assert result.returncode == 0, result.stderr


def test_optional_import_error_names_install_extra(monkeypatch):
    def missing(_module, package=None):
        raise ModuleNotFoundError("No module named 'scipy'", name="scipy")

    monkeypatch.setattr(optional, "import_module", missing)

    with pytest.raises(ModuleNotFoundError, match=r"multipanel\[scientific\]"):
        optional.import_optional(
            "scipy.spatial", extra="scientific", purpose="rotation")
