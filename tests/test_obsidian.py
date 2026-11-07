from pathlib import Path

import pytest

from product_forge.knowledge.obsidian import (
    ObsidianVaultError,
    export_vault_document,
    import_vault_document,
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
    assert (vault / "notes" / "result.md").read_text(encoding="utf-8") == "# Result\n\nDone.\n"


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
