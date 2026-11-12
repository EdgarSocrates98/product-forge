"""Persisted document-version helpers shared by the HTTP and Portal APIs.

Version families are intentionally opt-in: a stable ``document_key`` is
required so two unrelated manual imports are never merged accidentally. URL,
workspace and Obsidian imports provide that key from their source locator.
"""

from __future__ import annotations

from typing import Any


def source_document_key(metadata: dict[str, Any]) -> str | None:
    """Return a stable, non-secret family key for a source-backed document."""
    source = str(metadata.get("source") or "").strip().lower()
    locator = (
        metadata.get("source_url")
        if source == "url"
        else metadata.get("workspace_path")
        if source == "workspace"
        else metadata.get("obsidian_path")
        if source == "obsidian"
        else metadata.get("investigation_correlation_id")
        if source == "the-forge"
        else None
    )
    if not source or not locator:
        return None
    return f"{source}:{locator}"


def prepare_version(
    store: Any, product_id: str, metadata: dict[str, Any]
) -> tuple[dict[str, Any], str | None]:
    """Mark the previous source version non-current and enrich new metadata.

    The caller must perform the content-hash idempotency check first. The
    returned previous id is stored on the new document for a cheap lineage
    walk, while all family members remain queryable in the durable store.
    """
    enriched = dict(metadata)
    # Indexing is not validation.  All source-backed imports enter the
    # governed lifecycle as captured unless the producer explicitly marks an
    # agent projection as draft.
    enriched.setdefault("knowledge_state", "captured")
    key = source_document_key(enriched)
    if not key:
        return enriched, None
    enriched["document_key"] = key
    family = [
        item
        for item in store.list("documents", product_id=product_id, limit=5000)
        if (item.get("metadata") or {}).get("document_key") == key
    ]
    if not family:
        enriched.update({"version": 1, "is_current": True})
        return enriched, None

    previous = max(family, key=lambda item: int((item.get("metadata") or {}).get("version", 1)))
    previous_metadata = dict(previous.get("metadata") or {})
    previous_metadata["is_current"] = False
    previous["metadata"] = previous_metadata
    store.put_doc("documents", previous)
    next_version = int(previous_metadata.get("version", 1)) + 1
    enriched.update(
        {
            "version": next_version,
            "is_current": True,
            "previous_document_id": previous.get("id"),
        }
    )
    return enriched, previous.get("id")


def explorer_versions(store: Any, product_id: str, document: dict[str, Any]) -> dict[str, Any]:
    """Build the version section of a DocumentExplorer response."""
    metadata = document.get("metadata") or {}
    key = metadata.get("document_key")
    if not key:
        return {"state": "current_only", "items": [document]}
    family = [
        item
        for item in store.list("documents", product_id=product_id, limit=5000)
        if (item.get("metadata") or {}).get("document_key") == key
    ]
    family.sort(key=lambda item: int((item.get("metadata") or {}).get("version", 1)))
    return {
        "state": "historical",
        "document_key": key,
        "current_document_id": next(
            (
                item.get("id")
                for item in reversed(family)
                if (item.get("metadata") or {}).get("is_current", False)
            ),
            family[-1].get("id") if family else document.get("id"),
        ),
        "items": family or [document],
    }
