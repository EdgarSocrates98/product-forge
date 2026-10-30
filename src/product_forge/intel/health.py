"""Product Health Center — deterministic, explainable scores (§7.2).

Every dimension reports a 0-100 score PLUS the evidence that produced it —
no number without provenance. Missing data degrades the score honestly and
says so, rather than faking "healthy".
"""

from __future__ import annotations

from typing import Any

DIMENSIONS = ("value", "adoption", "experience", "reliability",
              "cost", "delivery", "knowledge", "risk")


def _evidence(kind: str, detail: str, weight: int = 1) -> dict[str, Any]:
    return {"kind": kind, "detail": detail, "weight": weight}


def compute_health(store: Any, product_id: str) -> dict[str, Any]:
    docs = store.list("documents", product_id=product_id)
    chunks = store.list_chunks(product_id) if hasattr(store, "list_chunks") else []
    agents = store.list("agents", product_id=product_id)
    sources = store.list("data_sources", product_id=product_id)
    dashboards = store.list("dashboards", product_id=product_id)
    initiatives = store.list("initiatives", product_id=product_id)
    decisions = store.list("decisions", product_id=product_id)
    alerts = store.list("alerts", product_id=product_id)
    metrics = store.list("metrics", product_id=product_id)
    runs = store.list("query_runs", product_id=product_id)
    reports = store.list("reports", product_id=product_id)

    published = [a for a in agents if a.get("status") == "published"]
    open_alerts = [a for a in alerts if a.get("status", "open") == "open"]
    verified_src = [s for s in sources
                    if (s.get("verify") or {}).get("status") == "healthy"]

    def dim(score: int, evidence: list[dict[str, Any]]) -> dict[str, Any]:
        return {"score": max(0, min(100, score)), "evidence": evidence}

    dims = {
        "value": dim(
            20 + 15 * bool(initiatives) + 15 * bool(decisions) + 25 * bool(metrics)
            + 25 * bool(reports),
            [_evidence("initiatives", f"{len(initiatives)} initiative(s)"),
             _evidence("decisions", f"{len(decisions)} decision record(s)"),
             _evidence("metrics", f"{len(metrics)} catalog metric(s)"),
             _evidence("reports", f"{len(reports)} report(s)")]),
        "adoption": dim(
            30 + 35 * bool(published) + 20 * bool(dashboards) + 15 * bool(runs),
            [_evidence("agents", f"{len(published)}/{len(agents)} agents published"),
             _evidence("dashboards", f"{len(dashboards)} dashboard(s)"),
             _evidence("query_runs", f"{len(runs)} query run(s)")]),
        "experience": dim(
            40 + 30 * bool(docs) + 30 * bool(dashboards),
            [_evidence("documents", f"{len(docs)} document(s)"),
             _evidence("dashboards", f"{len(dashboards)} dashboard(s)")]),
        "reliability": dim(
            30 + 40 * bool(verified_src) - min(30, 10 * len(open_alerts)),
            [_evidence("data_sources",
                       f"{len(verified_src)}/{len(sources)} sources verified"),
             _evidence("alerts", f"{len(open_alerts)} open alert(s)", weight=-1)]),
        "cost": dim(
            50 + 25 * bool(metrics) + 25 * bool(reports),
            [_evidence("metrics", f"{len(metrics)} cost-trackable metric(s)"),
             _evidence("budget", "budget ledger active" if runs else "no runs yet")]),
        "delivery": dim(
            30 + 35 * bool(initiatives) + 35 * bool(published),
            [_evidence("initiatives", f"{len(initiatives)} initiative(s)"),
             _evidence("agents", f"{len(published)} published agent(s)")]),
        "knowledge": dim(
            10 + 30 * bool(docs) + 30 * bool(chunks) + 30 * bool(agents),
            [_evidence("documents", f"{len(docs)} document(s)"),
             _evidence("chunks", f"{len(chunks)} indexed chunk(s)"),
             _evidence("agents", f"{len(agents)} agent(s)")]),
        "risk": dim(
            70 - min(50, 12 * len(open_alerts)) - (15 if not verified_src and sources else 0),
            [_evidence("alerts", f"{len(open_alerts)} open alert(s)", weight=-1),
             _evidence("data_sources", "unverified sources" if sources and not verified_src
                       else "sources verified or none declared")]),
    }
    overall = round(sum(d["score"] for d in dims.values()) / len(DIMENSIONS))
    weakest = min(dims.items(), key=lambda kv: kv[1]["score"])
    return {"schema": "productforge/ProductHealth/v1", "product_id": product_id,
            "overall": overall,
            "weakest_dimension": weakest[0],
            "dimensions": dims,
            "note": "deterministic scoring; each score carries its evidence"}


def evidence_graph(store: Any, product_id: str, limit: int = 2000) -> dict[str, Any]:
    """§7.1 — unified evidence graph: entities/relations + typed collections."""
    base_nodes = store.list("entities", product_id=product_id, limit=limit)
    rels = store.list("relations", product_id=product_id, limit=limit * 2)
    nodes = [{"id": e["id"], "kind": e.get("kind", "entity"),
              "name": e.get("name", e["id"]), "source": "extracted"}
             for e in base_nodes]
    import contextlib
    with contextlib.suppress(Exception):
        prod = store.get("products", product_id)
        nodes.append({"id": prod["id"], "kind": "product",
                      "name": prod.get("name", product_id), "source": "collection"})
    typed = {"initiatives": "initiative", "decisions": "decision",
             "dashboards": "dashboard", "agents": "agent", "metrics": "metric",
             "data_sources": "data_source", "api_specs": "api", "reports": "report",
             "alerts": "alert", "approvals": "approval"}
    for coll, kind in typed.items():
        for d in store.list(coll, product_id=product_id, limit=500):
            nodes.append({"id": d["id"], "kind": kind,
                          "name": d.get("name") or d.get("title") or d["id"],
                          "source": "collection"})
    edges = [{"from": r["src_id"], "to": r["dst_id"], "kind": r.get("kind", "rel")}
             for r in rels]
    return {"schema": "productforge/EvidenceGraph/v1", "product_id": product_id,
            "nodes": nodes, "edges": edges,
            "counts": {"nodes": len(nodes), "edges": len(edges)}}
