"""Obsidian vaults are scoped to the authenticated principal and workspace."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from product_forge.api.app import create_app
from product_forge.config import load_config, save_config
from product_forge.security import TokenStore


def test_obisidian_vault_connection_isolated_and_revoke_is_non_destructive(
    tmp_path: Path, monkeypatch
) -> None:
    home = tmp_path / "pf"
    allowed = tmp_path / "authorized-vaults"
    alice_vault = allowed / "alice"
    bob_vault = allowed / "bob"
    alice_vault.mkdir(parents=True)
    bob_vault.mkdir(parents=True)
    (alice_vault / "notes" ).mkdir()
    (alice_vault / "notes" / "incident.md").write_text("# Alice incident\n", encoding="utf-8")
    monkeypatch.setenv("FORGE_OBSIDIAN_ALLOWED_ROOT", str(allowed))

    # Bootstrap the shared workspace with the local installation token, then
    # switch the same state to two explicitly scoped principals.
    cfg = load_config(home)
    master_token = TokenStore(home / str(cfg["api"]["token_file"])).token
    bootstrap = TestClient(create_app(home))
    master_headers = {"Authorization": f"Bearer {master_token}"}
    workspace_response = bootstrap.post(
        "/api/v1/workspaces", json={"name": "Shared"}, headers=master_headers
    )
    assert workspace_response.status_code == 201, workspace_response.text
    workspace_id = workspace_response.json()["data"]["id"]
    product_response = bootstrap.post(
        "/api/v1/products",
        json={"workspace_id": workspace_id, "name": "Scoped product", "domain": "data"},
        headers=master_headers,
    )
    assert product_response.status_code == 201, product_response.text
    product_id = product_response.json()["data"]["id"]

    cfg["principals"] = [
        {"id": "alice", "token": "alice-token", "role": "editor", "workspaces": [workspace_id]},
        {"id": "bob", "token": "bob-token", "role": "editor", "workspaces": [workspace_id]},
    ]
    save_config(cfg, home)
    client = TestClient(create_app(home))
    alice = {"Authorization": "Bearer alice-token"}
    bob = {"Authorization": "Bearer bob-token"}

    def connect(headers: dict[str, str], path: Path, label: str) -> dict:
        response = client.post(
            "/api/v1/obsidian/vaults",
            json={
                "workspace_id": workspace_id,
                "path": str(path),
                "label": label,
                "confirm": "connect",
            },
            headers=headers,
        )
        assert response.status_code == 201, response.text
        data = response.json()["data"]
        assert data["path"] == "."
        assert str(path) not in response.text
        return data

    alice_vault_record = connect(alice, alice_vault, "Alice vault")
    assert client.get(
        "/api/v1/obsidian/vaults", params={"workspace_id": workspace_id}, headers=alice
    ).json()["data"]["items"]
    assert client.get(
        "/api/v1/obsidian/vaults", params={"workspace_id": workspace_id}, headers=bob
    ).json()["data"]["items"] == []

    alice_status = client.get(
        f"/api/v1/products/{product_id}/documents/obsidian/status", headers=alice
    )
    assert alice_status.status_code == 200, alice_status.text
    assert alice_status.json()["data"]["detected"] is True
    assert alice_status.json()["data"]["vault_record_id"] == alice_vault_record["vault_record_id"]
    assert alice_status.json()["data"]["path"] == "."

    bob_status = client.get(
        f"/api/v1/products/{product_id}/documents/obsidian/status", headers=bob
    )
    assert bob_status.status_code == 200, bob_status.text
    assert bob_status.json()["data"]["detected"] is False
    assert "OBSIDIAN-NOT-ASSIGNED" in bob_status.text

    alice_preview = client.get(
        f"/api/v1/products/{product_id}/documents/obsidian/preview",
        params={"path": "notes/incident.md"},
        headers=alice,
    )
    assert alice_preview.status_code == 200, alice_preview.text
    assert "Alice incident" in alice_preview.text

    forbidden_revoke = client.delete(
        f"/api/v1/obsidian/vaults/{alice_vault_record['vault_record_id']}", headers=bob
    )
    assert forbidden_revoke.status_code == 403, forbidden_revoke.text

    revoked = client.delete(
        f"/api/v1/obsidian/vaults/{alice_vault_record['vault_record_id']}", headers=alice
    )
    assert revoked.status_code == 200, revoked.text
    assert revoked.json()["data"]["revoked"] is True
    assert alice_vault.is_dir()
    assert (alice_vault / "notes" / "incident.md").is_file()

    after_revoke = client.get(
        f"/api/v1/products/{product_id}/documents/obsidian/status", headers=alice
    )
    assert after_revoke.status_code == 200, after_revoke.text
    assert after_revoke.json()["data"]["detected"] is False
    assert "vault_record_id" not in after_revoke.json()["data"]
