"""Clicks anywhere in a text field's cell start editing.

Regression: with fixed-size fonts vtkTextRepresentation shrinks its box to
the rendered text (about 13 px tall), and vtkBorderWidget's edge-resize
tolerance covered most of it, so clicks started an (invisible, locked) edge
drag instead of editing. A host application's panel fields could only be
edited by clicking a thin band through the middle of the text.
"""
import pytest

from multipanel._widget_support import set_ui_scale, ui_scale, user_scale
from multipanel.controls import TextWidget
from multipanel.testing import UiHarness

SIZE = (1000, 800)


@pytest.fixture
def ui():
    previous = user_scale()
    set_ui_scale(1.0)
    with UiHarness(size=SIZE) as harness:
        yield harness
    set_ui_scale(previous)


def field(ui, **options):
    widget = TextWidget(ui.renderer, ui.interactor, text="value",
                        position=(0.3, 0.5), size=(0.3, 0.04),
                        scale_text_to_widget=False, editable=True, **options)
    ui.render()
    return widget


def cell_point(widget, fx, fy):
    x0, x1, y0, y1 = widget.GetBounds()[:4]
    return (x0 + fx * (x1 - x0)) * SIZE[0], (y0 + fy * (y1 - y0)) * SIZE[1]


@pytest.mark.parametrize("fx, fy", [(0.9, 0.9), (0.9, 0.1), (0.05, 0.5),
                                    (0.5, 0.95)])
def test_click_anywhere_in_the_cell_starts_editing(ui, fx, fy):
    widget = field(ui)
    ui.click(cell_point(widget, fx, fy))
    assert widget.editing


def test_double_click_fields_need_two_clicks_anywhere(ui):
    widget = field(ui, edit_on_double_click=True)
    point = cell_point(widget, 0.9, 0.9)
    ui.click(point)
    assert not widget.editing
    ui.click(point)
    assert widget.editing


def test_claimed_press_does_not_reach_the_scene(ui):
    widget = field(ui)
    scene = []
    ui.interactor.AddObserver("LeftButtonPressEvent",
                              lambda *_: scene.append(1), 0.0)
    ui.click(cell_point(widget, 0.9, 0.5))
    assert scene == []
    ui.click((5, 5))
    assert scene == [1]


def test_click_outside_commits_editing(ui):
    widget = field(ui)
    ui.click(cell_point(widget, 0.5, 0.5))
    ui.key_clicks("s")
    ui.click((5, 5))
    assert not widget.editing
    assert widget.textValue() == "values"


def test_hidden_fields_ignore_clicks(ui):
    widget = field(ui)
    widget.SetVisibility(False)
    ui.click(cell_point(widget, 0.5, 0.5))
    assert not widget.editing


def test_opt_out_keeps_vtk_hit_box(ui):
    widget = field(ui, claim_cell_clicks=False)
    assert widget._cell_press_tag is None
