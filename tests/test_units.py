import json

import pytest

from multipanel import units
from multipanel._widget_support import set_ui_scale, ui_scale, user_scale
from multipanel.core import WidgetMixin
from multipanel.units import Length, frac, parse_length, px, strict_mode


@pytest.fixture
def scale():
    previous = user_scale()
    yield set_ui_scale
    set_ui_scale(previous)


def test_length_constructors_repr_and_equality():
    assert px(8) == Length(8, "px")
    assert frac(0.25) != px(0.25)
    assert repr(px(8)) == "px(8)"
    assert repr(frac(0.25)) == "frac(0.25)"
    assert -px(4) == px(-4)
    assert 2 * frac(0.1) == frac(0.2)
    with pytest.raises(AttributeError):
        px(1).value = 2


def test_parse_length_forms():
    assert parse_length("8px") == px(8)
    assert parse_length("25%") == frac(0.25)
    assert parse_length("0.3frac") == frac(0.3)
    assert parse_length(" 12 ") == px(12)
    assert parse_length(12, "frac") == frac(12)
    assert parse_length(px(3), "frac") == px(3)
    with pytest.raises(ValueError):
        parse_length("12em")
    with pytest.raises(TypeError):
        parse_length(True)


def test_strict_mode_rejects_bare_numbers_except_legacy():
    with strict_mode():
        with pytest.raises(TypeError):
            parse_length(4)
        with pytest.raises(TypeError):
            parse_length("4")
        assert parse_length(0.5, "frac", legacy=True) == frac(0.5)
        assert parse_length("4px") == px(4)
    assert parse_length(4) == px(4)


def test_resolution_uses_extent_for_frac_and_scale_for_px(scale):
    scale(1.5)
    assert frac(0.25).resolve(800) == 200
    assert px(10).resolve(800) == 15
    assert units.to_px(px(10), 800) == pytest.approx(10)
    assert units.to_px(frac(0.25), 800) == pytest.approx(200 / 1.5)
    assert units.to_frac(px(40), 600, scale=1.0) == pytest.approx(40 / 600)
    assert units.to_display("50%", 640) == 320


def test_viewport_extent_from_tuple_and_axis():
    assert units.viewport_extent((640, 480)) == (640, 480)
    assert units.viewport_extent((640, 480), "y") == 480
    assert units.viewport_extent((0, 0)) == (1, 1)
    with pytest.raises(ValueError):
        units.viewport_extent((1, 1), "z")


class SizedWidget(WidgetMixin):
    """Widget whose viewport is a plain (width, height) tuple."""

    def __init__(self, size=(800, 600)):
        self.size_px = size
        self.initWidget()

    def viewportSource(self):
        return self.size_px


def test_geometry_accepts_lengths_and_reports_every_unit(scale):
    scale(1.0)
    widget = SizedWidget((800, 600))

    widget.setGeometry(px(80), frac(0.5), "200px", "10%")

    assert widget.geometry() == pytest.approx((0.1, 0.5, 0.25, 0.1))
    assert widget.geometry("px") == pytest.approx((80, 300, 200, 60))
    assert widget.geometry("display") == pytest.approx((80, 300, 200, 60))
    assert widget.geometrySpec() == (px(80), frac(0.5), px(200), frac(0.1))


def test_geometry_units_keyword_applies_to_bare_numbers(scale):
    scale(1.0)
    widget = SizedWidget((400, 200))
    widget.setGeometry(40, 20, 100, 50, units="px")
    assert widget.geometry() == pytest.approx((0.1, 0.1, 0.25, 0.25))
    widget.resize(200, 100, units="px")
    assert widget.geometry() == pytest.approx((0.1, 0.1, 0.5, 0.5))
    widget.move(0.5, 0.5)
    assert widget.geometry() == pytest.approx((0.5, 0.5, 0.5, 0.5))


def test_saved_pixel_geometry_restores_against_new_viewport(scale):
    scale(1.0)
    widget = SizedWidget((800, 600))
    widget.setGeometry(px(80), frac(0.5), px(200), frac(0.1))
    state = json.loads(json.dumps(widget.saveState()))
    assert state["geometry"] == [[80, "px"], [0.5, "frac"],
                                 [200, "px"], [0.1, "frac"]]

    resized = SizedWidget((1600, 1200))
    resized.restoreState(state)

    # Pixel values stay the same size; fractions keep their proportion.
    assert resized.geometry("px") == pytest.approx((80, 600, 200, 120))


def test_legacy_untagged_geometry_state_still_restores():
    widget = SizedWidget()
    widget.restoreState({"geometry": [0.1, 0.2, 0.3, 0.4]})
    assert widget.geometry() == pytest.approx((0.1, 0.2, 0.3, 0.4))
    assert widget.geometrySpec() is None
