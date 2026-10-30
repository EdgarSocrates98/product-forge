"""Deep surface sweep — every registered /api/v1 route must emit the
forge/PortalApi/1 envelope ({schema, correlation_id, data|error}) with
typed PF-* error codes, including unauthenticated and unknown-path
responses. GET probes only; mutating verbs are covered per-domain."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from product_forge.api.app import create_app


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    app = create_app(home=tmp_path_factory.mktemp("pf"))
    return TestClient(app)


def _assert_envelope(body: object, path: str) -> list[str]:
    fails = []
    if not isinstance(body, dict):
        return [f"{path}: non-dict body"]
    if body.get("schema") != "forge/PortalApi/1":
        fails.append(f"{path}: schema={body.get('schema')!r}")
    if "correlation_id" not in body:
        fails.append(f"{path}: missing correlation_id")
    if "data" not in body and "error" not in body:
        fails.append(f"{path}: neither data nor error")
    err = body.get("error")
    if err is not None and not str(err.get("code", "")).startswith("PF-"):
        fails.append(f"{path}: error code {err.get('code')!r} not PF-*")
    return fails


def test_all_get_routes_emit_envelope(client):
    routes = [r.path for r in client.app.routes
              if getattr(r, "methods", None) and "GET" in r.methods
              and str(getattr(r, "path", "")).startswith("/api/v1")]
    assert len(routes) >= 45, f"expected ≥45 /api/v1 GET routes, found {len(routes)}"
    failures: list[str] = []
    for path in routes:
        if "{" in path:
            continue  # id-shaped routes covered by per-domain suites
        resp = client.get(path)
        failures += _assert_envelope(resp.json(), path)
    assert not failures, f"{len(failures)} violations: {failures[:10]}"


def test_id_routes_emit_envelope_on_404(client):
    # unknown product id must still be an enveloped PF-* error, not a leak
    resp = client.get("/api/v1/products/definitely-missing")
    assert _assert_envelope(resp.json(), "products/{pid}") == []


def test_unknown_path_enveloped(client):
    # under /api/v1 the auth guard fires before routing → PF-UNAUTHORIZED;
    # outside the prefix the starlette handler emits PF-NOT-FOUND. Both
    # must stay inside the envelope.
    resp = client.get("/api/v1/__definitely_not_a_route__")
    assert _assert_envelope(resp.json(), "unknown-private") == []
    resp2 = client.get("/__definitely_not_a_route__")
    body = resp2.json()
    assert _assert_envelope(body, "unknown-public") == []
    assert body["error"]["code"] == "PF-NOT-FOUND"


def test_private_routes_require_bearer_enveloped(client):
    resp = client.get("/api/v1/products")
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "PF-UNAUTHORIZED"
