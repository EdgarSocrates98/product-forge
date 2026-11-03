"""OIDC workspace claims must remain an explicit tenant boundary."""

from __future__ import annotations

import json

from fastapi.testclient import TestClient

from product_forge.api.app import create_app
from product_forge.domain.models import Product, Workspace
from product_forge.store.sqlite import Store


def test_oidc_claims_filter_lists_and_deny_cross_workspace(tmp_path, monkeypatch) -> None:
    home = tmp_path / "pf"
    home.mkdir()
    cfg = {
        "oidc": {
            "enabled": True,
            "issuer": "https://issuer.example",
            "audience": "product-forge",
            "jwks_url": "https://issuer.example/.well-known/jwks.json",
        }
    }
    (home / "config.json").write_text(json.dumps(cfg), encoding="utf-8")
    store = Store(home / "state" / "productforge.db")
    store.put("workspaces", Workspace(id="ws_allowed", name="Allowed"))
    store.put("workspaces", Workspace(id="ws_denied", name="Denied"))
    store.put("products", Product(id="prd_allowed", workspace_id="ws_allowed", name="Allowed"))
    store.put("products", Product(id="prd_denied", workspace_id="ws_denied", name="Denied"))
    store.close()

    def verify(token: str, _cfg: dict) -> dict:
        if token == "jwt-with-scope":  # noqa: S105 - test fixture token
            return {"sub": "user-1", "workspaces": ["ws_allowed"]}
        return {"sub": "user-2"}

    monkeypatch.setattr("product_forge.api.app.verify_oidc_token", verify)
    client = TestClient(create_app(home))
    scoped = {"Authorization": "Bearer jwt-with-scope"}
    workspaces = client.get("/api/v1/workspaces", headers=scoped).json()["data"]["items"]
    products = client.get("/api/v1/products", headers=scoped).json()["data"]["items"]
    assert [item["id"] for item in workspaces] == ["ws_allowed"]
    assert [item["id"] for item in products] == ["prd_allowed"]
    assert client.get("/api/v1/products/prd_denied", headers=scoped).status_code == 403
    assert client.get("/api/v1/workspaces/ws_denied", headers=scoped).status_code == 403

    without_scope = {"Authorization": "Bearer jwt-without-scope"}
    assert client.get("/api/v1/products/prd_allowed", headers=without_scope).status_code == 403
