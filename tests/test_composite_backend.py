"""Composite controls and the widget backend switch (W5 §9.1).

The contract tests run against both the native class (``multipanel.legacy``)
and its composite (``multipanel.composite``): moving a host over should be a
change of import.
"""
import numpy as np
import pytest

from multipanel import backend, composite, legacy
from multipanel.testing import UiHarness

BACKENDS = ("legacy", "composite")


@pytest.fixture
def ui():
    with UiHarness(size=(800, 600)) as harness:
        yield harness


@pytest.fixture(autouse=True)
def _restore_backend():
    previous = backend.widget_backend()
    yield
    backend.set_widget_backend(previous)


def classes(kind):
    return legacy if kind == "legacy" else composite


def pixel(ui, x, y):
    """RGB (0-255) at display pixel ``x, y`` after a render."""
    import vtk
    from vtkmodules.util.numpy_support import vtk_to_numpy

    ui.render()
    grab = vtk.vtkWindowToImageFilter()
    grab.SetInput(ui.interactor.GetRenderWindow())
    grab.ReadFrontBufferOff()
    grab.Update()
    image = grab.GetOutput()
    width, height, _ = image.GetDimensions()
    data = vtk_to_numpy(image.GetPointData().GetScalars())
    return tuple(int(v) for v in data.reshape(height, width, -1)[y, x, :3])


# -- PanelBackgroundWidget contract ---------------------------------------------------------
@pytest.mark.parametrize("kind", BACKENDS)
def test_background_bounds_grow_by_the_buffer(ui, kind):
    widget = classes(kind).PanelBackgroundWidget(
        ui.renderer, ui.interactor, panel_bounds=(0.2, 0.4, 0.3, 0.5),
        buffer=0.05)
    assert np.allclose(widget.panel_bounds, (0.15, 0.45, 0.25, 0.55))
    assert widget.width == pytest.approx(0.3)
    assert widget.height == pytest.approx(0.3)


@pytest.mark.parametrize("kind", BACKENDS)
def test_background_moves_and_resizes(ui, kind):
    widget = classes(kind).PanelBackgroundWidget(
        ui.renderer, ui.interactor, panel_bounds=(0.1, 0.2, 0.1, 0.2),
        buffer=0)
    widget.SetPosition(0.5, 0.6)
    widget.SetSize(0.25, 0.125)
    assert np.allclose(widget.panel_bounds, (0.5, 0.75, 0.6, 0.725))
    assert (widget.width, widget.height) == pytest.approx((0.25, 0.125))


@pytest.mark.parametrize("kind", BACKENDS)
def test_background_highlight_signal_and_state(ui, kind):
    widget = classes(kind).PanelBackgroundWidget(
        ui.renderer, ui.interactor, panel_bounds=(0.1, 0.2, 0.1, 0.2))
    seen = []
    widget.highlightedChanged.connect(seen.append)
    widget.Highlight(True)
    widget.Highlight(True)
    assert widget.highlighted
    widget.Highlight(False)
    assert not widget.highlighted
    assert seen == [True, False]


@pytest.mark.parametrize("kind", BACKENDS)
def test_background_enable_and_native(ui, kind):
    widget = classes(kind).PanelBackgroundWidget(
        ui.renderer, ui.interactor, panel_bounds=(0.1, 0.2, 0.1, 0.2))
    assert widget.GetEnabled()
    widget.SetEnabled(False)
    assert not widget.GetEnabled()
    widget.SetEnabled(True)
    assert widget.GetEnabled()
    assert widget.native is (widget if kind == "legacy" else None)
    widget.Delete()


@pytest.mark.parametrize("kind", BACKENDS)
def test_background_draws_its_colour_and_highlight(ui, kind):
    widget = classes(kind).PanelBackgroundWidget(
        ui.renderer, ui.interactor, panel_bounds=(0.25, 0.75, 0.25, 0.75),
        buffer=0, panel_color=(1.0, 0.0, 0.0), highlight_color=(0, 0, 1),
        opacity=1.0, border_width=0)
    ui.renderer.SetBackground(0, 0, 0)
    assert pixel(ui, 400, 300) == pytest.approx((255, 0, 0), abs=3)
    assert pixel(ui, 100, 100) == pytest.approx((0, 0, 0), abs=3)
    widget.Highlight(True)
    assert pixel(ui, 400, 300) == pytest.approx((0, 0, 255), abs=3)
    widget.SetEnabled(False)
    assert pixel(ui, 400, 300) == pytest.approx((0, 0, 0), abs=3)


