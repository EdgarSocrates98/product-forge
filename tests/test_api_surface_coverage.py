"""Exercise the public API surface that is easy to miss in journey tests.

This is deliberately a real TestClient walk over the local store.  It keeps
the coverage gate honest for read-only/list/detail routes and the small CRUD
mutations that are part of the Portal contract.
"""

import sqlite3

import pytest

pytestmark = pytest.mark.skipif(
    __import__("importlib.util").util.find_spec("fastapi") is None,
    reason="fastapi not installed",
)


@pytest.fixture()
def api(tmp_path, monkeypatch):
    monkeypatch.setenv("PRODUCT_FORGE_HOME", str(tmp_path / "pf"))
    db = tmp_path / "data.db"
    connection = sqlite3.connect(db)
    connection.execute("CREATE TABLE events (id TEXT, value INTEGER)")
    connection.executemany("INSERT INTO events VALUES (?, ?)", [("e1", 1), ("e2", 2)])
    connection.commit()
    connection.close()

    from fastapi.testclient import TestClient

    from product_forge.api.app import create_app
    from product_forge.config import load_config
    from product_forge.security import TokenStore

    home = tmp_path / "pf"
    cfg = load_config(home)
    token = TokenStore(home / str(cfg["api"]["token_file"])).token
    client = TestClient(create_app(home))
    headers = {"Authorization": f"Bearer {token}"}
    return client, headers, db


