"""Cycle 13 — security, persistence, delegate audit fixes."""

import pytest


def test_gets_require_auth(tmp_path, monkeypatch):
    pytest.importorskip("fastapi")
    monkeypatch.setenv("PRODUCT_FORGE_HOME", str(tmp_path / "pf"))
    from fastapi.testclient import TestClient

    from product_forge.api.app import create_app
    from product_forge.config import home_dir, load_config
    from product_forge.security import TokenStore

    home = home_dir("user")
    (home / "state" / "objects").mkdir(parents=True, exist_ok=True)
    tok = TokenStore(home / str(load_config(home)["api"]["token_file"])).token
    c = TestClient(create_app(home))
    # public
    assert c.get("/api/v1/health").status_code == 200
    # private GETs now require bearer (§3.2)
    for path in ("/api/v1/workspaces", "/api/v1/capabilities",
                 "/api/v1/delegates", "/api/v1/agent-templates"):
        assert c.get(path).status_code == 401, path
        assert c.get(path, headers={"Authorization": "Bearer wrong"}).status_code == 401
        assert c.get(path, headers={"Authorization": f"Bearer {tok}"}).status_code == 200


def test_security_headers(tmp_path, monkeypatch):
    pytest.importorskip("fastapi")
    monkeypatch.setenv("PRODUCT_FORGE_HOME", str(tmp_path / "pf"))
    from fastapi.testclient import TestClient

    from product_forge.api.app import create_app
    from product_forge.config import home_dir

    home = home_dir("user")
    (home / "state" / "objects").mkdir(parents=True, exist_ok=True)
    r = TestClient(create_app(home)).get("/api/v1/health")
    for h in ("x-content-type-options", "x-frame-options", "referrer-policy"):
        assert h in r.headers


def test_kql_dax_conservative():
    from product_forge.analytics.sqlvalidate import validate

    assert validate("T | summarize count() by bin(t,1h)", "kql").ok
    assert not validate("T; U | take 1", "kql").ok
    assert not validate(".drop table T", "kql").ok
    assert not validate("T | evaluate externaldata('x')", "kql").ok
    assert validate("T | take 5", "kql").engine == "kql-lite:unverified"
    assert validate("EVALUATE Sales", "dax").ok
    r = validate("DEFINE VAR x=1 EVALUATE x", "dax")
    assert not r.ok and "evaluate" in r.errors[0]


def test_migrations_and_backup(tmp_path, monkeypatch):
    monkeypatch.setenv("PRODUCT_FORGE_HOME", str(tmp_path / "pf"))
    from product_forge.config import db_path, home_dir, load_config
    from product_forge.domain.models import Product
    from product_forge.store.sqlite import Store

    home = home_dir("user")
    (home / "state" / "objects").mkdir(parents=True, exist_ok=True)
    st = Store(db_path(home, load_config(home)))
    assert st.migrate() == []  # already at SCHEMA_VERSION
    row = st._conn.execute("SELECT version FROM schema_migrations").fetchall()
    assert row and row[-1][0] == 2
    assert st._conn.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
    st.put("products", Product(id="p1", workspace_id="w1", name="X"))
    dest = st.backup(tmp_path / "bak.db")
    st.close()
    st2 = Store(dest)
    assert st2.integrity_check() and st2.get("products", "p1")["name"] == "X"
    st2.close()


def test_delegate_audit_ids_unique(tmp_path, monkeypatch):
    monkeypatch.setenv("PRODUCT_FORGE_HOME", str(tmp_path / "pf"))
    from product_forge.config import db_path, home_dir, load_config
    from product_forge.delegates.runner import call
    from product_forge.store.sqlite import Store

    fake = tmp_path / "fake"
    fake.write_text("#!/usr/bin/env python3\nimport json\nprint(json.dumps({'ok':1}))\n")
    fake.chmod(0o755)
    home = home_dir("user")
    (home / "state" / "objects").mkdir(parents=True, exist_ok=True)
    cfg = load_config(home)
    cfg["delegates"] = [{"id": "d", "cli": str(fake), "workflows": ["w"]}]
    st = Store(db_path(home, cfg))
    call(cfg, st, "p1", "d", "w")
    call(cfg, st, "p1", "d", "w")  # second call must NOT overwrite first audit
    rows = st._conn.execute(
        "SELECT id FROM entities WHERE collection='audit_events'").fetchall()
    assert len(rows) == 2 and rows[0][0] != rows[1][0]
    st.close()


