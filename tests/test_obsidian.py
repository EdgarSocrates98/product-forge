import json
import os
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

import product_forge.knowledge.obsidian as obsidian
from product_forge.knowledge.obsidian import (
    ObsidianVaultError,
    export_vault_document,
    import_vault_document,
    list_obsidian_receipts,
    obsidian_projection_metadata,
    parse_markdown_document,
    plan_vault_sync,
    rollback_vault_document,
    skip_vault_sync,
    validate_base_document,
    validate_canvas_document,
    validate_vault_authorization,
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
    assert (vault / exported["receipt_path"]).is_file()
    history = list_obsidian_receipts(vault)
    assert len(history) == 1
    assert history[0]["receipt_schema"] == "theforge/ObsidianSyncReceipt/v1"
    assert "content" not in history[0]


def test_reexport_of_identical_note_is_unchanged_and_does_not_need_baseline(tmp_path: Path):
    vault = tmp_path / "vault"
    vault.mkdir()
    first = export_vault_document(vault, "note.md", "# Note\n")
    second = export_vault_document(vault, "note.md", "# Note\n")

    assert first["sync_state"] == "created"
    assert second["sync_state"] == "unchanged"
    assert second["outcome"] == "unchanged"
    assert second["backup_path"] is None


def test_concurrent_exports_are_serialized_per_document(tmp_path: Path, monkeypatch):
    vault = tmp_path / "vault"
    vault.mkdir()
    original = obsidian._export_vault_document_unlocked
    active = 0
    maximum_active = 0
    counter_lock = threading.Lock()

    def observed_export(*args, **kwargs):
        nonlocal active, maximum_active
        with counter_lock:
            active += 1
            maximum_active = max(maximum_active, active)
        try:
            time.sleep(0.05)
            return original(*args, **kwargs)
        finally:
            with counter_lock:
                active -= 1

    monkeypatch.setattr(obsidian, "_export_vault_document_unlocked", observed_export)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: export_vault_document(vault, "note.md", "# Note\n"), range(2)))

    assert maximum_active == 1
    assert {result["sync_state"] for result in results} == {"created", "unchanged"}


