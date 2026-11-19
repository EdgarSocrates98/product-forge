# Wave 07 (cycle 16.1) — product-forge — REPORT

- Branch `cycle16_1/wave07` off baseline `e8c2b8c` (main, clean + synced).
- Implemented: re-vendor to cycle-16.1 canonical — `vendor.py --check .`
  clean: `_installkit.py` (canonical `b574efcfbc13c63e`) and
  `_forgecontext.py` (canonical `ec2a7a80d2467000`), generated via the
  canonical vendor script, never edited in place. New
  `install/lifecycle_state.py`: own-machinery `forge/InstallLifecycle/v1`
  derivation — closed state table (`planned | blocked | failed |
  applied | partially_applied | verified | unverified | ready |
  certified`), `completed` kept as a coarse receipt status that never
  implies readiness; terminal success = verified/ready/certified only.
  `lifecycle` envelope attached to every emitted doc: install plan +
  apply receipt, status, doctor, repair (plan + apply), update,
  uninstall. `_resolved_mcp_command` wired into `_ctx` (shim → absolute
  `sys.executable -m product_forge mcp serve`): the managed `.mcp.json`
  entry is PATH-independent and `mcp verify`/`doctor` probe the argv a
  host would actually spawn — real JSON-RPC handshake verified
  (initialize + initialized + tools/list + `productforge_status`
  invoke → PASS). New CLI `productforge mcp verify` (exit non-zero on
  FAIL/BLOCKED). `repair --dry-run` is now read-only: emits a
  `repair_plan` (`restore`/`keep` entries), no writes. `status`/`doctor`
  recognize docs-only installs via `.forge/context` registry truth.
  Incremental reinstall accounting per canonical installkit:
  `created/updated/unchanged/adopted/skipped` + aggregate `written` +
  `written_bytes`; byte-compare before write → unchanged assets keep
  mtimes (tested). Context byte accounting recorded honestly
  (`skills_bytes`, `agents_bytes`, `managed_bytes`, `mcp_entries`) —
  observed bytes, no invented token savings. Compact L0
  `forge:product-forge` block in AGENTS.md points to capability/
  protocol files instead of duplicating instructions (§8.1). Stale
  `.devin/skills/` duplicate tree removed — `.agents/` is the shared
  host surface, no physical duplication (§7.2).
- Bridge parity gate hardened: `test_embedded_bridge_python_sources_
  match_standalone_checkout` now compares the embedded copy against the
  sibling's *canonical ref* (`origin/main` → `main` → `HEAD`, working
  tree only when gitless). A concurrent wave's unmerged/uncommitted
  work in the sibling checkout is not drift. Verified: embedded
  `src/forge_agent_bridge/` is byte-parity with `forge-agent-bridge`
  `origin/main` @ `34d65b7` (the vendored snapshot point); sibling
  `cycle16_1/wave08` work is pending upstream merge, not vendored.
- Tests: 330 pass, 1 env-skip (+ new `tests/test_install_lifecycle.py`,
  ~20 tests: closed lifecycle vocabulary, receipt/health state mapping,
  `completed` ≠ ready/certified, partial/all-gated batch states, legacy
  receipt compatibility, schema validation, dry-run `planned`,
  status/doctor lifecycle blocks, unverified pristine state, uninstall
  lifecycle, incremental reinstall with unchanged mtimes, context
  metadata + secret absence, resolved MCP argv, `mcp verify` handshake,
  compact L0 block). `tests/test_install.py` updated for absolute MCP
  argv. `tests/test_manifest_version.py` updated as above.
- Gates (fresh): `python -m pytest -q` → 330 passed, 1 skipped ·
  `python -m ruff check src tests` → clean · `productforge install
  --dry-run` → `lifecycle.state: planned`, `verification: UNVERIFIED`,
  bridge skipped-with-reason, app_home planned · `productforge doctor`
  → `ok: true`, required checks green, optional `mcp`/`theforge`
  honestly unavailable, `agent-bridge` honestly `incomplete`.
- Live evidence (scratch `/tmp/pf-w07-ws`): first install →
  `status: completed` + `lifecycle: verified`, counts
  `{created: 45, written: 45, written_bytes: 34941}`, context metrics
  `skills_bytes 26245 / agents_bytes 6407 / managed_bytes 34941 /
  mcp_entries 1`. Second install → `unchanged` entries, no rewrites of
  unchanged assets. `.mcp.json` holds absolute argv
  `<repo>/.venv/bin/python -m product_forge mcp serve`. Deleting a
  managed skill → `repair --dry-run` plan `restore` (zero writes);
  `repair` restores file + context docs. MCP handshake → PASS incl.
  `productforge_status` invoke.
- Docs: `README.md` (lifecycle receipts, incremental reinstall,
  resolved argv, `mcp verify`, 17 MCP tools), `docs/INSTALL.md`
  (scopes/profiles/components/hosts, lifecycle states, incremental
  counts, repair dry-run, resolved MCP registration),
  `docs/MCP.md` (absolute command + real handshake semantics),
  `AGENTS.md` + `CLAUDE.md` (`mcp verify` in command lists),
  `CHANGELOG.md` wave-07 entry. Changed examples executed.
- Repo-local state honestly degraded (expected): this repo's own
  `.mcp.json` predates resolved-argv → `status` reports
  `partially_applied` / modified `.mcp.json`. Reported, not hidden —
  self-repair via `productforge repair` is a repo-state decision, left
  to the owner.
- Env notes: `forge-obsidian` installed editable into `.venv` for its
  subprocess tests (`uv pip install -p .venv/bin/python -e
  ./forge-obsidian`); `productforge install --dry-run`/`doctor` run from
  repo root are read-only.
- Review: independent review pending (per wave spec; record below or in
  the PR).
- NOT NO_CHANGE: real delta shipped (re-vendor + lifecycle envelopes +
  resolved argv + mcp verify + repair dry-run + incremental evidence +
  host-surface dedup + docs).
