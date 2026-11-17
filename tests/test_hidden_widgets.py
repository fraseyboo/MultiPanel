"""Widgets in hidden panels and inactive dock tabs must not be drawn or
interactive, whatever availability the host sets on them.

Regression: VectorButtonWidget used one ``enabled`` flag both for "shown"
(set by containers) and "available" (set by hosts, e.g. a toggle in an
appearance panel). A host marking a hidden button available
made it clickable while another dock tab was open.
"""
import numpy as np
import pytest

from multipanel._widget_support import set_ui_scale, ui_scale, user_scale
from multipanel.containers import DockPane, WidgetPanel
from multipanel.controls import VectorButtonWidget, VectorPanelBackground
from multipanel.testing import UiHarness

SIZE = (1200, 800)


@pytest.fixture
def ui():
    previous = user_scale()
    set_ui_scale(1.0)
    with UiHarness(size=SIZE) as harness:
        yield harness
    set_ui_scale(previous)


def centre(widget):
    x0, x1, y0, y1 = widget.GetBounds()[:4]
    return ((x0 + x1) / 2 * SIZE[0], (y0 + y1) / 2 * SIZE[1])


def square_button(ui, clicks, bounds=(0.4, 0.45, 0.4, 0.45)):
    square = np.asarray(((0.2, 0.2), (0.8, 0.2), (0.8, 0.8), (0.2, 0.8)))
    return VectorButtonWidget(
        ui.renderer, ui.interactor, input_data=[square], bounds=bounds,
        color=(0.3, 0.3, 0.3), callback=lambda *_: clicks.append(1))


def test_hidden_button_stays_inert_when_host_marks_it_available(ui):
    clicks = []
    button = square_button(ui, clicks)
    ui.render()
    button.SetEnabled(False)            # container hides it
    button.enabled = True               # host: "available for this selection"
    ui.click(centre(button))
    assert clicks == []
    assert not button.actor.GetVisibility()
    assert not button.GetEnabled() and not button.isVisible()

    button.SetEnabled(True)
    ui.click(centre(button))
    assert clicks == [1]


def test_availability_survives_hide_and_show(ui):
    clicks = []
    button = square_button(ui, clicks)
    ui.render()
    button.enabled = False              # host greys it out
    button.SetVisibility(False)
    button.SetVisibility(True)          # showing must not re-enable it
    assert button.enabled is False
    ui.click(centre(button))
    assert clicks == []
    assert not button.isEnabled() and button.isVisible()
    button.setEnabled(True)
    ui.click(centre(button))
    assert clicks == [1]


def panel_with_button(ui, clicks, title):
    panel = WidgetPanel(ui.renderer, ui.interactor, {
        "toggle": {"icon_names": ["question_sign"], "panel_offset": [0.3, -0.5],
                   "button_size": [0.3, 0.3],
                   "callback": lambda *_: clicks.append(title)}},
        panel_title=title, panel_position=(0.02, 0.8), panel_width=0.1,
        keep_aspect_ratio=False)
    return panel, panel.added_widgets["toggle"]


def test_buttons_in_inactive_dock_tabs_ignore_clicks(ui):
    dock = DockPane(ui.renderer, ui.interactor, side="left", width=.25)
    dock.add_tab("build", "question-sign")
    dock.add_tab("tools", "question-sign")
    clicks = []
    build, _ = panel_with_button(ui, clicks, "build")
    tools, toggle = panel_with_button(ui, clicks, "tools")
    dock.add_panel(build, tab="build")
    dock.add_panel(tools, tab="tools")
    dock.select_tab("tools")
    ui.render()
    position = centre(toggle)

    dock.select_tab("build")
    toggle.enabled = True               # e.g. a selection-change sync
    ui.render()
    ui.click(position)
    assert "tools" not in clicks
    assert not toggle.actor.GetVisibility()

    dock.select_tab("tools")
    ui.render()
    ui.click(position)
    assert clicks.count("tools") == 1


def test_hidden_panel_background_is_not_drawn_or_draggable(ui):
    panel = VectorPanelBackground(ui.renderer, ui.interactor,
                                  bounds=(0.3, 0.6, 0.3, 0.6),
                                  movable=True, resizable=True)
    ui.render()
    assert panel.actor.GetVisibility()
    panel.SetVisibility(False)
    assert not panel.actor.GetVisibility()
    edge = (0.6 * SIZE[0] - 2, 0.45 * SIZE[1])
    ui.drag(edge, (edge[0] + 100, edge[1]))
    assert panel.GetBounds()[1] == pytest.approx(0.6)
    assert not panel.resizing

    hidden = VectorPanelBackground(ui.renderer, ui.interactor, visible=False)
    assert not hidden.actor.GetVisibility()


def test_nothing_in_an_inactive_tab_is_drawn_or_enabled(ui):
    from multipanel.controls import SliderWidget, TextWidget, ValueChangerWidget

    dock = DockPane(ui.renderer, ui.interactor, side="left", width=.25)
    dock.add_tab("a", "question-sign")
    dock.add_tab("b", "question-sign")
    clicks = []
    shown, _ = panel_with_button(ui, clicks, "shown")
    hidden = WidgetPanel(ui.renderer, ui.interactor, {
        "toggle": {"icon_names": ["question_sign"], "panel_offset": [0.2, -0.4],
                   "button_size": [0.2, 0.2], "callback": lambda *_: None},
        "field": {"textbox_size": [0.9, 0.2], "panel_offset": [0.5, -0.8],
                  "text": "value", "editable": True},
        "spin": {"widget_type": "value_changer", "panel_offset": [0.5, -1.1],
                 "widget_size": [0.8, 0.15], "initial_value": 1.0,
                 "min_value": 0.0, "max_value": 10.0, "step": 0.1,
                 "callback": lambda *_: None},
    }, panel_title="hidden", panel_position=(0.02, 0.8), panel_width=0.1,
        keep_aspect_ratio=False)
    dock.add_panel(shown, tab="a")
    dock.add_panel(hidden, tab="b")
    dock.select_tab("a")
    hidden.added_widgets["toggle"].enabled = True     # host availability

    assert not hidden.panel_background.actor.GetVisibility()
    for name, widget in hidden.added_widgets.items():
        assert not widget.GetEnabled(), name
    assert not hidden.added_widgets["toggle"].actor.GetVisibility()
