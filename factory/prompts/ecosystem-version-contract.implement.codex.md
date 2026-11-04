You are implementing Loop Factory spec `ecosystem-version-contract`.

        Native adapter: `codex`
        Spec path: `E:\projetos\FORJAS\product-forge\factory\specs\active\ecosystem-version-contract.md`
        Spec hash: `076975830d9aebea3a18a5f38865d485a0a285cca2e5f66e2bb632dab27ec488`

        Operating rules:
        - Treat spec as source of truth.
        - Automate code generation and verification, not product decisions.
        - If spec is ambiguous, make smallest reversible assumption and record it in implementation notes.
        - Keep changes scoped to acceptance criteria.
        - Update living spec only for facts learned from implementation or tests.
        - Do not archive spec. Review step does that.
        - Use Codex subagents when work splits cleanly. Ask explicitly before spawning. Keep final answer terse with files changed and checks run.

        Required verification:
        - `python -m pytest -q tests/test_manifest_version.py tests/test_mcp_http.py`
- `python -m build --wheel --no-isolation`
- `python scripts/check_gates.py`

        Deliverables:
        1. Implement acceptance criteria.
        2. Run verification commands or explain why unavailable.
        3. Add notes under `factory/runs/` or in final response: changed files, checks, open risks.
        4. Leave spec in `factory/specs/active/` for review.

        Spec:
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
