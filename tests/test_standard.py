"""Standard native controls driven through the EventRouter."""
import pytest

from multipanel._widget_support import set_ui_scale, ui_scale, user_scale
from multipanel.actions import Action
from multipanel.containers import Frame
from multipanel.core import WidgetMixin
from multipanel.layouts import VBoxLayout
from multipanel.overlay import OverlayLayer
from multipanel.router import EventRouter
from multipanel.standard import (
    ButtonGroup,
    CheckBox,
    ComboBox,
    Label,
    Menu,
    ProgressBar,
    PushButton,
    RadioButton,
)
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


def place(widget, x=100, y=400, w=160, h=24):
    widget.setGeometry(px(x), px(y), px(w), px(h))
    return widget


def centre(widget, fx=0.5, fy=0.5):
    x, y, w, h = widget.geometry("display")
    return (x + fx * w, y + fy * h)


# -- label and push button -----------------------------------------------------

def test_label_measures_its_text(ui):
    label = Label(ui.renderer, ui.interactor, "Density")
    short = label.sizeHint()[0]
    label.setText("Density (g/cm3)")
    assert label.sizeHint()[0] > short
    place(label)
    assert label.text_actor.GetVisibility()


def test_push_button_clicks_on_release_inside(ui):
    button = place(PushButton(ui.renderer, ui.interactor, "Apply"))
    clicks = []
    button.clicked.connect(lambda: clicks.append(1))
    ui.click(centre(button))
    assert clicks == [1] and ui.scene == []
    ui.press(centre(button))
    ui.release((700, 50))                 # dragged off before release
    assert clicks == [1]
    button.setEnabled(False)
    ui.click(centre(button))
    assert clicks == [1]


def test_push_button_bound_to_action(ui):
    action = Action("Export")
    fired = []
    action.triggered.connect(lambda checked: fired.append(1))
    button = place(PushButton(ui.renderer, ui.interactor, action=action))
    assert button.text() == "Export"
    ui.click(centre(button))
    action.setEnabled(False)
    ui.click(centre(button))
    assert fired == [1] and not button.isEnabled()


# -- check boxes and radio buttons ----------------------------------------------

def test_check_box_toggles_by_mouse_and_keyboard(ui):
    box = place(CheckBox(ui.renderer, ui.interactor, "Wireframe"))
    toggled = []
    box.toggled.connect(toggled.append)
    ui.click(centre(box))
    assert box.isChecked() and toggled == [True]
    box.setFocus(reason="tab")            # keyboard focus: Space activates
    ui.key("space")
    assert not box.isChecked() and toggled == [True, False]


def test_tristate_check_box_cycles(ui):
    box = place(CheckBox(ui.renderer, ui.interactor, "Partial", tristate=True))
    states = []
    box.stateChanged.connect(states.append)
    for _ in range(3):
        ui.click(centre(box))
    assert states == [CheckBox.PARTIAL, CheckBox.CHECKED, CheckBox.UNCHECKED]


def test_radio_buttons_with_one_parent_are_exclusive(ui):
    frame = Frame(ui.renderer, ui.interactor)
    frame.setGeometry(px(100), px(300), px(200), px(80))
    column = VBoxLayout()
    radios = [RadioButton(ui.renderer, ui.interactor, name)
              for name in ("Point", "Sphere", "Box")]
    for radio in radios:
        column.addWidget(radio)
    frame.setLayout(column)
    ui.process_events()
    ui.click(centre(radios[0]))
    ui.click(centre(radios[2]))
    assert [radio.isChecked() for radio in radios] == [False, False, True]
    ui.click(centre(radios[2]))           # clicking the checked one keeps it
    assert radios[2].isChecked()


def test_button_group_ids(ui):
    group = ButtonGroup()
    radios = [place(RadioButton(ui.renderer, ui.interactor, name), y=400 - 30 * i)
              for i, name in enumerate(("A", "B"))]
    group.addButton(radios[0], 10)
    group.addButton(radios[1], 20)
    toggled = []
    group.idToggled.connect(lambda button_id, checked:
                            toggled.append((button_id, checked)))
    ui.click(centre(radios[0]))
    ui.click(centre(radios[1]))
    assert group.checkedId() == 20
    assert toggled == [(10, True), (10, False), (20, True)]


# -- progress bar ------------------------------------------------------------------

def test_progress_bar_value_text_and_busy_mode(ui):
    bar = place(ProgressBar(ui.renderer, ui.interactor))
    bar.setValue(42)
    assert bar.text() == "42%"
    bar.setFormat("%v of %m")
    assert bar.text() == "42 of 100"
    bar.setRange(0, 0)
    assert bar.isBusy() and bar.text() == ""
    phase = bar._busy_phase
    ui.process_events(200)
    assert bar._busy_phase != phase
    bar.setRange(0, 10)
    assert not bar.isBusy() and bar._busy_animation is None


