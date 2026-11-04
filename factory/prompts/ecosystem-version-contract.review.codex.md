Review Loop Factory spec `ecosystem-version-contract` against current working tree.

        Native adapter: `codex`
        Spec path: `E:\projetos\FORJAS\product-forge\factory\specs\active\ecosystem-version-contract.md`

        Review stance:
        - Findings first. Focus correctness, regressions, tests, security, maintainability.
        - Compare implementation against acceptance criteria.
        - Run or inspect verification evidence:
        - `uv run pytest -q tests/test_manifest_version.py tests/test_mcp_http.py`
- `uv build --wheel`
- `uv run ruff check src/product_forge/mcp/server.py tests/test_manifest_version.py tests/test_mcp_http.py`
        - If accepted, say `ACCEPTED`.
        - If not accepted, say `CHANGES_REQUESTED` and list blocking items.
        - Do not move files. Operator or CLI archive step moves accepted specs.

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
