"""Bounded, body-free search across Product Forge knowledge projections."""

from __future__ import annotations

from typing import Any


def _text(value: Any) -> str:
    return str(value or "").strip()


def _matches(query: str, *values: Any) -> bool:
    needle = query.casefold()
    return any(needle in _text(value).casefold() for value in values)


def search_knowledge(store: Any, product_id: str, query: str, limit: int = 20) -> dict[str, Any]:
    """Search documents, registered sources, entities and relations.

    Document hits use SQLite FTS; the smaller catalog projections are searched
    in memory so the endpoint remains deterministic on both SQLite and the
    PostgreSQL-backed store. No document body is returned.
    """
    safe_limit = max(1, min(int(limit), 100))
    needle = query.strip()
    if not needle:
        return {"schema": "productforge/KnowledgeSearch/v1", "items": []}

    items: list[dict[str, Any]] = []
    docs = {doc["id"]: doc for doc in store.list("documents", product_id=product_id, limit=5000)}
    for hit in store.search_fts(product_id, needle, safe_limit):
        doc = docs.get(hit["document_id"]) or store.get("documents", hit["document_id"])
        metadata = doc.get("metadata") or {}
        items.append(
            {
                "kind": "document",
                "id": hit["document_id"],
                "document_id": hit["document_id"],
                "chunk_id": hit["id"],
                "seq": hit["seq"],
                "title": doc.get("title", hit["document_id"]),
                "snippet": hit["snip"],
                "source": metadata.get("source"),
                "version": metadata.get("version", 1),
            }
        )

    for source in store.list("knowledge_sources", product_id=product_id, limit=5000):
        if len(items) >= safe_limit or not _matches(
            needle,
            source.get("name"),
            source.get("type"),
            source.get("locator"),
            source.get("classification"),
        ):
            continue
        items.append(
            {
                "kind": "source",
                "id": source["id"],
                "source_id": source["id"],
                "title": source.get("name", source["id"]),
                "snippet": " · ".join(
                    filter(
                        None,
                        (
                            _text(source.get("type")),
                            _text(source.get("locator")),
                            _text(source.get("status")),
                        ),
                    )
                ),
                "source": source.get("type"),
            }
        )

    entities = store.list("entities", product_id=product_id, limit=5000)
    entity_names = {entity["id"]: entity.get("name", entity["id"]) for entity in entities}
    for entity in entities:
        if len(items) >= safe_limit or not _matches(
            needle,
            entity.get("name"),
            entity.get("description"),
            entity.get("kind"),
        ):
            continue
        items.append(
            {
                "kind": "entity",
                "id": entity["id"],
                "entity_id": entity["id"],
                "title": entity.get("name", entity["id"]),
                "snippet": " · ".join(
                    filter(
                        None,
                        (
                            _text(entity.get("kind")),
                            _text(entity.get("description")),
                        ),
                    )
                ),
                "source": "knowledge-graph",
            }
        )

    for relation in store.list("relations", product_id=product_id, limit=5000):
        if len(items) >= safe_limit:
            break
        from_name = entity_names.get(relation.get("from_entity"), relation.get("from_entity"))
        to_name = entity_names.get(relation.get("to_entity"), relation.get("to_entity"))
        if not _matches(needle, from_name, to_name, relation.get("kind")):
            continue
        items.append(
            {
                "kind": "relation",
                "id": relation["id"],
                "relation_id": relation["id"],
                "title": f"{from_name} → {to_name}",
                "snippet": _text(relation.get("kind")),
                "source": "knowledge-graph",
                "from_entity": relation.get("from_entity"),
                "to_entity": relation.get("to_entity"),
            }
        )

    return {"schema": "productforge/KnowledgeSearch/v1", "items": items[:safe_limit]}
