Review Loop Factory spec `ecosystem-agentic-version-parity` against current working tree.

        Native adapter: `codex`
        Spec path: `E:\projetos\FORJAS\product-forge\factory\specs\active\ecosystem-agentic-version-parity.md`

        Review stance:
        - Findings first. Focus correctness, regressions, tests, security, maintainability.
        - Compare implementation against acceptance criteria.
        - Run or inspect verification evidence:
        - `uv run pytest -q tests/test_manifest_version.py tests/test_mcp_http.py`
- `uv build --wheel`
- `uv run ruff check src/product_forge tests/test_manifest_version.py tests/test_mcp_http.py`
        - If accepted, say `ACCEPTED`.
        - If not accepted, say `CHANGES_REQUESTED` and list blocking items.
        - Do not move files. Operator or CLI archive step moves accepted specs.

        Spec:
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
