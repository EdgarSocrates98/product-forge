"""Agent tool registry — every tool is a real store-backed function.

Tools receive (store, ctx) where ctx carries product_id (server-set,
never agent-supplied) — cross-product leakage is impossible by
construction. No network tools exist in the registry.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from ..store.sqlite import Store


@dataclass(frozen=True)
class ToolCtx:
    product_id: str
    actor: str = "agent"
    run_id: str = ""


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    permission: str  # maps to domain PERMISSIONS keys
    destructive: bool
    fn: Callable[[Store, ToolCtx, dict[str, Any]], dict[str, Any]]


def _knowledge_query(st: Store, cx: ToolCtx, args: dict[str, Any]) -> dict[str, Any]:
    hits = st.search_fts(cx.product_id, str(args.get("question", "")), limit=int(args.get("limit", 5)))
    return {"citations": [{"chunk_id": h["id"], "document_id": h["document_id"],
                           "snippet": h["snip"], "title": st.doc_title(h["document_id"])}
                          for h in hits],
            "hit_count": len(hits)}


def _context_package(st: Store, cx: ToolCtx, args: dict[str, Any]) -> dict[str, Any]:
    return {"product": st.get("products", cx.product_id),
            "sources": st.list("knowledge_sources", product_id=cx.product_id, limit=50),
            "entities": st.list("entities", product_id=cx.product_id, limit=100)}


def _graph_lookup(st: Store, cx: ToolCtx, args: dict[str, Any]) -> dict[str, Any]:
    from ..knowledge.graph import product_graph

    g = product_graph(st, cx.product_id, limit=int(args.get("limit", 500)))
    kind = args.get("kind")
    if kind:
        g["nodes"] = [n for n in g["nodes"] if n.get("kind") == kind]
    return g


def _knowledge_health(st: Store, cx: ToolCtx, args: dict[str, Any]) -> dict[str, Any]:
    from ..knowledge.graph import knowledge_health

    return knowledge_health(st, cx.product_id)


def _data_sources(st: Store, cx: ToolCtx, args: dict[str, Any]) -> dict[str, Any]:
    return {"items": st.list("data_sources", product_id=cx.product_id)}


def _entities(st: Store, cx: ToolCtx, args: dict[str, Any]) -> dict[str, Any]:
    kind = args.get("kind")
    items = st.list("entities", product_id=cx.product_id, limit=int(args.get("limit", 100)))
    if kind:
        items = [e for e in items if e.get("kind") == kind]
    return {"items": items}


REGISTRY: dict[str, Tool] = {
    t.name: t
    for t in [
        Tool("knowledge_query", "Grounded retrieval with citations", "product.read", False, _knowledge_query),
        Tool("context_package", "Product Context Package", "product.read", False, _context_package),
        Tool("graph_lookup", "Knowledge graph projection", "product.read", False, _graph_lookup),
        Tool("knowledge_health", "Knowledge coverage score", "product.read", False, _knowledge_health),
        Tool("data_sources", "Registered analytical sources", "product.read", False, _data_sources),
        Tool("entities", "Extracted entities by kind", "product.read", False, _entities),
    ]
}

TEMPLATES: dict[str, dict[str, Any]] = {
    "product-analyst": {
        "mission": "Answer product questions grounded in indexed knowledge",
        "tools": ["knowledge_query", "context_package", "entities"],
        "steps": ["knowledge_query", "entities"],
    },
    "product-researcher": {
        "mission": "Investigate topics and map evidence across sources",
        "tools": ["knowledge_query", "graph_lookup", "context_package"],
        "steps": ["knowledge_query", "graph_lookup"],
    },
    "api-analyst": {
        "mission": "Analyze API surface and contract entities",
        "tools": ["entities", "knowledge_query", "graph_lookup"],
        "steps": ["entities", "graph_lookup"],
    },
    "data-steward": {
        "mission": "Inventory data sources and assess knowledge health",
        "tools": ["data_sources", "knowledge_health", "entities"],
        "steps": ["data_sources", "knowledge_health"],
    },
    "custom": {"mission": "", "tools": ["knowledge_query"], "steps": ["knowledge_query"]},
}
