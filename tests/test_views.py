"""ListView, TreeView, TableView and model-backed combo boxes (W9)."""
import pytest

from multipanel._widget_support import set_ui_scale, ui_scale
from multipanel.animation import animations_enabled, set_animations_enabled
from multipanel.hierarchy import HierarchyNode
from multipanel.models import (
    CHECKED, UNCHECKED, ListModel, TableModel, TreeModel,
)
from multipanel.router import EventRouter
from multipanel.standard import ComboBox
from multipanel.testing import UiHarness
from multipanel.units import px
from multipanel.views import ListView, TableView, TreeView

VIEW = (100, 100, 240, 300)          # x, y, w, h (logical px)


@pytest.fixture
def ui():
    previous, animated = ui_scale(), animations_enabled()
    set_ui_scale(1.0)
    set_animations_enabled(False)
    with UiHarness(size=(800, 600)) as harness:
        EventRouter.install(harness.interactor)
        yield harness
        EventRouter.uninstall(harness.interactor)
    set_ui_scale(previous)
    set_animations_enabled(animated)


def make(ui, cls, model, geometry=VIEW, **options):
    view = cls(ui.renderer, ui.interactor, model=model, **options)
    view.setGeometry(*(px(v) for v in geometry))
    ui.render()
    return view


def row_point(view, row, x_fraction=0.6):
    key = view._key(view._index_at(row))
    x0, x1, y0, y1 = view._row_display_rect(key)
    return (x0 + (x1 - x0) * x_fraction, (y0 + y1) / 2)


def selected(view):
    return sorted(view._display_row(i) for i in view.selectedIndexes())


def shown_texts(view):
    return [cell.actor.GetInput() for slot in view._slots
            for name, cell in slot.items()
            if name[0] == "text" and cell.actor.GetVisibility()]


def big_list(count=10000):
    return ListModel([f"Row {i}" for i in range(count)])