# -- menus ----------------------------------------------------------------------------

def make_menu(ui):
    menu = Menu(ui.renderer, ui.interactor)
    fired = []
    copy = menu.addAction("Copy", lambda: fired.append("copy"))
    copy_shortcut = Action("Paste", interactor=ui.interactor, shortcut="Ctrl+V")
    copy_shortcut.triggered.connect(lambda checked: fired.append("paste"))
    menu.addAction(copy_shortcut)
    menu.addSeparator()
    disabled = menu.addAction("Disabled", lambda: fired.append("disabled"))
    disabled.setEnabled(False)
    more = menu.addMenu("More")
    more.addAction("Deep", lambda: fired.append("deep"))
    return menu, fired, copy, more


def test_menu_click_triggers_and_closes(ui):
    menu, fired, _copy, _more = make_menu(ui)
    triggered = []
    menu.triggered.connect(lambda action: triggered.append(action.text()))
    menu.popup(at=(200, 400))
    ui.process_events()
    items = menu.items()
    ui.move(centre(items[0]))
    assert menu.activeItem() is items[0]
    ui.click(centre(items[0]))
    assert fired == ["copy"] and triggered == ["Copy"]
    assert not menu.isOpen() and ui.scene == []


def test_menu_skips_separators_and_disabled_items(ui):
    menu, fired, _copy, _more = make_menu(ui)
    menu.popup(at=(200, 400))
    ui.click(centre(menu.items()[3]))      # disabled
    assert fired == [] and menu.isOpen()
    for _ in range(3):
        ui.key("Down")
    assert menu.activeItem() is menu.items()[4]   # past separator/disabled
    ui.key("Up")
    assert menu.activeItem() is menu.items()[1]
    ui.key("Return")
    assert fired == ["paste"] and not menu.isOpen()


def test_submenu_opens_on_hover_and_its_items_close_everything(ui):
    menu, fired, _copy, more = make_menu(ui)
    menu.popup(at=(200, 400))
    ui.move(centre(menu.items()[4]))
    assert more.isOpen()
    ui.click(centre(more.items()[0]))
    assert fired == ["deep"]
    assert not more.isOpen() and not menu.isOpen()
    assert OverlayLayer.for_renderer(ui.renderer, ui.interactor).popups() == ()


def test_checkable_menu_action_shows_a_mark(ui):
    menu = Menu(ui.renderer, ui.interactor)
    grid = Action("Show grid", checkable=True)
    menu.addAction(grid)
    menu.popup(at=(200, 400))
    ui.click(centre(menu.items()[0]))
    assert grid.isChecked()
    menu.popup(at=(200, 400))
    assert menu.items()[0].overlay_actor.GetVisibility()


# -- combo box ------------------------------------------------------------------------

def test_combo_box_selects_from_its_list(ui):
    combo = place(ComboBox(ui.renderer, ui.interactor))
    combo.addItems(["Air", "Lead", "Water"])
    combo.addItem("Steel", data="Fe")
    changed = []
    combo.currentTextChanged.connect(changed.append)
    assert combo.currentText() == "Air"
    ui.click(centre(combo))
    assert combo.isPopupVisible()
    ui.process_events()
    ui.click(centre(combo._menu.items()[3]))
    assert combo.currentText() == "Steel" and combo.currentData() == "Fe"
    assert changed == ["Steel"] and not combo.isPopupVisible()
    ui.process_events()                    # deferred release of the list


def test_combo_box_keyboard_and_lookup(ui):
    combo = place(ComboBox(ui.renderer, ui.interactor))
    combo.addItems(["Air", "Lead", "Water"])
    combo.setFocus(reason="tab")
    ui.key("Down")
    ui.key("Down")
    ui.key("Down")
    assert combo.currentText() == "Water"
    assert combo.findText("Lead") == 1
    combo.removeItem(2)
    assert combo.currentText() == "Lead"


# -- context menus ------------------------------------------------------------------

class Area(WidgetMixin):
    """A plain (legacy-style) widget with a context menu policy."""

    def __init__(self, ui):
        self.renderer = ui.renderer
        self.interactor = ui.interactor
        self.initWidget("area")
        self.setGeometry(px(300), px(200), px(200), px(150))
        self.registerWithRouter(ui.interactor)


def test_custom_context_menu_request(ui):
    area = Area(ui)
    requests = []
    area.setContextMenuPolicy("custom")
    area.customContextMenuRequested.connect(requests.append)
    ui.click(centre(area), button="right")
    assert requests == [(100.0, 75.0)]
    ui.drag((350, 250), (450, 250), button="right")   # a drag is not a click
    assert len(requests) == 1


