"""Analysis Notebooks — reproducible, versioned blocks (§6.3).

Blocks: markdown | sql. SQL blocks go through the SAME read-only
validation as /queries — a notebook can never execute what the API
would reject. Every run bumps the block version and records provenance
(source, statement hash, row count) so a rendered notebook is auditable.
"""

from __future__ import annotations

import hashlib
from typing import Any

BLOCK_KINDS = ("markdown", "sql")


def add_block(nb: dict[str, Any], kind: str, content: str,
              source_id: str | None = None) -> dict[str, Any]:
    from ..domain.models import new_id
    if kind not in BLOCK_KINDS:
        raise ValueError(f"block kind must be one of {BLOCK_KINDS}")
    block = {"id": new_id("blk"), "kind": kind, "content": content,
             "source_id": source_id, "version": 0,
             "last_result": None}
    nb.setdefault("blocks", []).append(block)
    return block


def run_sql_block(block: dict[str, Any], validate_fn: Any, execute_fn: Any) -> dict[str, Any]:
    """Validate (read-only) then execute a sql block; bump version+provenance."""
    v = validate_fn(block["content"])
    if not v.get("ok"):
        return {"ran": False, "status": "rejected",
                "reason": v.get("reason", "validation-failed")}
    res = execute_fn(block["source_id"], block["content"])
    block["version"] += 1
    block["last_result"] = {
        "status": res.get("status"),
        "rows": res.get("rows"),
        "statement_sha": hashlib.sha256(block["content"].encode()).hexdigest()[:12],
        "source_id": block["source_id"],
    }
    return {"ran": res.get("status") == "completed",
            "status": res.get("status"), "rows": res.get("rows"),
            "block_version": block["version"]}


def render(nb: dict[str, Any]) -> dict[str, Any]:
    """Reproducible render: ordered blocks with versions + provenance."""
    return {"schema": "productforge/NotebookRender/v1",
            "notebook_id": nb["id"], "title": nb.get("title", ""),
            "blocks": [{"id": b["id"], "kind": b["kind"], "version": b["version"],
                        "content": b["content"],
                        "result": b.get("last_result")}
                       for b in nb.get("blocks", [])],
            "executed": sum(1 for b in nb.get("blocks", []) if b.get("last_result")),
            "total": len(nb.get("blocks", [])),
            "note": "sql blocks execute only read-only validated statements"}
