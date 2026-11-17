"""Popups: placement, dismissal, modality, nesting and draw order."""
import numpy as np
import pytest

from multipanel._widget_support import set_ui_scale, ui_layer, ui_scale, user_scale
from multipanel.controls import VectorButtonWidget
from multipanel.core import SizePolicy, WidgetMixin
from multipanel.layouts import VBoxLayout
from multipanel.overlay import OverlayLayer, Popup
from multipanel.router import EventRouter
from multipanel.testing import UiHarness
from multipanel.units import px

SIZE = (800, 600)


@pytest.fixture
def ui():
    previous = user_scale()
    set_ui_scale(1.0)
    with UiHarness(size=SIZE) as harness:
        harness.scene = []
        harness.interactor.AddObserver(
            "LeftButtonPressEvent", lambda *_: harness.scene.append(1), 10.0)
        yield harness
        EventRouter.uninstall(harness.interactor)
    set_ui_scale(previous)


class Item(WidgetMixin):
    """Native popup row recording clicks."""

    def __init__(self, ui, name):
        self.renderer = ui.renderer
        self.interactor = ui.interactor
        self.clicks = []
        self.initWidget(name)
        self.setSizePolicy(SizePolicy.Expanding, SizePolicy.Fixed)

    def sizeHint(self):
        return (120.0, 24.0)

    def mousePressEvent(self, event):
        self.clicks.append(event.pos())
        event.accept()


class Anchor(WidgetMixin):
    def __init__(self, ui, geometry):
        self.renderer = ui.renderer
        self.interactor = ui.interactor
        self.initWidget("anchor")
        self.setGeometry(*(px(value) for value in geometry))


def menu(ui, count=3, modal=False):
    popup = Popup(ui.renderer, ui.interactor, modal=modal)
    column = VBoxLayout(spacing=2)
    items = [Item(ui, f"item {index}") for index in range(count)]
    for item in items:
        column.addWidget(item)
    popup.setLayout(column)
    return popup, items


def centre(widget):
    x, y, w, h = widget.geometry("display")
    return (x + w / 2, y + h / 2)


def test_popup_opens_below_anchor_and_flips_when_out_of_room(ui):
    popup, _items = menu(ui)
    width, height = popup.sizeHint()
    popup.popup(anchor=Anchor(ui, (100, 400, 80, 24)), placement="below")
    x, y, w, h = popup.geometry("px")
    assert (x, y + h) == pytest.approx((100, 400 - Popup.GAP_PX))
    popup.dismiss()

    popup.popup(anchor=Anchor(ui, (100, 20, 80, 24)), placement="below")
    x, y, w, h = popup.geometry("px")
    assert y == pytest.approx(20 + 24 + Popup.GAP_PX)        # flipped above
    popup.dismiss()

    popup.popup(anchor=Anchor(ui, (780, 300, 20, 24)), placement="below")
    x, y, w, h = popup.geometry("px")
    assert x + w <= SIZE[0] - Popup.MARGIN_PX + 1e-6         # clamped


def test_popup_at_point_opens_down_and_right(ui):
    popup, _items = menu(ui)
    popup.popup(at=(200, 300))
    x, y, w, h = popup.geometry("px")
    assert (x, y + h) == pytest.approx((200, 300))


def test_click_inside_reaches_item_and_keeps_popup_open(ui):
    popup, items = menu(ui)
    popup.popup(at=(200, 300))
    ui.process_events()
    ui.click(centre(items[1]))
    assert items[1].clicks and popup.isOpen()
    assert ui.scene == []


def test_outside_click_closes_and_does_not_click_underneath(ui):
    square = np.asarray(((0.2, 0.2), (0.8, 0.2), (0.8, 0.8), (0.2, 0.8)))
    beneath = VectorButtonWidget(ui.renderer, ui.interactor,
                                 input_data=[square], color=(0.3, 0.3, 0.3),
                                 bounds=(0.8, 0.9, 0.1, 0.2))
    pressed = []
    beneath.pressed.connect(lambda: pressed.append(1))
    ui.render()
    popup, _items = menu(ui)
    closed = []
    popup.closed.connect(lambda: closed.append(1))
    popup.popup(at=(200, 300))
    ui.click(centre(beneath))
    assert not popup.isOpen() and closed == [1]
    assert pressed == [] and ui.scene == []
    ui.click(centre(beneath))                 # nothing open: normal click
    assert pressed == [1]


def test_escape_closes_the_top_popup(ui):
    popup, _items = menu(ui)
    popup.popup(at=(200, 300))
    ui.key("Escape")
    assert not popup.isOpen()


def test_modal_popup_blocks_outside_input(ui):
    popup, items = menu(ui, modal=True)
    popup.popup(at=(200, 300))
    ui.click((700, 50))
    assert popup.isOpen() and ui.scene == []
    ui.click(centre(items[0]))
    assert items[0].clicks
    popup.dismiss()
    ui.click((700, 50))
    assert ui.scene == [1]


def test_clicking_a_parent_closes_its_sub_popup(ui):
    parent, parent_items = menu(ui)
    child, _child_items = menu(ui)
    parent.popup(at=(100, 400))
    child.popup(anchor=parent_items[0], placement="right")
    layer = OverlayLayer.for_renderer(ui.renderer, ui.interactor)
    assert layer.popups() == (parent, child)
    ui.click(centre(parent_items[2]))
    assert parent.isOpen() and not child.isOpen()
    child.popup(anchor=parent_items[0], placement="right")
    ui.click((790, 10))
    assert not parent.isOpen() and not child.isOpen()


def test_popup_draws_in_front_of_existing_ui(ui):
    square = np.asarray(((0.2, 0.2), (0.8, 0.2), (0.8, 0.8), (0.2, 0.8)))
    VectorButtonWidget(ui.renderer, ui.interactor, input_data=[square],
                       color=(0.3, 0.3, 0.3), bounds=(0.1, 0.2, 0.1, 0.2))
    popup, _items = menu(ui)
    popup.popup(at=(200, 300))
    # Popups draw on the window's popup layer, above every other renderer.
    panel_layer = ui_layer(ui.renderer)
    assert popup.renderer is not panel_layer
    assert popup.renderer.GetLayer() > panel_layer.GetLayer()
    assert popup.renderer.HasViewProp(popup._background.actor)
    renderers = ui.window.GetRenderers()
    assert all(renderers.GetItemAsObject(i).GetLayer() <=
               popup.renderer.GetLayer()
               for i in range(renderers.GetNumberOfItems()))


def test_router_filter_is_removed_when_everything_closes(ui):
    router = EventRouter.install(ui.interactor)
    popup, _items = menu(ui)
    popup.popup(at=(200, 300))
    assert router._filters
    popup.dismiss()
    assert not router._filters
