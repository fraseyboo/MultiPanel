"""State-based styling, the keyboard focus ring and the line caret (W7)."""
import pytest

from multipanel._widget_support import set_ui_scale, ui_scale, user_scale
from multipanel.controls import TextWidget
from multipanel.router import EventRouter
from multipanel.standard import CheckBox, ComboBox, PushButton
from multipanel.style import FocusRing, Style
from multipanel.testing import UiHarness
from multipanel.ui_theme import DARK, LIGHT, vtk_tokens
from multipanel.units import px

SIZE = (800, 600)


@pytest.fixture
def ui():
    previous = user_scale()
    set_ui_scale(1.0)
    with UiHarness(size=SIZE) as harness:
        EventRouter.install(harness.interactor)
        yield harness
        EventRouter.uninstall(harness.interactor)
    set_ui_scale(previous)


def place(widget, x=100, y=400, w=160, h=24):
    widget.setGeometry(px(x), px(y), px(w), px(h))
    return widget


def centre(widget):
    x, y, w, h = widget.geometry("display")
    return (x + w / 2, y + h / 2)


def ring(ui):
    return FocusRing._instances.get(ui.interactor)


# -- Style ------------------------------------------------------------------------

def test_style_maps_states_to_theme_tokens():
    class Renderer:
        theme = None

    renderer = Renderer()
    style = Style.for_renderer(renderer)
    t = vtk_tokens(LIGHT)
    assert style.color("button", "background") == t["button"]
    assert style.color("button", "background", {"hover"}) == t["button_hover"]
    assert style.color("button", "background", {"hover", "pressed"}) == \
        t["accent_soft"]
    assert style.color("button", "text", {"disabled"}) == t["disabled"]
    assert style.color("field", "border", {"focus"}) == t["accent"]
    assert style.color("field", "border", {"focus", "disabled"}) == \
        t["input_border"]
    renderer.theme = type("Theme", (), {"tokens": vtk_tokens(DARK)})()
    assert style.color("button", "background") == vtk_tokens(DARK)["button"]


def test_overrides_by_object_name_and_state(ui):
    style = Style.for_renderer(ui.renderer)
    try:
        button = place(PushButton(ui.renderer, ui.interactor, "Place",
                                  object_name="place"))
        other = place(PushButton(ui.renderer, ui.interactor, "Other"), y=300)
        style.setOverride("#place", "button", "background", (0.8, 0.2, 0.2))
        style.setOverride("*", "button", "background", (0.1, 0.9, 0.1),
                          states={"hover"})
        assert button.color("button", "background") == (0.8, 0.2, 0.2)
        assert other.color("button", "background") != (0.8, 0.2, 0.2)
        ui.move(centre(other))
        assert "hover" in other.styleState()
        assert other.color("button", "background") == (0.1, 0.9, 0.1)
        with pytest.raises(ValueError):
            style.setOverride("place", "button", "background", (0, 0, 0))
    finally:
        style.clearOverrides()


def test_style_state_reports_hover_pressed_checked_disabled(ui):
    box = place(CheckBox(ui.renderer, ui.interactor, "Bias"))
    assert box.styleState() == frozenset()
    ui.move(centre(box))
    assert "hover" in box.styleState()
    box.setChecked(True)
    assert "checked" in box.styleState()
    box.setEnabled(False)
    assert "disabled" in box.styleState()
    button = place(PushButton(ui.renderer, ui.interactor, "OK", default=True),
                   y=300)
    assert "default" in button.styleState()


# -- focus ring ----------------------------------------------------------------------

def test_ring_follows_tab_focus_but_not_mouse_focus(ui):
    first = place(ComboBox(ui.renderer, ui.interactor), y=400)
    first.addItems(["a", "b"])
    second = place(PushButton(ui.renderer, ui.interactor, "Go"), y=300)
    second.setFocusPolicy("StrongFocus")
    ui.render()
    ui.key("Tab")
    focused = first.focusManager().focusWidget()
    assert focused in (first, second)
    assert ring(ui) is not None and ring(ui).isVisible()
    assert ring(ui).target() is focused
    bounds = ring(ui)._actor.GetMapper().GetInput().GetBounds()
    x, y, w, h = focused.geometry("display")
    assert bounds[0] < x and bounds[1] > x + w
    # Clicking moves focus without a ring.
    ui.click(centre(second if focused is first else first))
    ui.render()
    assert not ring(ui).isVisible()


def test_ring_hides_with_its_widget_and_while_editing(ui):
    field = TextWidget(ui.renderer, ui.interactor, text="lead", editable=True,
                       position=(0.1, 0.5), size=(0.4, 0.05), text_size=16,
                       scale_text_to_widget=False)
    ui.render()
    field.setFocus(reason="tab")
    ui.render()
    assert ring(ui).isVisible()
    assert field.start_editing()
    ui.render()
    assert not ring(ui).isVisible()
    field.finish_editing()
    ui.render()
    assert ring(ui).isVisible()
    field.SetVisibility(False)
    ui.render()
    assert not ring(ui).isVisible()


def test_no_ring_is_created_without_keyboard_navigation(ui):
    button = place(PushButton(ui.renderer, ui.interactor, "Go"))
    button.setFocusPolicy("StrongFocus")
    ui.click(centre(button))
    assert ring(ui) is None


# -- caret ------------------------------------------------------------------------------

def editing_field(ui, text="lead shield"):
    field = TextWidget(ui.renderer, ui.interactor, text=text, editable=True,
                       position=(0.1, 0.5), size=(0.5, 0.05), text_size=16,
                       scale_text_to_widget=False)
    ui.render()
    assert field.start_editing()
    ui.render()
    return field


def test_caret_is_a_line_at_the_caret_position(ui):
    field = editing_field(ui)
    assert field.text_actor.GetInput() == "lead shield"     # no inline glyph
    ui.key("Home")
    for _ in range(4):
        ui.key("Right")
    actor = field._caret_line
    assert actor.GetVisibility()
    bounds = actor.GetMapper().GetInput().GetBounds()
    x, _box = field._display_x(field._display_index(4))
    assert (bounds[0] + bounds[1]) / 2 == pytest.approx(x, abs=1)
    assert bounds[1] - bounds[0] < 3
    ui.key("Right", shift=True)            # a selection replaces the caret
    assert not actor.GetVisibility()
    field.finish_editing()
    assert not actor.GetVisibility()


def test_caret_shows_in_an_empty_field_and_legacy_glyph_still_works(ui):
    field = editing_field(ui, text="")
    assert field._caret_line.GetVisibility()
    bounds = field._caret_line.GetMapper().GetInput().GetBounds()
    assert bounds[3] - bounds[2] >= 8
    field.finish_editing()
    legacy = TextWidget(ui.renderer, ui.interactor, text="ab", editable=True,
                        position=(0.1, 0.3), size=(0.4, 0.05), text_size=16,
                        scale_text_to_widget=False, caret_text="|")
    ui.render()
    legacy.start_editing()
    assert legacy.text_actor.GetInput() == "ab|"
    assert getattr(legacy, "_caret_line", None) is None or \
        not legacy._caret_line.GetVisibility()
