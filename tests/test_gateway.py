"""Spec: llm-gateway-integration — contract + routing, provider via subprocess+JSON."""


import pytest


def test_synthesis_unavailable_without_provider(tmp_path, monkeypatch):
    monkeypatch.setenv("PRODUCT_FORGE_HOME", str(tmp_path / "pf"))
    from product_forge.config import db_path, home_dir, load_config
    from product_forge.gateway.synthesis import synthesize
    from product_forge.store.sqlite import Store

    home = home_dir("user")
    (home / "state" / "objects").mkdir(parents=True, exist_ok=True)
    st = Store(db_path(home, load_config(home)))
    r = synthesize(st, "p1", "q?", [], load_config(home))
    assert r["status"] == "unavailable" and r["reason"] == "no-provider-adapter"
    st.close()


def test_synthesis_with_provider_and_budget(tmp_path, monkeypatch):
    monkeypatch.setenv("PRODUCT_FORGE_HOME", str(tmp_path / "pf"))
    from product_forge.config import db_path, home_dir, load_config
    from product_forge.gateway.synthesis import synthesize
    from product_forge.store.sqlite import Store

    provider = tmp_path / "fake_provider.py"
    provider.write_text(
        "import json,sys\n"
        "req=json.loads(sys.stdin.read())\n"
        "print(json.dumps({'text':'answer grounded in '+str(len(req['citations']))+' citations',"
        " 'tokens_in':12,'tokens_out':34}))\n")
    home = home_dir("user")
    (home / "state" / "objects").mkdir(parents=True, exist_ok=True)
    cfg = load_config(home)
    cfg["gateway"] = {"provider_cmd": ["python3", str(provider)], "timeout_s": 15}
    st = Store(db_path(home, cfg))
    r = synthesize(st, "p1", "why?", [{"chunk_id": "c1"}], cfg)
    assert r["status"] == "ok" and "answer grounded in 1 citations" in r["text"]
    day = __import__("product_forge.domain.models", fromlist=["utcnow"]).utcnow()[:10]
    led = st.get("budget_ledger", f"budget:p1:{day}")
    assert led["tokens_in"] == 12 and led["tokens_out"] == 34
    st.close()


def test_synthesis_provider_failure_is_error(tmp_path, monkeypatch):
    monkeypatch.setenv("PRODUCT_FORGE_HOME", str(tmp_path / "pf"))
    from product_forge.config import db_path, home_dir, load_config
    from product_forge.gateway.synthesis import synthesize
    from product_forge.store.sqlite import Store

    bad = tmp_path / "bad_provider.py"
    bad.write_text("import sys; sys.exit(2)")
    home = home_dir("user")
    (home / "state" / "objects").mkdir(parents=True, exist_ok=True)
    cfg = load_config(home)
    cfg["gateway"] = {"provider_cmd": ["python3", str(bad)], "timeout_s": 10}
    st = Store(db_path(home, cfg))
    r = synthesize(st, "p1", "q?", [], cfg)
    assert r["status"] == "error"
    # no budget recorded for a failed call
    from product_forge.errors import NotFoundError
    with pytest.raises(NotFoundError):
        st.get("budget_ledger", "budget:p1:1970-01-01")
    st.close()


def test_kn_query_gateway_states(tmp_path, monkeypatch):
    pytest.importorskip("fastapi")
    monkeypatch.setenv("PRODUCT_FORGE_HOME", str(tmp_path / "pf"))
    from fastapi.testclient import TestClient

    from product_forge.api.app import create_app
    from product_forge.config import home_dir, load_config
    from product_forge.security import TokenStore

    home = home_dir("user")
    (home / "state" / "objects").mkdir(parents=True, exist_ok=True)
    cfg = load_config(home)
    tok = TokenStore(home / str(cfg["api"]["token_file"])).token
    c = TestClient(create_app(home))
    h = {"Authorization": f"Bearer {tok}"}
    wid = c.post("/api/v1/workspaces", json={"name": "W"}, headers=h).json()["data"]["id"]
    pid = c.post("/api/v1/products", json={"workspace_id": wid, "name": "P"},
                 headers=h).json()["data"]["id"]
    r = c.post(f"/api/v1/products/{pid}/knowledge/query",
               json={"question": "anything"}, headers=h).json()["data"]
    assert r["synthesis"] == "unavailable:no-provider-adapter"
    assert r["answer"] is None
