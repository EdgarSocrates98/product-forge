from pathlib import Path

import pytest

from product_forge.workspace.discovery import (
    WorkspaceDiscoveryError,
    discover_workspace,
    import_workspace_document,
    preview_workspace_document,
)


@pytest.mark.skipif(
    __import__("importlib.util").util.find_spec("fastapi") is None,
    reason="fastapi not installed",
)
def test_standalone_api_exposes_the_same_discovery_contract(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from product_forge.api.app import create_app
    from product_forge.config import load_config
    from product_forge.security import TokenStore

    workspace = tmp_path / "workspace"
    repo = _repo(workspace, "api-repo")
    (repo / "brief.md").write_text("# API brief\n", encoding="utf-8")
    monkeypatch.setenv("FORGE_WORKSPACE_ROOT", str(workspace))
    home = tmp_path / "home"
    cfg = load_config(home)
    token = TokenStore(home / str(cfg["api"]["token_file"])).token
    client = TestClient(create_app(home))

    response = client.get("/api/v1/workspace/discovery", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["schema"] == "forge/PortalApi/1"
    assert payload["data"]["documents"][0]["kind"] == "brief"


def _repo(root: Path, name: str) -> Path:
    repo = root / name
    (repo / ".git").mkdir(parents=True)
    return repo


def test_discovery_finds_projects_and_classifies_context_without_reading_secrets(tmp_path, monkeypatch):
    workspace = tmp_path / "workspace"
    repo_a = _repo(workspace, "product-a")
    repo_b = _repo(workspace, "service-b")
    (repo_a / "docs").mkdir()
    (repo_a / "docs" / "product-brief.md").write_text("# Checkout brief\n", encoding="utf-8")
    (repo_a / "README.md").write_text("# Product A\n", encoding="utf-8")
    (repo_a / ".env.local").write_text("TOKEN=must-not-appear\n", encoding="utf-8")
    (repo_b / "PRD.md").write_text("# Service PRD\n", encoding="utf-8")
    (repo_b / "knowledge").mkdir()
    (repo_b / "knowledge" / "adr-001.md").write_text("# Decision\n", encoding="utf-8")
    (repo_b / "node_modules").mkdir()
    (repo_b / "node_modules" / "hidden.md").write_text("# hidden\n", encoding="utf-8")
    monkeypatch.setenv("FORGE_WORKSPACE_ROOT", str(workspace))

    result = discover_workspace(repo_a)

    assert result["schema"] == "productforge/WorkspaceDiscovery/v1"
    assert result["workspace"]["source"] == "environment"
    assert {item["repository"] for item in result["repositories"]} == {"product-a", "service-b"}
    by_path = {item["path"]: item for item in result["documents"]}
    assert by_path["product-a/docs/product-brief.md"]["kind"] == "brief"
    assert by_path["service-b/PRD.md"]["kind"] == "prd"
    assert by_path["service-b/knowledge/adr-001.md"]["kind"] == "knowledge"
    assert "product-a/.env.local" in result["skipped"]
    assert all("node_modules" not in item["path"] for item in result["documents"])


def test_preview_and_import_are_bounded_and_return_provenance(tmp_path):
    repo = _repo(tmp_path, "repo")
    (repo / "brief.md").write_text("# Brief\n\nKnown problem.\n", encoding="utf-8")
    (repo / "credentials.md").write_text("secret", encoding="utf-8")

    preview = preview_workspace_document(tmp_path, "repo/brief.md")
    imported = import_workspace_document(tmp_path, "repo/brief.md")

    assert preview["state"] == "previewed"
    assert preview["kind"] == "brief"
    assert "Known problem" in preview["preview"]
    assert imported["state"] == "ready_for_import"
    assert imported["content_hash"]
    assert imported["path"] == "repo/brief.md"


@pytest.mark.parametrize("raw_path", ["../outside.md", "repo/.env", "repo/credentials.md", "missing.md"])
def test_preview_refuses_traversal_and_sensitive_or_unknown_files(tmp_path, raw_path):
    repo = _repo(tmp_path, "repo")
    (repo / "brief.md").write_text("# Brief\n", encoding="utf-8")
    (repo / ".env").write_text("TOKEN=x", encoding="utf-8")
    (repo / "credentials.md").write_text("secret", encoding="utf-8")

    with pytest.raises(WorkspaceDiscoveryError):
        preview_workspace_document(tmp_path, raw_path)
