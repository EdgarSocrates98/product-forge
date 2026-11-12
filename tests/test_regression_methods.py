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
            body = (
                resp.json() if resp.headers.get("content-type", "").startswith("application/json") else None
            )
            if not _envelope_ok(body):
                misses.append(f"{m} {path} -> {resp.status_code}")
            elif path == "/api/v1/health":
                continue  # documented public route
            elif resp.status_code != 401:
                # unauthenticated call on a private route must be denied
                misses.append(f"{m} {path} -> expected 401, got {resp.status_code}")
    assert not misses, f"{len(misses)} violations: {misses[:12]}"


def test_health_is_public_enveloped(client):
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    assert _envelope_ok(resp.json())
    assert resp.json()["data"]["status"] == "healthy"


def test_task_board_persists_move_and_comment(tmp_path):
    from product_forge.config import load_config
    from product_forge.security import TokenStore

    app = create_app(home=tmp_path)
    client = TestClient(app)
    cfg = load_config(tmp_path)
    token = TokenStore(tmp_path / str(cfg["api"]["token_file"])).token
    headers = {"Authorization": f"Bearer {token}"}
    wid = client.post("/api/v1/workspaces", json={"name": "Tasks"}, headers=headers).json()["data"]["id"]
    pid = client.post(
        "/api/v1/products", json={"workspace_id": wid, "name": "Planner"}, headers=headers
    ).json()["data"]["id"]
    created = client.post(f"/api/v1/products/{pid}/tasks", json={"title": "Ship board"}, headers=headers)
    assert created.status_code == 201
    task = created.json()["data"]
    assert task["workspace_id"] == wid and task["board_id"]
    moved = client.post(
        f"/api/v1/products/{pid}/tasks/{task['id']}/move",
        json={"column_id": "doing", "position": 0},
        headers=headers,
    )
    assert moved.status_code == 200
    comment = client.post(
        f"/api/v1/products/{pid}/tasks/{task['id']}/comments",
        json={"text": "Ready for review"},
        headers=headers,
    )
    assert comment.status_code == 201
    board = client.get(f"/api/v1/products/{pid}/board", headers=headers).json()["data"]
    refreshed = next(item for item in board["tasks"] if item["id"] == task["id"])
    assert refreshed["column_id"] == "doing"
    assert refreshed["comments"][0]["text"] == "Ready for review"


def test_chat_task_proposal_requires_approval_and_is_idempotent(tmp_path):
    from product_forge.config import load_config
    from product_forge.security import TokenStore

    client = TestClient(create_app(home=tmp_path))
    cfg = load_config(tmp_path)
    token = TokenStore(tmp_path / str(cfg["api"]["token_file"])).token
    headers = {"Authorization": f"Bearer {token}"}
    wid = client.post("/api/v1/workspaces", json={"name": "Proposals"}, headers=headers).json()["data"]["id"]
    pid = client.post(
        "/api/v1/products", json={"workspace_id": wid, "name": "Chat PM"}, headers=headers
    ).json()["data"]["id"]
    payload = {
        "source": "chat",
        "session_id": "ses_1",
        "idempotency_key": "msg_1",
        "tasks": [{"title": "Validate onboarding", "priority": "high"}],
    }
    first = client.post(f"/api/v1/products/{pid}/task-proposals", json=payload, headers=headers)
    assert first.status_code == 201
    proposal = first.json()["data"]
    assert proposal["state"] == "proposed"
    assert client.get(f"/api/v1/products/{pid}/tasks", headers=headers).json()["data"]["items"] == []
    approved = client.post(
        f"/api/v1/products/{pid}/task-proposals/{proposal['id']}/approve",
        json={
            "approved": True,
            "tasks": [
                {
                    "title": "Validate onboarding copy",
                    "description": "Review the welcome flow",
                    "priority": "low",
                }
            ],
        },
        headers=headers,
    )
    assert approved.status_code == 200 and approved.json()["data"]["state"] == "approved"
    retry = client.post(
        f"/api/v1/products/{pid}/task-proposals/{proposal['id']}/approve",
        json={"approved": True},
        headers=headers,
    )
    assert retry.status_code == 200
    tasks = client.get(f"/api/v1/products/{pid}/tasks", headers=headers).json()["data"]["items"]
    assert len(tasks) == 1
    assert tasks[0]["title"] == "Validate onboarding copy"
    assert tasks[0]["description"] == "Review the welcome flow"
    assert tasks[0]["priority"] == "low"