@pytest.mark.parametrize("kind", BACKENDS)
def test_transparent_rows_show_only_when_highlighted(ui, kind):
    # Themed list rows: invisible until selected.
    widget = classes(kind).PanelBackgroundWidget(
        ui.renderer, ui.interactor, panel_bounds=(0.25, 0.75, 0.25, 0.75),
        buffer=0, panel_color=(1.0, 0.0, 0.0), highlight_color=(0, 1, 0),
        opacity=0.0, border_width=0)
    ui.renderer.SetBackground(0, 0, 0)
    assert pixel(ui, 400, 300) == pytest.approx((0, 0, 0), abs=3)
    widget.Highlight(True)
    assert pixel(ui, 400, 300) == pytest.approx((0, 255, 0), abs=3)


# -- the backend switch ---------------------------------------------------------------------
def test_switch_rebinds_the_names():
    from multipanel import containers, widgets

    assert backend.widget_backend() == "legacy"
    assert containers.PanelBackgroundWidget is legacy.PanelBackgroundWidget
    assert backend.set_widget_backend("composite") == "legacy"
    assert containers.PanelBackgroundWidget is composite.PanelBackgroundWidget
    assert widgets.PanelBackgroundWidget is composite.PanelBackgroundWidget
    from multipanel.containers import PanelBackgroundWidget
    assert PanelBackgroundWidget is composite.PanelBackgroundWidget
    # The native class stays reachable.
    assert legacy.PanelBackgroundWidget.__module__ == "multipanel.containers"
    backend.set_widget_backend("legacy")
    assert containers.PanelBackgroundWidget is legacy.PanelBackgroundWidget


def test_unknown_backend_is_refused():
    with pytest.raises(ValueError):
        backend.set_widget_backend("qt")


def test_library_containers_build_composites(ui):
    from multipanel.containers import ScrollablePanel

    backend.set_widget_backend("composite")
    panel = ScrollablePanel(ui.interactor, ["a", "b", "c"], x=0.1, y=0.5,
                            title="Items")
    ui.render()
    rows = list(panel.scroll_box.visible_elements.values())
    backgrounds = [element for row in rows for element in row.elements
                   if type(element).__name__ == "PanelBackgroundWidget"]
    assert backgrounds
    assert all(b.native is None for b in backgrounds)
    # Selecting a row highlights its (composite) background.
    rows[0].Highlight(True)
    assert backgrounds[0].highlighted


# -- ButtonWidget contract ------------------------------------------------------------------
def make_button(ui, kind, **options):
    from multipanel.router import EventRouter

    EventRouter.install(ui.interactor)
    calls = []
    options.setdefault("icon_name", ["visible", "invisible"])
    button = classes(kind).ButtonWidget(
        ui.renderer, ui.interactor,
        callback=lambda widget, event: calls.append(
            widget.GetRepresentation().GetState()),
        widget_bounds=(0.25, 0.3, 0.5, 0.5 + 0.05 * 800 / 600), **options)
    ui.render()
    return button, calls


@pytest.fixture
def routed():
    from multipanel.router import EventRouter

    with UiHarness(size=(800, 600)) as harness:
        yield harness
        EventRouter.uninstall(harness.interactor)


@pytest.mark.parametrize("kind", BACKENDS)
def test_button_click_cycles_states_and_calls_back(routed, kind):
    button, calls = make_button(routed, kind)
    seen = {"clicked": [], "toggled": [], "pressed": 0, "released": 0}
    button.clicked.connect(seen["clicked"].append)
    button.toggled.connect(seen["toggled"].append)
    button.pressed.connect(lambda: seen.__setitem__(
        "pressed", seen["pressed"] + 1))
    button.released.connect(lambda: seen.__setitem__(
        "released", seen["released"] + 1))
    centre = (220, 320)
    routed.click(centre)
    assert button.state() == 1 and calls == [1]
    routed.click(centre)
    assert button.state() == 0 and calls == [1, 0]
    assert seen["clicked"] == [True, False]
    assert seen["toggled"] == [True, False]
    assert seen["pressed"] == seen["released"] == 2
    routed.click((600, 100))                     # elsewhere
    assert calls == [1, 0]


@pytest.mark.parametrize("kind", BACKENDS)
def test_button_state_api(routed, kind):
    button, calls = make_button(routed, kind, initial_state=1)
    assert button.state() == 1 and button.isChecked()
    toggled = []
    button.toggled.connect(toggled.append)
    button.setChecked(False)
    button.setChecked(False)
    assert toggled == [False]
    button.toggle()
    assert button.GetRepresentation().GetState() == 1
    button.click()
    assert button.state() == 0 and calls == [0]
    assert button.saveState()["state"] == 0
    button.restoreState({"state": 1})
    assert button.state() == 1
    assert calls == [0]                          # programmatic: no callback