def test_durable_jobs(tmp_path, monkeypatch):
    monkeypatch.setenv("PRODUCT_FORGE_HOME", str(tmp_path / "pf"))
    from product_forge.config import db_path, home_dir, load_config
    from product_forge.jobs.registry import JobRegistry
    from product_forge.store.sqlite import Store

    home = home_dir("user")
    (home / "state" / "objects").mkdir(parents=True, exist_ok=True)
    st = Store(db_path(home, load_config(home)))
    reg = JobRegistry(st)
    reg.register("echo", lambda p: {"echo": p["msg"]})
    j1 = reg.enqueue("echo", {"msg": "a"}, "p1", idempotency_key="k1")
    j2 = reg.enqueue("echo", {"msg": "b"}, "p1", idempotency_key="k1")
    assert j1["id"] == j2["id"]  # idempotent
    done = reg.run_next()
    assert done["status"] == "done"
    import json
    assert json.loads(done["result"])["echo"] == "a"
    # crash simulation: force a job to running, then recover
    st._conn.execute("UPDATE jobs SET status='running' WHERE id=?", (done["id"],))
    assert JobRegistry(st).recover() == 1
    assert st._conn.execute("SELECT status FROM jobs WHERE id=?",
                            (done["id"],)).fetchone()[0] == "queued"
    # handler that always fails → dead_letter after MAX_ATTEMPTS
    reg.register("boom", lambda p: 1 / 0)
    reg.enqueue("boom", {})
    last = None
    for _ in range(4):  # echo retry first, then 3 boom attempts
        job = reg.run_next()
        if job is not None:
            last = job
    assert last is not None and last["status"] == "dead_letter"
    st.close()


def test_rbac_workspace_scope(tmp_path, monkeypatch):
    pytest.importorskip("fastapi")
    monkeypatch.setenv("PRODUCT_FORGE_HOME", str(tmp_path / "pf"))
    from fastapi.testclient import TestClient

    from product_forge.api.app import create_app
    from product_forge.config import home_dir, load_config
    from product_forge.security import TokenStore

    home = home_dir("user")
    (home / "state" / "objects").mkdir(parents=True, exist_ok=True)
    cfg = load_config(home)
    admin = TokenStore(home / str(cfg["api"]["token_file"])).token
    cfg["principals"] = [{"token": admin, "role": "admin", "workspaces": []},
                         {"token": "viewer_tok", "role": "viewer", "workspaces": []}]
    (home / "config.json").write_text(__import__("json").dumps(cfg))
    c = TestClient(create_app(home))
    h_adm = {"Authorization": f"Bearer {admin}"}
    # admin creates workspace+product OUTSIDE its declared scope → also 403
    wid = c.post("/api/v1/workspaces", json={"name": "W"}, headers=h_adm).json()["data"]["id"]
    pid = c.post("/api/v1/products", json={"workspace_id": wid, "name": "P"},
                 headers=h_adm).json()["data"]["id"]
    # any product route is now outside both principals' workspace lists
    assert c.get(f"/api/v1/products/{pid}", headers=h_adm).status_code == 403
    # unknown-token principal → 401, not a scope leak
    assert c.get(f"/api/v1/products/{pid}").status_code == 401


def test_metrics_catalog_and_nl(tmp_path, monkeypatch):
    monkeypatch.setenv("PRODUCT_FORGE_HOME", str(tmp_path / "pf"))
    from product_forge.analytics.metrics import metric_sql, put_metric, resolve
    from product_forge.config import db_path, home_dir, load_config
    from product_forge.store.sqlite import Store

    home = home_dir("user")
    (home / "state" / "objects").mkdir(parents=True, exist_ok=True)
    st = Store(db_path(home, load_config(home)))
    put_metric(st, "p1", {"name": "monthly recurring revenue",
                          "formula": "SUM(mrr)", "source_id": "s1",
                          "dimensions": ["region"], "owner": "finops"})
    r = resolve(st, "p1", "show me monthly recurring revenue by region")
    assert r["status"] == "matched"
    sql = metric_sql(r["matched"][0]["metric"], "subscriptions")
    assert "SUM(mrr)" in sql and "GROUP BY region" in sql
    unknown = resolve(st, "p1", "how many widgets flew?")
    assert unknown["status"] == "unknown-metric"
    st.close()


def test_health_center_and_evidence_graph(tmp_path, monkeypatch):
    monkeypatch.setenv("PRODUCT_FORGE_HOME", str(tmp_path / "pf"))
    from product_forge.config import db_path, home_dir, load_config
    from product_forge.domain.models import Product
    from product_forge.intel.health import compute_health, evidence_graph
    from product_forge.store.sqlite import Store

    home = home_dir("user")
    (home / "state" / "objects").mkdir(parents=True, exist_ok=True)
    st = Store(db_path(home, load_config(home)))
    st.put("products", Product(id="p1", workspace_id="w1", name="X"))
    h = compute_health(st, "p1")
    assert h["schema"] == "productforge/ProductHealth/v1"
    assert set(h["dimensions"]) == {"value", "adoption", "experience",
                                    "reliability", "cost", "delivery",
                                    "knowledge", "risk"}
    # every score is explainable — evidence lists non-empty
    for d in h["dimensions"].values():
        assert d["evidence"], "score without provenance is forbidden"
    g = evidence_graph(st, "p1")
    assert g["counts"]["nodes"] >= 1 and g["schema"] == "productforge/EvidenceGraph/v1"
    st.close()
