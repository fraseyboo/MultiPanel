"""The router must not change how existing (legacy) widgets behave."""
import numpy as np
import pytest

from multipanel.containers import DockPane, WidgetPanel
from multipanel.controls import TextWidget, VectorButtonWidget
from multipanel.router import EventRouter
from multipanel.testing import UiHarness


@pytest.fixture(params=[False, True], ids=["no-router", "router"])
def ui(request):
    with UiHarness(size=(800, 600)) as harness:
        if request.param:
            EventRouter.install(harness.interactor)
        yield harness
        EventRouter.uninstall(harness.interactor)


def host_like_scene(ui):
    properties = {
        "info text": {"textbox_size": [0.95, 0.20], "panel_offset": [0.5, -0.4],
                      "text": "Current Material: lead"},
    }
    panel = WidgetPanel(ui.renderer, ui.interactor, properties,
                        panel_title="Panel", panel_position=(0.4, 0.8),
                        panel_width=0.2, keep_aspect_ratio=False)
    dock = DockPane(ui.renderer, ui.interactor, side="left", width=.22)
    docked = WidgetPanel(ui.renderer, ui.interactor, dict(properties),
                         panel_title="Docked", panel_position=(0.0, 0.8),
                         panel_width=0.2, keep_aspect_ratio=False)
    dock.add_panel(docked)
    ui.renderer.UI_panels = {"panel": panel, "dock": dock, "docked": docked}
    return panel, dock


def test_vector_button_clicks_work_with_or_without_router(ui):
    triangle = np.asarray(((0.1, 0.1), (0.9, 0.5), (0.1, 0.9)))
    button = VectorButtonWidget(
        ui.renderer, ui.interactor, input_data=[triangle, triangle],
        color=(0.5, 0.5, 0.5), bounds=(0.6, 0.7, 0.1, 0.2))
    pressed = []
    button.pressed.connect(lambda: pressed.append(1))
    ui.render()
    ui.click(button)
    assert pressed == [1]


def test_text_widget_typing_works_with_or_without_router(ui):
    field = TextWidget(ui.renderer, ui.interactor, text="", editable=True)
    assert field.start_editing()
    ui.key_clicks("Lead 82")
    ui.key("Return")
    assert field.textValue() == "Lead 82"


def test_pointer_sweep_over_real_containers_is_safe(ui):
    host_like_scene(ui)
    ui.render()
    router = EventRouter.for_interactor(ui.interactor)
    for x in range(0, 800, 40):
        for y in range(0, 600, 40):
            ui.move((x, y))
            if router is not None:
                router.hitChain(x, y)      # raises directly if broken
    ui.wheel((80, 300), steps=3)
    ui.wheel((80, 300), steps=-3)
    ui.click((400, 450))


def test_router_reports_containers_as_ui(ui):
    _panel, dock = host_like_scene(ui)
    ui.render()
    router = EventRouter.install(ui.interactor)
    x0, x1, y0, y1 = dock.bounds
    inside = ((x0 + x1) / 2 * 800, (y0 + y1) / 2 * 600)
    assert router.isOverUi(*inside)
    assert not router.isOverUi(790, 5)


def test_hidden_legacy_panels_are_not_hit():
    # A panel under an inactive dock tab is hidden with SetEnabled(False);
    # it has no GetVisibility, so isVisible() alone still says True. Its
    # stale bounds must not hide what is drawn there (sliders in one tab sat
    # under another tab's status text).
    with UiHarness(size=(800, 600)) as ui:
        router = EventRouter.install(ui.interactor)
        try:
            _panel, _dock = host_like_scene(ui)
            docked = ui.renderer.UI_panels["docked"]
            ui.render()
            x0, x1, y0, y1 = docked.panel_background.GetBounds()[:4]
            centre = ((x0 + x1) / 2 * 800, (y0 + y1) / 2 * 600)
            assert docked in router.hitChain(*centre)
            docked.SetEnabled(False)          # as an inactive tab does
            assert not docked.GetEnabled()
            chain = router.hitChain(*centre)
            assert docked not in chain
            assert docked.added_widgets["info text"] not in chain
        finally:
            EventRouter.uninstall(ui.interactor)
