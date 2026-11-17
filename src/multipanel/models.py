"""Item models and selection (``docs/QT_PARITY_PROPOSAL.md`` §13, W9).

One data model shared by :class:`~multipanel.views.ListView`,
:class:`~multipanel.views.TreeView`, :class:`~multipanel.views.TableView`
and :class:`~multipanel.standard.ComboBox`, after ``QAbstractItemModel``::

    materials = ListModel(["Air", "Lead", "Water"])
    materials.append({"display": "Steel", "decoration": (0.6, 0.6, 0.7),
                      "toolTip": "ρ = 7.9 g/cm³", "user": steel})
    view = ListView(renderer, interactor, model=materials)

    scene = TreeModel.from_hierarchy(root_node)     # hierarchy.HierarchyNode

Roles are strings: ``"display"``, ``"decoration"`` (an icon name or an RGB
swatch), ``"toolTip"``, ``"checkState"`` (``"unchecked"``,
``"partially"``, ``"checked"`` or ``None``), ``"user"`` and any custom
role. Flags are a frozenset of ``"selectable"``, ``"enabled"``,
``"editable"`` and ``"checkable"``.

Models announce changes with ``dataChanged``, ``rowsInserted``,
``rowsRemoved`` (after ``rowsAboutToBeRemoved``) and ``modelReset``, so
views update only the rows that changed. The built-in models give every
row a stable item object (:meth:`ItemModel.persistentKey`), which is how
selections and expanded branches survive inserts and removals.
"""
from __future__ import annotations

from .core import Signal
from .hierarchy import HierarchyNode

__all__ = [
    "CHECKED", "DISPLAY", "DECORATION", "ItemModel", "ListModel",
    "ModelIndex", "PARTIALLY_CHECKED", "SelectionModel", "TableModel",
    "TOOLTIP", "CHECK_STATE", "TreeModel", "UNCHECKED", "USER",
]

DISPLAY = "display"
DECORATION = "decoration"
TOOLTIP = "toolTip"
CHECK_STATE = "checkState"
USER = "user"
EDIT = "edit"

UNCHECKED, PARTIALLY_CHECKED, CHECKED = "unchecked", "partially", "checked"

DEFAULT_FLAGS = frozenset({"selectable", "enabled"})


class ModelIndex:
    """Locates one cell of a model (``QModelIndex``).

    Indexes are cheap values; do not keep them across model changes, keep
    :meth:`ItemModel.persistentKey` instead.
    """

    __slots__ = ("_row", "_column", "_item", "_model")

    def __init__(self, row=-1, column=-1, item=None, model=None):
        self._row = int(row)
        self._column = int(column)
        self._item = item
        self._model = model

    def row(self):
        return self._row

    def column(self):
        return self._column

    def internalPointer(self):
        return self._item

    def model(self):
        return self._model

    def isValid(self):
        return self._model is not None and self._row >= 0 and \
            self._column >= 0

    def parent(self):
        return self._model.parent(self) if self.isValid() else ModelIndex()

    def sibling(self, row, column):
        if not self.isValid():
            return ModelIndex()
        return self._model.index(row, column, self.parent())

    def data(self, role=DISPLAY):
        return self._model.data(self, role) if self.isValid() else None

    def flags(self):
        return self._model.flags(self) if self.isValid() else frozenset()

    def _key(self):
        return (self._row, self._column, id(self._item), id(self._model))

    def __eq__(self, other):
        if not isinstance(other, ModelIndex):
            return NotImplemented
        if not self.isValid() and not other.isValid():
            return True
        return self._key() == other._key()

    def __hash__(self):
        return hash(self._key()) if self.isValid() else 0

    def __repr__(self):
        if not self.isValid():
            return "ModelIndex()"
        return f"ModelIndex({self._row}, {self._column})"


