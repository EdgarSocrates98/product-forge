"""Cycle 30.2 — forge/ProductAgentSessionContext/v2 authorization API.

The server validates product/workspace existence and principal scope;
client-supplied ids are never trusted. Issued contexts are re-checkable
and revocable server-side.
"""

import pytest

pytestmark = pytest.mark.skipif(
    __import__("importlib.util").util.find_spec("fastapi") is None,
    reason="fastapi not installed")


@pytest.fixture()
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("PRODUCT_FORGE_HOME", str(tmp_path / "pf"))
    from fastapi.testclient import TestClient

    from product_forge.api.app import create_app
    from product_forge.config import load_config
    from product_forge.security import TokenStore

    cfg = load_config(tmp_path / "pf")
    tok = TokenStore(tmp_path / "pf" / str(cfg["api"]["token_file"])).token
    cl = TestClient(create_app(tmp_path / "pf"))
    h = {"Authorization": f"Bearer {tok}"}
    wid = cl.post("/api/v1/workspaces", json={"name": "W"}, headers=h) \
        .json()["data"]["id"]
    pid = cl.post("/api/v1/products",
                  json={"workspace_id": wid, "name": "Payments API"},
                  headers=h).json()["data"]["id"]
    return cl, h, wid, pid


def test_authorize_issues_v2_context(env):
    cl, h, wid, pid = env
    r = cl.post("/api/v1/context/authorize", headers=h, json={
        "principal": "edgar", "product_id": pid, "provider": "codex",
        "session_id": "ses_x"})
    assert r.status_code == 201
    d = r.json()["data"]
    assert d["schema"] == "forge/ProductAgentSessionContext/v2"
    assert d["workspace_id"] == wid
    assert d["product_id"] == pid
    assert d["state"] == "active"
    assert d["revocation_ref"] == d["id"]
    assert d["expires_at_ts"] > d["issued_at_ts"]
    # permissions are server-resolved, never client-supplied
    assert d["allowed_tools"] == ["chat"]


def test_authorize_unknown_product_404(env):
    cl, h, _, _ = env
    r = cl.post("/api/v1/context/authorize", headers=h,
                json={"product_id": "prd_nope"})
    assert r.status_code == 404


def test_authorize_workspace_mismatch(env):
    cl, h, _, pid = env
    r = cl.post("/api/v1/context/authorize", headers=h, json={
        "product_id": pid, "workspace_id": "wsp_other"})
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "PF-VALIDATION"


def test_authorize_requires_auth(env):
    cl, _, _, pid = env
    r = cl.post("/api/v1/context/authorize", json={"product_id": pid})
    assert r.status_code == 401


def test_get_and_revoke_state_machine(env):
    cl, h, _, pid = env
    cid = cl.post("/api/v1/context/authorize", headers=h,
                  json={"product_id": pid}).json()["data"]["id"]
    g = cl.get(f"/api/v1/context/{cid}", headers=h)
    assert g.json()["data"]["state"] == "active"
    r = cl.post(f"/api/v1/context/{cid}/revoke", headers=h)
    assert r.json()["data"]["state"] == "revoked"
    g2 = cl.get(f"/api/v1/context/{cid}", headers=h)
    assert g2.json()["data"]["state"] == "revoked"
    # unknown context → 404, never fabricated
    assert cl.get("/api/v1/context/ctx_nope", headers=h).status_code == 404


def test_expired_context_state(env):
    cl, h, _, pid = env
    r = cl.post("/api/v1/context/authorize", headers=h,
                json={"product_id": pid, "ttl_s": 60})
    d = r.json()["data"]
    # force expiry by rewriting the stored record
    from product_forge.config import load_config
    import pathlib
    # expired check is evaluated at read time; simulate by direct store edit
    ctx = cl.app.state.ctx
    rec = ctx.store.get("session_contexts", d["id"])
    rec["expires_at_ts"] = 1.0
    ctx.store.put_doc("session_contexts", rec)
    g = cl.get(f"/api/v1/context/{d['id']}", headers=h)
    assert g.json()["data"]["state"] == "expired"
