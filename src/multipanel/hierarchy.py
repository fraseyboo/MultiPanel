"""Small UI-independent hierarchy model used by scene and material trees."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Hashable


@dataclass
class HierarchyNode:
    """A labelled tree node whose leaves carry application values."""

    label: str
    value: Any = None
    children: list["HierarchyNode"] = field(default_factory=list)
    key: Hashable | None = None
    expanded_by_default: bool = False
    chevron_colors: list[tuple[float, float, float]] | None = None

    def __post_init__(self):
        if self.key is None:
            self.key = (self.label, id(self))

    @property
    def is_branch(self):
        return bool(self.children)