class ItemModel:
    """Base class for item models (``QAbstractItemModel``).

    Subclasses implement :meth:`rowCount`, :meth:`columnCount`,
    :meth:`data`, :meth:`index` and :meth:`parent` (tree models) and call
    the ``begin*/end*`` methods around structural changes.
    """

    def __init__(self):
        self.dataChanged = Signal()           # (top_left, bottom_right, roles)
        self.headerDataChanged = Signal()     # (orientation, first, last)
        self.rowsAboutToBeInserted = Signal()  # (parent, first, last)
        self.rowsInserted = Signal()          # (parent, first, last)
        self.rowsAboutToBeRemoved = Signal()  # (parent, first, last)
        self.rowsRemoved = Signal()           # (parent, first, last)
        self.modelAboutToBeReset = Signal()
        self.modelReset = Signal()
        self._pending = []

    # -- structure (override) -------------------------------------------------------
    def rowCount(self, parent=None):
        return 0

    def columnCount(self, parent=None):
        return 1

    def index(self, row, column=0, parent=None):
        if not self.hasIndex(row, column, parent):
            return ModelIndex()
        return self.createIndex(row, column, None)

    def parent(self, index):
        return ModelIndex()

    def hasChildren(self, parent=None):
        return self.rowCount(parent) > 0

    def hasIndex(self, row, column, parent=None):
        return 0 <= row < self.rowCount(parent) and \
            0 <= column < self.columnCount(parent)

    def createIndex(self, row, column, item=None):
        return ModelIndex(row, column, item, self)

    # -- data (override) ------------------------------------------------------------
    def data(self, index, role=DISPLAY):
        return None

    def setData(self, index, value, role=EDIT):
        return False

    def flags(self, index):
        return DEFAULT_FLAGS if index is not None and index.isValid() \
            else frozenset()

    def headerData(self, section, orientation="horizontal", role=DISPLAY):
        if role != DISPLAY:
            return None
        return str(section + 1)

    # -- persistence ---------------------------------------------------------------
    def persistentKey(self, index):
        """A key for ``index``'s row that survives inserts and removals.

        The built-in models use the row's item object. The default (row
        path) is only valid until the next structural change; views and
        selection models drop such keys when rows move.
        """
        if index is None or not index.isValid():
            return None
        item = index.internalPointer()
        if item is not None:
            try:
                hash(item)
                return item
            except TypeError:
                pass
        path = []
        while index.isValid():
            path.append(index.row())
            index = index.parent()
        return ("path", tuple(reversed(path)))

    def indexForKey(self, key, column=0):
        """The current index of a :meth:`persistentKey` (invalid if gone)."""
        if isinstance(key, tuple) and len(key) == 2 and key[0] == "path":
            index = ModelIndex()
            last = len(key[1]) - 1
            for depth, row in enumerate(key[1]):
                index = self.index(row, column if depth == last else 0,
                                   index)
                if not index.isValid():
                    return ModelIndex()
            return index
        return ModelIndex()

    def hasStableKeys(self):
        """True when :meth:`persistentKey` survives structural changes."""
        return False

    # -- change notification -----------------------------------------------------------
    def beginInsertRows(self, parent, first, last):
        self.rowsAboutToBeInserted.emit(parent or ModelIndex(), first, last)
        self._pending.append(("insert", parent or ModelIndex(), first, last))

    def endInsertRows(self):
        _kind, parent, first, last = self._pending.pop()
        self.rowsInserted.emit(parent, first, last)

    def beginRemoveRows(self, parent, first, last):
        self.rowsAboutToBeRemoved.emit(parent or ModelIndex(), first, last)
        self._pending.append(("remove", parent or ModelIndex(), first, last))

    def endRemoveRows(self):
        _kind, parent, first, last = self._pending.pop()
        self.rowsRemoved.emit(parent, first, last)

    def beginResetModel(self):
        self.modelAboutToBeReset.emit()

    def endResetModel(self):
        self.modelReset.emit()

    def emitDataChanged(self, index, roles=None):
        self.dataChanged.emit(index, index, tuple(roles or ()))


# ---------------------------------------------------------------------------------------
# List and table models


class _Row:
    """One row of a :class:`ListModel`: a role dictionary per column."""

    __slots__ = ("cells", "__weakref__")

    def __init__(self, cells):
        self.cells = cells

    def __repr__(self):
        return f"_Row({self.cells[0].get(DISPLAY)!r})"


def _cell(value):
    if isinstance(value, dict):
        cell = dict(value)
        if DISPLAY not in cell and USER in cell:
            cell[DISPLAY] = str(cell[USER])
        return cell
    if isinstance(value, str):
        return {DISPLAY: value}
    if value is None:
        return {DISPLAY: ""}
    if isinstance(value, (int, float)):
        return {DISPLAY: _format_number(value), USER: value}
    return {DISPLAY: str(value), USER: value}


def _format_number(value):
    if isinstance(value, float):
        return f"{value:g}"
    return str(value)


