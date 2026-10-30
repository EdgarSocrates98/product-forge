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