def test_actions_context_menu_pops_up_at_the_pointer(ui):
    area = Area(ui)
    fired = []
    area.setContextMenuPolicy("actions")
    area.addAction(Action("Rename")).triggered.connect(
        lambda checked: fired.append("rename"))
    ui.click(centre(area), button="right")
    layer = OverlayLayer.for_renderer(ui.renderer, ui.interactor)
    (menu,) = layer.popups()
    x, y, _w, h = menu.geometry("px")
    assert (x, y + h) == pytest.approx(centre(area))
    ui.click(centre(menu.items()[0]))
    assert fired == ["rename"] and layer.popups() == ()


def test_check_mark_draws_every_segment(ui):
    """Line glyphs need point colours: VTK 9.5's 2D mapper draws only the
    first segment of line cells coloured per cell."""
    import vtk
    from vtk.util.numpy_support import vtk_to_numpy

    box = CheckBox(ui.renderer, ui.interactor, "", checked=True)
    place(box, x=40, y=40, w=60, h=60)
    box.BOX_PX = 60
    box.refresh()
    ui.render()
    grab = vtk.vtkWindowToImageFilter()
    grab.SetInput(ui.window)
    grab.ReadFrontBufferOff()
    grab.Update()
    image = vtk_to_numpy(grab.GetOutput().GetPointData().GetScalars())
    image = image.reshape(SIZE[1], SIZE[0], -1)[40:100, 40:100]
    mark = (image[..., 0] > 230) & (image[..., 1] > 230) & (image[..., 2] > 230)
    columns = mark.any(axis=0).nonzero()[0]
    assert columns.max() - columns.min() > 30      # both strokes drawn


# -- message box, status bar, menu bar --------------------------------------------

from multipanel.standard import MenuBar, MessageBox, StatusBar  # noqa: E402


def test_message_box_is_modal_centred_and_dimmed(ui):
    box = MessageBox.question(ui.renderer, ui.interactor, "Delete actors?",
                              "Delete the 3 selected actors?")
    results = []
    box.finished.connect(results.append)
    ui.process_events()
    x, y, w, h = box.geometry("px")
    assert x + w / 2 == pytest.approx(SIZE[0] / 2, abs=1)
    assert y + h / 2 == pytest.approx(SIZE[1] / 2, abs=1)
    assert box._scrim_actor.GetVisibility()
    ui.click((20, 20))                       # outside: blocked, stays open
    assert box.isOpen() and ui.scene == []
    ui.click(centre(box.button("No")))
    assert results == ["No"] and not box.isOpen()
    assert not box._scrim_actor.GetVisibility()


def test_message_box_keyboard(ui):
    box = MessageBox.question(ui.renderer, ui.interactor, "Save?", "Save now?")
    results = []
    box.finished.connect(results.append)
    ui.key("Return")
    assert results == ["Yes"]
    box.show_box()
    ui.key("Escape")
    assert results == ["Yes", "No"]


def test_status_bar_messages_and_hover_tips(ui):
    bar = place(StatusBar(ui.renderer, ui.interactor), x=0, y=0, w=800, h=22)
    button = place(PushButton(ui.renderer, ui.interactor, "Apply"), y=300)
    button.setStatusTip("Apply the changes to the selection")
    bar.showMessage("Saved", timeout_ms=2000)
    assert bar.currentMessage() == "Saved"
    ui.move(centre(button))
    assert bar.currentMessage() == "Apply the changes to the selection"
    ui.move((700, 500))
    assert bar.currentMessage() == "Saved"
    ui.process_events(2000)
    assert bar.currentMessage() == ""


def test_menu_bar_open_switch_and_close(ui):
    bar = MenuBar(ui.renderer, ui.interactor)
    bar.setGeometry(px(0), px(570), px(800), px(28))
    fired = []
    file_menu = bar.addMenu("File")
    file_menu.addAction("Save", lambda: fired.append("save"))
    edit_menu = bar.addMenu("Edit")
    edit_menu.addAction("Undo", lambda: fired.append("undo"))
    ui.process_events()
    file_title, edit_title = bar._titles
    ui.click(centre(file_title))
    assert file_menu.isOpen()
    ui.move(centre(edit_title))              # hover switches while open
    assert edit_menu.isOpen() and not file_menu.isOpen()
    ui.click(centre(edit_title))             # its own title closes it
    assert bar.openMenu() is None
    ui.process_events()
    ui.click(centre(file_title))
    ui.click(centre(file_menu.items()[0]))
    assert fired == ["save"] and bar.openMenu() is None
