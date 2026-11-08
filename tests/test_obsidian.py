from pathlib import Path

import pytest

from product_forge.knowledge.obsidian import (
    ObsidianVaultError,
    export_vault_document,
    import_vault_document,
    plan_vault_sync,
    validate_base_document,
    validate_canvas_document,
)


def test_import_and_export_are_pure_markdown_operations(tmp_path: Path):
    vault = tmp_path / "vault"
    (vault / "notes").mkdir(parents=True)
    (vault / "notes" / "spark.md").write_text("# Spark\n\nUse the runbook.\n", encoding="utf-8")

    imported = import_vault_document(vault, "notes/spark.md")
    exported = export_vault_document(vault, "notes/result.md", "# Result\n\nDone.\n")

    assert imported["schema"] == "productforge/ObsidianDocument/v1"
    assert imported["title"] == "Spark"
    assert imported["provenance"]["cli_required"] is False
    assert exported["state"] == "exported"
    assert exported["sync_state"] == "created"
    assert (vault / "notes" / "result.md").read_text(encoding="utf-8") == "# Result\n\nDone.\n"


def test_export_requires_baseline_for_existing_note_and_preserves_backup(tmp_path: Path):
    vault = tmp_path / "vault"
    (vault / "notes").mkdir(parents=True)
    note = vault / "notes" / "result.md"
    note.write_text("# Original\n", encoding="utf-8")
    plan = plan_vault_sync(vault, "notes/result.md", "# Candidate\n")
    assert plan["outcome"] == "conflict"
    with pytest.raises(ObsidianVaultError, match="baseline_hash"):
        export_vault_document(vault, "notes/result.md", "# Candidate\n")
    exported = export_vault_document(
        vault,
        "notes/result.md",
        "# Candidate\n",
        baseline_hash=plan["previous_hash"],
    )
    assert exported["state"] == "exported"
    assert exported["sync_state"] == "updated"
    assert (vault / exported["backup_path"]).read_text(encoding="utf-8") == "# Original\n"


def test_export_refuses_manual_change_after_plan(tmp_path: Path):
    vault = tmp_path / "vault"
    vault.mkdir()
    note = vault / "note.md"
    note.write_text("baseline", encoding="utf-8")
    plan = plan_vault_sync(vault, "note.md", "candidate")
    note.write_text("manual", encoding="utf-8")
    with pytest.raises(ObsidianVaultError, match="changed"):
        export_vault_document(vault, "note.md", "candidate", baseline_hash=plan["previous_hash"])


@pytest.mark.parametrize("raw_path", ["../outside.md", "notes/data.json", "notes/missing.md"])
def test_vault_refuses_traversal_non_markdown_and_missing_files(tmp_path: Path, raw_path: str):
    vault = tmp_path / "vault"
    (vault / "notes").mkdir(parents=True)
    (vault / "notes" / "ok.md").write_text("# OK\n", encoding="utf-8")

    with pytest.raises(ObsidianVaultError):
        import_vault_document(vault, raw_path)


def test_vault_refuses_symlinked_document(tmp_path: Path):
    vault = tmp_path / "vault"
    vault.mkdir()
    outside = tmp_path / "outside.md"
    outside.write_text("secret", encoding="utf-8")
    link = vault / "link.md"
    try:
        link.symlink_to(outside)
    except (OSError, NotImplementedError):
        pytest.skip("symlink creation unavailable")

    with pytest.raises(ObsidianVaultError):
        import_vault_document(vault, "link.md")


def test_canvas_validation_checks_graph_integrity_without_rendering():
    result = validate_canvas_document(
        {
            "nodes": [
                {"id": "n1", "type": "text", "text": "Start", "x": 0, "y": 0, "width": 200, "height": 100},
                {
                    "id": "n2",
                    "type": "file",
                    "file": "runbook.md",
                    "x": 300,
                    "y": 0,
                    "width": 200,
                    "height": 100,
                },
            ],
            "edges": [{"id": "e1", "fromNode": "n1", "toNode": "n2", "fromSide": "right", "toEnd": "arrow"}],
        }
    )

    assert result == {
        "schema": "productforge/ObsidianCanvasValidation/v1",
        "kind": "canvas",
        "state": "validated",
        "nodes": 2,
        "edges": 1,
        "warnings": [],
    }


@pytest.mark.parametrize(
    "document",
    [
        {},
        {
            "nodes": [{"id": "n1", "type": "text"}],
            "edges": [{"id": "e1", "fromNode": "n1", "toNode": "missing"}],
        },
        {
            "nodes": [{"id": "n1", "type": "text", "text": "x", "x": 0, "y": 0, "width": 0, "height": 100}],
            "edges": [],
        },
        {
            "nodes": [{"id": "n1", "type": "text", "text": "x", "x": 0, "y": 0, "width": 100, "height": 100}],
            "edges": [{"id": "e1", "fromNode": "n1", "toNode": "n1", "fromSide": "diagonal"}],
        },
        {"nodes": [{"id": "n1", "type": "unknown"}], "edges": []},
        b"\xff\xfe",
    ],
)
def test_canvas_validation_rejects_invalid_documents(document):
    with pytest.raises(ObsidianVaultError, match="canvas|UTF-8"):
        validate_canvas_document(document)


def test_base_validation_is_explicit_about_partial_semantics():
    result = validate_base_document(
        "views:\n  - name: Payments\n    type: table\nfilters: status = 'open'\n"
    )

    assert result["schema"] == "productforge/ObsidianBaseValidation/v1"
    assert result["state"] == "validated"
    assert result["views"] == 1
    assert result["warnings"]


@pytest.mark.parametrize(
    "document",
    ["views: [broken", {"views": ["not-an-object"]}, {"filters": 42}, b"\xff"],
)
def test_base_validation_rejects_invalid_documents(document):
    with pytest.raises(ObsidianVaultError):
        validate_base_document(document)
