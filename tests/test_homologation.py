"""Cycle 12 homologation — Payments Product Intelligence (30 steps).

Full user journey through the real API: workspace → product → docs →
api spec → data source → knowledge → graph → agent → evals → publish →
analytics → dashboard → planning → ops → audit trail. No mocks.
"""

import sqlite3

import pytest

pytestmark = pytest.mark.skipif(
    __import__("importlib.util").util.find_spec("fastapi") is None,
    reason="fastapi not installed")

DOC = """# Payments Service

GET /api/v1/charges processes card charges. POST /api/v1/refunds issues refunds.
Table payments.transactions stores every charge. Metric: error rate (target < 5%).
Owner: Payments Team. Retry policy: exponential backoff, 5 attempts.
Error codes: E42 (insufficient funds), E99 (processor timeout).
"""

OPENAPI = """
openapi: 3.0.0
info: {title: Payments API, version: "1.0"}
paths:
  /charges:
    post: {operationId: createCharge, requestBody: {required: true}, responses: {"201": {}, "402": {}}}
  /refunds:
    post: {operationId: createRefund, responses: {"201": {}}}
components:
  schemas:
    Charge: {type: object, required: [id, amount], properties: {id: {}, amount: {}}}
"""


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("PRODUCT_FORGE_HOME", str(tmp_path / "pf"))
    db = tmp_path / "pay.db"
    c = sqlite3.connect(db)
    c.execute("CREATE TABLE transactions (id TEXT, day TEXT, amount REAL, error_code TEXT)")
    rows = [(f"t{i}", f"2024-0{m}", 10.0 * i, "E42" if i % 3 == 0 else None)
            for i, m in enumerate(range(1, 4) for _ in range(0))]
    rows = [(f"t{d}_{i}", f"2024-0{d}", 100 + i, "E42" if d == 3 else None)
            for d in (1, 2, 3) for i in range(3)]
    c.executemany("INSERT INTO transactions VALUES (?,?,?,?)", rows)
    c.commit()
    c.close()

    from fastapi.testclient import TestClient

    from product_forge.api.app import create_app
    from product_forge.config import load_config
    from product_forge.security import TokenStore

    cfg = load_config(tmp_path / "pf")
    tok = TokenStore(tmp_path / "pf" / str(cfg["api"]["token_file"])).token
    cl = TestClient(create_app(tmp_path / "pf"))
    return cl, {"Authorization": f"Bearer {tok}"}, db


