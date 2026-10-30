"""Watches — scheduled metric checks over governed queries.

A watch runs its statement via the analytics engine, extracts a numeric
value, compares against threshold and opens an alert on breach. No
daemon: `run_due` is invoked by CLI/API/scheduler — honest and testable.
"""

from __future__ import annotations

import time
from typing import Any

from ..analytics.engine import execute_query
from ..domain.models import new_id, utcnow
from ..store.sqlite import Store

_OPS = {
    ">": lambda v, t: v > t,
    ">=": lambda v, t: v >= t,
    "<": lambda v, t: v < t,
    "<=": lambda v, t: v <= t,
    "==": lambda v, t: v == t,
    "!=": lambda v, t: v != t,
}


def create_watch(store: Store, product_id: str, spec: dict[str, Any]) -> dict[str, Any]:
    w = {"id": new_id("wat"), "schema": "productforge/Watch/v1",
         "product_id": product_id, "name": spec.get("name", "watch"),
         "source_id": spec["source_id"], "statement": spec["statement"],
         "value_column": spec.get("value_column", 0),
         "threshold": {"op": spec.get("op", ">"), "value": float(spec.get("value", 0))},
         "interval_s": int(spec.get("interval_s", 3600)),
         "state": "active", "last_run_at": None, "last_value": None,
         "created_at": utcnow(), "updated_at": utcnow()}
    return store.put_doc("watches", w, status="active", name=w["name"])


def evaluate_watch(store: Store, watch: dict[str, Any]) -> dict[str, Any]:
    run = execute_query(store, watch["product_id"], watch["source_id"],
                        watch["statement"], row_limit=1)
    result = {"watch_id": watch["id"], "query_id": run["id"],
              "evaluated_at": utcnow(), "breached": False, "alert_id": None}
    if run["status"] != "completed":
        result["error"] = run.get("error", run["status"])
        _touch(store, watch, None)
        return result
    rows = run.get("result_preview", [])
    col_idx = watch["value_column"]
    if isinstance(col_idx, str) and col_idx in run.get("columns", []):
        col_idx = run["columns"].index(col_idx)
    col_idx = int(col_idx) if not isinstance(col_idx, int) else col_idx
    value = rows[0][col_idx] if rows and len(rows[0]) > col_idx else None
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        result["error"] = f"non-numeric value at column {col_idx}: {value!r}"
        _touch(store, watch, None)
        return result
    thr = watch["threshold"]
    breached = _OPS.get(thr["op"], _OPS[">"])(numeric, thr["value"])
    result.update({"value": numeric, "threshold": thr, "breached": breached})
    if breached:
        alert = {"id": new_id("alr"), "schema": "productforge/Alert/v1",
                 "product_id": watch["product_id"], "watch_id": watch["id"],
                 "severity": "warning", "state": "open",
                 "message": f"{watch['name']}: {numeric} {thr['op']} {thr['value']}",
                 "value": numeric, "created_at": utcnow(), "updated_at": utcnow()}
        store.put_doc("alerts", alert, status="open")
        result["alert_id"] = alert["id"]
    _touch(store, watch, numeric)
    return result


def run_due(store: Store, product_id: str, *, now: float | None = None) -> dict[str, Any]:
    now = now or time.time()
    out = []
    for w in store.list("watches", product_id=product_id):
        if w.get("state") != "active":
            continue
        last = w.get("last_run_at")
        due = True if not last else (now - _ts(last)) >= w["interval_s"]
        if due:
            out.append(evaluate_watch(store, w))
    return {"schema": "productforge/WatchRun/v1", "evaluated": len(out),
            "results": out}


def _ts(iso: str) -> float:
    from datetime import datetime

    return datetime.fromisoformat(iso.replace("Z", "+00:00")).timestamp()


def _touch(store: Store, w: dict[str, Any], value: float | None) -> None:
    w["last_run_at"] = utcnow()
    w["last_value"] = value
    store.put_doc("watches", w, status=w["state"], name=w["name"])
