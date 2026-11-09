from __future__ import annotations

from pathlib import Path

import forge_obsidian
from forge_obsidian import obsidian as canonical
from product_forge.knowledge import obsidian as compatibility


def test_neutral_library_does_not_import_product_forge_runtime() -> None:
    assert canonical.__name__ == "forge_obsidian.obsidian"
    assert "product_forge" not in canonical.__dict__
    assert forge_obsidian.ObsidianVaultError is canonical.ObsidianVaultError
    assert forge_obsidian.obsidian_projection_metadata is canonical.obsidian_projection_metadata


def test_product_forge_path_is_a_compatibility_facade() -> None:
    assert compatibility.ObsidianVaultError is canonical.ObsidianVaultError
    assert compatibility.scan_vault_documents is canonical.scan_vault_documents


def test_compatibility_fault_injection_reaches_canonical_module(monkeypatch) -> None:
    sentinel = object()
    monkeypatch.setattr(compatibility, "_atomic_write", sentinel)
    assert canonical._atomic_write is sentinel


def test_library_surface_has_no_filesystem_relative_imports() -> None:
    source = Path(canonical.__file__).read_text(encoding="utf-8")
    assert "from product_forge" not in source
    assert "import product_forge" not in source