def test_payments_product_intelligence(client):
    c, h, db = client
    steps = []

    def step(n, ok=True):
        steps.append((n, ok))
        assert ok, f"step {n} failed"

    # 1-2 workspace + product
    wid = c.post("/api/v1/workspaces", json={"name": "Acme Pay"}, headers=h).json()["data"]["id"]
    step(1, bool(wid))
    pid = c.post("/api/v1/products", json={"workspace_id": wid, "name": "Payments",
                                           "domain": "fintech", "tags": ["payments"]},
                 headers=h).json()["data"]["id"]
    step(2, bool(pid))

    # 3 import documentation
    r = c.post(f"/api/v1/products/{pid}/documents",
               json={"title": "payments.md", "content": DOC}, headers=h)
    step(3, r.status_code == 201 and r.json()["data"]["chunk_count"] > 0)

    # 4 connect API spec + data source
    r = c.post(f"/api/v1/products/{pid}/apis/import",
               json={"name": "Payments API", "spec": OPENAPI}, headers=h)
    step(4, r.status_code == 201 and r.json()["data"]["entities_created"] == 2)
    sid = c.post(f"/api/v1/products/{pid}/data-sources",
                 json={"name": "pay-db", "connector": "sqlite", "locator": str(db)},
                 headers=h).json()["data"]["id"]
    step(5, bool(sid))
    step(6, c.post(f"/api/v1/products/{pid}/data-sources/{sid}/verify",
                   headers=h).json()["data"]["status"] == "healthy")
    step(7, any(t["name"] == "transactions" for t in
                c.get(f"/api/v1/products/{pid}/data-sources/{sid}/schema", headers=h)
                .json()["data"]["tables"]))

    # 8-9 index knowledge + grounded answer with citations
    r = c.post(f"/api/v1/products/{pid}/knowledge/query",
               json={"question": "what is error code E42?"}, headers=h)
    step(8, len(r.json()["data"]["citations"]) > 0)
    r = c.post(f"/api/v1/products/{pid}/knowledge/extract", headers=h)
    step(9, r.json()["data"]["entities"] > 0)

    # 10-11 context package + navigable graph
    ctx = c.get(f"/api/v1/products/{pid}/context", headers=h).json()["data"]
    step(10, ctx["schema"] == "productforge/ProductContextPackage/v1"
         and len(ctx["entities"]) >= 2)
    g = c.get(f"/api/v1/products/{pid}/graph", headers=h).json()["data"]
    step(11, g["stats"]["nodes"] >= 4 and g["stats"]["edges"] >= 4)

    # 12-15 agent: create, configure, eval, publish
    aid = c.post(f"/api/v1/products/{pid}/agents",
                 json={"name": "Payments Analyst", "template": "product-analyst",
                       "mission": "answer questions about payments"},
                 headers=h).json()["data"]["id"]
    step(12, bool(aid))
    r = c.patch(f"/api/v1/products/{pid}/agents/{aid}",
                json={"tools_allowed": ["knowledge_query", "entities", "graph_lookup"],
                      "knowledge_scope": [sid]}, headers=h)
    step(13, r.status_code == 200)
    ev = c.post(f"/api/v1/products/{pid}/agents/{aid}/eval", headers=h).json()["data"]
    step(14, ev["total"] == 2 and ev["passed"] >= 1)
    r = c.post(f"/api/v1/products/{pid}/agents/{aid}/publish", headers=h)
    step(15, r.status_code == 200 and r.json()["data"]["status"] == "published")

    # 16-18 ask about error-rate growth → explainable query → review → execute
    run = c.post(f"/api/v1/products/{pid}/agents/{aid}/run",
                 json={"input": "why did the error rate grow in March?"},
                 headers=h).json()["data"]
    step(16, run["status"] == "completed" and run["output"]["grounded"])
    v = c.post(f"/api/v1/products/{pid}/queries/validate",
               json={"statement": "SELECT day, count(*) FROM transactions "
                                  "WHERE error_code = 'E42' GROUP BY day"},
               headers=h).json()["data"]
    step(17, v["ok"])
    qr = c.post(f"/api/v1/products/{pid}/queries/execute",
                json={"source_id": sid,
                      "statement": "SELECT day, count(*) AS n FROM transactions "
                                   "WHERE error_code = 'E42' GROUP BY day"},
                headers=h).json()["data"]
    step(18, qr["status"] == "completed" and qr["rows"] == 1)

    # 19-20 dashboard from real data
    did = c.post(f"/api/v1/products/{pid}/dashboards",
                 json={"name": "Error Monitoring", "widgets": [
                     {"id": "k", "type": "kpi_card", "title": "E42 total",
                      "source_id": sid,
                      "spec": {"table": "transactions",
                               "aggregate": {"fn": "count"},
                               "filters": [{"column": "error_code", "op": "=",
                                            "value": "E42"}]}},
                     {"id": "t", "type": "bar_chart", "title": "by day",
                      "source_id": sid,
                      "statement": "SELECT day, count(*) FROM transactions GROUP BY day"}]},
                 headers=h).json()["data"]["id"]
    dr = c.post(f"/api/v1/products/{pid}/dashboards/{did}/render", headers=h).json()["data"]
    step(19, dr["stats"]["ok"] == 2)
    step(20, dr["widgets"][0]["data"]["value"] == 3)

    # 21-25 opportunity → hypothesis → initiative → PRD → prioritize → roadmap
    iid = c.post(f"/api/v1/products/{pid}/initiatives",
                 json={"title": "Reduce E42 errors",
                       "hypothesis": "retry with backoff cuts E42 by 30%"},
                 headers=h).json()["data"]["id"]
    step(21, bool(iid))
    prd = c.post(f"/api/v1/products/{pid}/initiatives/{iid}/prd",
                 headers=h).json()["data"]
    step(22, "backoff" in prd["markdown"])
    r = c.post(f"/api/v1/products/{pid}/initiatives/{iid}/prioritize",
               json={"factors": {"rice": {"reach": 5000, "impact": 2,
                                          "confidence": 70, "effort": 3}}},
               headers=h)
    step(23, r.json()["data"]["score"] > 2000)
    rm = c.get(f"/api/v1/products/{pid}/roadmap", headers=h).json()["data"]
    step(24, any(x["id"] == iid for x in rm["lanes"]["later"]))
    dec = c.post(f"/api/v1/products/{pid}/decisions",
                 json={"title": "Adopt retry-with-backoff",
                       "decision": "implement exponential backoff for E42",
                       "alternatives": ["fixed delay", "no retry"]},
                 headers=h)
    step(25, dec.status_code == 201)

    # 26-27 contract validation + impact analysis
    cid = c.post(f"/api/v1/products/{pid}/contracts",
                 json={"name": "charge", "fields": [
                     {"name": "id", "type": "string", "required": True},
                     {"name": "amount", "type": "number", "required": True}]},
                 headers=h).json()["data"]["id"]
    v = c.post(f"/api/v1/products/{pid}/contracts/{cid}/validate",
               json={"payload": {"id": "c1", "amount": 10.5}}, headers=h).json()["data"]
    step(26, v["valid"])
    api_ent = next(e for e in ctx["entities"] if e["kind"] == "api")
    imp = c.get(f"/api/v1/products/{pid}/impact/{api_ent['id']}", headers=h).json()["data"]
    step(27, imp["schema"] == "productforge/ImpactAnalysis/v1")

    # 28 executive report
    rep = c.post(f"/api/v1/products/{pid}/reports/executive", headers=h).json()["data"]
    step(28, "Executive Report — Payments" in rep["markdown"])

    # 29 monitoring watch (breach detection configured)
    wid2 = c.post(f"/api/v1/products/{pid}/watches",
                  json={"name": "e42-count", "source_id": sid,
                        "statement": "SELECT count(*) FROM transactions WHERE error_code='E42'",
                        "op": ">", "value": 2, "interval_s": 0},
                  headers=h).json()["data"]["id"]
    wr = c.post(f"/api/v1/products/{pid}/watches/{wid2}/run", headers=h).json()["data"]
    step(29, wr["breached"] and wr["alert_id"])

    # 30 audit trail covers the journey
    audit = c.get("/api/v1/audit", params={"product_id": pid}, headers=h).json()["data"]["items"]
    actions = {a["action"] for a in audit}
    step(30, {"product.create", "agent.publish", "query.execute",
              "dashboard.render", "watch.run"} <= actions)

    print("\nHOMOLOGATION PASSED —", len(steps), "steps verified")
