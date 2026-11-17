"""DockPane wheel scrolling (smooth, W8) and per-pass hint caching (W2)."""
import pytest

from multipanel._widget_support import set_ui_scale, ui_scale
from multipanel.animation import animations_enabled, set_animations_enabled
from multipanel.containers import DockPane, Frame, WidgetPanel
from multipanel.controls import TextWidget
from multipanel.layouts import VBoxLayout, layout_pass
from multipanel.standard import Label
from multipanel.testing import UiHarness
from multipanel.units import px


@pytest.fixture
def ui():
    previous, animated = ui_scale(), animations_enabled()
    set_ui_scale(1.0)
    with UiHarness(size=(1000, 400)) as harness:
        yield harness
    set_ui_scale(previous)
    set_animations_enabled(animated)


def overflowing_dock(ui, panels=6, tabs=False):
    dock = DockPane(ui.renderer, ui.interactor, side="left", width=.25)
    if tabs:
        dock.add_tab("first", "add_shape")
        dock.add_tab("second", "GRI")
    for index in range(panels):
        panel = WidgetPanel(ui.renderer, ui.interactor, {},
                            panel_title=f"Panel {index}",
                            panel_position=(0.4, 0.8), panel_width=0.15,
                            keep_aspect_ratio=False)
        column = VBoxLayout(spacing=4)
        for row in range(4):
            column.addWidget(TextWidget(ui.renderer, ui.interactor,
                                        text=f"Row {row}",
                                        scale_text_to_widget=False))
        panel.setLayout(column)
        dock.add_panel(panel, tab="first" if tabs else None)
    if tabs:
        dock.select_tab("first")
    ui.process_events()
    maximum = dock.scroll_box.total_height - 1.0
    assert maximum > 0.2, "the test needs a dock that overflows"
    return dock, maximum


def wheel_down(dock):
    x0, x1, y0, y1 = dock.bounds
    return dock.handle_mouse_wheel((x0 + x1) / 2, (y0 + y1) / 2, -1)


def step(maximum):
    return max(0.06, 0.08 * maximum)


def test_without_animations_a_notch_scrolls_at_once(ui):
    set_animations_enabled(False)
    dock, maximum = overflowing_dock(ui)
    assert wheel_down(dock)
    assert dock.scrollOffset() == pytest.approx(step(maximum))


def test_wheel_scrolls_smoothly_and_notches_accumulate(ui):
    set_animations_enabled(True)
    dock, maximum = overflowing_dock(ui)
    panel = dock.panels[0]
    top_before = panel.GetBounds()[3]
    assert wheel_down(dock)
    assert dock.scrollOffset() < step(maximum)       # not there yet
    ui.process_events(DockPane.SCROLL_MS // 3)
    middle = dock.scrollOffset()
    assert 0 < middle < step(maximum)
    assert wheel_down(dock)                          # before the first ends
    ui.process_events(DockPane.SCROLL_MS * 3)
    assert dock.scrollOffset() == pytest.approx(min(maximum,
                                                     2 * step(maximum)))
    # Panels moved up with the stack.
    assert panel.GetBounds()[3] == pytest.approx(
        top_before + dock.scrollOffset())


def test_switching_tabs_stops_a_running_scroll(ui):
    set_animations_enabled(True)
    dock, _maximum = overflowing_dock(ui, tabs=True)
    wheel_down(dock)
    ui.process_events(DockPane.SCROLL_MS // 4)
    assert dock.scrollOffset() > 0
    dock.select_tab("second")
    dock.select_tab("first")
    ui.process_events(DockPane.SCROLL_MS * 2)
    assert dock.scrollOffset() == 0.0               # nothing kept moving


def test_wheel_at_the_end_is_not_consumed_when_passing_events(ui):
    set_animations_enabled(False)
    dock, maximum = overflowing_dock(ui)
    dock.pass_scroll_events = True
    dock.setScrollOffset(maximum)
    assert not wheel_down(dock)


# -- per-pass hint cache ---------------------------------------------------------------
class CountingLabel(Label):
    calls = 0

    def sizeHint(self):
        CountingLabel.calls += 1
        return super().sizeHint()


def labelled_frame(ui, count):
    frame = Frame(ui.renderer, ui.interactor)
    frame.setGeometry(px(10), px(10), px(300), px(200))
    column = VBoxLayout()
    labels = [CountingLabel(ui.renderer, ui.interactor, f"Label {i}")
              for i in range(count)]
    for label in labels:
        column.addWidget(label)
    frame.setLayout(column)
    return column, labels


def measure_one_widget():
    """sizeHint calls for one Label measured once (its minimumSizeHint
    asks its own sizeHint too)."""
    label_calls = CountingLabel.calls
    CountingLabel.calls = 0
    return label_calls


def test_a_pass_measures_each_widget_once_and_the_next_pass_afresh(ui):
    column, labels = labelled_frame(ui, 3)
    probe = CountingLabel(ui.renderer, ui.interactor, "probe")
    CountingLabel.calls = 0
    probe.sizeHint()
    probe.minimumSizeHint()
    per_widget = measure_one_widget()          # what measuring once costs
    column.activate()
    assert CountingLabel.calls == 3 * per_widget
    # A hint that changes without updateGeometry() (as legacy controls do)
    # is measured again by the next pass: nothing is cached across passes.
    labels[0]._text = "A much longer label than before"
    CountingLabel.calls = 0
    column.activate()
    assert CountingLabel.calls == 3 * per_widget
    assert labels[0].geometry("px")[2] >= labels[0].sizeHint()[0] - 1


def test_nested_passes_share_one_cache(ui):
    column, _labels = labelled_frame(ui, 1)
    CountingLabel.calls = 0
    column.activate()
    one_pass = CountingLabel.calls
    CountingLabel.calls = 0
    with layout_pass():
        column.sizeHint()
        column.minimumSize()
        column.activate()
    assert CountingLabel.calls == one_pass
