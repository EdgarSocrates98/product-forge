"""Graph projection + knowledge health — computed views over the store."""

from __future__ import annotations

from typing import Any

from ..store.sqlite import Store


def product_graph(store: Store, product_id: str, limit: int = 2000) -> dict[str, Any]:
    entities = store.list("entities", product_id=product_id, limit=limit)
    relations = store.list("relations", product_id=product_id, limit=limit * 2)
    nodes = [{"id": e["id"], "label": e.get("name"), "kind": e.get("kind"),
              "confidence": e.get("confidence"), "provisional": e.get("provisional", True)}
             for e in entities]
    edges = [{"id": r["id"], "from": r["from_entity"], "to": r["to_entity"],
              "kind": r["kind"], "confidence": r["confidence"]} for r in relations]
    return {"schema": "productforge/KnowledgeGraph/v1", "product_id": product_id,
            "nodes": nodes, "edges": edges,
            "stats": {"nodes": len(nodes), "edges": len(edges)}}


def knowledge_health(store: Store, product_id: str) -> dict[str, Any]:
    sources = store.list("knowledge_sources", product_id=product_id)
    docs = store.list("documents", product_id=product_id)
    entities = store.list("entities", product_id=product_id, limit=5000)
    indexed = sum(1 for s in sources if s.get("status") == "indexed")
    failed = [s for s in sources if s.get("status") in ("error", "stale")]
    provisional = sum(1 for e in entities if e.get("provisional"))
    coverage = indexed / len(sources) if sources else 0.0
    score = round(100 * (0.5 * coverage
                         + 0.3 * min(1.0, len(entities) / max(1, len(docs) * 3) if docs else 0)
                         + 0.2 * (1 - provisional / len(entities) if entities else 0)))
    return {"schema": "productforge/KnowledgeHealth/v1", "product_id": product_id,
            "score": score,
            "sources": {"total": len(sources), "indexed": indexed,
                        "unverified_or_failed": len(failed)},
            "documents": len(docs),
            "entities": {"total": len(entities), "provisional": provisional},
            "warnings": ([f"{len(failed)} source(s) not indexed or failed"] if failed else [])
                        + (["no documents imported"] if not docs else [])}
