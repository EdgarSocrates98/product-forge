---
id: ecosystem-agentic-version-parity
title: Agentic manifest version parity
status: proposed
created: 2026-11-04
owner: product-forge
scope: product-forge
cycle: "01"
priority: p0
risk: medium
agent: codex
source: prompt_evo_mastering_melhorias.md §8.4
verification:
  - uv run pytest -q tests/test_manifest_version.py tests/test_mcp_http.py
  - uv build --wheel
  - uv run ruff check src/product_forge tests/test_manifest_version.py tests/test_mcp_http.py
---

# Agentic manifest version parity

## Outcome

Every public Product Forge version surface, including the root agentic
capability manifest, must resolve to the package version used by the wheel.

## Acceptance contract

- `forge.agentic.json.version` equals `product_forge.__version__`.
- The regression suite fails if the package and manifest versions diverge.
- The wheel contains the corrected manifest and the existing MCP/portal
  version surfaces remain coherent.
- Verification commands pass from a clean checkout.

## Out of scope

- Publishing a new release version.
- Changing the agentic capability schema or workflow semantics.

## Evidence classification

- Before: `forge.agentic.json` declared `0.1.0` while the package declared
  `0.2.0`.
- Target: `VERIFIED_FIXED` after the listed checks and wheel inspection pass.