def test_authenticated_route_error_matrix_is_enveloped(tmp_path):
    from product_forge.config import load_config
    from product_forge.security import TokenStore

    app = create_app(home=tmp_path)
    client = TestClient(app)
    cfg = load_config(tmp_path)
    token = TokenStore(tmp_path / str(cfg["api"]["token_file"])).token
    headers = {"Authorization": f"Bearer {token}"}
    wid = client.post("/api/v1/workspaces", json={"name": "Matrix"}, headers=headers).json()["data"]["id"]
    pid = client.post(
        "/api/v1/products", json={"workspace_id": wid, "name": "Matrix Product"}, headers=headers
    ).json()["data"]["id"]

    skipped = {"/api/v1/auth/rotate", "/api/v1/auth/revoke", "/api/v1/products/{pid}/cloud/inventory"}
    failures = []
    for route in client.app.routes:
        path = str(getattr(route, "path", ""))
        if not path.startswith("/api/v1") or path in skipped:
            continue
        concrete = path.replace("{pid}", pid)
        concrete = concrete.replace("{", "missing-").replace("}", "")
        for method in sorted(getattr(route, "methods", set()) or set()):
            if method not in {"GET", "POST", "PATCH", "DELETE"} or path == "/api/v1/health":
                continue
            response = client.request(method, concrete, json={}, headers=headers)
            body = response.json()
            code = str(body.get("error", {}).get("code", "PF-OK"))
            if not _envelope_ok(body) or not code.startswith("PF-"):
                failures.append(f"{method} {path}: {response.status_code} {body}")
    assert not failures, failures[:10]


def test_rate_limit_is_enveloped(tmp_path):
    import time

    from product_forge.api import app as app_module

    app = create_app(home=tmp_path)
    client = TestClient(app)
    app.state.ctx._req.append(time.time() - app_module.RATE_WINDOW - 1)
    app.state.ctx._req.extend([time.time()] * app_module.RATE_LIMIT)
    response = client.get("/api/v1/products")
    assert response.status_code == 429
    assert response.json()["error"]["code"] == "PF-RATE-LIMIT"
    assert (
        app_module._principal_allows({"principals": [{"token": "other", "workspaces": ["w"]}]}, "token", "w")
        is False
    )


def test_terminal_job_rejects_invalid_transition(tmp_path):
    from product_forge.config import load_config
    from product_forge.security import TokenStore

    app = create_app(home=tmp_path)
    client = TestClient(app)
    cfg = load_config(tmp_path)
    token = TokenStore(tmp_path / str(cfg["api"]["token_file"])).token
    headers = {"Authorization": f"Bearer {token}"}

    created = client.post(
        "/api/v1/jobs",
        json={"kind": "unknown", "payload": {}},
        headers=headers,
    )
    assert created.status_code == 200
    job_id = created.json()["data"]["id"]

    drained = client.post("/api/v1/jobs/drain", headers=headers)
    assert drained.status_code == 200
    assert drained.json()["data"]["ran"][0]["status"] == "dead_letter"

    cancelled = client.post(f"/api/v1/jobs/{job_id}/cancel", headers=headers)
    assert cancelled.status_code == 409
    assert cancelled.json()["error"]["code"] == "PF-CONFLICT"


def test_expired_job_reaches_terminal_state(tmp_path):
    from product_forge.config import load_config
    from product_forge.security import TokenStore

    client = TestClient(create_app(home=tmp_path))
    cfg = load_config(tmp_path)
    token = TokenStore(tmp_path / str(cfg["api"]["token_file"])).token
    headers = {"Authorization": f"Bearer {token}"}
    job = client.post(
        "/api/v1/jobs",
        json={"kind": "known-later", "expires_at": "2000-01-01T00:00:00.000Z"},
        headers=headers,
    ).json()["data"]
    polled = client.get("/api/v1/jobs", params={"status": "expired"}, headers=headers)
    assert polled.status_code == 200
    assert any(
        item["id"] == job["id"] and item["status"] == "expired" for item in polled.json()["data"]["items"]
    )