def test_api_surface_routes_are_executable(api, monkeypatch):
    client, headers, db = api

    def call(method, path, **kwargs):
        response = client.request(method, path, headers=headers, **kwargs)
        assert response.status_code < 400, (method, path, response.text)
        return response.json()["data"]

    def fail(method, path, **kwargs):
        response = client.request(method, path, headers=headers, **kwargs)
        assert 400 <= response.status_code < 500, (method, path, response.text)
        return response

    call("GET", "/api/v1/health")
    call("GET", "/api/v1/jobs")
    call("GET", "/api/v1/delegates")
    call("GET", "/api/v1/agent-templates")
    call("GET", "/api/v1/capabilities")

    workspace = call("POST", "/api/v1/workspaces", json={"name": "Surface"})
    wid = workspace["id"]
    call("GET", "/api/v1/workspaces")
    call("GET", f"/api/v1/workspaces/{wid}")
    call("PATCH", f"/api/v1/workspaces/{wid}", json={"name": "Surface 2"})
    call("GET", "/api/v1/workspace/discovery")

    product = call(
        "POST",
        "/api/v1/products",
        json={"workspace_id": wid, "name": "Surface Product", "domain": "data"},
    )
    pid = product["id"]
    call("GET", "/api/v1/products")
    call("GET", f"/api/v1/products/{pid}")
    call("PATCH", f"/api/v1/products/{pid}", json={"description": "coverage"})
    call("GET", f"/api/v1/products/{pid}/context")
    context = call(
        "POST",
        "/api/v1/context/authorize",
        json={"principal": "surface-agent", "product_id": pid, "workspace_id": wid},
    )
    cid = context["id"]
    call("GET", f"/api/v1/context/{cid}")
    call("POST", f"/api/v1/context/{cid}/revoke")

    job = call("POST", "/api/v1/jobs", json={"kind": "noop", "product_id": pid})
    call("POST", f"/api/v1/jobs/{job['id']}/cancel")
    call("POST", "/api/v1/jobs/drain", params={"limit": 2})

    source = call(
        "POST", f"/api/v1/products/{pid}/sources",
        json={"name": "brief", "type": "markdown", "locator": "brief.md"},
    )
    sid = source["id"]
    call("GET", f"/api/v1/products/{pid}/sources")
    call("GET", f"/api/v1/products/{pid}/sources/{sid}")
    call("PATCH", f"/api/v1/products/{pid}/sources/{sid}", json={"name": "brief-updated"})
    call("DELETE", f"/api/v1/products/{pid}/sources/{sid}")

    call("GET", f"/api/v1/products/{pid}/board")
    fail("POST", f"/api/v1/products/{pid}/board", json={"name": "Duplicate"})
    task = call(
        "POST", f"/api/v1/products/{pid}/tasks",
        json={"title": "Diagnose", "column_id": "todo", "position": 0},
    )
    tid = task["id"]
    call("GET", f"/api/v1/products/{pid}/tasks")
    call("GET", f"/api/v1/products/{pid}/tasks/{tid}")
    call("PATCH", f"/api/v1/products/{pid}/tasks/{tid}", json={"description": "trace"})
    call("POST", f"/api/v1/products/{pid}/tasks/{tid}/move", json={"column_id": "doing"})
    call("POST", f"/api/v1/products/{pid}/tasks/{tid}/comments", json={"text": "started"})
    call("DELETE", f"/api/v1/products/{pid}/tasks/{tid}")

    agent = call(
        "POST", f"/api/v1/products/{pid}/agents",
        json={"name": "Surface agent", "mission": "summarize evidence", "template": "product-analyst"},
    )
    aid = agent["id"]
    call("GET", f"/api/v1/products/{pid}/agents")
    call("PATCH", f"/api/v1/products/{pid}/agents/{aid}", json={"tools_allowed": ["knowledge_query"]})
    call("POST", f"/api/v1/products/{pid}/agents/{aid}/eval")
    call("GET", f"/api/v1/products/{pid}/agents/{aid}/runs")
    call("POST", f"/api/v1/products/{pid}/agents/{aid}/archive")

    notebook = call(
        "POST", f"/api/v1/products/{pid}/notebooks", json={"title": "Surface notebook"}
    )
    nid = notebook["id"]
    block = call(
        "POST", f"/api/v1/products/{pid}/notebooks/{nid}/blocks",
        json={"kind": "markdown", "content": "Evidence notes"},
    )
    call("POST", f"/api/v1/products/{pid}/notebooks/{nid}/blocks/{block['id']}/run")
    call("GET", f"/api/v1/products/{pid}/notebooks/{nid}/render")

    document = call(
        "POST", f"/api/v1/products/{pid}/documents",
        json={"title": "surface.md", "content": "# Events\n\nThe events table is healthy."},
    )
    did = document["id"]
    call("GET", f"/api/v1/products/{pid}/documents")
    call("GET", f"/api/v1/products/{pid}/documents/search", params={"q": "events"})
    call("GET", f"/api/v1/products/{pid}/knowledge/search", params={"q": "events"})
    call("GET", f"/api/v1/products/{pid}/documents/{did}")
    call("GET", f"/api/v1/products/{pid}/graph")
    call("GET", f"/api/v1/products/{pid}/knowledge-health")
    call("POST", f"/api/v1/products/{pid}/knowledge/extract")

    data_source = call(
        "POST", f"/api/v1/products/{pid}/data-sources",
        json={"name": "sqlite", "connector": "sqlite", "locator": str(db)},
    )
    dsid = data_source["id"]
    call("GET", f"/api/v1/products/{pid}/data-sources/{dsid}/schema")
    call("POST", f"/api/v1/products/{pid}/data-sources/{dsid}/verify")
    metric = call(
        "POST", f"/api/v1/products/{pid}/metrics",
        json={"name": "event count", "formula": "count(*)", "source_id": dsid},
    )
    call("GET", f"/api/v1/products/{pid}/metrics")
    call("POST", f"/api/v1/products/{pid}/metrics/resolve", json={"question": "event count"})

    call("POST", f"/api/v1/products/{pid}/queries/validate", json={"statement": "SELECT 1"})
    call(
        "POST", f"/api/v1/products/{pid}/queries/compile",
        json={"spec": {"table": "events", "aggregate": {"fn": "count"}}},
    )
    call("GET", f"/api/v1/products/{pid}/health")
    call("GET", f"/api/v1/products/{pid}/evidence-graph")
    run = call(
        "POST", f"/api/v1/products/{pid}/queries/execute",
        json={"source_id": dsid, "statement": "SELECT * FROM events"},
    )
    qid = run["id"]
    call("GET", f"/api/v1/products/{pid}/queries")
    call("GET", f"/api/v1/products/{pid}/queries/{qid}")
    call("PATCH", f"/api/v1/products/{pid}/queries/{qid}", json={"status": "reviewed"})
    call("POST", f"/api/v1/products/{pid}/queries/{qid}/cancel")
    call("DELETE", f"/api/v1/products/{pid}/queries/{qid}")

    dashboard = call(
        "POST", f"/api/v1/products/{pid}/dashboards",
        json={"name": "Surface dashboard", "widgets": []},
    )
    call("GET", f"/api/v1/products/{pid}/dashboards")
    call("POST", f"/api/v1/products/{pid}/dashboards/{dashboard['id']}/render")
    initiative = call(
        "POST", f"/api/v1/products/{pid}/initiatives",
        json={"title": "Improve observability", "hypothesis": "fewer blind spots"},
    )
    call("GET", f"/api/v1/products/{pid}/initiatives")
    call("POST", f"/api/v1/products/{pid}/initiatives/{initiative['id']}/prioritize", json={})
    call("POST", f"/api/v1/products/{pid}/initiatives/{initiative['id']}/prd")
    call("GET", f"/api/v1/products/{pid}/roadmap")
    call("GET", f"/api/v1/products/{pid}/routing")
    call("GET", f"/api/v1/products/{pid}/budget")
    call("GET", "/api/v1/audit", params={"product_id": pid})

    # Error paths are part of the Portal contract and must remain typed.
    fail("GET", f"/api/v1/products/{pid}/tasks/{tid}")
    fail("POST", f"/api/v1/products/{pid}/tasks/{tid}/move", json={"column_id": ""})
    fail("POST", f"/api/v1/products/{pid}/queries/execute", json={"source_id": dsid})
    call("POST", f"/api/v1/products/{pid}/queries/nl", json={"question": "show the flux capacitor"})
    fail("POST", f"/api/v1/products/{pid}/cloud/inventory", json={"provider": "unknown", "service": "x"})
    fail("GET", f"/api/v1/products/{pid}/data-sources/other/schema")
    fail("GET", f"/api/v1/products/{pid}/documents/missing")

    from product_forge.api.app import _obsidian_vault, _oidc_role
    from product_forge.errors import ForgeError

    assert _oidc_role(None) == "viewer"
    assert _oidc_role({"roles": 7}) == "viewer"
    assert _oidc_role({"roles": ["viewer", "editor"]}) == "editor"
    assert _oidc_role({"role": "admin"}) == "admin"
    monkeypatch.delenv("FORGE_OBSIDIAN_VAULT", raising=False)
    with pytest.raises(ForgeError):
        _obsidian_vault()
    monkeypatch.setenv("FORGE_OBSIDIAN_VAULT", str(db.parent))
    assert _obsidian_vault() == db.parent
    status = call("GET", f"/api/v1/products/{pid}/documents/obsidian/status")
    assert status["schema"] == "theforge/ObsidianVaultDescriptor/v1"
    assert status["detected"] is True
    assert "path_hash" in status["provenance"]
    assert str(db.parent) not in str(status)
    history = call("GET", f"/api/v1/products/{pid}/documents/obsidian/history")
    assert history["items"] == []

    assert metric["name"] == "event count"
