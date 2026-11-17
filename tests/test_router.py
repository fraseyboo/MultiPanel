import pytest
import vtk

from multipanel.controls import TextWidget
from multipanel.core import WidgetMixin
from multipanel.router import EventRouter
from multipanel.testing import UiHarness

SCENE_EVENTS = (
    "LeftButtonPressEvent", "LeftButtonReleaseEvent", "MouseMoveEvent",
    "RightButtonPressEvent", "RightButtonReleaseEvent",
    "MouseWheelForwardEvent", "MouseWheelBackwardEvent",
    "KeyPressEvent", "CharEvent",
)


@pytest.fixture
def ui():
    with UiHarness(size=(640, 480)) as harness:
        harness.router = EventRouter.install(harness.interactor)
        harness.scene = []
        for name in SCENE_EVENTS:
            # Priority 10: below the router, above the interactor style.
            harness.interactor.AddObserver(
                name, lambda _c, event: harness.scene.append(event), 10.0)
        yield harness
        EventRouter.uninstall(harness.interactor)


class Box(WidgetMixin):
    """Native test widget that records events and accepts selected ones."""

    def __init__(self, ui, geometry, name, parent=None, accept=(), z=0):
        self.renderer = ui.renderer
        self.interactor = ui.interactor
        self.ui_z_order = z
        self.accepting = set(accept)
        self.log = []
        self.initWidget(name, parent)
        self.setGeometry(*geometry)
        if parent is None:
            self.registerWithRouter()

    def _record(self, kind, event):
        self.log.append((kind, event.pos()))
        if kind in self.accepting:
            event.accept()

    def mousePressEvent(self, event):
        self._record("press", event)

    def mouseReleaseEvent(self, event):
        self._record("release", event)

    def mouseMoveEvent(self, event):
        self._record("move", event)

    def mouseDoubleClickEvent(self, event):
        self._record("double", event)

    def wheelEvent(self, event):
        self.log.append(("wheel", event.delta()))
        if "wheel" in self.accepting:
            event.accept()

    def keyPressEvent(self, event):
        self.log.append(("key", event.key(), event.text()))
        if "key" in self.accepting:
            event.accept()

    def contextMenuEvent(self, event):
        self._record("context", event)

    def enterEvent(self, event):
        self.log.append(("enter",))

    def leaveEvent(self, event):
        self.log.append(("leave",))

    def kinds(self):
        return [entry[0] for entry in self.log]


CENTRE_BOX = (0.25, 0.25, 0.5, 0.5)       # display px 160..480 x 120..360


def test_accepted_press_and_release_are_hidden_from_scene(ui):
    box = Box(ui, CENTRE_BOX, "box", accept={"press", "release"})
    ui.click(box)
    assert box.kinds()[-2:] == ["press", "release"]
    assert "LeftButtonPressEvent" not in ui.scene
    assert "LeftButtonReleaseEvent" not in ui.scene

    ui.scene.clear()
    ui.click((10, 10))
    assert "LeftButtonPressEvent" in ui.scene


def test_ignored_press_reaches_scene(ui):
    box = Box(ui, CENTRE_BOX, "box")
    ui.click(box)
    assert "press" in box.kinds()
    assert "LeftButtonPressEvent" in ui.scene


def test_topmost_z_order_receives_click(ui):
    low = Box(ui, CENTRE_BOX, "low", accept={"press"}, z=10)
    high = Box(ui, CENTRE_BOX, "high", accept={"press"}, z=20)
    later = Box(ui, CENTRE_BOX, "later", accept={"press"}, z=10)
    ui.click((320, 240))
    assert "press" in high.kinds()
    assert "press" not in low.kinds()
    assert "press" not in later.kinds()
    assert ui.router.widgetAt(320, 240) is high


def test_press_bubbles_from_child_to_parent_with_local_positions(ui):
    parent = Box(ui, CENTRE_BOX, "parent", accept={"press"})
    child = Box(ui, (0.25, 0.25, 0.1, 0.1), "child", parent=parent)
    ui.click((170, 130))
    assert ("press", (10.0, 10.0)) in child.log
    assert ("press", (10.0, 10.0)) in parent.log   # parent origin is (160, 120)
    assert "LeftButtonPressEvent" not in ui.scene
    assert ui.router.hitChain(170, 130) == [child, parent]


