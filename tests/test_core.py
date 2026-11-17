import json

from multipanel.core import (
    FocusManager,
    ObserverRegistry,
    RenderScheduler,
    Signal,
    WidgetMixin,
    refresh_renderer_theme,
)


class FakeSubject:
    def __init__(self):
        self.next_tag = 1
        self.observers = {}

    def AddObserver(self, event, callback, priority=None):
        tag = self.next_tag
        self.next_tag += 1
        self.observers[tag] = (event, callback, priority)
        return tag

    def RemoveObserver(self, tag):
        self.observers.pop(tag, None)


class FakeInteractor(FakeSubject):
    def __init__(self):
        super().__init__()
        self.key = ""

    def GetKeySym(self):
        return self.key

    def GetShiftKey(self):
        return False

    def GetCommand(self, _tag):
        return None


class FakeWindow:
    def __init__(self):
        self.renders = 0

    def Render(self):
        self.renders += 1


class FakeWidget(WidgetMixin):
    def __init__(self):
        self.enabled = True
        self.visible = True
        self.bounds = (0.0, 1.0, 0.0, 1.0)
        self.deleted = 0
        self.theme_refreshes = 0
        self.initWidget()

    def GetEnabled(self):
        return self.enabled

    def SetEnabled(self, enabled):
        self.enabled = bool(enabled)

    def GetVisibility(self):
        return self.visible

    def SetVisibility(self, visible):
        self.visible = bool(visible)

    def GetBounds(self):
        return self.bounds

    def SetBounds(self, x0, x1, y0, y1):
        self.bounds = (x0, x1, y0, y1)

    def Delete(self):
        self.deleted += 1

    def _applyTheme(self):
        self.theme_refreshes += 1


def test_signal_connection_disconnection_and_blocking():
    widget = FakeWidget()
    values = []
    widget.enabledChanged.connect(values.append)

    widget.setEnabled(False)
    with widget.signalBlocker():
        widget.setEnabled(True)

    assert values == [False]
    assert widget.isEnabled()


def test_common_geometry_visibility_and_parent_contract():
    parent = FakeWidget()
    child = FakeWidget()
    child.setParent(parent)
    child.setGeometry(2, 3, 4, 5)
    child.hide()

    assert child.parentWidget() is parent
    assert parent.children() == (child,)
    assert child.geometry() == (2, 3, 4, 5)
    assert not child.isVisible()


def test_close_is_idempotent_and_closes_children():
    parent = FakeWidget()
    child = FakeWidget()
    child.setParent(parent)

    assert parent.close()
    assert not parent.close()
    assert parent.deleted == 1
    assert child.deleted == 1


def test_observer_registry_removes_owned_tags():
    subject = FakeSubject()
    registry = ObserverRegistry()
    registry.add(subject, "ModifiedEvent", lambda *_: None)
    registry.add(subject, "RenderEvent", lambda *_: None, priority=2.0)

    assert len(subject.observers) == 2
    registry.clear()
    assert not subject.observers


def test_render_scheduler_batches_nested_requests():
    window = FakeWindow()
    scheduler = RenderScheduler(window)

    with scheduler.batch():
        scheduler.request()
        scheduler.request()

    assert window.renders == 1


def test_signal_can_disconnect_individual_slot():
    signal = Signal()
    values = []
    slot = signal.connect(values.append)
    signal.emit(1)
    signal.disconnect(slot)
    signal.emit(2)

    assert values == [1]


def test_focus_manager_traversal_activation_and_mouse_capture():
    interactor = FakeInteractor()
    first = FakeWidget()
    second = FakeWidget()
    first.registerFocus(interactor)
    second.registerFocus(interactor)
    manager = FocusManager.for_interactor(interactor)
    changes = []
    manager.focusChanged.connect(
        lambda current, previous: changes.append((current, previous)))

    first.setFocus(reason="test")
    assert first.hasFocus()
    assert manager.focusNext() is second
    assert second.hasFocus()
    assert second.grabMouse()
    assert second.hasMouseCapture()
    assert second.releaseMouse()
    assert changes == [(first, None), (second, first)]

    manager.close()


def test_space_is_left_for_an_active_text_editor():
    interactor = FakeInteractor()
    widget = FakeWidget()
    widget.editing = True
    widget.clicks = 0
    widget.click = lambda: setattr(widget, "clicks", widget.clicks + 1)
    widget.registerFocus(interactor)
    widget.setFocus()
    interactor.key = "space"

    widget.focusManager()._on_key_press(interactor, "KeyPressEvent")

    assert widget.editing
    assert widget.clicks == 0
    widget.focusManager().close()


def test_common_state_is_json_compatible_and_restorable():
    widget = FakeWidget()
    widget.setObjectName("example")
    widget.setToolTip("Details")
    widget.setGeometry(2, 3, 4, 5)
    widget.setEnabled(False)
    state = widget.saveState()

    json.dumps(state)
    restored = FakeWidget()
    assert restored.restoreState(state)
    assert restored.objectName() == "example"
    assert restored.toolTip() == "Details"
    assert restored.geometry() == (2.0, 3.0, 4.0, 5.0)
    assert not restored.isEnabled()


def test_renderer_theme_refresh_visits_each_registered_widget_once():
    widget = FakeWidget()
    child = FakeWidget()
    child.setParent(widget)
    renderer = type("Renderer", (), {})()
    renderer.widgets = {
        "primary": widget, "alias": widget, "registered-child": child}

    refresh_renderer_theme(renderer)

    assert widget.theme_refreshes == 1
    assert child.theme_refreshes == 1
