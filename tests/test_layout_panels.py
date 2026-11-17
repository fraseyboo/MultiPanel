"""Layouts inside WidgetPanel, Frame and DockPane."""
import numpy as np
import pytest

from multipanel._widget_support import panel_header_metrics, set_ui_scale, ui_scale, user_scale
from multipanel.containers import DockPane, Frame, WidgetPanel
from multipanel.controls import SliderWidget, TextWidget, VectorButtonWidget
from multipanel.layouts import HBoxLayout, VBoxLayout
from multipanel.testing import UiHarness
from multipanel.units import frac, px

SIZE = (1400, 900)


@pytest.fixture
def ui():
    previous = user_scale()
    set_ui_scale(1.0)
    with UiHarness(size=SIZE) as harness:
        yield harness
    set_ui_scale(previous)


def text(ui, value, **options):
    return TextWidget(ui.renderer, ui.interactor, text=value,
                      scale_text_to_widget=False, **options)


def button(ui):
    square = np.asarray(((0.2, 0.2), (0.8, 0.2), (0.8, 0.8), (0.2, 0.8)))
    return VectorButtonWidget(ui.renderer, ui.interactor,
                              input_data=[square], color=(0.3, 0.3, 0.3))


def layout_panel(ui, title="Layout panel", position=(0.4, 0.8)):
    panel = WidgetPanel(ui.renderer, ui.interactor, {}, panel_title=title,
                        panel_position=position, panel_width=0.15,
                        keep_aspect_ratio=False)
    first, second = text(ui, "First row"), text(ui, "Second row")
    row = HBoxLayout(spacing=6)
    left, right = button(ui), button(ui)
    row.addWidget(left)
    row.addStretch()
    row.addWidget(right)
    column = VBoxLayout(spacing=4)
    column.addWidget(first)
    column.addWidget(second)
    column.addLayout(row)
    panel.setLayout(column)
    ui.process_events()
    return panel, column, [first, second, left, right]


def shown(widget):
    """Raw on-screen state: visibility where available, else enabled."""
    getter = getattr(widget, "GetVisibility", None) or widget.GetEnabled
    return bool(getter())


def frac_rect(widget):
    x0, x1, y0, y1 = widget.GetBounds()[:4]
    return x0, x1, y0, y1


def within(inner, outer, tolerance=1e-6):
    return (inner[0] >= outer[0] - tolerance and inner[1] <= outer[1] + tolerance
            and inner[2] >= outer[2] - tolerance and inner[3] <= outer[3] + tolerance)


def test_floating_panel_grows_to_fit_its_layout(ui):
    panel, column, widgets = layout_panel(ui)
    bounds = panel.GetBounds()
    band = panel_header_metrics(ui.interactor)[0]
    content = panel._content_frac_rect()
    assert content[3] == pytest.approx(bounds[3] - band)
    for widget in widgets:
        assert within(frac_rect(widget), content), widget.objectName()
    needed = column.sizeHint()[1] / SIZE[1]
    assert content[3] - content[2] >= needed - 1e-6
    # The header still holds the title and the collapse control.
    title_y = panel.text_anchor.GetBounds()[2]
    assert title_y > content[3] - 1e-6


def test_hint_change_grows_the_panel_once_rendered(ui):
    panel, _column, widgets = layout_panel(ui)
    old_bottom = panel.GetBounds()[2]
    widgets[1].setFixedHeight(80)
    ui.process_events()
    assert panel.GetBounds()[2] < old_bottom - 60 / SIZE[1]
    assert within(frac_rect(widgets[3]), panel._content_frac_rect())


def test_collapse_hides_layout_widgets_and_expand_restores(ui):
    panel, _column, widgets = layout_panel(ui)
    widgets[0].hide()                       # explicitly hidden by the caller
    ui.process_events()
    panel.collapse_panel()
    assert not shown(widgets[1])
    panel.expand_panel()
    assert shown(widgets[1])
    assert not widgets[0].isVisible()       # stays hidden
    panel.SetVisibility(False)
    assert not shown(widgets[2])
    panel.SetVisibility(True)
    assert shown(widgets[2])


def test_docked_layout_panel_takes_its_hinted_height(ui):
    dock = DockPane(ui.renderer, ui.interactor, side="left", width=.22)
    legacy = WidgetPanel(ui.renderer, ui.interactor, {
        "note": {"textbox_size": [0.94, 0.2], "panel_offset": [0.5, -0.4],
                 "text": "legacy"}}, panel_title="Legacy",
        panel_position=(0.02, 0.8), panel_width=0.1, keep_aspect_ratio=False)
    dock.add_panel(legacy)
    legacy_bounds = legacy.GetBounds()
    panel, _column, widgets = layout_panel(ui)
    dock.add_panel(panel)
    ui.process_events()

    bounds = panel.GetBounds()
    assert bounds[3] - bounds[2] == pytest.approx(panel.dockHeight())
    assert bounds[3] < legacy.GetBounds()[2]          # stacked below
    assert legacy.GetBounds() == pytest.approx(legacy_bounds)
    for widget in widgets:
        assert within(frac_rect(widget), panel._content_frac_rect())

    widgets[0].setFixedHeight(60)
    ui.process_events()
    bounds = panel.GetBounds()
    assert bounds[3] - bounds[2] == pytest.approx(panel.dockHeight())
    assert within(frac_rect(widgets[0]), panel._content_frac_rect())