def test_implicit_grab_follows_drag_outside_widget(ui):
    box = Box(ui, CENTRE_BOX, "box", accept={"press", "move", "release"})
    ui.drag((200, 200), (600, 460), steps=4)
    moves = [entry[1] for entry in box.log if entry[0] == "move"]
    assert moves[-1] == (440.0, 340.0)        # local to the box, outside it
    # Leave is deferred until the grab ends, as in Qt.
    assert box.kinds()[-2:] == ["release", "leave"]
    # Only the hover move before the press reaches the scene; drag moves
    # are owned by the grabbing widget.
    assert ui.scene.count("MouseMoveEvent") == 1
    assert "LeftButtonReleaseEvent" not in ui.scene
    assert ui.router.mouseGrabber() is None


def test_hover_enter_and_leave_are_sent_once(ui):
    box = Box(ui, CENTRE_BOX, "box")
    ui.move((10, 10))
    ui.move((200, 200))
    ui.move((210, 210))
    assert box.underMouse()
    ui.move((10, 10))
    assert box.kinds().count("enter") == 1
    assert box.kinds().count("leave") == 1
    assert not box.underMouse()


def test_hover_moves_are_never_consumed(ui):
    Box(ui, CENTRE_BOX, "box", accept={"move"})
    ui.move((200, 200))
    assert "MouseMoveEvent" in ui.scene


def test_cursor_shape_applies_while_hovering(ui):
    box = Box(ui, CENTRE_BOX, "box")
    box.setCursor(vtk.VTK_CURSOR_HAND)
    shapes = []
    original = ui.window.SetCurrentCursor
    ui.window.SetCurrentCursor = lambda shape: (shapes.append(shape),
                                                original(shape))
    ui.move((200, 200))
    ui.move((10, 10))
    assert shapes == [vtk.VTK_CURSOR_HAND, vtk.VTK_CURSOR_DEFAULT]


def test_double_click_within_interval(ui):
    box = Box(ui, CENTRE_BOX, "box", accept={"press", "double", "release"})
    ui.click(box)
    ui.process_events(100)
    ui.click(box)
    assert box.kinds().count("double") == 1

    box.log.clear()
    ui.process_events(1000)
    ui.click(box)
    ui.process_events(500)
    ui.click(box)
    assert box.kinds().count("double") == 0
    assert box.kinds().count("press") == 2


def test_unhandled_double_click_is_a_second_press(ui):
    class PressOnly(Box):
        mouseDoubleClickEvent = WidgetMixin.mouseDoubleClickEvent

    box = PressOnly(ui, CENTRE_BOX, "box", accept={"press"})
    ui.double_click(box)
    assert box.kinds().count("press") == 2


def test_context_menu_on_right_click_but_not_right_drag(ui):
    box = Box(ui, CENTRE_BOX, "box", accept={"context"})
    ui.click(box, button="right")
    assert box.kinds().count("context") == 1
    ui.drag((200, 200), (300, 300), button="right")
    assert box.kinds().count("context") == 1


def test_native_wheel_is_consumed(ui):
    box = Box(ui, CENTRE_BOX, "box", accept={"wheel"})
    ui.wheel(box, steps=2)
    ui.wheel(box, steps=-1)
    assert [e for e in box.log if e[0] == "wheel"] == [
        ("wheel", 1), ("wheel", 1), ("wheel", -1)]
    assert not any("Wheel" in event for event in ui.scene)


class LegacyPanel(WidgetMixin):
    """Mimics a legacy container: normalized bounds plus wheel handler."""

    def __init__(self, bounds, handles=True, nested=False):
        self.bounds = bounds
        self.handles = handles
        self.wheel_calls = []
        if nested:
            self.panels = []
        self.initWidget("legacy")

    def is_within_bounds(self, x, y):
        x0, x1, y0, y1 = self.bounds
        return x0 <= x <= x1 and y0 <= y <= y1

    def handle_mouse_wheel(self, x, y, direction):
        self.wheel_calls.append(direction)
        return self.handles


def test_legacy_wheel_routing_and_ui_panels_discovery(ui):
    plain = LegacyPanel((0.0, 0.5, 0.0, 1.0))
    dock = LegacyPanel((0.0, 0.5, 0.0, 1.0), nested=True)
    ui.renderer.UI_panels = {"plain": plain, "dock": dock}

    ui.wheel((100, 100), steps=1)
    assert dock.wheel_calls == [1]          # containers with panels first
    assert plain.wheel_calls == []
    assert "MouseWheelForwardEvent" not in ui.scene

    dock.handles = False
    ui.wheel((100, 100), steps=-1)
    assert plain.wheel_calls == [-1]

    plain.handles = False
    ui.wheel((100, 100), steps=1)
    assert "MouseWheelForwardEvent" in ui.scene

    ui.scene.clear()
    ui.wheel((600, 100), steps=1)           # outside every panel
    assert "MouseWheelForwardEvent" in ui.scene


