"""Executive reports — deterministic composition over real product data."""

from __future__ import annotations

from typing import Any

from ..domain.models import new_id, utcnow
from ..knowledge.graph import knowledge_health
from ..store.sqlite import Store


def generate_executive(store: Store, product_id: str) -> dict[str, Any]:
    p = store.get("products", product_id)
    health = knowledge_health(store, product_id)
    agents = store.list("agents", product_id=product_id)
    published = [a for a in agents if a.get("status") == "published"]
    sources = store.list("data_sources", product_id=product_id)
    queries = store.list("query_runs", product_id=product_id, limit=100)
    failed_q = [q for q in queries if q.get("status") in ("failed", "rejected")]
    initiatives = store.list("initiatives", product_id=product_id)
    alerts = [a for a in store.list("alerts", product_id=product_id)
              if a.get("state") == "open"]
    decisions = store.list("decisions", product_id=product_id)

    ent_line = (f"{health['documents']} docs, {health['entities']['total']} entities "
                f"({health['entities']['provisional']} provisional)")
    src = health["sources"]
    in_prog = sum(1 for i in initiatives if i.get("status") == "in_progress")
    md = f"""# Executive Report — {p.get('name')}
Generated: {utcnow()} · Product: `{product_id}`

## Product health
- Knowledge score: **{health['score']}/100** — {ent_line}
- Sources: {src['indexed']}/{src['total']} indexed; {src['unverified_or_failed']} failed/unverified
- Agents: {len(published)} published / {len(agents)} total
- Data sources: {len(sources)} registered
- Open alerts: **{len(alerts)}**

## Analytics activity (last {len(queries)} queries)
- Completed: {sum(1 for q in queries if q.get('status') == 'completed')}
- Failed/rejected: {len(failed_q)}

## Pipeline
- Initiatives: {len(initiatives)} ({in_prog} in progress)
- Decisions recorded: {len(decisions)}

## Risks & warnings
{chr(10).join(f"- {w}" for w in health['warnings']) or '- none'}
{chr(10).join(f"- ALERT {a['id']}: {a.get('message')}" for a in alerts[:10])}
"""
    rec = {"id": new_id("rep"), "schema": "productforge/Report/v1",
           "product_id": product_id, "kind": "executive", "markdown": md,
           "stats": {"knowledge_score": health["score"], "open_alerts": len(alerts),
                     "initiatives": len(initiatives)},
           "created_at": utcnow(), "updated_at": utcnow()}
    store.put_doc("reports", rec, name=f"executive:{product_id}")
    return rec
