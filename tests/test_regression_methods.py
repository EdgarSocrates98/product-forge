"""deep-regression-suite slice — parametric envelope+auth sweep across
every method of every /api/v1 route, plus negative paths."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from product_forge.api.app import create_app

METHODS = ("GET", "POST", "PUT", "PATCH", "DELETE")


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    return TestClient(create_app(home=tmp_path_factory.mktemp("pf")))


def _envelope_ok(body: object) -> bool:
    if not isinstance(body, dict):
        return False
    if body.get("schema") != "forge/PortalApi/1" or "correlation_id" not in body:
        return False
    if "data" not in body and "error" not in body:
        return False
    err = body.get("error")
    return err is None or str(err.get("code", "")).startswith("PF-")


def test_every_method_every_route_enveloped_unauthenticated(client):
    misses = []
    for r in client.app.routes:
        methods = getattr(r, "methods", None) or set()
        path = str(getattr(r, "path", ""))
        if not path.startswith("/api/v1"):
            continue
        for m in sorted(set(METHODS) & set(methods)):
            concrete = path.replace("{", "x-").replace("}", "")
            resp = client.request(m, concrete, json={})
            body = resp.json() if resp.headers.get(
                "content-type", "").startswith("application/json") else None
            if not _envelope_ok(body):
                misses.append(f"{m} {path} -> {resp.status_code}")
            elif path == "/api/v1/health":
                continue  # documented public route
            elif resp.status_code != 401:
                # unauthenticated call on a private route must be denied
                misses.append(f"{m} {path} -> expected 401, got "
                              f"{resp.status_code}")
    assert not misses, f"{len(misses)} violations: {misses[:12]}"


def test_health_is_public_enveloped(client):
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    assert _envelope_ok(resp.json())
    assert resp.json()["data"]["status"] == "healthy"
