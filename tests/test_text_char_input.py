"""Typed text arrives as characters (CharEvent) and never reaches the
interactor style's hotkeys, with or without an EventRouter (W6)."""
import pytest
import vtk

from multipanel._widget_support import set_ui_scale, user_scale
from multipanel.animation import animations_enabled, set_animations_enabled
from multipanel.controls import TextWidget
from multipanel.router import EventRouter
from multipanel.testing import UiHarness


@pytest.fixture(params=[True, False], ids=["router", "no-router"])
def ui(request):
    previous, animated = user_scale(), animations_enabled()
    set_ui_scale(1.0)
    set_animations_enabled(False)
    with UiHarness(size=(800, 500)) as harness:
        harness.interactor.SetInteractorStyle(
            vtk.vtkInteractorStyleTrackballCamera())
        source = vtk.vtkCubeSource()
        mapper = vtk.vtkPolyDataMapper()
        mapper.SetInputConnection(source.GetOutputPort())
        cube = vtk.vtkActor()
        cube.SetMapper(mapper)
        harness.renderer.AddActor(cube)
        harness._keep = source
        harness.cube = cube
        if request.param:
            EventRouter.install(harness.interactor)
        yield harness
        EventRouter.uninstall(harness.interactor)
    set_ui_scale(previous)
    set_animations_enabled(animated)


def editing_field(ui, text=""):
    widget = TextWidget(ui.renderer, ui.interactor, text=text, editable=True,
                        position=(0.1, 0.5), size=(0.4, 0.06), text_size=16,
                        scale_text_to_widget=False)
    ui.render()
    widget.start_editing()
    return widget


def test_typing_never_reaches_the_style_hotkeys(ui):
    field = editing_field(ui)
    representation = ui.cube.GetProperty().GetRepresentation()
    ui.key_clicks("w3s e")                  # wireframe, stereo, surface...
    assert field.text == "w3s e"
    assert ui.cube.GetProperty().GetRepresentation() == representation
    assert not ui.interactor.GetRenderWindow().GetStereoRender()
    field.finish_editing()
    ui.key("w")                             # not editing: the hotkey works
    assert ui.cube.GetProperty().GetRepresentation() == vtk.VTK_WIREFRAME


def test_text_comes_from_the_character_not_the_key(ui):
    field = editing_field(ui)
    ui.key("e", text="é", alt=True)         # Option+e, e on macOS
    ui.key("m", text="µ", alt=True)         # Option+m
    ui.key("2", text="@", shift=True)       # a layout's shifted symbol
    assert field.text == "éµ@"
    # A key press without a character types nothing.
    info = ui.interactor
    info.SetKeyEventInformation(0, 0, "\0", 0, "F5")
    info.InvokeEvent("KeyPressEvent")
    assert field.text == "éµ@"


def test_ctrl_combinations_are_not_text(ui):
    field = editing_field(ui, "abc")
    ui.key("s", ctrl=True)
    assert field.text == "abc"


def test_editing_keys_still_work(ui):
    field = editing_field(ui, "abcd")
    ui.key("BackSpace")
    ui.key("Left")
    ui.key_clicks("X")
    ui.key("Return")
    assert field.text == "abXc" and not field.editing


# -- long text in a narrow field -----------------------------------------------------------
def narrow_field(ui, text, **options):
    widget = TextWidget(ui.renderer, ui.interactor, text=text, editable=True,
                        position=(0.1, 0.5), size=(0.15, 0.05), text_size=16,
                        scale_text_to_widget=False, prepend_text="Energies: ",
                        **options)
    ui.render()
    return widget


def test_long_text_is_shortened_and_shown_on_hover(ui):
    from multipanel.controls import get_hover_text_overlay

    field = narrow_field(ui, "0.662, 1.173, 1.332, 2.614")
    shown = field.text_actor.GetInput()
    assert shown.endswith("…") and shown.startswith("Energies: 0.")
    assert len(shown) < len("Energies: 0.662, 1.173, 1.332, 2.614")
    assert field.text == "0.662, 1.173, 1.332, 2.614"   # the value is whole
    hover = field._elide_hover
    assert hover is not None and hover in get_hover_text_overlay(
        ui.renderer, ui.interactor).buttons
    assert hover.hover_text == "Energies: 0.662, 1.173, 1.332, 2.614"
    field.start_editing()
    assert not hover.enabled                   # no tooltip while editing
    field.finish_editing()
    field.text = "1.0"
    field._update_edit_display()
    assert field.text_actor.GetInput() == "Energies: 1.0"
    assert hover.hover_text is None            # fits: nothing to show


def test_eliding_can_be_turned_off(ui):
    field = narrow_field(ui, "0.662, 1.173, 1.332, 2.614",
                         elide_to_bounds=False)
    assert field.text_actor.GetInput() == \
        "Energies: 0.662, 1.173, 1.332, 2.614"
