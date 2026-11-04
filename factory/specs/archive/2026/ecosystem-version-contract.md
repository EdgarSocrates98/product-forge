---
id: ecosystem-version-contract
title: Keep Product Forge distribution version coherent across public surfaces
agent: codex
risk: medium
grill: completed
verification:
  - uv run pytest -q tests/test_manifest_version.py tests/test_mcp_http.py
  - uv build --wheel
  - uv run ruff check src/product_forge/mcp/server.py tests/test_manifest_version.py tests/test_mcp_http.py
---

# Grill Gate

- Owner: ecosystem operator.
- Problem: the package and operational manifest report `0.2.0`, while the MCP
  initialize response and the generated portal web manifest still report
  `0.1.0`.
- Scope: derive public Product Forge version surfaces from the package source,
  add regression coverage, refresh the generated asset, and document the
  release gate.
- Out of scope: bumping the package version, changing MCP protocol versions,
  redesigning the Portal, or publishing a release.
- Review failure: any public version remains hard-coded, the wheel omits the
  corrected asset, or a verification command is skipped/marked pass without
  evidence.
- Riskiest assumption: the checked-in Angular browser manifest is the shipped
  asset and may safely be updated without regenerating the whole bundle.
- Smallest acceptable implementation: MCP handshake and checked-in web
  manifest agree with `product_forge.__version__`, covered by tests and build.

# Context

The master evolution plan calls for one source of truth for distribution
versions and for release gates that reject artifact disagreement. Product
Forge already uses `src/product_forge/__init__.py` as Hatch's dynamic version
source and has a manifest-version test, but two shipped surfaces still embed
the old value.

# Acceptance Criteria

- MCP `initialize` returns `product_forge.__version__` in `serverInfo.version`.
- The checked-in browser manifest uses the same package version.
- Tests fail if either surface diverges from the package version.
- A wheel build includes the corrected public surfaces.
- The verification commands use the repository's supported `uv` environment;
  no nonexistent local `scripts/check_gates.py` is referenced.
- No package version bump or external publication is performed by this spec.

# Constraints

- Keep the MCP protocol version unchanged.
- Preserve the existing Angular bundle and do not edit minified JavaScript
  solely to make an unrelated historical document look current.
- Keep the package source as the version authority.

# Review Notes

- Check both source and built wheel, not only runtime imports from the
  checkout.
- Record stale historical audit text as documentation debt if it is not part
  of the shipped artifact; do not rewrite evidence retroactively.

## Review evidence — 2026-11-04

- `uv run pytest -q tests/test_manifest_version.py tests/test_mcp_http.py` →
  `4 passed`.
- `uv run pytest -q` → `164 passed, 1 skipped`.
- `uv build --wheel` → `product_forge-0.2.0-py3-none-any.whl`.
- Wheel inspection confirmed `product_forge/mcp/server.py` and
  `product_forge/portal_assets/angular/browser/manifest.json` are present.
- Targeted Ruff passed. Full Ruff remains `NOT_ACCEPTED` for this unit because
  five pre-existing findings are in `scripts/forge_bootstrap.py`, outside the
  changed surface; the gap is recorded for the broader release gate.
- Review verdict: ACCEPTED for this spec; the package version was not bumped
  and no publication was performed.