class ListModel(ItemModel):
    """A flat list of rows (``QStandardItemModel`` used as a list).

    Each item is a string, a ``{role: value}`` dict or any object (shown
    with ``str`` and returned for the ``"user"`` role). Pass ``headers`` to
    give the model several columns; each item is then a sequence with one
    value per column.
    """

    def __init__(self, items=(), headers=None):
        super().__init__()
        self._headers = list(headers) if headers is not None else None
        self._rows = [self._make_row(item) for item in items]
        self._row_of = None

    # -- construction ---------------------------------------------------------------
    def _columns(self):
        return len(self._headers) if self._headers else 1

    def _make_row(self, item):
        if self._headers is None:
            return _Row([_cell(item)])
        values = list(item) if isinstance(item, (list, tuple)) else [item]
        values += [None] * (self._columns() - len(values))
        return _Row([_cell(v) for v in values[:self._columns()]])

    # -- structure ------------------------------------------------------------------
    def rowCount(self, parent=None):
        if parent is not None and parent.isValid():
            return 0
        return len(self._rows)

    def columnCount(self, parent=None):
        return self._columns()

    def index(self, row, column=0, parent=None):
        if not self.hasIndex(row, column, parent):
            return ModelIndex()
        return ModelIndex(row, column, self._rows[row], self)

    def hasStableKeys(self):
        return True

    def indexForKey(self, key, column=0):
        if not isinstance(key, _Row):
            return super().indexForKey(key, column)
        if self._row_of is None:
            self._row_of = {id(row): i for i, row in enumerate(self._rows)}
        row = self._row_of.get(id(key))
        if row is None or self._rows[row] is not key:
            return ModelIndex()
        return ModelIndex(row, column, key, self)

    # -- data -------------------------------------------------------------------------
    def _cell_at(self, index):
        if index is None or not index.isValid() or index.model() is not self:
            return None
        row = index.internalPointer()
        if not isinstance(row, _Row) or index.column() >= len(row.cells):
            return None
        return row.cells[index.column()]

    def data(self, index, role=DISPLAY):
        cell = self._cell_at(index)
        if cell is None:
            return None
        if role == EDIT:
            role = DISPLAY
        return cell.get(role)

    def setData(self, index, value, role=EDIT):
        cell = self._cell_at(index)
        if cell is None:
            return False
        if role == EDIT:
            role = DISPLAY
        if cell.get(role) == value and role in cell:
            return True
        cell[role] = value
        self.dataChanged.emit(index, index, (role,))
        return True

    def itemData(self, index):
        cell = self._cell_at(index)
        return dict(cell) if cell is not None else {}

    def flags(self, index):
        cell = self._cell_at(index)
        if cell is None:
            return frozenset()
        flags = cell.get("flags")
        if flags is not None:
            return frozenset(flags)
        if cell.get(CHECK_STATE) is not None:
            return DEFAULT_FLAGS | {"checkable"}
        return DEFAULT_FLAGS

    def setFlags(self, index, flags):
        cell = self._cell_at(index)
        if cell is not None:
            cell["flags"] = frozenset(flags)
            self.dataChanged.emit(index, index, ("flags",))

    def headerData(self, section, orientation="horizontal", role=DISPLAY):
        if orientation == "horizontal" and role == DISPLAY and self._headers \
                and 0 <= section < len(self._headers):
            return self._headers[section]
        return super().headerData(section, orientation, role)

    def setHeaderData(self, section, value, orientation="horizontal"):
        if self._headers is None or not 0 <= section < len(self._headers):
            return False
        self._headers[section] = value
        self.headerDataChanged.emit(orientation, section, section)
        return True

    # -- list convenience ---------------------------------------------------------------
    def __len__(self):
        return len(self._rows)

    def item(self, row, role=DISPLAY):
        """Shortcut for ``data(index(row), role)``."""
        return self.data(self.index(row), role)

    def items(self, role=DISPLAY):
        return [row.cells[0].get(role) for row in self._rows]

    def append(self, item):
        self.insert(len(self._rows), item)

    def insert(self, row, item):
        self.insertItems(row, [item])

    def insertItems(self, row, items):
        rows = [self._make_row(item) for item in items]
        if not rows:
            return
        row = max(0, min(int(row), len(self._rows)))
        self.beginInsertRows(ModelIndex(), row, row + len(rows) - 1)
        self._rows[row:row] = rows
        self._row_of = None
        self.endInsertRows()

    def removeRows(self, row, count=1, parent=None):
        row, count = int(row), int(count)
        if count <= 0 or row < 0 or row + count > len(self._rows):
            return False
        self.beginRemoveRows(ModelIndex(), row, row + count - 1)
        del self._rows[row:row + count]
        self._row_of = None
        self.endRemoveRows()
        return True

    def removeRow(self, row, parent=None):
        return self.removeRows(row, 1)

    def setItems(self, items):
        """Replace every row (``modelReset``)."""
        self.beginResetModel()
        self._rows = [self._make_row(item) for item in items]
        self._row_of = None
        self.endResetModel()

    def clear(self):
        self.setItems([])

    def findRow(self, value, role=DISPLAY):
        for row, entry in enumerate(self._rows):
            if entry.cells[0].get(role) == value:
                return row
        return -1