@pytest.mark.parametrize("kind", BACKENDS)
def test_button_geometry_conventions(routed, kind):
    button, _calls = make_button(routed, kind)
    assert button.GetBounds() == pytest.approx(
        (0.25, 0.3, 0.5, 0.5 + 0.05 * 800 / 600))
    button.SetPosition(0.5, 0.25)                # fractions
    button.SetSize(64, 32)                       # display pixels
    assert button.GetBounds() == pytest.approx((0.5, 0.58, 0.25,
                                                0.25 + 32 / 600))
    button.SetPixelPosition(10, 20, 30, 40)
    assert tuple(button.Bounds[:4]) == pytest.approx((10, 40, 20, 60))
    button.SetBounds(0.1, 0.2, 0.1, 0.2)
    assert button.GetBounds() == pytest.approx((0.1, 0.2, 0.1, 0.2))
    assert button.sizeHint() == (32.0, 32.0)


@pytest.mark.parametrize("kind", BACKENDS)
def test_button_draws_the_state_icon_and_hides(routed, kind):
    routed.renderer.SetBackground(1, 1, 1)
    button, _calls = make_button(routed, kind, icon_name=["visible", "invisible"])
    button.SetPixelPosition(300, 200, 200, 200)

    def dark_pixels():
        import vtk
        from vtkmodules.util.numpy_support import vtk_to_numpy

        routed.render()
        grab = vtk.vtkWindowToImageFilter()
        grab.SetInput(routed.interactor.GetRenderWindow())
        grab.ReadFrontBufferOff()
        grab.Update()
        data = vtk_to_numpy(grab.GetOutput().GetPointData().GetScalars())
        image = data.reshape(600, 800, -1)[200:400, 300:500, :3]
        return int((image.max(axis=2) < 128).sum())

    play = dark_pixels()
    button.setState(1)
    stop = dark_pixels()
    assert play > 500 and stop > 500 and play != stop
    button.SetVisibility(False)
    assert dark_pixels() == 0


# -- SliderWidget contract ------------------------------------------------------------------
def make_slider(ui, kind, **options):
    from multipanel.router import EventRouter

    EventRouter.install(ui.interactor)
    calls = []
    settings = dict(min_value=0, max_value=10, initial_value=0,
                    title="Value", position=(0.25, 0.5), bar_length=0.5,
                    use_relative_position=True, slider_thickness=0.5,
                    callback=lambda widget, event: calls.append(
                        round(widget.value(), 6)))
    settings.update(options)
    slider = classes(kind).SliderWidget(ui.renderer, ui.interactor,
                                        **settings)
    ui.render()
    return slider, calls


def thumb_x(slider, value, width=800):
    """Display x of the thumb centre at ``value`` (VTK's geometry)."""
    rep = slider.rep
    span = (rep.GetMaximumValue() - rep.GetMinimumValue())
    t = (value - rep.GetMinimumValue()) / span
    x0 = 0.25 * width
    length = 0.5 * width
    cap, thumb = (rep.GetEndCapLength() * width,
                  rep.GetSliderLength() * width)
    return x0 + cap + t * (length - 2 * cap - thumb) + thumb / 2


@pytest.mark.parametrize("kind", BACKENDS)
def test_slider_drag_moves_value_and_signals(routed, kind):
    slider, calls = make_slider(routed, kind)
    events = []
    slider.sliderPressed.connect(lambda: events.append("pressed"))
    slider.sliderReleased.connect(lambda: events.append("released"))
    moved, changed = [], []
    slider.sliderMoved.connect(moved.append)
    slider.valueChanged.connect(changed.append)
    start = (thumb_x(slider, 0), 300)
    routed.press(start)
    routed.move((thumb_x(slider, 5), 300))
    routed.move((thumb_x(slider, 8), 300))
    routed.release()
    assert slider.value() == pytest.approx(8, abs=0.05)
    assert events == ["pressed", "released"]
    assert len(moved) == 2 and moved[-1] == pytest.approx(8, abs=0.05)
    assert changed == moved and calls == [round(v, 6) for v in moved]