def test_core_domain_mutation_round_trips(tmp_path):
    import sqlite3

    from product_forge.config import load_config
    from product_forge.security import TokenStore

    client = TestClient(create_app(home=tmp_path))
    cfg = load_config(tmp_path)
    token = TokenStore(tmp_path / str(cfg["api"]["token_file"])).token
    headers = {"Authorization": f"Bearer {token}"}

    wid = client.post("/api/v1/workspaces", json={"name": "Regression"}, headers=headers).json()["data"]["id"]
    product = client.post(
        "/api/v1/products", json={"workspace_id": wid, "name": "Original"}, headers=headers
    ).json()["data"]
    pid = product["id"]

    updated = client.patch(f"/api/v1/products/{pid}", json={"name": "Updated"}, headers=headers)
    assert updated.status_code == 200 and updated.json()["data"]["name"] == "Updated"
    assert client.get(f"/api/v1/products/{pid}", headers=headers).json()["data"]["name"] == "Updated"
    assert client.patch(f"/api/v1/products/{pid}", json={}, headers=headers).status_code == 422

    source = client.post(
        f"/api/v1/products/{pid}/sources",
        json={"name": "Notes", "type": "markdown", "locator": "notes.md"},
        headers=headers,
    ).json()["data"]
    sid = source["id"]
    assert client.get(f"/api/v1/products/{pid}/sources/{sid}", headers=headers).json()["data"]["id"] == sid
    assert (
        client.patch(
            f"/api/v1/products/{pid}/sources/{sid}", json={"name": "Updated notes"}, headers=headers
        ).json()["data"]["name"]
        == "Updated notes"
    )
    assert client.patch(f"/api/v1/products/{pid}/sources/{sid}", json={}, headers=headers).status_code == 422
    assert client.delete(f"/api/v1/products/{pid}/sources/{sid}", headers=headers).json()["data"]["deleted"]
    assert client.get(f"/api/v1/products/{pid}/sources/{sid}", headers=headers).status_code == 404

    agent = client.post(f"/api/v1/products/{pid}/agents", json={"name": "Analyst"}, headers=headers).json()[
        "data"
    ]
    aid = agent["id"]
    assert (
        client.patch(
            f"/api/v1/products/{pid}/agents/{aid}", json={"mission": "Answer clearly"}, headers=headers
        ).json()["data"]["mission"]
        == "Answer clearly"
    )
    assert client.delete(f"/api/v1/products/{pid}/agents/{aid}", headers=headers).status_code == 200

    dashboard = client.post(
        f"/api/v1/products/{pid}/dashboards", json={"name": "Overview"}, headers=headers
    ).json()["data"]
    did = dashboard["id"]
    assert (
        client.patch(
            f"/api/v1/products/{pid}/dashboards/{did}", json={"description": "Updated"}, headers=headers
        ).json()["data"]["description"]
        == "Updated"
    )
    assert client.delete(f"/api/v1/products/{pid}/dashboards/{did}", headers=headers).status_code == 200

    initiative = client.post(
        f"/api/v1/products/{pid}/initiatives", json={"title": "Plan"}, headers=headers
    ).json()["data"]
    iid = initiative["id"]
    assert (
        client.patch(
            f"/api/v1/products/{pid}/initiatives/{iid}", json={"title": "Updated plan"}, headers=headers
        ).json()["data"]["title"]
        == "Updated plan"
    )
    assert client.delete(f"/api/v1/products/{pid}/initiatives/{iid}", headers=headers).status_code == 200

    db = tmp_path / "queries.db"
    with sqlite3.connect(db) as conn:
        conn.execute("create table facts (value integer)")
        conn.execute("insert into facts values (1)")
    data_source = client.post(
        f"/api/v1/products/{pid}/data-sources",
        json={"name": "Query DB", "connector": "sqlite", "locator": str(db)},
        headers=headers,
    ).json()["data"]["id"]
    query = client.post(
        f"/api/v1/products/{pid}/queries/execute",
        json={"source_id": data_source, "statement": "select * from facts"},
        headers=headers,
    ).json()["data"]
    qid = query["id"]
    assert client.get(f"/api/v1/products/{pid}/queries/{qid}", headers=headers).json()["data"]["id"] == qid
    assert (
        client.patch(
            f"/api/v1/products/{pid}/queries/{qid}", json={"truncated": True}, headers=headers
        ).json()["data"]["truncated"]
        is True
    )
    assert client.patch(f"/api/v1/products/{pid}/queries/{qid}", json={}, headers=headers).status_code == 422
    assert client.delete(f"/api/v1/products/{pid}/queries/{qid}", headers=headers).json()["data"]["deleted"]
    assert client.get(f"/api/v1/products/{pid}/queries/{qid}", headers=headers).status_code == 404

    assert client.delete(f"/api/v1/products/{pid}", headers=headers).json()["data"]["deleted"]
    assert client.get(f"/api/v1/products/{pid}", headers=headers).status_code == 404
