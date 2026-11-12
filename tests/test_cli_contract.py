import io
import json
from pathlib import Path

from typer.testing import CliRunner

from product_forge import __version__, cli
from product_forge.cli import app


def test_version_flag_is_available_at_the_cli_root() -> None:
    result = CliRunner().invoke(app, ["--version"])
    assert result.exit_code == 0
    assert result.stdout.strip() == __version__


def test_json_output_falls_back_to_ascii_for_legacy_windows_codepages(monkeypatch) -> None:
    class LegacyStdout(io.StringIO):
        encoding = "cp1252"

    stream = LegacyStdout()
    monkeypatch.setattr(cli.sys, "stdout", stream)
    cli._out({"plan": "managed bridge → workspace"})
    output = stream.getvalue()
    assert "managed bridge" in output
    assert "\\u2192" in output


def test_obsidian_cli_exposes_safe_preview_plan_and_explicit_apply(tmp_path: Path, monkeypatch) -> None:
    vault = tmp_path / "vault"
    (vault / "notes").mkdir(parents=True)
    (vault / "notes" / "runbook.md").write_text("# Runbook\n\nRestart the worker safely.\n", encoding="utf-8")
    candidate = tmp_path / "candidate.md"
    candidate.write_text("# Candidate\n\nReviewed change.\n", encoding="utf-8")
    monkeypatch.setenv("FORGE_OBSIDIAN_VAULT", str(vault))

    runner = CliRunner()
    preview = runner.invoke(app, ["knowledge", "obsidian", "preview", "notes/runbook.md"])
    assert preview.exit_code == 0, preview.stdout
    preview_payload = json.loads(preview.stdout)
    assert preview_payload["schema"] == "theforge/ObsidianPreview/v1"
    assert preview_payload["path"] == "notes/runbook.md"
    assert "content" not in preview_payload

    plan = runner.invoke(
        app,
        ["knowledge", "obsidian", "sync-plan", "notes/next.md", str(candidate)],
    )
    assert plan.exit_code == 0, plan.stdout
    assert json.loads(plan.stdout)["outcome"] == "created"

    refused = runner.invoke(
        app,
        ["knowledge", "obsidian", "export", "notes/next.md", str(candidate)],
    )
    assert refused.exit_code != 0
    assert not (vault / "notes" / "next.md").exists()

    applied = runner.invoke(
        app,
        ["knowledge", "obsidian", "export", "notes/next.md", str(candidate), "--yes"],
    )
    assert applied.exit_code == 0, applied.stdout
    applied_payload = json.loads(applied.stdout)
    assert applied_payload["sync_state"] == "created"
    assert (vault / "notes" / "next.md").read_text(encoding="utf-8") == candidate.read_text(encoding="utf-8")


def test_obsidian_import_and_evidence_are_real_product_capabilities(tmp_path: Path, monkeypatch) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / "runbook.md").write_text("# Runbook\n\nEvidence.\n", encoding="utf-8")
    monkeypatch.setenv("FORGE_OBSIDIAN_VAULT", str(vault))
    monkeypatch.setenv("PRODUCT_FORGE_HOME", str(tmp_path / "product-home"))

    runner = CliRunner()
    assert runner.invoke(app, ["install", "--yes"]).exit_code == 0
    workspace = json.loads(runner.invoke(app, ["workspace", "create", "ws"]).stdout)
    product = json.loads(runner.invoke(app, ["product", "create", workspace["id"], "Payments"]).stdout)

    imported = runner.invoke(
        app,
        ["knowledge", "obsidian", "import", product["id"], "runbook.md"],
    )
    assert imported.exit_code == 0, imported.stdout
    imported_payload = json.loads(imported.stdout)
    assert imported_payload["state"] == "imported"
    assert imported_payload["receipt"]["schema"] == "theforge/ObsidianKnowledgeImportReceipt/v1"
    assert "content" not in imported_payload

    evidence = runner.invoke(app, ["knowledge", "evidence", product["id"]])
    assert evidence.exit_code == 0, evidence.stdout
    evidence_payload = json.loads(evidence.stdout)
    assert evidence_payload["schema"] == "theforge/KnowledgeEvidenceList/v1"
    assert evidence_payload["items"][0]["metadata"]["obsidian_path"] == "runbook.md"