@pytest.mark.parametrize("kind", BACKENDS)
def test_slider_track_click_jumps_on_release(routed, kind):
    slider, calls = make_slider(routed, kind)
    routed.press((thumb_x(slider, 6), 300))
    assert slider.value() == 0                 # VTK jumps on release
    routed.release()
    assert slider.value() == pytest.approx(6, abs=0.05)
    assert len(calls) == 1


@pytest.mark.parametrize("kind", BACKENDS)
def test_slider_without_tracking_commits_on_release(routed, kind):
    slider, calls = make_slider(routed, kind)
    slider.setTracking(False)
    changed = []
    slider.valueChanged.connect(changed.append)
    routed.press((thumb_x(slider, 0), 300))
    routed.move((thumb_x(slider, 4), 300))
    assert changed == []
    routed.release()
    assert changed == [pytest.approx(4, abs=0.05)] and len(calls) == 1


@pytest.mark.parametrize("kind", BACKENDS)
def test_slider_ignores_input_when_disabled_or_unavailable(routed, kind):
    slider, calls = make_slider(routed, kind)
    slider.SetEnabled(False)
    assert not slider.GetEnabled()
    routed.click((thumb_x(slider, 6), 300))
    slider.SetEnabled(True)
    slider.SetAvailable(False)
    routed.click((thumb_x(slider, 6), 300))
    assert slider.value() == 0 and calls == []
    slider.SetAvailable(True)
    routed.click((thumb_x(slider, 6), 300))
    assert slider.value() == pytest.approx(6, abs=0.05)


@pytest.mark.parametrize("kind", BACKENDS)
def test_slider_value_api_and_state(routed, kind):
    slider, calls = make_slider(routed, kind, initial_value=5)
    changed = []
    slider.valueChanged.connect(changed.append)
    slider.setRange(-2, 2)
    assert slider.value() == 2 and changed == [2]
    slider.setValue(1.5)
    slider.setValue(1.5)
    assert changed == [2, 1.5] and calls == []
    state = slider.saveState()
    assert (state["minimum"], state["maximum"], state["value"]) == (-2, 2,
                                                                    1.5)
    slider.restoreState({"value": -1, "tracking": False})
    assert slider.value() == -1 and not slider.isTracking()
    assert slider.native is (slider if kind == "legacy" else None)


@pytest.mark.parametrize("kind", BACKENDS)
@pytest.mark.parametrize("orientation", ["horizontal", "vertical"])
def test_slider_layout_bounds(routed, kind, orientation):
    slider, _calls = make_slider(routed, kind, orientation=orientation)
    slider.SetBounds(0.1, 0.4, 0.2, 0.3)
    assert slider.GetBounds() == pytest.approx((0.1, 0.4, 0.2, 0.3))
    assert slider.sizeHint() == ((160.0, 28.0) if orientation == "horizontal"
                                 else (28.0, 160.0))


def test_composite_slider_draws_like_vtk():
    """The composite's parts and text land on VTK's pixels."""
    import vtk
    from vtkmodules.util.numpy_support import vtk_to_numpy

    images = {}
    for kind in BACKENDS:
        with UiHarness(size=(600, 400)) as ui:
            ui.renderer.SetBackground(1, 1, 1)
            module = classes(kind)
            module.SliderWidget(
                ui.renderer, ui.interactor, 0, 10, 3, title="Energy",
                callback=lambda *_: None, position=(0.1, 0.7),
                bar_length=0.6, use_relative_position=True,
                slider_thickness=0.5)
            module.SliderWidget(
                ui.renderer, ui.interactor, 0, 1, 0.75, title=None,
                callback=lambda *_: None, position=(0.85, 0.9),
                bar_length=0.5, use_relative_position=True,
                orientation="vertical", slider_thickness=0.05,
                slider_bar_fraction=0.1, show_value=False)
            flat = module.SliderWidget(
                ui.renderer, ui.interactor, 0, 100, 40, title="Flat",
                callback=lambda *_: None, position=(0.1, 0.3),
                bar_length=0.5, use_relative_position=True,
                slider_thickness=0.4)
            flat.apply_flat_style()
            ui.render()
            grab = vtk.vtkWindowToImageFilter()
            grab.SetInput(ui.interactor.GetRenderWindow())
            grab.ReadFrontBufferOff()
            grab.Update()
            images[kind] = vtk_to_numpy(
                grab.GetOutput().GetPointData().GetScalars()).astype(int)
    difference = np.abs(images["legacy"] - images["composite"]).max(axis=1)
    assert int((difference > 60).sum()) <= 20
    assert int((images["legacy"][:, :3].max(axis=1) < 128).sum()) > 1000