class TableModel(ListModel):
    """A :class:`ListModel` with named columns, for :class:`TableView`."""

    def __init__(self, rows=(), headers=("",)):
        super().__init__(rows, headers=list(headers))


# ---------------------------------------------------------------------------------------
# Tree model


class TreeModel(ItemModel):
    """A tree of :class:`~multipanel.hierarchy.HierarchyNode` objects.

    Column 0 shows each node's ``label``; ``"user"`` returns its ``value``.
    Pass ``columns=[(header, getter), ...]`` for more columns, where
    ``getter(node)`` returns the cell's display value. Other roles are
    stored per node with :meth:`setData`.
    """

    def __init__(self, roots=(), columns=None):
        super().__init__()
        self._roots = list(roots)
        self._columns = list(columns) if columns else [("", None)]
        self._parents = {}
        self._nodes = {}          # id(node) -> node (nodes are unhashable)
        self._roles = {}
        self._index_nodes(None, self._roots)

    @classmethod
    def from_hierarchy(cls, hierarchy, columns=None, include_root=False):
        """Build from a root node (its children become the top level)
        or a list of top-level nodes."""
        if isinstance(hierarchy, HierarchyNode):
            roots = [hierarchy] if include_root else hierarchy.children
        else:
            roots = list(hierarchy)
        return cls(roots, columns)

    def _index_nodes(self, parent, nodes):
        for node in nodes:
            self._parents[id(node)] = parent
            self._nodes[id(node)] = node
            self._index_nodes(node, node.children)

    def _forget_nodes(self, nodes):
        for node in nodes:
            self._parents.pop(id(node), None)
            self._nodes.pop(id(node), None)
            self._roles.pop(id(node), None)
            self._forget_nodes(node.children)

    # -- structure --------------------------------------------------------------------
    def _children(self, parent):
        node = self.node(parent)
        return self._roots if node is None else node.children

    def node(self, index):
        """The ``HierarchyNode`` of ``index`` (``None`` for the root)."""
        if index is None or not index.isValid() or index.model() is not self:
            return None
        return index.internalPointer()

    def roots(self):
        return list(self._roots)

    def rowCount(self, parent=None):
        if parent is not None and parent.isValid() and parent.column() != 0:
            return 0
        return len(self._children(parent))

    def columnCount(self, parent=None):
        return len(self._columns)

    def index(self, row, column=0, parent=None):
        children = self._children(parent)
        if not (0 <= row < len(children) and
                0 <= column < len(self._columns)):
            return ModelIndex()
        return ModelIndex(row, column, children[row], self)

    def parent(self, index):
        node = self.node(index)
        if node is None:
            return ModelIndex()
        return self.indexForNode(self._parents.get(id(node)))

    def indexForNode(self, node, column=0):
        if node is None or id(node) not in self._parents:
            return ModelIndex()
        parent = self._parents[id(node)]
        siblings = self._roots if parent is None else parent.children
        for row, sibling in enumerate(siblings):
            if sibling is node:
                return ModelIndex(row, column, node, self)
        return ModelIndex()

    def hasStableKeys(self):
        return True

    def persistentKey(self, index):
        node = self.node(index)
        return None if node is None else ("node", id(node))

    def indexForKey(self, key, column=0):
        if isinstance(key, tuple) and len(key) == 2 and key[0] == "node":
            node = self._nodes.get(key[1])
            return self.indexForNode(node, column) if node is not None \
                else ModelIndex()
        return super().indexForKey(key, column)

    # -- data ----------------------------------------------------------------------------
    def data(self, index, role=DISPLAY):
        node = self.node(index)
        if node is None:
            return None
        if role == EDIT:
            role = DISPLAY
        column = index.column()
        stored = self._roles.get(id(node), {}).get((column, role))
        if stored is not None:
            return stored
        if column == 0:
            if role == DISPLAY:
                return node.label
            if role == USER:
                return node.value
            return None
        if role == DISPLAY:
            getter = self._columns[column][1]
            value = getter(node) if getter is not None else None
            if isinstance(value, (int, float)):
                return _format_number(value)
            return "" if value is None else str(value)
        return None

    def setData(self, index, value, role=EDIT):
        node = self.node(index)
        if node is None:
            return False
        if role == EDIT:
            role = DISPLAY
        if index.column() == 0 and role == DISPLAY:
            node.label = str(value)
        elif index.column() == 0 and role == USER:
            node.value = value
        else:
            self._roles.setdefault(id(node), {})[(index.column(), role)] = value
        self.dataChanged.emit(index, index, (role,))
        return True

    def flags(self, index):
        node = self.node(index)
        if node is None:
            return frozenset()
        flags = self._roles.get(id(node), {}).get((index.column(), "flags"))
        if flags is not None:
            return frozenset(flags)
        if self.data(index, CHECK_STATE) is not None:
            return DEFAULT_FLAGS | {"checkable"}
        return DEFAULT_FLAGS

    def headerData(self, section, orientation="horizontal", role=DISPLAY):
        if orientation == "horizontal" and role == DISPLAY and \
                0 <= section < len(self._columns):
            return self._columns[section][0]
        return super().headerData(section, orientation, role)

    # -- editing the tree -------------------------------------------------------------------
    def insertNode(self, parent, row, node):
        """Insert ``node`` (with its subtree) under index ``parent``."""
        children = self._children(parent)
        row = max(0, min(int(row), len(children)))
        self.beginInsertRows(parent or ModelIndex(), row, row)
        children.insert(row, node)
        owner = self.node(parent)
        self._parents[id(node)] = owner
        self._index_nodes(node, node.children)
        self.endInsertRows()
        return ModelIndex(row, 0, node, self)

    def appendNode(self, parent, node):
        return self.insertNode(parent, len(self._children(parent)), node)

    def removeRows(self, row, count=1, parent=None):
        children = self._children(parent)
        row, count = int(row), int(count)
        if count <= 0 or row < 0 or row + count > len(children):
            return False
        self.beginRemoveRows(parent or ModelIndex(), row, row + count - 1)
        removed = children[row:row + count]
        del children[row:row + count]
        self._forget_nodes(removed)
        self.endRemoveRows()
        return True

    def removeNode(self, node):
        index = self.indexForNode(node)
        if not index.isValid():
            return False
        return self.removeRows(index.row(), 1, index.parent())

    def setRoots(self, roots):
        self.beginResetModel()
        self._roots = list(roots)
        self._parents.clear()
        self._nodes.clear()
        self._roles.clear()
        self._index_nodes(None, self._roots)
        self.endResetModel()

    def walk(self, parent=None):
        """Yield every index below ``parent`` depth first."""
        for row in range(self.rowCount(parent)):
            index = self.index(row, 0, parent)
            yield index
            yield from self.walk(index)


