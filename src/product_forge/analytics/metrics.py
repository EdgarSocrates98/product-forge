"""Semantic metrics catalog — KPI definitions are data, not guesses (§6.1).

Agents must resolve metric names to catalog entries instead of inventing
formulas. Each metric carries formula (SQL fragment), source, granularity,
dimensions, owner, version and freshness. Unknown metric → `unknown-metric`
state, never a made-up definition.
"""

from __future__ import annotations

from typing import Any

from ..domain.models import new_id, utcnow


def put_metric(store: Any, product_id: str, data: dict[str, Any]) -> dict[str, Any]:
    doc = {"id": data.get("id") or new_id("m"),
           "schema": "productforge/Metric/v1",
           "product_id": product_id,
           "name": data["name"],
           "description": data.get("description", ""),
           "formula": data["formula"],          # SQL fragment, e.g. "SUM(amount)"
           "source_id": data.get("source_id"),
           "granularity": data.get("granularity", "day"),
           "dimensions": list(data.get("dimensions") or []),
           "filters": list(data.get("filters") or []),
           "owner": data.get("owner", ""),
           "version": int(data.get("version", 1)),
           "objective": data.get("objective", ""),
           "examples": list(data.get("examples") or []),
           "validations": list(data.get("validations") or []),
           "updated_at": utcnow()}
    store.put_doc("metrics", doc)
    return doc


def resolve(store: Any, product_id: str, question: str) -> dict[str, Any]:
    """Match a question to catalog metrics by name/keywords. Honest scoring."""
    q = question.lower()
    metrics = [m for m in store.list("metrics", product_id=product_id)]
    hits = []
    for m in metrics:
        name = m["name"].lower()
        score = 0.0
        if name in q:
            score += 2.0
        score += sum(1 for t in name.split() if len(t) > 3 and t in q) * 0.5
        score += sum(0.25 for d in m.get("dimensions", []) if d.lower() in q)
        if score > 0:
            hits.append((score, m))
    hits.sort(key=lambda x: -x[0])
    matched = [{"score": round(s, 2), "metric": m} for s, m in hits[:5]]
    if not matched:
        return {"status": "unknown-metric", "matched": [],
                "detail": "no catalog metric matched — refusing to invent a KPI"}
    return {"status": "ambiguous" if len(matched) > 1 and
            matched[0]["score"] == matched[1]["score"] else "matched",
            "matched": matched}


def metric_sql(metric: dict[str, Any], table: str, dimensions: list[str] | None = None) -> str:
    """Compile a catalog metric into a validated SELECT (formula is trusted
    definition, table comes from the registered data source)."""
    dims = dimensions if dimensions is not None else metric.get("dimensions", [])
    select_dims = ", ".join(dims) + ", " if dims else ""
    group = f" GROUP BY {', '.join(dims)}" if dims else ""
    where = f" WHERE {' AND '.join(metric.get('filters') or [])}" if metric.get("filters") else ""
    sql = (f"SELECT {select_dims}{metric['formula']} "  # noqa: S608 — operator-authored
           f"AS {metric['name'].replace(' ', '_')} FROM {table}{where}{group}")
    return sql
