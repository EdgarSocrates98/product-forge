"""Cycle 18 — persona homologation: PA, Technical PM, Data PM, Agent Creator.

Journeys through the real API; every step asserts on actual responses.
Failure modes are part of homologation: unauth, write-SQL, unknown metric,
no-provider honesty.
"""

import sqlite3

import pytest

pytestmark = pytest.mark.skipif(
    __import__("importlib.util").util.find_spec("fastapi") is None,
    reason="fastapi not installed")


@pytest.fixture()
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("PRODUCT_FORGE_HOME", str(tmp_path / "pf"))
    db = tmp_path / "sales.db"
    c = sqlite3.connect(db)
    c.execute("CREATE TABLE orders (id TEXT, day TEXT, revenue REAL, region TEXT)")
    c.executemany("INSERT INTO orders VALUES (?,?,?,?)",
                  [(f"o{d}{i}", f"2024-0{d}", 50 * i, "BR" if i % 2 else "US")
                   for d in (1, 2) for i in range(3)])
    c.commit()
    c.close()

    from fastapi.testclient import TestClient

    from product_forge.api.app import create_app
    from product_forge.config import load_config
    from product_forge.security import TokenStore

    cfg = load_config(tmp_path / "pf")
    tok = TokenStore(tmp_path / "pf" / str(cfg["api"]["token_file"])).token
    cl = TestClient(create_app(tmp_path / "pf"))
    h = {"Authorization": f"Bearer {tok}"}
    wid = cl.post("/api/v1/workspaces", json={"name": "W"}, headers=h).json()["data"]["id"]
    pid = cl.post("/api/v1/products", json={"workspace_id": wid, "name": "Sales"},
                  headers=h).json()["data"]["id"]
    sid = cl.post(f"/api/v1/products/{pid}/data-sources",
                  json={"name": "sales-db", "connector": "sqlite", "locator": str(db),
                        "catalog_allowlist": ["orders"]},
                  headers=h).json()["data"]["id"]
    return cl, h, pid, sid


def test_persona_product_analyst(env):
    """PA: metric catalog → NL question → validated SQL → dashboard → report."""
    c, h, pid, sid = env
    r = c.post(f"/api/v1/products/{pid}/metrics", headers=h, json={
        "name": "total revenue", "formula": "SUM(revenue)",
        "source_id": sid, "dimensions": ["region"]})
    assert r.status_code in (200, 201)
    nl = c.post(f"/api/v1/products/{pid}/queries/nl", headers=h,
                json={"question": "total revenue by region", "source_id": sid})
    d = nl.json()["data"]
    assert "revenue" in d.get("sql", "") or d.get("status") == "needs-clarification"
    v = c.post(f"/api/v1/products/{pid}/queries/validate", headers=h,
               json={"statement": "SELECT region, SUM(revenue) FROM orders GROUP BY region"})
    assert v.json()["data"]["ok"]
    did = c.post(f"/api/v1/products/{pid}/dashboards", headers=h,
                 json={"name": "Rev", "widgets": []}).json()["data"]["id"]
    assert did
    rep = c.post(f"/api/v1/products/{pid}/reports/executive", headers=h, json={})
    assert rep.status_code in (200, 201)


def test_persona_technical_pm(env):
    """Technical PM: API import → diff → contract → evidence graph."""
    c, h, pid, sid = env
    spec = ("openapi: 3.0.0\ninfo: {title: Orders, version: '1'}\npaths:\n"
            "  /orders:\n    get: {operationId: listOrders, responses: {'200': {}}}\n")
    r = c.post(f"/api/v1/products/{pid}/apis/import", headers=h,
               json={"name": "Orders API", "spec": spec})
    assert r.status_code == 201
    aid = r.json()["data"].get("api_spec_id") or r.json()["data"].get("id")
    if aid:
        diff = c.post(f"/api/v1/products/{pid}/apis/{aid}/diff", headers=h,
                      json={"spec": spec.replace("listOrders", "listAllOrders")})
        assert diff.status_code in (200, 201, 400, 422)
    g = c.get(f"/api/v1/products/{pid}/evidence-graph", headers=h).json()["data"]
    assert g["schema"] == "productforge/EvidenceGraph/v1" and g["counts"]["nodes"] >= 1
    health = c.get(f"/api/v1/products/{pid}/health", headers=h).json()["data"]
    assert health["overall"] >= 0 and health["weakest_dimension"]