def test_concurrent_exports_are_serialized_across_processes(tmp_path: Path):
    vault = tmp_path / "vault"
    vault.mkdir()
    script = """
import json
import sys
from product_forge.knowledge.obsidian import export_vault_document

result = export_vault_document(sys.argv[1], "note.md", "# Note\\n")
print(json.dumps({"sync_state": result["sync_state"]}))
"""
    processes = [
        subprocess.Popen(  # noqa: S603 - test invokes the current interpreter with a fixed script
            [sys.executable, "-c", script, str(vault)],
            cwd=Path(__file__).parents[1],
            env=os.environ.copy(),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        for _ in range(2)
    ]
    outputs = []
    for process in processes:
        stdout, stderr = process.communicate(timeout=20)
        assert process.returncode == 0, stderr
        outputs.append(json.loads(stdout))

    assert {result["sync_state"] for result in outputs} == {"created", "unchanged"}


def test_process_exit_during_atomic_write_is_recoverable(tmp_path: Path):
    vault = tmp_path / "vault"
    vault.mkdir()
    script = """
import os
import sys
import tempfile
import product_forge.knowledge.obsidian as obsidian

def interrupted_write(path, content):
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    with os.fdopen(descriptor, "wb") as handle:
        handle.write(content)
        handle.flush()
        os.fsync(handle.fileno())
    os._exit(23)

obsidian._atomic_write = interrupted_write
obsidian.export_vault_document(sys.argv[1], "note.md", "# Interrupted\\n")
"""
    result = subprocess.run(  # noqa: S603 - test invokes the current interpreter with a fixed script
        [sys.executable, "-c", script, str(vault)],
        cwd=Path(__file__).parents[1],
        env=os.environ.copy(),
        capture_output=True,
        text=True,
        timeout=20,
    )

    assert result.returncode == 23
    assert not (vault / "note.md").exists()
    recovered = export_vault_document(vault, "note.md", "# Recovered\n")
    assert recovered["sync_state"] == "created"
    assert (vault / "note.md").read_text(encoding="utf-8") == "# Recovered\n"


def test_skip_records_a_receipt_without_mutating_the_vault(tmp_path: Path):
    vault = tmp_path / "vault"
    vault.mkdir()
    note = vault / "note.md"
    note.write_text("# Manual\n", encoding="utf-8")

    skipped = skip_vault_sync(vault, "note.md", "# Candidate\n", reason="operator deferred")

    assert skipped["sync_state"] == "skipped"
    assert skipped["outcome"] == "skipped"
    assert note.read_text(encoding="utf-8") == "# Manual\n"
    assert skipped["backup_path"] is None


def test_rollback_restores_backup_and_keeps_a_distinct_receipt(tmp_path: Path):
    vault = tmp_path / "vault"
    vault.mkdir()
    first = export_vault_document(vault, "note.md", "# Original\n")
    plan = plan_vault_sync(vault, "note.md", "# Candidate\n")
    exported = export_vault_document(
        vault,
        "note.md",
        "# Candidate\n",
        baseline_hash=plan["previous_hash"],
    )

    rolled_back = rollback_vault_document(
        vault,
        "note.md",
        receipt_path=exported["receipt_path"],
    )

    assert rolled_back["sync_state"] == "rolled_back"
    assert (vault / "note.md").read_text(encoding="utf-8") == "# Original\n"
    assert rolled_back["receipt_path"] != first["receipt_path"]
    assert len(list_obsidian_receipts(vault)) == 3


def test_rollback_refuses_a_manual_edit_after_export(tmp_path: Path):
    vault = tmp_path / "vault"
    vault.mkdir()
    export_vault_document(vault, "note.md", "# Original\n")
    plan = plan_vault_sync(vault, "note.md", "# Candidate\n")
    exported = export_vault_document(
        vault,
        "note.md",
        "# Candidate\n",
        baseline_hash=plan["previous_hash"],
    )
    (vault / "note.md").write_text("# Manual\n", encoding="utf-8")

    with pytest.raises(ObsidianVaultError, match="manual edit"):
        rollback_vault_document(vault, "note.md", receipt_path=exported["receipt_path"])


def test_export_refuses_manual_change_after_plan(tmp_path: Path):
    vault = tmp_path / "vault"
    vault.mkdir()
    note = vault / "note.md"
    note.write_text("baseline", encoding="utf-8")
    plan = plan_vault_sync(vault, "note.md", "candidate")
    note.write_text("manual", encoding="utf-8")
    with pytest.raises(ObsidianVaultError, match="changed"):
        export_vault_document(vault, "note.md", "candidate", baseline_hash=plan["previous_hash"])


def test_import_tracks_rename_and_removal_without_fallback_content(tmp_path: Path):
    vault = tmp_path / "vault"
    vault.mkdir()
    original = vault / "original.md"
    renamed = vault / "renamed.md"
    original.write_bytes(b"# Stable\n")
    original.rename(renamed)

    with pytest.raises(ObsidianVaultError, match="found"):
        import_vault_document(vault, "original.md")
    assert import_vault_document(vault, "renamed.md")["content"] == "# Stable\n"

    renamed.unlink()
    with pytest.raises(ObsidianVaultError, match="found"):
        import_vault_document(vault, "renamed.md")


def test_export_revalidates_destination_before_atomic_replace(tmp_path: Path, monkeypatch):
    vault = tmp_path / "vault"
    vault.mkdir()
    original_safe = obsidian._safe
    calls = 0

    def final_validation_refuses(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise ObsidianVaultError("OBSIDIAN-SYMLINK-REFUSED", "destination changed during validation")
        return original_safe(*args, **kwargs)

    monkeypatch.setattr(obsidian, "_safe", final_validation_refuses)
    with pytest.raises(ObsidianVaultError, match="destination changed"):
        export_vault_document(vault, "note.md", "# Note\n")
    assert not (vault / "note.md").exists()


def test_sync_plan_applies_the_same_size_limit_as_export(tmp_path: Path):
    vault = tmp_path / "vault"
    vault.mkdir()
    oversized = "x" * (16 * 1024 * 1024 + 1)
    with pytest.raises(ObsidianVaultError, match="size limit"):
        plan_vault_sync(vault, "large.md", oversized)


def test_markdown_projection_preserves_obsidian_native_syntax():
    content = """---
type: runbook
reviewed: true
---
# Spark

See [[Spark Runtime#Skew|the skew section]] and ![[diagram.png]].
See [the source](docs/source.md) and [the PDF](assets/guide.pdf).
This paragraph has a stable anchor. ^diagnostic-anchor

aliases: not body metadata

#diagnostics #spark/runtime
> [!warning] Check partitions
```python
print('keep')
```
"""
    projection = parse_markdown_document(content)
    assert projection["frontmatter"] == {"type": "runbook", "reviewed": True}
    assert projection["wikilinks"] == ["Spark Runtime"]
    assert projection["embeds"] == ["diagram.png"]
    assert projection["tags"] == ["diagnostics", "spark/runtime"]
    assert projection["callouts"] == ["warning"]
    assert projection["code_blocks"] == ["python"]
    assert projection["aliases"] == []
    assert projection["block_references"] == ["diagnostic-anchor"]
    assert projection["relative_links"] == ["assets/guide.pdf", "docs/source.md"]
    assert projection["attachments"] == ["assets/guide.pdf", "diagram.png"]
    assert projection["content"] == content
    assert projection["unknown_syntax_preserved"] is True


def test_markdown_projection_extracts_aliases_without_rewriting_content():
    content = "---\naliases:\n  - Spark diagnosis\n  - Spark runbook\n---\n# Diagnosis\n"
    projection = parse_markdown_document(content)
    assert projection["aliases"] == ["Spark diagnosis", "Spark runbook"]
    assert projection["content"] == content


def test_persisted_projection_is_structural_and_excludes_frontmatter_and_body():
    projection = parse_markdown_document(
        "---\ntoken: do-not-persist\n---\n# Note\nSee [[Other]].\n"
    )
    safe = obsidian_projection_metadata(projection)
    assert safe["wikilinks"] == ["Other"]
    assert "frontmatter" not in safe
    assert "content" not in safe


def test_security_projection_warns_without_copying_secret_values():
    projection = parse_markdown_document(
        "---\npassword: top-secret\n---\n# Note\nToken=abc123\n"
    )
    safe = obsidian_projection_metadata(projection)
    assert safe["security_warnings"] == ["possible-secret-like-text-detected"]
    assert "top-secret" not in str(safe)
    assert "abc123" not in str(safe)


def test_vault_authorization_rejects_outside_operator_root(tmp_path: Path, monkeypatch):
    allowed = tmp_path / "allowed"
    outside = tmp_path / "outside"
    allowed.mkdir()
    outside.mkdir()
    monkeypatch.setenv("FORGE_OBSIDIAN_ALLOWED_ROOT", str(allowed))
    with pytest.raises(ObsidianVaultError, match="authorized"):
        validate_vault_authorization(outside)


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


def test_vault_refuses_symlinked_adapter_directory(tmp_path: Path):
    vault = tmp_path / "vault"
    vault.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    try:
        (vault / ".forge").symlink_to(outside, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("symlink creation unavailable")

    with pytest.raises(ObsidianVaultError):
        export_vault_document(vault, "note.md", "# Note\n")


@pytest.mark.parametrize("raw_path", [".obsidian/app.md", ".git/note.md", ".forge/note.md"])
def test_vault_refuses_internal_hidden_directories(tmp_path: Path, raw_path: str):
    vault = tmp_path / "vault"
    vault.mkdir()
    with pytest.raises(ObsidianVaultError, match="internal|cache|target"):
        export_vault_document(vault, raw_path, "# blocked\n")


def test_vault_refuses_hardlinked_document(tmp_path: Path):
    vault = tmp_path / "vault"
    vault.mkdir()
    source = vault / "source.md"
    linked = vault / "linked.md"
    source.write_text("# Source\n", encoding="utf-8")
    try:
        linked.hardlink_to(source)
    except OSError:
        pytest.skip("hardlink creation unavailable")
    with pytest.raises(ObsidianVaultError, match="hardlink"):
        import_vault_document(vault, "linked.md")


def test_export_refuses_unknown_classification(tmp_path: Path):
    vault = tmp_path / "vault"
    vault.mkdir()
    with pytest.raises(ObsidianVaultError, match="classification"):
        export_vault_document(vault, "note.md", "# Note\n", classification="secret")


@pytest.mark.parametrize("payload", [b"\xff\xfe", b"# note\x00\x01"])
def test_vault_refuses_invalid_utf8_and_binary_markdown(tmp_path: Path, payload: bytes):
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / "invalid.md").write_bytes(payload)

    with pytest.raises(ObsidianVaultError, match="UTF-8|binary"):
        import_vault_document(vault, "invalid.md")


def test_atomic_replace_failure_is_named_and_leaves_no_temp_file(tmp_path: Path, monkeypatch):
    vault = tmp_path / "vault"
    vault.mkdir()

    def fail_replace(_temporary, _destination):
        raise OSError("disk full")

    monkeypatch.setattr(obsidian.os, "replace", fail_replace)
    with pytest.raises(ObsidianVaultError, match="atomic vault replace failed"):
        export_vault_document(vault, "note.md", "# Note\n")
    assert not (vault / "note.md").exists()
    assert list(vault.glob(".*.tmp")) == []


def test_atomic_write_faults_are_structured(tmp_path: Path, monkeypatch):
    vault = tmp_path / "vault"
    vault.mkdir()

    def disk_full(*args, **kwargs):
        raise OSError("simulated disk full")

    monkeypatch.setattr(obsidian.tempfile, "mkstemp", disk_full)
    with pytest.raises(ObsidianVaultError) as error:
        export_vault_document(vault, "note.md", "# Note\n")

    assert error.value.code == "OBSIDIAN-WRITE-FAILED"
    assert error.value.sync_state == "failed"
    assert not (vault / "note.md").exists()


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