def test_legacy_widgets_are_not_sent_pointer_events(ui):
    plain = LegacyPanel((0.0, 0.5, 0.0, 1.0))
    ui.renderer.UI_panels = {"plain": plain}
    ui.click((100, 100))
    assert ui.router.isOverUi(100, 100)
    assert not ui.router.isOverUi(600, 100)
    # Legacy widgets keep their own observers; the scene still sees the press
    # and the host asks isOverUi() to ignore it.
    assert "LeftButtonPressEvent" in ui.scene


def test_text_input_guard_blocks_scene_hotkeys(ui):
    cube = vtk.vtkActor()
    mapper = vtk.vtkPolyDataMapper()
    source = vtk.vtkCubeSource()       # keep a reference: VTK may free a
    mapper.SetInputConnection(source.GetOutputPort())   # temporary source
    cube.SetMapper(mapper)
    ui.renderer.AddActor(cube)
    field = TextWidget(ui.renderer, ui.interactor, text="", editable=True)
    ui.move((320, 240))

    assert field.start_editing()
    ui.key_clicks("w3s")
    assert field.text == "w3s"
    assert "CharEvent" not in ui.scene
    assert "KeyPressEvent" not in ui.scene
    assert cube.GetProperty().GetRepresentation() == vtk.VTK_SURFACE
    assert ui.router.isTextInputActive()

    field.finish_editing(commit=True)
    assert not ui.router.isTextInputActive()
    ui.key("w")
    assert "CharEvent" in ui.scene
    assert cube.GetProperty().GetRepresentation() == vtk.VTK_WIREFRAME


def test_host_text_edit_flag_is_respected(ui):
    ui.interactor.text_edit_mode = True
    try:
        assert ui.router.isTextInputActive()
        ui.key("c", ctrl=True)
        assert "KeyPressEvent" not in ui.scene
    finally:
        ui.interactor.text_edit_mode = False


def test_native_key_delivery_to_focused_widget_and_parent(ui):
    parent = Box(ui, CENTRE_BOX, "parent", accept={"key"})
    child = Box(ui, (0.3, 0.3, 0.1, 0.1), "child", parent=parent)
    child.registerFocus(ui.interactor)
    child.setFocus()
    ui.key("x")
    assert ("key", "x", "x") in child.log
    assert ("key", "x", "x") in parent.log
    assert "KeyPressEvent" not in ui.scene
    assert "CharEvent" in ui.scene     # only text widgets suppress Char


def test_click_focus_for_focusable_native_widgets(ui):
    box = Box(ui, CENTRE_BOX, "box", accept={"press"})
    box.setFocusPolicy("StrongFocus")
    ui.click(box)
    assert box.hasFocus()


def test_router_and_widget_event_filters(ui):
    box = Box(ui, CENTRE_BOX, "box", accept={"press"})
    seen = []
    ui.router.installEventFilter(
        lambda target, event: seen.append((target, event.type())) or
        event.type() == "Wheel")
    ui.wheel(box, steps=1)
    assert (box, "Wheel") in seen
    assert ("wheel", 1) not in box.log
    assert "MouseWheelForwardEvent" not in ui.scene

    class Blocker:
        def eventFilter(self, target, event):
            return event.type() == "MouseButtonPress"

    box.installEventFilter(Blocker())
    ui.click(box)
    assert "press" not in box.kinds()
    assert "LeftButtonPressEvent" not in ui.scene


def test_disabled_native_widget_swallows_input(ui):
    box = Box(ui, CENTRE_BOX, "box", accept={"press"})
    box.setEnabled(False)
    ui.click(box)
    assert "press" not in box.kinds()
    assert "LeftButtonPressEvent" not in ui.scene


def test_hidden_and_closed_widgets_are_not_hit(ui):
    box = Box(ui, CENTRE_BOX, "box", accept={"press"})
    box.hide()
    assert ui.router.widgetAt(320, 240) is None
    box.show()
    assert ui.router.widgetAt(320, 240) is box
    box.close()
    assert ui.router.widgetAt(320, 240) is None


def test_uninstall_removes_all_observers(ui):
    box = Box(ui, CENTRE_BOX, "box", accept={"press"})
    EventRouter.uninstall(ui.interactor)
    ui.click(box)
    assert "press" not in box.kinds()
    assert "LeftButtonPressEvent" in ui.scene
