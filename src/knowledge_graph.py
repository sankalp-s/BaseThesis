"""In-memory knowledge graph for conversational facts."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


@dataclass
class GraphNode:
    node_id: str
    label: str
    node_type: str
    attributes: Dict[str, str] = field(default_factory=dict)


@dataclass
class GraphEdge:
    source: str
    target: str
    relation: str
    weight: float = 1.0


class KnowledgeGraph:
    def __init__(self) -> None:
        self.nodes: Dict[str, GraphNode] = {}
        self.edges: List[GraphEdge] = []

    def upsert_entity(self, node_id: str, label: str, node_type: str, attributes: Dict[str, str]) -> None:
        self.nodes[node_id] = GraphNode(node_id=node_id, label=label, node_type=node_type, attributes=attributes)

    def add_edge(self, source: str, target: str, relation: str, weight: float = 1.0) -> None:
        self.edges.append(GraphEdge(source=source, target=target, relation=relation, weight=weight))

    def ingest_entities(self, entities) -> None:
        for entity in entities:
            attributes = {k: str(v.get("value", v)) for k, v in entity.attributes.items()} if getattr(entity, "attributes", None) else {}
            self.upsert_entity(entity.entity_id, entity.canonical_name, entity.entity_type.value, attributes)

    def ingest_memory(self, memory_item) -> None:
        digest = hashlib.md5(memory_item.content.encode("utf-8")).hexdigest()[:10]
        node_id = f"memory:{memory_item.turn_number}:{digest}"
        self.upsert_entity(
            node_id=node_id,
            label=memory_item.content[:80],
            node_type="memory",
            attributes={
                "retention": memory_item.retention.value,
                "importance": f"{memory_item.importance_score:.1f}",
            },
        )

    def link_memory_to_entities(self, memory_item, entities) -> None:
        digest = hashlib.md5(memory_item.content.encode("utf-8")).hexdigest()[:10]
        mem_node = f"memory:{memory_item.turn_number}:{digest}"
        for entity in entities:
            self.add_edge(mem_node, entity.entity_id, relation="MENTIONS")

    def get_summary(self) -> Dict[str, int]:
        return {
            "nodes": len(self.nodes),
            "edges": len(self.edges),
            "people": len([n for n in self.nodes.values() if n.node_type == "person"]),
            "medical": len([n for n in self.nodes.values() if n.node_type == "medical_condition"]),
        }

    def query_focus(self, label_contains: str) -> List[GraphNode]:
        return [node for node in self.nodes.values() if label_contains.lower() in node.label.lower()]
