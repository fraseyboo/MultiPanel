"""Click-to-edit must work when the UI is drawn on an overlay renderer.

A host may draw its 2D UI on a full-window overlay renderer (``ui_overlay``)
and clips the scene renderer's viewport to the gap between its panes.
TextWidget used to pick against the scene renderer, so clicks on a field
activated the widget but never started editing.
"""
import pytest
import vtk

from multipanel.containers import WidgetPanel
from multipanel.router import EventRouter
from multipanel.testing import UiHarness

SIZE = (1000, 800)


@pytest.fixture(params=[False, True], ids=["no-router", "router"])
def ui(request):
    with UiHarness(size=SIZE) as harness:
        overlay = vtk.vtkRenderer()
        overlay.SetLayer(1)
        overlay.InteractiveOff()
        harness.window.SetNumberOfLayers(2)
        harness.window.AddRenderer(overlay)
        harness.renderer.ui_overlay = overlay
        harness.renderer.SetViewport(0.25, 0.0, 0.75, 1.0)
        if request.param:
            EventRouter.install(harness.interactor)
        yield harness
        EventRouter.uninstall(harness.interactor)


def field_centre(field):
    rep = field.GetRepresentation()
    (x, y), (w, h) = rep.GetPosition(), rep.GetPosition2()
    return (int((x + w / 2) * SIZE[0]), int((y + h / 2) * SIZE[1]))


def make_field(ui, **extra):
    committed = []
    properties = {"path": {
        "textbox_size": [0.94, 0.22], "editable": True,
        "panel_offset": [0.5, -0.68], "text": "scene.i",
        "end_of_edit_callback": lambda _w, text: committed.append(text),
        **extra}}
    panel = WidgetPanel(ui.renderer, ui.interactor, properties,
                        panel_title="Export", panel_position=(0.05, 0.8),
                        panel_width=0.2, keep_aspect_ratio=False)
    ui.renderer.UI_panels = {"export": panel}
    ui.render()
    return panel.added_widgets["path"], committed


def test_single_click_edit_type_and_commit_over_overlay(ui):
    field, committed = make_field(ui)
    ui.click(field_centre(field))
    assert field.editing

    # The click put the caret where it landed; replace the whole value.
    ui.key("a", ctrl=True)
    ui.key_clicks("model.i")
    ui.key("Return")

    assert not field.editing
    assert field.textValue() == "model.i"
    assert committed == ["model.i"]


def test_double_click_fields_start_on_second_click(ui):
    field, _committed = make_field(ui, edit_on_double_click=True)
    centre = field_centre(field)
    ui.click(centre)
    assert not field.editing
    ui.click(centre)            # within TextWidget's 0.35 s window
    assert field.editing
