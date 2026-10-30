"""Roadmap builder — now/next/later lanes from real initiatives."""

from __future__ import annotations

from typing import Any

from ..domain.models import utcnow
from ..store.sqlite import Store

_LANES = {
    "now": {"in_progress"},
    "next": {"prioritized"},
    "later": {"proposed"},
    "done": {"done"},
}


def build_roadmap(store: Store, product_id: str) -> dict[str, Any]:
    initiatives = store.list("initiatives", product_id=product_id, limit=500)
    lanes: dict[str, list[dict[str, Any]]] = {k: [] for k in _LANES}
    for ini in initiatives:
        lane = next((k for k, states in _LANES.items()
                     if ini.get("status") in states), "later")
        lanes[lane].append({
            "id": ini["id"], "title": ini.get("title"),
            "priority_score": ini.get("priority_score", 0),
            "status": ini.get("status"),
            "evidence_count": len(ini.get("evidence", []))})
    for items in lanes.values():
        items.sort(key=lambda x: x["priority_score"], reverse=True)
    rejected = [i for i in initiatives if i.get("status") == "rejected"]
    return {"schema": "productforge/Roadmap/v1", "product_id": product_id,
            "generated_at": utcnow(), "lanes": lanes,
            "stats": {"initiatives": len(initiatives), "rejected": len(rejected)}}
