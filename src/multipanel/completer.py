"""Completion candidates for text fields (``QCompleter``, W6).

::

    field.setCompleter(["Aluminium", "Air", "Argon", "Lead"])
    field.setCompleter(Completer(material_model, filter_mode="contains"))

While the field is edited, matching candidates appear in a list under it;
Up/Down choose, Enter or a click accepts, Escape closes the list. The
filtering is plain Python and can be used without a field.
"""
from __future__ import annotations

from .core import Signal

__all__ = ["Completer"]


class Completer:
    """Candidates from a list of strings or an item model's column.

    ``filter_mode`` is ``"startsWith"`` (default) or ``"contains"``;
    matching ignores case unless ``case_sensitive``. At most
    ``max_visible`` candidates are shown.
    """

    def __init__(self, items=(), filter_mode="startsWith",
                 case_sensitive=False, max_visible=7, column=0):
        if filter_mode not in ("startsWith", "contains"):
            raise ValueError("filter_mode must be 'startsWith' or 'contains'")
        self._model = None
        self._items = []
        self._column = int(column)
        self.filter_mode = filter_mode
        self.case_sensitive = bool(case_sensitive)
        self.max_visible = max(1, int(max_visible))
        self.activated = Signal()           # (text) when a candidate is taken
        self.setModel(items)

    def setModel(self, items):
        """A list of strings or an :class:`~multipanel.models.ItemModel`."""
        from .models import ItemModel

        if isinstance(items, ItemModel):
            self._model, self._items = items, None
        else:
            self._model, self._items = None, [str(item) for item in items]

    def model(self):
        return self._model

    def candidates(self):
        if self._model is None:
            return list(self._items)
        model = self._model
        texts = []
        for row in range(model.rowCount()):
            value = model.index(row, self._column).data()
            if value is not None:
                texts.append(str(value))
        return texts

    def completions(self, prefix):
        """Candidates matching ``prefix`` (none for an empty prefix)."""
        prefix = str(prefix)
        if not prefix:
            return []
        fold = (lambda text: text) if self.case_sensitive else str.casefold
        key = fold(prefix)
        found = []
        for text in self.candidates():
            folded = fold(text)
            hit = folded.startswith(key) if self.filter_mode == "startsWith" \
                else key in folded
            if hit and text not in found:
                found.append(text)
        return found
