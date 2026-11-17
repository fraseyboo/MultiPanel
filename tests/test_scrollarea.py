"""ScrollArea: clipped viewport, scroll bar, wheel, popups (W2)."""
import numpy as np
import pytest
from vtkmodules.util.numpy_support import vtk_to_numpy
import vtk

from multipanel._widget_support import set_ui_scale, ui_scale, user_scale
from multipanel.animation import animations_enabled, set_animations_enabled
from multipanel.containers import Frame
from multipanel.layouts import VBoxLayout
from multipanel.router import EventRouter
from multipanel.scrollarea import ScrollArea
from multipanel.standard import CheckBox, ComboBox
from multipanel.testing import UiHarness
from multipanel.units import px

AREA = (100, 200, 300, 200)          # x, y, w, h (logical px)
ROWS = 20


@pytest.fixture
def ui():
    previous = user_scale()
    set_ui_scale(1.0)
    with UiHarness(size=(800, 600)) as harness:
        EventRouter.install(harness.interactor)
        yield harness
        EventRouter.uninstall(harness.interactor)
    set_ui_scale(previous)


def build(ui, rows=ROWS):
    area = ScrollArea(ui.renderer, ui.interactor)
    area.setGeometry(*(px(v) for v in AREA))
    content = Frame(area.contentRenderer(), ui.interactor, background=True,
                    panel_color=(1.0, 1.0, 1.0))
    column = VBoxLayout(spacing=4)
    boxes = [CheckBox(area.contentRenderer(), ui.interactor, f"Material {i}")
             for i in range(rows)]
    for box in boxes:
        column.addWidget(box)
    content.setLayout(column)
    area.setWidget(content)
    ui.render()
    return area, content, boxes


def centre(widget):
    x, y, w, h = widget.geometry("display")
    return (x + w / 2, y + h / 2)


def test_content_starts_at_the_top_and_the_bar_covers_the_overflow(ui):
    area, content, boxes = build(ui)
    bar = area.verticalScrollBar()
    content_h = content.sizeHint()[1]
    assert content_h > AREA[3]
    assert bar.isVisible() and bar.maximum() == pytest.approx(
        content_h - AREA[3])
    x, y, w, h = area.contentRenderer().GetViewport()
    assert (x * 800, y * 600) == pytest.approx(AREA[:2])
    assert ((w - x) * 800, (h - y) * 600) == pytest.approx(
        (AREA[2] - ScrollArea.BAR_PX, AREA[3]))
    top = content.geometry("display")
    assert top[1] + top[3] == pytest.approx(AREA[1] + AREA[3])


def test_short_content_needs_no_bar(ui):
    area, content, _boxes = build(ui, rows=3)
    assert not area.verticalScrollBar().isVisible()
    assert content.geometry("display")[3] == pytest.approx(AREA[3])


def test_content_is_clipped_to_the_viewport(ui):
    ui.renderer.SetBackground(0.0, 0.0, 0.0)
    build(ui)
    ui.render()
    grab = vtk.vtkWindowToImageFilter()
    grab.SetInput(ui.window)
    grab.ReadFrontBufferOff()
    grab.Update()
    image = grab.GetOutput()
    width, height, _ = image.GetDimensions()
    pixels = vtk_to_numpy(image.GetPointData().GetScalars()).reshape(
        height, width, -1)
    inside = pixels[AREA[1] + 20, AREA[0] + 50, :3]
    below = pixels[AREA[1] - 20, AREA[0] + 50, :3]
    assert inside.min() > 200            # white content
    assert below.max() < 30              # nothing drawn outside the area


def test_viewport_is_transparent_over_the_panel_behind_it(ui):
    ui.renderer.SetBackground(0.5, 0.5, 0.5)
    area = ScrollArea(ui.renderer, ui.interactor)
    area.setGeometry(*(px(v) for v in AREA))
    area.setWidget(Frame(area.contentRenderer(), ui.interactor))
    ui.render()
    grab = vtk.vtkWindowToImageFilter()
    grab.SetInput(ui.window)
    grab.ReadFrontBufferOff()
    grab.Update()
    value = grab.GetOutput().GetScalarComponentAsDouble(
        AREA[0] + 50, AREA[1] + 50, 0, 0)
    assert value == pytest.approx(128, abs=2)        # not cleared to black


