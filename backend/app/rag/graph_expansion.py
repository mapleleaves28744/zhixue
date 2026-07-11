from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class GraphExpansionContext:
    seed_nodes: list[str] = field(default_factory=list)
    expanded_nodes: list[str] = field(default_factory=list)
    seed_knowledge_ids: list[str] = field(default_factory=list)
    expanded_knowledge_ids: list[str] = field(default_factory=list)
    relation_paths: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "seed_nodes": self.seed_nodes,
            "expanded_nodes": self.expanded_nodes,
            "seed_knowledge_ids": self.seed_knowledge_ids,
            "expanded_knowledge_ids": self.expanded_knowledge_ids,
            "relation_paths": self.relation_paths,
        }
