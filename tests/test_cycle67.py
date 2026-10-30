"""Cycles 6-7: dashboard rendering + planning (prioritize, PRD, roadmap)."""

import sqlite3

import pytest


@pytest.fixture()
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("PRODUCT_FORGE_HOME", str(tmp_path / "pfhome"))
    return tmp_path / "pfhome"


@pytest.fixture()
def dbfile(tmp_path):
    p = tmp_path / "d.db"
    c = sqlite3.connect(p)
    c.execute("CREATE TABLE errors (day TEXT, code TEXT, n INT)")
    c.executemany("INSERT INTO errors VALUES (?,?,?)",
                  [("2024-01", "E42", 5), ("2024-02", "E42", 12), ("2024-02", "E99", 3)])
    c.commit()
    c.close()
    return p


def _seed(home, dbfile):
    from product_forge.config import db_path, load_config
    from product_forge.domain.models import ConnectorType, DataSource
    from product_forge.store.sqlite import Store

    st = Store(db_path(home, load_config(home)))
    st.put("data_sources", DataSource(id="src_d", product_id="prd_d", name="db",
                                      connector=ConnectorType.SQLITE, locator=str(dbfile)))
    return st


def test_dashboard_render_real_data(home, dbfile):
    from product_forge.dashboards.render import render_dashboard

    st = _seed(home, dbfile)
    dash = {"id": "d1", "name": "Errors", "widgets": [
        {"id": "w1", "type": "kpi_card", "title": "Total errors", "source_id": "src_d",
         "spec": {"table": "errors", "aggregate": {"fn": "sum", "column": "n"}}},
        {"id": "w2", "type": "bar_chart", "title": "By day", "source_id": "src_d",
         "statement": "SELECT day, sum(n) FROM errors GROUP BY day"},
        {"id": "w3", "type": "table", "title": "bad widget"},
    ]}
    r = render_dashboard(st, "prd_d", dash)
    assert r["stats"]["ok"] == 2 and r["stats"]["unavailable"] == 1
    kpi = next(w for w in r["widgets"] if w["id"] == "w1")
    assert kpi["state"] == "ok" and kpi["data"]["value"] == 20
    chart = next(w for w in r["widgets"] if w["id"] == "w2")
    assert chart["data"]["labels"] == ["2024-01", "2024-02"]
    st.close()


def test_prioritize_and_roadmap(home):
    from product_forge.config import db_path, load_config
    from product_forge.domain.models import Initiative
    from product_forge.planning.prioritize import score_initiative
    from product_forge.planning.roadmap import build_roadmap
    from product_forge.store.sqlite import Store

    st = Store(db_path(home, load_config(home)))
    ini = Initiative(id="ini_1", product_id="prd_p", title="Reduce E42",
                     status="prioritized")
    st.put("initiatives", ini)
    res = score_initiative(ini.model_dump(),
                           {"rice": {"reach": 1000, "impact": 2, "confidence": 80, "effort": 4}})
    assert res["score"] == 400.0
    rm = build_roadmap(st, "prd_p")
    assert rm["lanes"]["next"][0]["title"] == "Reduce E42"
    st.close()


def test_prd_generation(home):
    from product_forge.config import db_path, load_config
    from product_forge.domain.models import Product, Workspace
    from product_forge.planning.prd import generate_prd
    from product_forge.store.sqlite import Store

    st = Store(db_path(home, load_config(home)))
    st.put("workspaces", Workspace(id="ws_p", name="W"))
    st.put("products", Product(id="prd_p", workspace_id="ws_p", name="Pay"))
    ini = {"id": "i1", "product_id": "prd_p", "title": "Fix retries",
           "hypothesis": "exponential backoff cuts E42 by 30%", "status": "proposed",
           "evidence": ["chk_1", "chk_2"]}
    prd = generate_prd(st, "prd_p", ini)
    assert "exponential backoff" in prd["markdown"] and len(prd["evidence"]) == 2
    st.close()


def test_api_dashboard_planning(home, dbfile):
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    from product_forge.api.app import create_app
    from product_forge.config import load_config
    from product_forge.security import TokenStore

    cfg = load_config(home)
    tok = TokenStore(home / str(cfg["api"]["token_file"])).token
    c = TestClient(create_app(home))
    h = {"Authorization": f"Bearer {tok}"}
    wid = c.post("/api/v1/workspaces", json={"name": "W"}, headers=h).json()["data"]["id"]
    pid = c.post("/api/v1/products", json={"workspace_id": wid, "name": "P"},
                 headers=h).json()["data"]["id"]
    sid = c.post(f"/api/v1/products/{pid}/data-sources",
                 json={"name": "db", "connector": "sqlite", "locator": str(dbfile)},
                 headers=h).json()["data"]["id"]
    did = c.post(f"/api/v1/products/{pid}/dashboards",
                 json={"name": "D", "widgets": [
                     {"id": "w", "type": "kpi_card", "source_id": sid,
                      "spec": {"table": "errors", "aggregate": {"fn": "sum", "column": "n"}}}]},
                 headers=h).json()["data"]["id"]
    r = c.post(f"/api/v1/products/{pid}/dashboards/{did}/render", headers=h)
    assert r.json()["data"]["widgets"][0]["data"]["value"] == 20
    iid = c.post(f"/api/v1/products/{pid}/initiatives",
                 json={"title": "I1"}, headers=h).json()["data"]["id"]
    r = c.post(f"/api/v1/products/{pid}/initiatives/{iid}/prioritize",
               json={"factors": {"wsjf": {"user_value": 8, "time_criticality": 5,
                                          "risk_reduction": 3, "job_size": 2}}}, headers=h)
    assert r.json()["data"]["methods"]["wsjf"]["score"] == 8.0
    r = c.get(f"/api/v1/products/{pid}/roadmap")
    assert r.json()["data"]["schema"] == "productforge/Roadmap/v1"