def test_wheel_scrolls_smoothly(ui):
    area, content, boxes = build(ui)
    assert animations_enabled()
    ui.wheel(centre(boxes[2]), steps=-1)
    assert area.scrollValue() == 0.0               # animating
    ui.process_events(ScrollArea.SCROLL_MS / 2)
    assert 0.0 < area.scrollValue() < ScrollArea.WHEEL_STEP_PX
    ui.process_events(ScrollArea.SCROLL_MS)
    assert area.scrollValue() == ScrollArea.WHEEL_STEP_PX
    top = content.geometry("display")
    assert top[1] + top[3] == pytest.approx(
        AREA[1] + AREA[3] + ScrollArea.WHEEL_STEP_PX)
    # Wheel steps accumulate while an animation runs.
    ui.wheel(centre(boxes[4]), steps=-1)
    ui.wheel(centre(boxes[4]), steps=-1)
    ui.process_events(500)
    assert area.scrollValue() == 3 * ScrollArea.WHEEL_STEP_PX


def test_wheel_without_animations_and_clamping(ui):
    previous = animations_enabled()
    set_animations_enabled(False)
    try:
        area, _content, boxes = build(ui)
        for _ in range(50):
            ui.wheel(centre(area), steps=-1)
        assert area.scrollValue() == area.verticalScrollBar().maximum()
        ui.wheel(centre(area), steps=1)
        assert area.scrollValue() == pytest.approx(
            area.verticalScrollBar().maximum() - ScrollArea.WHEEL_STEP_PX)
    finally:
        set_animations_enabled(previous)


def test_only_visible_children_can_be_hit(ui):
    area, _content, boxes = build(ui)
    area.scrollTo(100, animated=False)
    hidden = boxes[0]
    x, y, w, h = hidden.geometry("display")
    assert y > AREA[1] + AREA[3]                  # scrolled out above
    assert not hidden.hitTest(x + 5, y + h / 2)
    visible = boxes[8]
    ui.click(centre(visible))
    assert visible.isChecked()


def test_dragging_the_thumb_and_paging(ui):
    area, _content, _boxes = build(ui)
    bar = area.verticalScrollBar()
    x, y, w, h = bar.geometry("display")
    top, length = bar._thumb(y, h)
    start = (x + w / 2, top - length / 2)
    ui.drag(start, (start[0], start[1] - 50), steps=5)
    assert bar.value() > 0
    dragged = bar.value()
    ui.click((x + w / 2, y + 3))                  # track below the thumb
    assert bar.value() == pytest.approx(min(bar.maximum(),
                                            dragged + bar.pageStep()))


def test_ensure_widget_visible(ui):
    previous = animations_enabled()
    set_animations_enabled(False)
    try:
        area, _content, boxes = build(ui)
        area.ensureWidgetVisible(boxes[-1])
        x, y, w, h = boxes[-1].geometry("display")
        assert y >= AREA[1] - 0.5
        area.ensureWidgetVisible(boxes[0])
        assert area.scrollValue() == 0.0
    finally:
        set_animations_enabled(previous)


def test_combo_box_popup_from_the_content_draws_on_the_popup_layer(ui):
    area = ScrollArea(ui.renderer, ui.interactor)
    area.setGeometry(*(px(v) for v in AREA))
    content = Frame(area.contentRenderer(), ui.interactor)
    combo = ComboBox(area.contentRenderer(), ui.interactor)
    combo.addItems(["Air", "Lead", "Water"])
    column = VBoxLayout()
    column.addWidget(combo)
    column.addStretch()
    content.setLayout(column)
    area.setWidget(content)
    ui.render()
    ui.click(centre(combo))
    menu = combo._menu if hasattr(combo, "_menu") else combo.view()
    assert menu.isOpen()
    assert menu.renderer.GetLayer() > area.contentRenderer().GetLayer()
    cx, cy, cw, ch = combo.geometry("display")
    mx, my, mw, mh = menu.geometry("display")
    assert my + mh <= cy and abs(mx - cx) < 1           # just below it


def test_hiding_the_area_hides_its_viewport_and_content(ui):
    area, content, boxes = build(ui)
    area.SetVisibility(False)
    assert not area.contentRenderer().GetDraw()
    assert not content.isVisible() and not area.verticalScrollBar().isVisible()
    area.SetVisibility(True)
    assert area.contentRenderer().GetDraw() and content.isVisible()


def test_theme_and_style_follow_the_parent_renderer(ui):
    from types import SimpleNamespace

    from multipanel.style import Style
    from multipanel.ui_theme import DARK, vtk_tokens

    area, _content, boxes = build(ui, rows=2)
    ui.renderer.theme = SimpleNamespace(tokens=vtk_tokens(DARK))
    assert area.contentRenderer().theme is ui.renderer.theme
    assert Style.for_renderer(area.contentRenderer()) is \
        Style.for_renderer(ui.renderer)


def test_content_must_be_built_on_the_content_renderer(ui):
    area = ScrollArea(ui.renderer, ui.interactor)
    with pytest.raises(ValueError):
        area.setWidget(Frame(ui.renderer, ui.interactor))
