import pytest


def test_document_explorer_returns_product_scoped_chunks_and_metadata(tmp_path, monkeypatch):
    pytest.importorskip("fastapi")
    monkeypatch.setenv("PRODUCT_FORGE_HOME", str(tmp_path / "pf"))
    from fastapi.testclient import TestClient

    from product_forge.api.app import create_app
    from product_forge.config import home_dir, load_config
    from product_forge.security import TokenStore

    home = home_dir("user")
    cfg = load_config(home)
    token = TokenStore(home / str(cfg["api"]["token_file"])).token
    headers = {"Authorization": f"Bearer {token}"}
    client = TestClient(create_app(home))
    workspace = client.post("/api/v1/workspaces", json={"name": "W"}, headers=headers).json()["data"]
    product = client.post(
        "/api/v1/products", json={"workspace_id": workspace["id"], "name": "P"}, headers=headers
    ).json()["data"]
    document = client.post(
        f"/api/v1/products/{product['id']}/documents",
        json={"title": "Runbook", "content": "# Spark\n\nGET /api/v1/x reads table orders."},
        headers=headers,
    ).json()["data"]

    response = client.get(f"/api/v1/products/{product['id']}/documents/{document['id']}", headers=headers)

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["schema"] == "productforge/DocumentExplorer/v1"
    assert payload["document"]["title"] == "Runbook"
    assert payload["content"]["chunks"]
    assert payload["versions"]["state"] == "current_only"

    search = client.get(f"/api/v1/products/{product['id']}/documents/search?q=Spark", headers=headers)
    assert search.status_code == 200
    assert search.json()["data"]["schema"] == "productforge/DocumentSearch/v1"
    assert search.json()["data"]["items"][0]["document_id"] == document["id"]

    source = client.post(
        f"/api/v1/products/{product['id']}/sources",
        json={"name": "Spark runbooks", "type": "markdown", "locator": "runbooks/"},
        headers=headers,
    )
    assert source.status_code == 201
    federated = client.get(f"/api/v1/products/{product['id']}/knowledge/search?q=Spark", headers=headers)
    assert federated.status_code == 200
    payload = federated.json()["data"]
    assert payload["schema"] == "productforge/KnowledgeSearch/v1"
    assert {item["kind"] for item in payload["items"]} == {"document", "source"}
    assert all("content" not in item for item in payload["items"])

    extracted = client.post(f"/api/v1/products/{product['id']}/knowledge/extract", headers=headers)
    assert extracted.status_code == 200
    graph_hits = client.get(f"/api/v1/products/{product['id']}/knowledge/search?q=related", headers=headers)
    assert graph_hits.status_code == 200
    assert any(item["kind"] == "relation" for item in graph_hits.json()["data"]["items"])
