"""Item models and the selection model (W9); no rendering involved."""
import pytest

from multipanel.hierarchy import HierarchyNode
from multipanel.models import (
    CHECKED, ItemModel, ListModel, ModelIndex, SelectionModel, TableModel,
    TreeModel,
)


class Recorder:
    def __init__(self, model):
        self.events = []
        model.dataChanged.connect(
            lambda a, b, roles: self.events.append(("data", a.row(), roles)))
        model.rowsInserted.connect(
            lambda p, f, l: self.events.append(("inserted", p.isValid(), f, l)))
        model.rowsAboutToBeRemoved.connect(
            lambda p, f, l: self.events.append(("removing", f, l)))
        model.rowsRemoved.connect(
            lambda p, f, l: self.events.append(("removed", f, l)))
        model.modelReset.connect(lambda: self.events.append(("reset",)))


def scene():
    return HierarchyNode("root", children=[
        HierarchyNode("Cells", children=[HierarchyNode("Cell 1", value=1),
                                         HierarchyNode("Cell 2", value=2)]),
        HierarchyNode("Materials", children=[HierarchyNode("Lead")]),
    ])


# -- ListModel -------------------------------------------------------------------------------
def test_list_model_roles_from_strings_dicts_and_objects():
    lead = object()
    model = ListModel(["Air", {"display": "Lead", "user": lead,
                               "toolTip": "dense"}, 7.5])
    assert model.rowCount() == 3 and model.columnCount() == 1
    assert model.index(0).data() == "Air"
    assert model.index(1).data("user") is lead
    assert model.index(1).data("toolTip") == "dense"
    assert model.index(2).data() == "7.5" and model.index(2).data("user") == 7.5
    assert not model.index(3).isValid()
    assert model.index(0).parent() == ModelIndex()


def test_list_model_signals_and_set_data():
    model = ListModel(["a", "b"])
    record = Recorder(model)
    model.append("c")
    model.insert(0, "z")
    model.removeRows(1, 2)
    assert model.setData(model.index(0), "Z")
    model.setItems(["x"])
    assert record.events == [
        ("inserted", False, 2, 2), ("inserted", False, 0, 0),
        ("removing", 1, 2), ("removed", 1, 2),
        ("data", 0, ("display",)), ("reset",)]
    assert model.items() == ["x"]


def test_check_state_makes_items_checkable():
    model = ListModel([{"display": "a", "checkState": CHECKED}, "b"])
    assert "checkable" in model.index(0).flags()
    assert "checkable" not in model.index(1).flags()
    model.setFlags(model.index(1), {"enabled"})
    assert model.index(1).flags() == frozenset({"enabled"})


def test_list_keys_survive_inserts_and_vanish_on_removal():
    model = ListModel(["a", "b", "c"])
    key = model.persistentKey(model.index(1))
    model.insert(0, "new")
    assert model.indexForKey(key).row() == 2
    model.removeRow(2)
    assert not model.indexForKey(key).isValid()


def test_table_model_columns_and_headers():
    model = TableModel([("Cell 1", "Lead", 11.35), ("Cell 2",)],
                       headers=("Cell", "Material", "Density"))
    assert model.columnCount() == 3
    assert model.headerData(1) == "Material"
    assert model.index(0, 2).data() == "11.35"
    assert model.index(1, 1).data() == ""
    assert model.index(0, 1).sibling(1, 0).data() == "Cell 2"


# -- TreeModel ----------------------------------------------------------------------------------
def test_tree_model_from_hierarchy():
    model = TreeModel.from_hierarchy(scene())
    assert model.rowCount() == 2
    cells = model.index(0)
    assert cells.data() == "Cells" and model.rowCount(cells) == 2
    cell2 = model.index(1, 0, cells)
    assert cell2.data() == "Cell 2" and cell2.data("user") == 2
    assert cell2.parent() == cells
    assert not cells.parent().isValid()
    assert [i.data() for i in model.walk()] == [
        "Cells", "Cell 1", "Cell 2", "Materials", "Lead"]


