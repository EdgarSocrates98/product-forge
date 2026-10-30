"""Dashboard rendering — widgets bound to real query executions.

A widget references a data_source + statement or QuerySpec. Rendering
executes each query through the governed engine (validation, allowlist,
limits, masking) and returns per-widget state — unavailable sources are
reported honestly, never substituted with fake data.
"""

from __future__ import annotations

from typing import Any

from ..analytics.engine import compile_spec, execute_query
from ..store.sqlite import Store

WIDGET_TYPES = {"kpi_card", "table", "bar_chart", "line_chart", "pie_chart", "metric_trend"}


def render_dashboard(store: Store, product_id: str, dashboard: dict[str, Any],
                     *, max_rows: int = 500) -> dict[str, Any]:
    out_widgets = []
    for w in dashboard.get("widgets", []):
        out_widgets.append(_render_widget(store, product_id, w,
                                          dashboard.get("filters", {}), max_rows))
    ok = sum(1 for w in out_widgets if w["state"] == "ok")
    return {"schema": "productforge/DashboardRender/v1",
            "dashboard_id": dashboard["id"], "name": dashboard.get("name"),
            "widgets": out_widgets,
            "stats": {"total": len(out_widgets), "ok": ok,
                      "unavailable": len(out_widgets) - ok}}


def _render_widget(store: Store, product_id: str, w: dict[str, Any],
                   dash_filters: dict[str, Any], max_rows: int) -> dict[str, Any]:
    base = {"id": w.get("id"), "type": w.get("type", "table"), "title": w.get("title", "")}
    source_id = w.get("source_id")
    if not source_id:
        return {**base, "state": "error", "error": "widget has no source_id"}
    spec = dict(w.get("spec") or {})
    if dash_filters and spec:
        spec.setdefault("filters", [])
        for k, v in dash_filters.items():
            spec["filters"].append({"column": k, "op": "=", "value": v})
    try:
        statement = w.get("statement") or (compile_spec(spec) if spec else None)
        if not statement:
            return {**base, "state": "error", "error": "no statement or spec"}
        run = execute_query(store, product_id, source_id, statement, row_limit=max_rows)
    except Exception as e:
        return {**base, "state": "unavailable", "error": str(e)[:200]}
    if run["status"] != "completed":
        return {**base, "state": "unavailable", "error": run.get("error", run["status"]),
                "query_id": run["id"]}
    rows, cols = run.get("result_preview", []), run.get("columns", [])
    return {**base, "state": "ok", "query_id": run["id"],
            "duration_ms": run["duration_ms"], "truncated": run.get("truncated", False),
            "data": _shape(w.get("type", "table"), cols, rows)}


def _shape(wtype: str, cols: list[str], rows: list[list[Any]]) -> dict[str, Any]:
    if wtype == "kpi_card":
        val = rows[0][0] if rows and rows[0] else None
        return {"value": val, "label": cols[0] if cols else "value"}
    if wtype in {"bar_chart", "line_chart", "pie_chart"}:
        labels = [str(r[0]) for r in rows] if cols else []
        series = [{"name": cols[i] if i < len(cols) else f"c{i}",
                   "values": [r[i] if i < len(r) else None for r in rows]}
                  for i in range(1, len(cols))]
        return {"labels": labels, "series": series}
    return {"columns": cols, "rows": rows}