def test_frame_in_a_dock_uses_its_size_hint(ui):
    dock = DockPane(ui.renderer, ui.interactor, side="right", width=px(300),
                    margin=px(8))
    frame = Frame(ui.renderer, ui.interactor, background=True)
    frame.setContentsMargins(8, 8, 8, 8)
    column = VBoxLayout(spacing=4)
    labels = [text(ui, f"Row {index}") for index in range(3)]
    for label in labels:
        column.addWidget(label)
    frame.setLayout(column)
    dock.add_panel(frame)
    ui.process_events()

    height_px = (frame.GetBounds()[3] - frame.GetBounds()[2]) * SIZE[1]
    assert height_px == pytest.approx(frame.sizeHint()[1])
    assert frame.geometry("px")[2] == pytest.approx(300 - 2 * 8)
    for label in labels:
        assert within(frac_rect(label), frame.GetBounds())


def test_dock_pixel_width_survives_window_resize(ui):
    dock = DockPane(ui.renderer, ui.interactor, side="left", width=px(280))
    assert dock.width * SIZE[0] == pytest.approx(280)
    ui.window.SetSize(1000, 900)
    ui.window.InvokeEvent("WindowResizeEvent")
    assert dock.width * 1000 == pytest.approx(280)
    dock.setDockWidth(px(350))
    assert dock.width * 1000 == pytest.approx(350)
    state = dock.saveState()
    dock.setDockWidth(px(200))
    dock.restoreState(state)
    assert dock.width * 1000 == pytest.approx(350)


def test_dock_bare_numbers_keep_legacy_meaning(ui):
    dock = DockPane(ui.renderer, ui.interactor, side="left", width=.2,
                    margin=.01)
    assert dock.width == pytest.approx(.2 * ui_scale())
    assert dock.margin == pytest.approx(.01)
    assert dock.vertical_margin == pytest.approx(.01)


def test_widgets_can_move_from_properties_into_a_layout(ui):
    panel = WidgetPanel(ui.renderer, ui.interactor, {
        "status": {"textbox_size": [0.94, 0.2], "panel_offset": [0.5, -0.4],
                   "text": "status"}}, panel_title="Mixed",
        panel_position=(0.4, 0.8), panel_width=0.15, keep_aspect_ratio=False)
    status = panel.removeWidget("status")
    column = VBoxLayout()
    column.addWidget(status)
    panel.setLayout(column)
    ui.process_events()
    assert "status" not in panel.added_widgets
    assert within(frac_rect(status), panel._content_frac_rect())


def test_hiding_a_slider_disables_it(ui):
    slider = SliderWidget(ui.renderer, ui.interactor, callback=lambda *_: None)
    slider.hide()
    assert not slider.GetEnabled()
    slider.show()
    assert slider.GetEnabled()


def test_panel_docked_under_inactive_tab_lays_out_when_shown(ui):
    dock = DockPane(ui.renderer, ui.interactor, side="left", width=.22)
    dock.add_tab("first", "question-sign")
    dock.add_tab("second", "question-sign")
    panel, _column, widgets = layout_panel(ui)
    dock.add_panel(panel, tab="second")     # hidden: "first" is active
    ui.process_events()
    dock.select_tab("second")
    ui.process_events()
    for widget in widgets:
        assert within(frac_rect(widget), panel._content_frac_rect())


def test_buttons_placed_by_a_layout_still_receive_clicks(ui):
    dock = DockPane(ui.renderer, ui.interactor, side="left", width=.22)
    panel, _column, widgets = layout_panel(ui)
    dock.add_panel(panel)
    ui.process_events()
    ui.render()
    pressed = []
    widgets[3].pressed.connect(lambda: pressed.append(1))
    x0, x1, y0, y1 = widgets[3].GetBounds()[:4]
    ui.click(((x0 + x1) / 2 * SIZE[0], (y0 + y1) / 2 * SIZE[1]))
    assert pressed == [1]


def form_panel(ui):
    from multipanel.layouts import FormLayout

    panel = WidgetPanel(ui.renderer, ui.interactor, {
        "first": {"textbox_size": [0.9, 0.2], "panel_offset": [0.5, -0.4],
                  "text": "one", "editable": True},
        "second": {"textbox_size": [0.9, 0.2], "panel_offset": [0.5, -0.7],
                   "text": "two", "editable": True},
    }, panel_title="Form", panel_position=(0.4, 0.8), panel_width=0.15,
        keep_aspect_ratio=False)
    form = FormLayout(spacing=4)
    form.addRow("First", panel.removeWidget("first"))
    form.addRow("Second", panel.removeWidget("second"))
    panel.setLayout(form)
    ui.process_events()
    return panel, form


def test_set_element_shown_hides_a_form_row_with_its_label(ui):
    panel, form = form_panel(ui)
    label, field = form.labelForRow(1), panel.widget("second")
    height = panel.GetBounds()[3] - panel.GetBounds()[2]

    panel.set_element_shown("second", False)
    ui.process_events()
    assert not shown(field) and not shown(label)
    assert panel.GetBounds()[3] - panel.GetBounds()[2] < height

    panel.set_element_shown("second", True)
    ui.process_events()
    assert shown(field) and shown(label)
    assert panel.GetBounds()[3] - panel.GetBounds()[2] == pytest.approx(height)


def test_show_on_a_widget_in_a_hidden_panel_does_not_draw_it(ui):
    panel, form = form_panel(ui)
    field = panel.widget("first")
    field.hide()
    panel.SetVisibility(False)
    field.show()                         # host code while the tab is closed
    ui.process_events()
    assert not shown(field)
    panel.SetVisibility(True)
    ui.process_events()
    assert shown(field) and shown(form.labelForRow(0))
