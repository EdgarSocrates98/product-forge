"""Spec: inter-forge-delegation — own delegate mechanism (subprocess+JSON)."""

import pytest


def _store(tmp_path, monkeypatch):
    monkeypatch.setenv("PRODUCT_FORGE_HOME", str(tmp_path / "pf"))
    from product_forge.config import db_path, home_dir, load_config
    from product_forge.store.sqlite import Store

    home = home_dir("user")
    (home / "state" / "objects").mkdir(parents=True, exist_ok=True)
    cfg = load_config(home)
    return Store(db_path(home, cfg)), cfg


def test_delegate_not_declared(tmp_path, monkeypatch):
    st, cfg = _store(tmp_path, monkeypatch)
    from product_forge.delegates.runner import call

    r = call(cfg, st, None, "ghost", "inventory")
    assert r["status"] == "unavailable" and r["reason"] == "delegate-not-declared"
    st.close()


def test_delegate_cli_not_found(tmp_path, monkeypatch):
    st, cfg = _store(tmp_path, monkeypatch)
    cfg["delegates"] = [{"id": "ds", "cli": "no-such-cli-xyz", "workflows": ["inventory"]}]
    from product_forge.delegates.catalog import catalog
    from product_forge.delegates.runner import call

    row = catalog(cfg)[0]
    assert row["status"] == "unavailable:cli-not-found"
    r = call(cfg, st, None, "ds", "inventory")
    assert r["status"] == "unavailable" and r["reason"] == "cli-not-found"
    st.close()


def test_delegate_call_success(tmp_path, monkeypatch):
    st, cfg = _store(tmp_path, monkeypatch)
    fake = tmp_path / "fake-forge"
    fake.write_text(
        "#!/usr/bin/env python3\n"
        "import json,sys\n"
        "assert sys.argv[1] == 'inventory'\n"
        "print(json.dumps({'forge':'data-sentinel','inventory':['table_a','table_b']}))\n")
    fake.chmod(0o755)
    cfg["delegates"] = [{"id": "ds", "cli": str(fake), "workflows": ["inventory"]}]
    from product_forge.delegates.runner import call

    r = call(cfg, st, "p1", "ds", "inventory", [])
    assert r["status"] == "ok" and r["result"]["forge"] == "data-sentinel"
    assert r["result"]["inventory"] == ["table_a", "table_b"]
    st.close()


def test_delegate_workflow_refused(tmp_path, monkeypatch):
    st, cfg = _store(tmp_path, monkeypatch)
    cfg["delegates"] = [{"id": "ds", "cli": "python3", "workflows": ["inventory"]}]
    from product_forge.delegates.runner import call

    r = call(cfg, st, None, "ds", "rm-everything")
    assert r["status"] == "refused" and r["reason"] == "workflow-not-allowed"
    assert r["allowed"] == ["inventory"]
    st.close()


def test_delegates_api(tmp_path, monkeypatch):
    pytest.importorskip("fastapi")
    monkeypatch.setenv("PRODUCT_FORGE_HOME", str(tmp_path / "pf"))
    from fastapi.testclient import TestClient

    from product_forge.api.app import create_app
    from product_forge.config import home_dir, load_config
    from product_forge.security import TokenStore

    home = home_dir("user")
    (home / "state" / "objects").mkdir(parents=True, exist_ok=True)
    cfg = load_config(home)
    cfg["delegates"] = [{"id": "ds", "cli": "no-such-cli", "workflows": ["inventory"]}]
    cfg_path = home / "config.json"
    import json
    merged = {**cfg, "delegates": cfg["delegates"]}
    cfg_path.write_text(json.dumps(merged))
    tok = TokenStore(home / str(cfg["api"]["token_file"])).token
    c = TestClient(create_app(home))
    h = {"Authorization": f"Bearer {tok}"}
    rows = c.get("/api/v1/delegates", headers=h).json()["data"]["delegates"]
    assert rows[0]["id"] == "ds" and rows[0]["status"] == "unavailable:cli-not-found"
    r = c.post("/api/v1/delegates/ghost/call", json={"workflow": "x"}, headers=h)
    assert r.json()["data"]["reason"] == "delegate-not-declared"