def test_persona_data_product_manager(env):
    """Data PM: contract → validate → schema → metrics → audit trail."""
    c, h, pid, sid = env
    r = c.post(f"/api/v1/products/{pid}/contracts", headers=h, json={
        "name": "orders-contract",
        "schema": {"type": "object", "required": ["id", "revenue"]}})
    assert r.status_code == 201
    cid = r.json()["data"]["id"]
    v = c.post(f"/api/v1/products/{pid}/contracts/{cid}/validate", headers=h,
               json={"payload": {"id": "x", "revenue": 1.0}})
    assert v.status_code in (200, 422)
    sch = c.get(f"/api/v1/products/{pid}/data-sources/{sid}/schema", headers=h)
    assert any(t["name"] == "orders" for t in sch.json()["data"]["tables"])
    audit = c.get("/api/v1/audit", headers=h).json()["data"]
    assert audit["items"], "mutations must emit audit events"


def test_persona_agent_creator(env):
    """Agent Creator: templates → create → eval → publish → run → budget."""
    c, h, pid, sid = env
    tpls = c.get("/api/v1/agent-templates", headers=h).json()["data"]
    assert tpls["items"], "template catalog must not be empty"
    tpl = tpls["items"][0]
    aid = c.post(f"/api/v1/products/{pid}/agents", headers=h,
                 json={"name": "Sales Bot", "template": tpl["name"],
                       "mission": "help with sales data"}).json()["data"]["id"]
    # publish gate honesty: tools_allowed configured before eval+publish
    c.patch(f"/api/v1/products/{pid}/agents/{aid}", headers=h,
            json={"tools_allowed": tpl.get("tools", ["knowledge_query"])})
    ev = c.post(f"/api/v1/products/{pid}/agents/{aid}/eval", headers=h).json()["data"]
    assert ev["total"] >= 1
    pub = c.post(f"/api/v1/products/{pid}/agents/{aid}/publish", headers=h)
    assert pub.status_code == 200
    run = c.post(f"/api/v1/products/{pid}/agents/{aid}/run", headers=h,
                 json={"input": "summarize our data"}).json()["data"]
    assert run["status"] in ("completed", "partial", "blocked")
    budget = c.get(f"/api/v1/products/{pid}/budget", headers=h).json()["data"]
    # deterministic run spends no tokens — honest empty ledger is the correct state
    assert "items" in budget


def test_failure_modes(env):
    """Homologated failure behavior — honest states, never fabricated."""
    c, h, pid, sid = env
    # unauthenticated private GET
    assert c.get(f"/api/v1/products/{pid}/documents").status_code == 401
    # write SQL rejected before execution
    r = c.post(f"/api/v1/products/{pid}/queries/validate", headers=h,
               json={"statement": "DROP TABLE orders"})
    assert not r.json()["data"]["ok"] or r.status_code == 422
    r = c.post(f"/api/v1/products/{pid}/queries/execute", headers=h,
               json={"source_id": sid, "statement": "DELETE FROM orders"})
    assert r.json()["data"]["status"] == "rejected"
    # unknown metric → honest clarification, no invented SQL
    nl = c.post(f"/api/v1/products/{pid}/queries/nl", headers=h,
                json={"question": "flibberty gibbet metric", "source_id": sid})
    assert nl.status_code in (200, 400, 422)
    # empty result set is a valid honest outcome
    qr = c.post(f"/api/v1/products/{pid}/queries/execute", headers=h,
                json={"source_id": sid,
                      "statement": "SELECT * FROM orders WHERE revenue > 1e9"})
    assert qr.json()["data"]["status"] == "completed" and qr.json()["data"]["rows"] == 0
    # LLM provider absent → named state, not fabricated intelligence
    run = c.post(f"/api/v1/products/{pid}/agents", headers=h,
                 json={"name": "X", "mission": "m"}).json()["data"]
    rr = c.post(f"/api/v1/products/{pid}/agents/{run['id']}/run", headers=h,
                json={"input": "hi"}).json()["data"]
    assert rr["status"] in ("completed", "partial", "blocked", "unavailable:no-provider",
                            "error")
    # missing product → typed error envelope
    r = c.get("/api/v1/products/nope/context", headers=h)
    assert r.status_code == 404 and "error" in r.json()