# -- virtualisation --------------------------------------------------------------------------
def test_only_visible_rows_get_actors(ui):
    view = make(ui, ListView, big_list())
    visible = -(-(VIEW[3] - 2) // ListView.ROW_PX)        # ceil
    assert len(view._slots) <= visible + 1
    assert shown_texts(view)[:3] == ["Row 0", "Row 1", "Row 2"]
    assert view.verticalScrollBar().isVisible()


def test_inserting_into_a_10k_model_touches_only_changed_actors(ui):
    model = big_list()
    view = make(ui, ListView, model)
    before = view.actor_updates
    model.insert(5000, "Inserted")          # below the viewport
    ui.render()
    assert view.actor_updates == before
    model.setData(model.index(3), "Changed")
    ui.render()
    assert view.actor_updates == before + 1
    model.append("Last")
    ui.render()
    assert view.actor_updates == before + 1
    assert view.verticalScrollBar().maximum() == pytest.approx(
        10002 * ListView.ROW_PX - (VIEW[3] - 2))


def test_wheel_scrolls_and_rows_follow(ui):
    view = make(ui, ListView, big_list(100))
    ui.wheel(row_point(view, 2), steps=-2)
    ui.render()
    assert view.scrollValue() == pytest.approx(2 * ListView.WHEEL_STEP_PX)
    first = int(view.scrollValue() // ListView.ROW_PX)
    assert shown_texts(view)[0] == f"Row {first}"
    view.scrollTo(view.model().index(99))
    ui.render()
    assert shown_texts(view)[-1] == "Row 99"


# -- selection by mouse and keyboard -----------------------------------------------------------
def test_click_ctrl_click_and_shift_click(ui):
    view = make(ui, ListView, big_list(20))
    clicked = []
    view.clicked.connect(lambda index: clicked.append(index.row()))
    ui.click(row_point(view, 2))
    assert selected(view) == [2] and clicked == [2]
    ui.click(row_point(view, 5), ctrl=True)
    assert selected(view) == [2, 5]
    ui.click(row_point(view, 8), shift=True)
    assert selected(view) == [5, 6, 7, 8]           # range from the anchor
    ui.click(row_point(view, 3), shift=True, ctrl=True)
    assert selected(view) == [3, 4, 5, 6, 7, 8]
    assert view.currentIndex().row() == 3


def test_single_and_multi_modes(ui):
    view = make(ui, ListView, big_list(10), selection_mode="single")
    ui.click(row_point(view, 1))
    ui.click(row_point(view, 4), ctrl=True)
    assert selected(view) == [4]
    view.setSelectionMode("multi")
    ui.click(row_point(view, 1))
    ui.click(row_point(view, 4))
    assert selected(view) == [1]


def test_clicking_empty_space_clears_the_selection(ui):
    view = make(ui, ListView, ListModel(["a", "b"]))
    ui.click(row_point(view, 0))
    ui.click((VIEW[0] + 50, VIEW[1] + 20))          # below the rows
    assert selected(view) == []


def test_keyboard_moves_and_extends(ui):
    view = make(ui, ListView, big_list(50))
    ui.click(row_point(view, 0))
    ui.key("Down")
    ui.key("Down", shift=True)
    ui.key("Down", shift=True)
    assert selected(view) == [1, 2, 3]
    ui.key("End")
    ui.render()
    assert selected(view) == [49] and shown_texts(view)[-1] == "Row 49"
    activated = []
    view.activated.connect(lambda index: activated.append(index.row()))
    ui.key("Return")
    assert activated == [49]
    ui.key("a", ctrl=True)
    assert len(selected(view)) == 50


def test_check_boxes_toggle_the_model(ui):
    model = ListModel([{"display": "Lead", "checkState": UNCHECKED}])
    view = make(ui, ListView, model)
    start, end = view._check_box_span(0, 0, model.index(0))
    x0, _x1, y0, y1 = view._row_display_rect(view._key(model.index(0)))
    ui.click((x0 + (start + end) / 2, (y0 + y1) / 2))
    assert model.index(0).data("checkState") == CHECKED
    assert selected(view) == []            # the box does not select
    ui.click(row_point(view, 0))
    ui.key("space")
    assert model.index(0).data("checkState") == UNCHECKED


def test_hidden_view_does_not_draw_or_take_clicks(ui):
    view = make(ui, ListView, big_list(10))
    point = row_point(view, 1)
    view.SetVisibility(False)
    ui.render()
    assert not view._content.GetDraw()
    assert not shown_texts(view)
    ui.click(point)
    assert selected(view) == []
    view.SetVisibility(True)
    ui.render()
    assert view._content.GetDraw() and shown_texts(view)


# -- trees ------------------------------------------------------------------------------------------
def scene():
    return HierarchyNode("root", children=[
        HierarchyNode("Cells", expanded_by_default=True, children=[
            HierarchyNode(f"Cell {i}") for i in range(4)]),
        HierarchyNode("Materials", children=[
            HierarchyNode("Lead", children=[HierarchyNode("Pb-208")]),
            HierarchyNode("Water")]),
    ])


def test_tree_shows_expanded_branches(ui):
    view = make(ui, TreeView, TreeModel.from_hierarchy(scene()))
    assert shown_texts(view) == ["Cells", "Cell 0", "Cell 1", "Cell 2",
                                 "Cell 3", "Materials"]
    assert view.isHeaderHidden()


def test_tree_expand_and_collapse_keep_the_selection(ui):
    view = make(ui, TreeView, TreeModel.from_hierarchy(scene()))
    ui.click(row_point(view, 2))                       # Cell 1
    ui.click(row_point(view, 4), shift=True)           # Cell 3
    assert [i.data() for i in view.selectedIndexes()] == [
        "Cell 1", "Cell 2", "Cell 3"]
    cells = view._index_at(0)
    ui.click(row_point(view, 0, x_fraction=0.0) and
             (view._row_display_rect(view._key(cells))[0]
              + sum(view._chevron_span(0)) / 2, row_point(view, 0)[1]))
    ui.render()
    assert not view.isExpanded(cells)
    assert shown_texts(view) == ["Cells", "Materials"]
    assert {i.data() for i in view.selectedIndexes()} == {
        "Cell 1", "Cell 2", "Cell 3"}
    assert view.currentIndex().data() == "Cells"       # current moved up
    view.expand(cells)
    ui.render()
    assert selected(view) == [2, 3, 4]


def test_tree_double_click_and_arrow_keys(ui):
    view = make(ui, TreeView, TreeModel.from_hierarchy(scene()))
    ui.double_click(row_point(view, 5))                # Materials
    ui.render()
    assert view.isExpanded(view._index_at(5))
    assert shown_texts(view)[-2:] == ["Lead", "Water"]
    ui.key("Down")                                     # Lead
    ui.key("Right")                                    # expand Lead
    ui.key("Right")                                    # to Pb-208
    assert view.currentIndex().data() == "Pb-208"
    ui.key("Left")                                     # to Lead
    ui.key("Left")                                     # collapse Lead
    assert view.currentIndex().data() == "Lead"
    assert not view.isExpanded(view.currentIndex())


def test_tree_follows_model_inserts(ui):
    model = TreeModel.from_hierarchy(scene())
    view = make(ui, TreeView, model)
    ui.click(row_point(view, 1))                       # Cell 0
    model.insertNode(model.index(0), 0, HierarchyNode("Cell new"))
    ui.render()
    assert shown_texts(view)[1] == "Cell new"
    assert view.currentIndex().data() == "Cell 0"
    assert selected(view) == [2]
    view.scrollTo(model.index(0, 0, model.index(0, 0, model.index(1))))
    assert view.isExpanded(model.index(1))             # revealed


# -- tables ---------------------------------------------------------------------------------------------
def table_model():
    return TableModel([(f"Cell {i}", "Lead", 11.35, "x" * 80)
                       for i in range(30)],
                      headers=("Cell", "Material", "Density", "Comment"))


def test_table_columns_fit_and_long_text_is_elided(ui):
    view = make(ui, TableView, table_model(), geometry=(100, 100, 440, 300))
    rows_w = view._geometry()["rows"][2]
    spans = view._column_spans(rows_w)
    assert spans[-1][1] + spans[-1][2] == pytest.approx(rows_w)
    texts = shown_texts(view)
    assert texts[:3] == ["Cell 0", "Lead", "11.35"]
    assert texts[3].endswith("…") and len(texts[3]) < 80
    assert [c.actor.GetInput() for c in view._header_cells] == [
        "Cell", "Material", "Density", "Comment"]


def test_dragging_a_header_edge_resizes_the_column(ui):
    view = make(ui, TableView, table_model())
    width = view.columnWidth(0)
    hx, hy, _hw, hh = view._geometry()["header"]
    ox, oy = view._geometry()["origin"]
    edge = (hx + ox + width, hy + oy + hh / 2)
    ui.drag(edge, (edge[0] + 30, edge[1]))
    assert view.columnWidth(0) == pytest.approx(width + 30, abs=1)
    assert selected(view) == []


# -- tooltips ---------------------------------------------------------------------------------------------
def test_row_tooltips_show_on_hover(ui):
    from multipanel.controls import get_hover_text_overlay, set_tooltip_delay

    set_tooltip_delay(0)
    try:
        model = ListModel([{"display": "Lead", "toolTip": "ρ = 11.35"},
                           {"display": "Air", "toolTip": "ρ = 0.0012"}])
        view = make(ui, ListView, model)
        overlay = get_hover_text_overlay(ui.renderer, ui.interactor)
        ui.move(row_point(view, 0))
        ui.move(row_point(view, 0))
        assert overlay.text_actor.GetVisibility()
        assert "11.35" in overlay.text_actor.GetInput()
        ui.move(row_point(view, 1))
        ui.move(row_point(view, 1))
        assert "0.0012" in overlay.text_actor.GetInput()
        ui.move((VIEW[0] - 40, VIEW[1] - 40))
        assert not overlay.text_actor.GetVisibility()
    finally:
        set_tooltip_delay(500)


# -- combo box with a model ---------------------------------------------------------------------------------
def test_combo_box_follows_its_model(ui):
    model = ListModel([{"display": "Air", "user": 1},
                       {"display": "Lead", "user": 2}])
    combo = ComboBox(ui.renderer, ui.interactor)
    texts = []
    combo.currentTextChanged.connect(texts.append)
    combo.setModel(model)
    combo.setCurrentIndex(1)
    assert combo.currentText() == "Lead" and combo.currentData() == 2
    model.insert(0, "Water")                 # current item keeps its row
    assert combo.count() == 3 and combo.currentIndex() == 2
    model.setData(model.index(2), "Lead (Pb)")
    assert combo.currentText() == "Lead (Pb)"
    combo.addItem("Steel", 4)                # edits the ListModel
    assert model.rowCount() == 4 and model.index(3).data("user") == 4
    model.removeRow(2)                       # the current row: as in Qt,
    assert combo.currentIndex() == 2         # the next row takes its place
    assert combo.currentText() == "Steel"
    # The insert moved the current row (index 1 -> 2), which re-emits its
    # text, as QComboBox does.
    assert texts == ["Air", "Lead", "Lead", "Lead (Pb)", "Steel"]


# -- legacy ScrollablePanel with a model -----------------------------------------------------------------
def test_scrollable_panel_follows_an_item_model(ui):
    from multipanel.containers import ScrollablePanel

    lead = object()
    panel = ScrollablePanel(ui.interactor, ["old"], title="Materials")
    model = ListModel(["Air", {"display": "Lead", "user": lead}])
    changes = []
    panel.itemsChanged.connect(lambda: changes.append(list(panel.iterable)))
    panel.setModel(model)
    assert panel.iterable == ["Air", lead] and panel.itemModel() is model
    model.append("Water")
    assert panel.iterable == ["Air", lead, "Water"]
    panel.insertItem(0, "Steel")                 # edits the model
    assert model.items() == ["Steel", "Air", "Lead", "Water"]
    assert panel.takeItem(1) == "Air" and model.rowCount() == 3
    panel.setModel(["plain"])                    # detaches the model
    model.append("Ignored")
    assert panel.iterable == ["plain"] and panel.itemModel() is None
    assert len(changes) == 5
