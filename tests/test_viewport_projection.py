"""The viewport panel's perspective / parallel projection button."""
import math

import pytest

from multipanel.containers import ViewportDisplayPanel
from multipanel.router import EventRouter
from multipanel.testing import UiHarness


@pytest.fixture
def ui():
    with UiHarness(size=(1000, 700)) as harness:
        EventRouter.install(harness.interactor)
        camera = harness.renderer.GetActiveCamera()
        camera.SetPosition(0, -4, 3)
        camera.SetFocalPoint(0, 0, 0)
        camera.SetViewUp(0, 0, 1)
        yield harness
        EventRouter.uninstall(harness.interactor)


def make_panel(ui, **options):
    panel = ViewportDisplayPanel(ui.renderer, ui.interactor, **options)
    ui.render()
    return panel


def test_button_switches_projection_and_keeps_the_view_size(ui):
    panel = make_panel(ui)
    camera = ui.renderer.GetActiveCamera()
    distance = camera.GetDistance()
    seen = []
    panel.projectionChanged.connect(seen.append)
    ui.click(panel.projection_button)
    assert camera.GetParallelProjection() and panel.isParallelProjection()
    assert panel.projection_button.state == 1
    # Half the view height at the focal point is unchanged.
    expected = distance * math.tan(math.radians(camera.GetViewAngle()) / 2)
    assert camera.GetParallelScale() == pytest.approx(expected)
    ui.click(panel.projection_button)
    assert not camera.GetParallelProjection()
    assert panel.projection_button.state == 0
    assert camera.GetDistance() == pytest.approx(distance)
    assert camera.GetFocalPoint() == pytest.approx((0, 0, 0))
    assert seen == [True, False]


def test_perspective_distance_follows_a_parallel_zoom(ui):
    panel = make_panel(ui)
    camera = ui.renderer.GetActiveCamera()
    panel.set_projection(True, render=False)
    camera.SetParallelScale(camera.GetParallelScale() / 2)   # zoomed in
    distance = camera.GetDistance()
    panel.set_projection(False, render=False)
    assert camera.GetDistance() == pytest.approx(distance / 2)


def test_button_follows_changes_made_elsewhere_and_state(ui):
    panel = make_panel(ui)
    ui.renderer.GetActiveCamera().ParallelProjectionOn()
    ui.render()
    assert panel.isParallelProjection()
    assert panel.projection_button.state == 1
    assert "click for perspective" in panel.projection_button.hover_text
    assert panel.saveState()["parallelProjection"] is True
    panel.restoreState({"parallelProjection": False})
    assert not ui.renderer.GetActiveCamera().GetParallelProjection()


def test_buttons_share_the_row_and_hide_together(ui):
    panel = make_panel(ui)
    modes = [panel.buttons[mode].GetBounds() for mode in panel.MODES]
    projection = panel.projection_button.GetBounds()
    assert projection[0] > modes[-1][1]                # after the modes
    assert projection[2:4] == pytest.approx(modes[-1][2:4])
    x0, x1, y0, y1 = panel.GetBounds()
    assert x0 <= projection[0] and projection[1] <= x1
    panel.set_controls_visible(False, render=False)
    assert not panel.projection_button.GetVisibility()


def test_the_button_can_be_left_out(ui):
    panel = make_panel(ui, show_projection_button=False)
    assert panel.projection_button is None
    panel.set_projection(True, render=False)
    assert ui.renderer.GetActiveCamera().GetParallelProjection()
