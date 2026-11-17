"""PropertyAnimation, easing, global disable and the animated controls (W8)."""
import pytest

from multipanel._widget_support import set_ui_scale, ui_scale, user_scale
from multipanel.animation import (
    EASINGS,
    PropertyAnimation,
    animate,
    animations_enabled,
    set_animations_enabled,
)
from multipanel.overlay import Popup
from multipanel.router import EventRouter
from multipanel.standard import Menu, ProgressBar
from multipanel.testing import UiHarness
from multipanel.units import px


@pytest.fixture
def ui():
    previous = user_scale()
    set_ui_scale(1.0)
    with UiHarness(size=(800, 600)) as harness:
        EventRouter.install(harness.interactor)
        yield harness
        EventRouter.uninstall(harness.interactor)
    set_ui_scale(previous)


@pytest.fixture
def no_animations():
    previous = animations_enabled()
    set_animations_enabled(False)
    yield
    set_animations_enabled(previous)


class Box:
    def __init__(self, interactor):
        self.interactor = interactor
        self.height = 10.0
        self._color = (0.0, 0.0, 0.0)
        self.renders = 0

    def color(self):
        return self._color

    def setColor(self, color):
        self._color = color

    def requestRender(self):
        self.renders += 1


def test_easings_start_at_zero_and_end_at_one():
    for name, curve in EASINGS.items():
        assert curve(0.0) == pytest.approx(0.0, abs=1e-9), name
        assert curve(1.0) == pytest.approx(1.0, abs=1e-9), name
    assert EASINGS["outCubic"](0.5) > 0.5 > EASINGS["inCubic"](0.5)


def test_animates_an_attribute_over_its_duration(ui):
    box = Box(ui.interactor)
    animation = PropertyAnimation(box, "height", duration_ms=100,
                                  easing="linear", end_value=60.0)
    done, values = [], []
    animation.finished.connect(lambda: done.append(1))
    animation.valueChanged.connect(values.append)
    animation.start()
    assert animation.state() == "running" and box.height == 10.0
    ui.process_events(50)
    assert 25.0 < box.height < 45.0
    ui.process_events(100)
    assert box.height == 60.0 and done == [1]
    assert animation.state() == "stopped"
    assert values == sorted(values) and box.renders >= 3


def test_uses_setters_and_interpolates_tuples(ui):
    box = Box(ui.interactor)
    anim = animate(box, "color", (1.0, 0.5, 0.0), duration_ms=80,
                   easing="linear")
    ui.process_events(40)
    r, g, _b = box.color()
    assert 0.3 < r < 0.7 and g == pytest.approx(r / 2)
    ui.process_events(80)
    assert box.color() == (1.0, 0.5, 0.0) and anim.state() == "stopped"


def test_callable_setter_loops_and_stop(ui):
    seen = []
    animation = PropertyAnimation(None, seen.append, duration_ms=100,
                                  easing="linear", start_value=0.0,
                                  end_value=1.0, interactor=ui.interactor,
                                  loop_count=-1)
    animation.start()
    ui.process_events(250)
    assert animation.currentLoop() == 2 and animation.state() == "running"
    assert min(seen[1:]) < 0.2 and max(seen) > 0.8     # wrapped around
    animation.stop()
    count = len(seen)
    ui.process_events(100)
    assert len(seen) == count


def test_pause_resume_and_backward(ui):
    box = Box(ui.interactor)
    animation = PropertyAnimation(box, "height", duration_ms=100,
                                  easing="linear", start_value=0.0,
                                  end_value=100.0)
    animation.setDirection("backward")
    animation.start()
    assert box.height == 100.0
    ui.process_events(48)
    animation.pause()
    paused = box.height
    ui.process_events(500)
    assert box.height == paused and animation.state() == "paused"
    animation.resume()
    ui.process_events(200)
    assert box.height == 0.0


def test_fire_and_forget_animations_stay_alive(ui):
    box = Box(ui.interactor)
    animate(box, "height", 20.0, duration_ms=50)
    import gc

    gc.collect()
    ui.process_events(100)
    assert box.height == 20.0


def test_disabled_animations_jump_to_the_end(ui, no_animations):
    box = Box(ui.interactor)
    done = []
    animation = animate(box, "height", 99.0, duration_ms=500)
    animation.finished.connect(lambda: done.append(1))
    assert box.height == 99.0 and animation.state() == "stopped"


def test_errors_for_bad_configuration(ui):
    box = Box(ui.interactor)
    with pytest.raises(ValueError):
        PropertyAnimation(box, "height", easing="bouncy")
    with pytest.raises(ValueError):
        PropertyAnimation(box, "height").start()          # no end value
    with pytest.raises(ValueError):
        PropertyAnimation(object(), "height")             # no interactor


# -- uses ------------------------------------------------------------------------

def test_progress_bar_busy_mode_animates_and_stops(ui):
    bar = ProgressBar(ui.renderer, ui.interactor, minimum=0, maximum=0)
    bar.setGeometry(px(100), px(300), px(200), px(18))
    assert bar._busy_animation.state() == "running"
    phases = set()
    for _ in range(10):
        ui.process_events(100)
        phases.add(round(bar.busyPhase(), 2))
    assert len(phases) > 5
    bar.setRange(0, 100)
    assert bar._busy_animation is None


def test_progress_bar_busy_mode_is_still_without_animations(ui, no_animations):
    bar = ProgressBar(ui.renderer, ui.interactor, minimum=0, maximum=0)
    assert bar._busy_animation is None and bar.busyPhase() == 0.5


def test_popups_fade_in(ui):
    menu = Menu(ui.renderer, ui.interactor)
    menu.addAction("Copy")
    menu.popup(at=(200, 400))
    assert menu.windowOpacity() == 0.0
    item = menu.items()[0]
    assert item.text_actor.GetTextProperty().GetOpacity() == 0.0
    ui.process_events(Popup.FADE_IN_MS / 2)
    assert 0.0 < menu.windowOpacity() < 1.0
    ui.process_events(Popup.FADE_IN_MS)
    assert menu.windowOpacity() == 1.0
    assert item.text_actor.GetTextProperty().GetOpacity() == 1.0
    assert item.actor.GetProperty().GetOpacity() == 1.0


def test_dismissing_mid_fade_restores_full_opacity(ui):
    menu = Menu(ui.renderer, ui.interactor)
    menu.addAction("Copy")
    menu.popup(at=(200, 400))
    ui.process_events(10)
    menu.dismiss()
    assert menu.windowOpacity() == 1.0
    assert menu.items()[0].text_actor.GetTextProperty().GetOpacity() == 1.0
    menu.popup(at=(200, 400))
    ui.process_events(500)
    assert menu.items()[0].text_actor.GetTextProperty().GetOpacity() == 1.0


def test_popups_open_fully_opaque_without_animations(ui, no_animations):
    menu = Menu(ui.renderer, ui.interactor)
    menu.addAction("Copy")
    menu.popup(at=(200, 400))
    assert menu.windowOpacity() == 1.0


def test_hidden_busy_bar_requests_no_renders(ui):
    bar = ProgressBar(ui.renderer, ui.interactor, minimum=0, maximum=0)
    bar.setGeometry(px(100), px(300), px(200), px(18))
    bar.SetVisibility(False)
    ui.process_events(50)                  # the render that hides it
    renders = []
    ui.window.AddObserver("StartEvent", lambda *_: renders.append(1))
    ui.process_events(500)
    assert renders == [] and bar._busy_animation.state() == "running"
