"""Delegate catalog — operator-declared sibling forges and their status.

A delegate is a sibling specialist forge that product-forge may invoke
directly via subprocess+JSON (Forge Protocol). Delegates are declared in
config, never auto-discovered:

    "delegates": [
        {"id": "data-sentinel", "cli": "data-sentinel",
         "workflows": ["inventory", "health"], "description": "..."}
    ]

Status is honest: `available` only when the CLI resolves on PATH; anything
else reports `unavailable:<reason>` — never pretended presence.
"""

from __future__ import annotations

import shutil
from typing import Any


def delegates(cfg: dict[str, Any]) -> list[dict[str, Any]]:
    """Declared delegates normalized — operator allowlist, no discovery."""
    out: list[dict[str, Any]] = []
    for d in cfg.get("delegates") or []:
        out.append({"id": str(d.get("id", "")),
                    "cli": str(d.get("cli", "")),
                    "workflows": [str(w) for w in d.get("workflows") or []],
                    "description": str(d.get("description", ""))})
    return out


def catalog(cfg: dict[str, Any]) -> list[dict[str, Any]]:
    """Delegates with live availability — honest, probed via PATH only."""
    rows = []
    for d in delegates(cfg):
        resolved = shutil.which(d["cli"]) if d["cli"] else None
        rows.append({**d,
                     "status": "available" if resolved else "unavailable:cli-not-found",
                     "resolved": resolved})
    return rows


def find(cfg: dict[str, Any], delegate_id: str) -> dict[str, Any] | None:
    return next((d for d in catalog(cfg) if d["id"] == delegate_id), None)
