You are implementing Loop Factory spec `ecosystem-agentic-version-parity`.

        Native adapter: `codex`
        Spec path: `E:\projetos\FORJAS\product-forge\factory\specs\active\ecosystem-agentic-version-parity.md`
        Spec hash: `bc4457dcea46ea3738c243958db0bc28f3e50230372f82e289611fdd4fc51e71`

        Operating rules:
        - Treat spec as source of truth.
        - Automate code generation and verification, not product decisions.
        - If spec is ambiguous, make smallest reversible assumption and record it in implementation notes.
        - Keep changes scoped to acceptance criteria.
        - Update living spec only for facts learned from implementation or tests.
        - Do not archive spec. Review step does that.
        - Use Codex subagents when work splits cleanly. Ask explicitly before spawning. Keep final answer terse with files changed and checks run.

        Required verification:
        - `uv run pytest -q tests/test_manifest_version.py tests/test_mcp_http.py`
- `uv build --wheel`
- `uv run ruff check src/product_forge tests/test_manifest_version.py tests/test_mcp_http.py`

        Deliverables:
        1. Implement acceptance criteria.
        2. Run verification commands or explain why unavailable.
        3. Add notes under `factory/runs/` or in final response: changed files, checks, open risks.
        4. Leave spec in `factory/specs/active/` for review.

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
