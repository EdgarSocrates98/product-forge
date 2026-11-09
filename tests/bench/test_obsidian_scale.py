"""Bounded Obsidian projection smoke at the Phase 2 target sizes."""

from pathlib import Path
from time import perf_counter

import pytest

from product_forge.knowledge.obsidian import import_vault_document


@pytest.mark.benchmark
@pytest.mark.parametrize("count", [100, 1000])
def test_import_projection_scales_to_target_note_counts(tmp_path: Path, count: int) -> None:
    vault = tmp_path / "vault"
    notes = vault / "notes"
    notes.mkdir(parents=True)
    for index in range(count):
        (notes / f"note-{index:04d}.md").write_text(
            f"---\naliases: [Note {index}]\n---\n# Note {index}\n\nSee [[note-{(index + 1) % count:04d}]].\n",
            encoding="utf-8",
        )

    started = perf_counter()
    imported = [
        import_vault_document(vault, f"notes/note-{index:04d}.md")
        for index in range(count)
    ]
    elapsed = perf_counter() - started

    assert len(imported) == count
    assert all(item["markdown"]["wikilinks"] for item in imported)
    assert all(item["content_hash"] for item in imported)
    # This is intentionally generous for Windows CI; the assertion catches
    # accidental quadratic work without pretending to be a benchmark suite.
    assert elapsed < 15, f"{count} notes took {elapsed:.2f}s"
