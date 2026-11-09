"""The Forge → Product Forge governed investigation import contract."""

import pytest

pytestmark = pytest.mark.skipif(
    __import__("importlib.util").util.find_spec("fastapi") is None,
    reason="fastapi not installed",
)


def _api(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from product_forge.api.app import create_app
    from product_forge.config import load_config
    from product_forge.security import TokenStore

    home = tmp_path / "pf"
    monkeypatch.setenv("PRODUCT_FORGE_HOME", str(home))
    cfg = load_config(home)
    token = TokenStore(home / str(cfg["api"]["token_file"])).token
    return TestClient(create_app(home)), {"Authorization": f"Bearer {token}"}


def _report(**overrides):
    value = {
        "schema": "theforge/OrchestrationReport/v1",
        "kind": "run",
        "intent": "diagnose spark skew",
        "correlation_id": "orch-investigation-001",
        "generated_at": "2026-11-09T10:00:00Z",
        "plan_status": "completed",
        "entries": [
            {
                "provider": "spark-forge-aws",
                "capability": "spark.diagnose",
                "status": "completed",
            }
        ],
        "findings": [
            {
                "id": "spark-skew",
                "finding_class": "RUNTIME",
                "severity": "warning",
                "confidence": "medium",
                "summary": "Skew was observed in the fixture evidence.",
                "providers": ["spark-forge-aws"],
                "evidence_refs": ["aws-evidence-1"],
            }
        ],
        "unresolved": [],
        "recommended": [],
        "limitations": ["fixture-only"],
        "unknowns": [],
        "provenance": {"discovery_digest": "digest-1"},
    }
    value.update(overrides)
    return value


def _product(client, headers):
    workspace = client.post(
        "/api/v1/workspaces", headers=headers, json={"name": "Investigations"}
    ).json()["data"]
    return client.post(
        "/api/v1/products",
        headers=headers,
        json={"workspace_id": workspace["id"], "name": "Spark knowledge"},
    ).json()["data"]["id"]


def test_imports_redacted_investigation_with_provenance_and_is_idempotent(tmp_path, monkeypatch):
    client, headers = _api(tmp_path, monkeypatch)
    pid = _product(client, headers)

    response = client.post(
        f"/api/v1/products/{pid}/documents/from-investigation",
        headers=headers,
        json={"confirm": "import", "report": _report()},
    )
    assert response.status_code == 201, response.text
    data = response.json()["data"]
    assert data["state"] == "imported"
    assert data["source_kind"] == "the-forge-investigation"
    assert data["metadata"]["trust_state"] == "draft"
    assert data["metadata"]["freshness"] == "captured"
    assert data["metadata"]["knowledge_state"] == "draft"
    assert data["metadata"]["investigation_correlation_id"] == "orch-investigation-001"
    assert data["suggested_obsidian_path"].startswith("investigations/")
    assert "content" not in data

    duplicate = client.post(
        f"/api/v1/products/{pid}/documents/from-investigation",
        headers=headers,
        json={"confirm": "import", "report": _report()},
    )
    assert duplicate.status_code == 201, duplicate.text
    duplicate_data = duplicate.json()["data"]
    assert duplicate_data["state"] == "already_imported"
    assert duplicate_data["id"] == data["id"]

    search = client.get(
        f"/api/v1/products/{pid}/documents/search",
        headers=headers,
        params={"q": "skew"},
    )
    assert search.status_code == 200, search.text
    assert search.json()["data"]["items"][0]["source"] == "the-forge"


@pytest.mark.parametrize(
    "report, expected",
    [
        ({"schema": "theforge/OrchestrationReport/v1", "kind": "plan"}, "completed"),
        (
            {
                "schema": "theforge/OrchestrationReport/v1",
                "kind": "run",
                "intent": "diagnose",
                "correlation_id": "orch-investigation-002",
                "api_key": "must-not-cross-boundary",
            },
            "secret-shaped",
        ),
    ],
)
def test_import_refuses_untrusted_or_incomplete_report(tmp_path, monkeypatch, report, expected):
    client, headers = _api(tmp_path, monkeypatch)
    pid = _product(client, headers)
    response = client.post(
        f"/api/v1/products/{pid}/documents/from-investigation",
        headers=headers,
        json={"confirm": "import", "report": report},
    )
    assert response.status_code == 422, response.text
    assert expected in response.json()["error"]["message"]


def test_import_requires_explicit_confirmation(tmp_path, monkeypatch):
    client, headers = _api(tmp_path, monkeypatch)
    pid = _product(client, headers)
    response = client.post(
        f"/api/v1/products/{pid}/documents/from-investigation",
        headers=headers,
        json={"report": _report()},
    )
    assert response.status_code == 422
    assert "confirm=import" in response.json()["error"]["message"]


def test_knowledge_lifecycle_requires_evidence_to_validate(tmp_path, monkeypatch):
    client, headers = _api(tmp_path, monkeypatch)
    pid = _product(client, headers)
    imported = client.post(
        f"/api/v1/products/{pid}/documents/from-investigation",
        headers=headers,
        json={"confirm": "import", "report": _report(correlation_id="orch-lifecycle-001")},
    ).json()["data"]
    did = imported["id"]

    reviewed = client.post(
        f"/api/v1/products/{pid}/documents/{did}/knowledge-state",
        headers=headers,
        json={"confirm": "transition", "state": "reviewed", "reason": "human review"},
    )
    assert reviewed.status_code == 200, reviewed.text

    refused = client.post(
        f"/api/v1/products/{pid}/documents/{did}/knowledge-state",
        headers=headers,
        json={"confirm": "transition", "state": "validated"},
    )
    assert refused.status_code == 422
    assert "evidence" in refused.json()["error"]["message"]

    validated = client.post(
        f"/api/v1/products/{pid}/documents/{did}/knowledge-state",
        headers=headers,
        json={
            "confirm": "transition",
            "state": "validated",
            "evidence_refs": ["spark-job-42"],
            "reason": "receipt checked",
        },
    )
    assert validated.status_code == 200, validated.text
    data = validated.json()["data"]
    assert data["document"]["metadata"]["knowledge_state"] == "validated"
    assert data["transition"]["evidence_refs"] == ["spark-job-42"]