# ---------------------------------------------------------------------------------------
# Selection


class SelectionModel:
    """Which rows of a model are selected, and the current row.

    Like ``QItemSelectionModel`` with whole-row selection. ``mode`` is
    ``"single"``, ``"multi"`` (each click toggles), ``"extended"``
    (Ctrl toggles, Shift selects a range) or ``"none"``. Selected rows are
    kept by :meth:`ItemModel.persistentKey`, so a selection survives rows
    being inserted, removed or (in trees) collapsed.
    """

    MODES = ("none", "single", "multi", "extended")

    def __init__(self, model, mode="extended"):
        self._model = None
        self._selected = {}       # persistent key -> None (insertion order)
        self._current = None
        self._anchor = None
        self.setSelectionMode(mode)
        self.selectionChanged = Signal()   # (selected, deselected) index lists
        self.currentChanged = Signal()     # (current, previous)
        self.setModel(model)

    # -- model ---------------------------------------------------------------------------
    def model(self):
        return self._model

    def setModel(self, model):
        if self._model is not None:
            self._model.rowsRemoved.disconnect(self._on_rows_removed)
            self._model.rowsInserted.disconnect(self._on_rows_inserted)
            self._model.modelReset.disconnect(self._on_reset)
        self._model = model
        self._selected.clear()
        self._current = self._anchor = None
        if model is not None:
            model.rowsRemoved.connect(self._on_rows_removed)
            model.rowsInserted.connect(self._on_rows_inserted)
            model.modelReset.connect(self._on_reset)

    def selectionMode(self):
        return self._mode

    def setSelectionMode(self, mode):
        if mode not in self.MODES:
            raise ValueError(f"selection mode must be one of {self.MODES}")
        self._mode = mode

    # -- keys ------------------------------------------------------------------------------
    def _key(self, index):
        if index is None or not index.isValid():
            return None
        if index.column() != 0:
            index = index.sibling(index.row(), 0)
        return self._model.persistentKey(index)

    def _index(self, key):
        if key is None:
            return None
        index = self._model.indexForKey(key, 0)
        return index if index.isValid() else None

    # -- queries -------------------------------------------------------------------------------
    def currentIndex(self):
        index = self._index(self._current)
        return index if index is not None else ModelIndex()

    def anchorIndex(self):
        index = self._index(self._anchor)
        return index if index is not None else ModelIndex()

    def isSelected(self, index):
        key = self._key(index)
        return key is not None and key in self._selected

    def hasSelection(self):
        return bool(self._selected)

    def selectedRows(self):
        """Selected rows (column 0 indexes) in selection order."""
        rows = []
        for key in self._selected:
            index = self._index(key)
            if index is not None:
                rows.append(index)
        return rows

    selectedIndexes = selectedRows

    # -- changes ---------------------------------------------------------------------------------
    def setCurrentIndex(self, index, command="none"):
        """Make ``index`` current; ``command`` as for :meth:`select`."""
        key = self._key(index)
        previous = self.currentIndex()
        if key != self._current:
            self._current = key
            self.currentChanged.emit(self.currentIndex(), previous)
        if command != "none":
            self.select(index, command)

    def setAnchor(self, index):
        self._anchor = self._key(index)

    def select(self, indexes, command="clearAndSelect"):
        """Change the selection.

        ``indexes`` is one index or a list. ``command`` is
        ``"clearAndSelect"``, ``"select"``, ``"deselect"`` or ``"toggle"``.
        """
        if self._mode == "none":
            return
        if isinstance(indexes, ModelIndex):
            indexes = [indexes]
        keys = []
        for index in indexes:
            key = self._key(index)
            if key is not None and "selectable" in index.flags() and \
                    key not in keys:
                keys.append(key)
        before = dict(self._selected)
        if command == "clearAndSelect":
            self._selected = dict.fromkeys(keys)
        elif command == "select":
            for key in keys:
                self._selected[key] = None
        elif command == "deselect":
            for key in keys:
                self._selected.pop(key, None)
        elif command == "toggle":
            for key in keys:
                if key in self._selected:
                    del self._selected[key]
                else:
                    self._selected[key] = None
        else:
            raise ValueError(f"unknown selection command {command!r}")
        if self._mode == "single" and len(self._selected) > 1:
            last = next(reversed(self._selected))
            self._selected = {last: None}
        self._emit_change(before)

    def clearSelection(self):
        before = dict(self._selected)
        self._selected.clear()
        self._emit_change(before)

    def clear(self):
        self.clearSelection()
        self.setCurrentIndex(ModelIndex())
        self._anchor = None

    def _emit_change(self, before):
        added = [k for k in self._selected if k not in before]
        removed = [k for k in before if k not in self._selected]
        if added or removed:
            self.selectionChanged.emit(
                [i for i in map(self._index, added) if i is not None],
                [i for i in map(self._index, removed) if i is not None])

    # -- model changes ---------------------------------------------------------------------------
    def _on_rows_inserted(self, parent, first, last):
        if not self._model.hasStableKeys():
            self._drop_all()

    def _on_rows_removed(self, parent, first, last):
        if not self._model.hasStableKeys():
            self._drop_all()
            return
        gone = [k for k in self._selected if self._index(k) is None]
        for key in gone:
            del self._selected[key]
        if gone:
            self.selectionChanged.emit([], [])
        if self._current is not None and self._index(self._current) is None:
            self._current = None
            self.currentChanged.emit(ModelIndex(), ModelIndex())
        if self._anchor is not None and self._index(self._anchor) is None:
            self._anchor = None

    def _on_reset(self):
        self._drop_all()

    def _drop_all(self):
        had = bool(self._selected)
        self._selected.clear()
        self._anchor = None
        if self._current is not None:
            self._current = None
            self.currentChanged.emit(ModelIndex(), ModelIndex())
        if had:
            self.selectionChanged.emit([], [])
