# Obsidian interoperability evidence — 2026-11-07

## Delivered

- Added bounded, UTF-8 checked validation for JSON Canvas documents.
- Added bounded YAML/JSON validation for the Obsidian Bases container.
- Canvas validation rejects missing arrays, duplicate/empty IDs, unsupported
  node types and edges that point to absent nodes.
- Bases validation rejects malformed documents and invalid known section
  shapes, while preserving unknown fields by design.
- No Obsidian application, CLI, renderer or remote process is invoked.

## Explicit boundary

This is an interoperability safety seam, not full Obsidian feature parity. The
implementation does not claim to evaluate Bases formulas/filters, render a
Canvas, or provide a visual editor. Those remain follow-up work behind the
same versioned validation contracts.

## Verification

```text
uv run pytest -q tests/test_obsidian.py  # 15 passed
uv run ruff check src/product_forge/knowledge/obsidian.py tests/test_obsidian.py
```
