"""Layouts driving the library's real controls in an off-screen window."""
import numpy as np
import pytest

from multipanel._widget_support import set_ui_scale, ui_scale, user_scale
from multipanel.containers import Frame
from multipanel.controls import (
    ButtonWidget,
    SliderWidget,
    TextWidget,
    ValueChangerWidget,
    VectorButtonWidget,
)
from multipanel.layouts import FormLayout, HBoxLayout, VBoxLayout
from multipanel.testing import UiHarness
from multipanel.units import frac, px

SIZE = (1000, 800)


@pytest.fixture
def ui():
    previous = user_scale()
    set_ui_scale(1.0)
    with UiHarness(size=SIZE) as harness:
        yield harness
    set_ui_scale(previous)


def triangle_button(ui):
    triangle = np.asarray(((0.1, 0.1), (0.9, 0.5), (0.1, 0.9)))
    return VectorButtonWidget(ui.renderer, ui.interactor,
                              input_data=[triangle, triangle],
                              color=(0.5, 0.5, 0.5))


def build_panel(ui):
    frame = Frame(ui.renderer, ui.interactor, background=True,
                  geometry=(frac(0.05), frac(0.5), px(320), px(260)))
    name = TextWidget(ui.renderer, ui.interactor, text="lead", editable=True,
                      scale_text_to_widget=False)
    density = ValueChangerWidget(ui.renderer, ui.interactor, 11.35, 0.0,
                                 30.0, step=0.05)
    slider = SliderWidget(ui.renderer, ui.interactor, min_value=0,
                          max_value=10, initial_value=5,
                          callback=lambda *_: None)
    apply_button = triangle_button(ui)
    help_button = ButtonWidget(ui.renderer, ui.interactor,
                               icon_name="question-sign", callback=None)

    form = FormLayout(spacing=6)
    form.addRow("Material", name)
    form.addRow("Density", density)
    buttons = HBoxLayout(spacing=6)
    buttons.addWidget(apply_button)
    buttons.addStretch()
    buttons.addWidget(help_button)
    column = VBoxLayout(margins=(10, 10, 10, 10), spacing=8)
    column.addLayout(form)
    column.addWidget(slider)
    column.addStretch()
    column.addLayout(buttons)
    frame.setLayout(column)
    ui.process_events()            # the deferred layout pass runs here
    return frame, column, form, dict(name=name, density=density, slider=slider,
                                     apply=apply_button, help=help_button)


def inside(inner, outer, tolerance=0.5):
    ix, iy, iw, ih = inner
    ox, oy, ow, oh = outer
    return (ix >= ox - tolerance and iy >= oy - tolerance
            and ix + iw <= ox + ow + tolerance
            and iy + ih <= oy + oh + tolerance)


def overlaps(a, b):
    return not (a[0] + a[2] <= b[0] + 0.5 or b[0] + b[2] <= a[0] + 0.5 or
                a[1] + a[3] <= b[1] + 0.5 or b[1] + b[3] <= a[1] + 0.5)


def test_real_controls_are_placed_inside_the_frame_without_overlap(ui):
    frame, column, form, widgets = build_panel(ui)
    assert column.passes == 1
    content = frame.contentsRect()
    labels = [form.labelForRow(0), form.labelForRow(1)]
    every = list(widgets.values()) + labels
    rects = {id(w): w.geometry("px") for w in every}
    for widget in every:
        assert inside(rects[id(widget)], content), widget.objectName()
    for i, a in enumerate(every):
        for b in every[i + 1:]:
            assert not overlaps(rects[id(a)], rects[id(b)]), (
                a.objectName(), b.objectName())
    # Fields share one left edge and fill to the right margin.
    name_rect, density_rect = rects[id(widgets["name"])], rects[id(widgets["density"])]
    assert name_rect[0] == pytest.approx(density_rect[0])
    assert name_rect[0] + name_rect[2] == pytest.approx(
        content[0] + content[2] - 10)
    # Buttons sit at the bottom corners at their hinted sizes.
    apply_rect, help_rect = rects[id(widgets["apply"])], rects[id(widgets["help"])]
    assert apply_rect[2:] == pytest.approx((32, 32))
    assert help_rect[2:] == pytest.approx((32, 32))
    assert apply_rect[1] == pytest.approx(content[1] + 10)
    assert help_rect[0] + 32 == pytest.approx(content[0] + content[2] - 10)


def test_set_bounds_round_trips_for_each_control(ui):
    _frame, _column, _form, widgets = build_panel(ui)
    for name, widget in widgets.items():
        widget.setGeometry(px(100), px(200), px(150), px(30))
        assert widget.geometry("px") == pytest.approx((100, 200, 150, 30)), name


def test_hint_changes_relayout_once_per_frame(ui):
    frame, column, form, widgets = build_panel(ui)
    passes = column.passes
    label = form.labelForRow(0)
    for text in ("Material name", "Material (long)", "Mat"):
        label.setText(text)
        label.updateGeometry()
        widgets["slider"].updateGeometry()
    assert column.passes == passes        # nothing until the frame renders
    ui.process_events()
    assert column.passes == passes + 1


def test_hiding_a_row_widget_closes_the_gap(ui):
    _frame, _column, _form, widgets = build_panel(ui)
    slider_top = sum(widgets["slider"].geometry("px")[1::2])
    widgets["density"].hide()
    ui.process_events()
    assert sum(widgets["slider"].geometry("px")[1::2]) > slider_top


def test_window_resize_relayouts_fractional_geometry(ui):
    frame, column, _form, widgets = build_panel(ui)
    passes = column.passes
    ui.window.SetSize(1600, 800)
    ui.window.InvokeEvent("WindowResizeEvent")
    ui.process_events()
    assert column.passes > passes
    assert frame.geometry("px")[0] == pytest.approx(0.05 * 1600)
    assert inside(widgets["name"].geometry("px"), frame.contentsRect())


def test_frame_hides_and_restores_children(ui):
    frame, _column, _form, widgets = build_panel(ui)
    widgets["help"].hide()
    frame.hide()
    # Children's actors are switched off; their own state is untouched, so
    # they keep their layout space while the frame is hidden.
    assert not widgets["name"].GetEnabled()
    assert not widgets["name"].isHidden()
    frame.show()
    assert widgets["name"].GetEnabled()
    assert widgets["help"].isHidden() and not widgets["help"].GetEnabled()


def test_text_field_in_a_layout_is_still_editable(ui):
    _frame, _column, _form, widgets = build_panel(ui)
    ui.render()
    # Anywhere in the field's cell, not just on the rendered text.
    x, y, w, h = widgets["name"].geometry("display")
    ui.click((x + w * 0.8, y + h - 2))
    assert widgets["name"].editing
    ui.key_clicks("s")
    ui.key("Return")
    assert widgets["name"].textValue() == "leads"
