"""Splitter: sizes, stretch, handle dragging, collapsing (W2)."""
import pytest

from multipanel._widget_support import set_ui_scale, ui_scale, user_scale
from multipanel.containers import Frame
from multipanel.layouts import VBoxLayout
from multipanel.router import EventRouter
from multipanel.splitter import Splitter
from multipanel.standard import Label
from multipanel.testing import UiHarness
from multipanel.units import px

AREA = (100, 100, 506, 300)          # 500 px for widgets + one 6 px handle


@pytest.fixture
def ui():
    previous = user_scale()
    set_ui_scale(1.0)
    with UiHarness(size=(800, 600)) as harness:
        EventRouter.install(harness.interactor)
        yield harness
        EventRouter.uninstall(harness.interactor)
    set_ui_scale(previous)


def build(ui, orientation="horizontal", count=2, area=AREA):
    split = Splitter(ui.renderer, ui.interactor, orientation)
    labels = []
    for i in range(count):
        label = Label(ui.renderer, ui.interactor, f"Pane {i}")
        label.setMinimumSize(px(60), px(20))
        split.addWidget(label)
        labels.append(label)
    split.setGeometry(*(px(v) for v in area))
    ui.render()
    return split, labels


def width(widget):
    return widget.geometry("px")[2]


def test_sizes_fill_the_splitter_and_place_children(ui):
    split, (left, right) = build(ui)
    split.setSizes([200, 300])
    assert split.sizes() == pytest.approx([200, 300])
    assert left.geometry("px") == pytest.approx((100, 100, 200, 300))
    assert right.geometry("px")[0] == pytest.approx(306)
    handle = split.handle(1)
    assert handle.geometry("px") == pytest.approx((300, 100, 6, 300))


def test_set_sizes_scale_to_fit(ui):
    split, _ = build(ui)
    split.setSizes([100, 100])
    assert split.sizes() == pytest.approx([250, 250])


def test_resizing_shares_the_change_by_stretch_or_proportion(ui):
    split, _ = build(ui)
    split.setSizes([200, 300])
    split.setGeometry(*(px(v) for v in (100, 100, 606, 300)))
    assert split.sizes() == pytest.approx([240, 360])      # proportional
    split.setStretchFactor(1, 1)
    split.setGeometry(*(px(v) for v in (100, 100, 706, 300)))
    assert split.sizes() == pytest.approx([240, 460])      # stretch only


def test_dragging_the_handle_moves_both_neighbours(ui):
    split, (left, right) = build(ui)
    split.setSizes([250, 250])
    moves = []
    split.splitterMoved.connect(lambda pos, index: moves.append((pos, index)))
    start = ui.point_of(split.handle(1))
    ui.drag(start, (start[0] - 50, start[1]))
    assert split.sizes() == pytest.approx([200, 300])
    assert width(left) == pytest.approx(200) and width(right) == pytest.approx(300)
    assert moves[-1] == (pytest.approx(200), 1)


def test_dragging_past_half_the_minimum_collapses(ui):
    split, (left, right) = build(ui)
    split.setSizes([250, 250])
    split.moveSplitter(40, 1)                 # 40 < 60 but > 30: stops at 60
    assert split.sizes() == pytest.approx([60, 440])
    split.moveSplitter(20, 1)                 # below half: collapses
    assert split.sizes() == pytest.approx([0, 500])
    assert not left.isVisible() and right.isVisible()
    split.setCollapsible(1, False)
    split.moveSplitter(495, 1)
    assert split.sizes() == pytest.approx([440, 60])


def test_vertical_splitter_stacks_from_the_top(ui):
    split, (top, bottom) = build(ui, "vertical", area=(100, 100, 300, 406))
    split.setSizes([100, 300])
    assert top.geometry("px")[1] == pytest.approx(100 + 406 - 100)
    assert bottom.geometry("px")[1] == pytest.approx(100)
    start = ui.point_of(split.handle(1))
    ui.drag(start, (start[0], start[1] - 50))     # down: top grows
    assert split.sizes() == pytest.approx([150, 250])


def test_hiding_hides_children_and_handles(ui):
    split, labels = build(ui, count=3, area=(100, 100, 512, 300))
    split.SetVisibility(False)
    assert not any(l.isVisible() for l in labels)
    assert not split.handle(1).isVisible()
    split.SetVisibility(True)
    assert all(l.isVisible() for l in labels)


def test_splitter_in_a_layout_and_state_round_trip(ui):
    panel = Frame(ui.renderer, ui.interactor, background=True)
    panel.setGeometry(px(50), px(50), px(600), px(400))
    split, _ = build(ui)
    column = VBoxLayout()
    column.addWidget(split, stretch=1)
    panel.setLayout(column)
    panel.contentLayout().activate()
    assert sum(split.sizes()) + split.handleWidth() == pytest.approx(
        split.geometry("px")[2])
    split.setSizes([100, 400])
    state = split.saveState()
    split.setSizes([300, 200])
    split.restoreState(state)
    assert split.sizes()[0] == pytest.approx(
        100 / 500 * sum(split.sizes()))


def test_sizes_set_before_layout_are_scaled_in_proportion(ui):
    split = Splitter(ui.renderer, ui.interactor)
    for i in range(3):
        label = Label(ui.renderer, ui.interactor, f"Pane {i}")
        label.setMinimumSize(px(60), px(20))
        split.addWidget(label)
    split.setSizes([1, 1, 2])                 # no geometry yet
    split.setStretchFactor(2, 1)
    split.setGeometry(*(px(v) for v in (100, 100, 412, 300)))
    assert split.sizes() == pytest.approx([100, 100, 200])