def test_tree_model_edits_signal_and_keep_keys():
    model = TreeModel.from_hierarchy(scene())
    record = Recorder(model)
    cells = model.index(0)
    lead_key = model.persistentKey(model.index(0, 0, model.index(1)))
    hash(lead_key)                       # nodes themselves are unhashable
    model.insertNode(None, 0, HierarchyNode("Surfaces"))
    added = model.appendNode(model.index(1), HierarchyNode("Cell 3"))
    assert added.data() == "Cell 3" and added.parent().data() == "Cells"
    assert model.indexForKey(lead_key).parent().data() == "Materials"
    model.setData(added, "Cell three")
    assert model.removeNode(model.node(model.index(2)))   # Materials
    assert not model.indexForKey(lead_key).isValid()
    assert record.events == [
        ("inserted", False, 0, 0), ("inserted", True, 2, 2),
        ("data", 2, ("display",)), ("removing", 2, 2), ("removed", 2, 2)]
    assert cells.data() == "Cells"


def test_tree_model_extra_columns():
    model = TreeModel.from_hierarchy(
        scene(), columns=[("Name", None), ("Value", lambda n: n.value)])
    cell1 = model.index(0, 1, model.index(0))
    assert model.columnCount() == 2 and model.headerData(1) == "Value"
    assert cell1.data() == "1"


# -- SelectionModel -------------------------------------------------------------------------------
def test_single_mode_keeps_one_row():
    model = ListModel(list("abc"))
    selection = SelectionModel(model, "single")
    selection.select([model.index(0), model.index(2)], "select")
    assert [i.row() for i in selection.selectedRows()] == [2]


def test_toggle_select_deselect_and_signals():
    model = ListModel(list("abcd"))
    selection = SelectionModel(model)
    changes = []
    selection.selectionChanged.connect(
        lambda added, removed: changes.append(
            ([i.row() for i in added], [i.row() for i in removed])))
    selection.select([model.index(0), model.index(1)])
    selection.select(model.index(1), "toggle")
    selection.select(model.index(3), "select")
    selection.select(model.index(0), "deselect")
    assert [i.row() for i in selection.selectedRows()] == [3]
    assert changes == [([0, 1], []), ([], [1]), ([3], []), ([], [0])]


def test_selection_follows_rows_through_inserts_and_removals():
    model = ListModel(list("abcd"))
    selection = SelectionModel(model)
    selection.select([model.index(1), model.index(3)])
    selection.setCurrentIndex(model.index(3))
    model.insert(0, "new")
    assert sorted(i.row() for i in selection.selectedRows()) == [2, 4]
    model.removeRow(4)                      # "d", the current row
    assert [i.data() for i in selection.selectedRows()] == ["b"]
    assert not selection.currentIndex().isValid()
    model.setItems(["x"])
    assert not selection.hasSelection()


def test_unselectable_rows_are_skipped():
    model = ListModel(list("ab"))
    model.setFlags(model.index(0), {"enabled"})
    selection = SelectionModel(model)
    selection.select([model.index(0), model.index(1)])
    assert [i.row() for i in selection.selectedRows()] == [1]


class Squares(ItemModel):
    """A custom model without stable keys."""

    def __init__(self, count):
        super().__init__()
        self.count = count

    def rowCount(self, parent=None):
        return 0 if parent is not None and parent.isValid() else self.count

    def data(self, index, role="display"):
        return str(index.row() ** 2) if role == "display" else None

    def grow(self):
        self.beginInsertRows(None, self.count, self.count)
        self.count += 1
        self.endInsertRows()


def test_custom_models_without_stable_keys_drop_the_selection_on_change():
    model = Squares(3)
    selection = SelectionModel(model)
    selection.select(model.index(2))
    assert selection.selectedRows()[0].data() == "4"
    model.grow()
    assert not selection.hasSelection()


def test_bad_mode_and_command_raise():
    model = ListModel(["a"])
    with pytest.raises(ValueError):
        SelectionModel(model, "sideways")
    with pytest.raises(ValueError):
        SelectionModel(model).select(model.index(0), "maybe")
