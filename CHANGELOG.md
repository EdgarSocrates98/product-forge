# Changelog — Product Forge

All notable changes. Format follows the evolution cycles (see
`prompt_evo_pf_continue.md` / `prompt_evo_ai_workspace.md` programs).

## [0.2.5] — 2026-11-13

### Changed

- Unified platform release: version bump + VERSION_DUMP.unified-release.json.

## [Unreleased]

### Fixed — cycle-16.1.1 wave-07b

- `setup.sh`: python probe tolerates all-missing (`|| true`) — under
  `set -euo pipefail` the unguarded substitution exited `rc=1` silently
  before `FORGE-PYTHON-NOT-FOUND` could print (vendored defect;
  canonical fix in the-forge wave-01).
- `product_forge/ui/` + `forge_agent_bridge/ui/` — `kit.py`, `i18n.py`,
  `wizard.py` re-vendored to canonical the-forge: both packages had
  drifted (the vendored bridge kit was missing the `installation`
  consolidated-plan block and lifecycle states; product_forge carried a
  pre-refactor kit). product-forge sits outside the the-forge
  `KIT_PARITY_REPOS` gate — a repo-local parity test now covers all six
  vendored copies.

### Changed — cycle-16.1 wave-07

- Re-vendored the canonical installkit + forge_context to the cycle-16.1
  wave-01 state (byte-parity, `_SOURCE_SHA256`-stamped; no in-place edits):
  - **Incremental install** — byte-identical managed files are never
    re-touched; receipts now carry per-asset actions
    (`created`/`updated`/`unchanged`/`adopted`/`skipped`) plus `counts`
    (`written`, `written_bytes`) and an honest `context` byte budget.
  - **Resolved `.mcp.json` argv** — the managed server key now declares
    the bootstrap shim (absolute) or `python -m product_forge mcp serve`;
    hosts never launch the forge through a PATH lookup (§9.3).
  - **Compact `forge:*` doc block** — the AGENTS.md per-forge block is
    the routing-critical minimum (identity, domains, verifiable
    pointers), not a duplicated instruction dump (§8.1).
  - The install `doctor` now runs a real MCP JSON-RPC handshake
    (`mcp-handshake`/`mcp-invoke` checks) instead of inferring health
    from file presence.
- New `forge/InstallLifecycle/v1` envelope on every install-surface
  document (ported from `the-forge`'s lifecycle model; the vendored
  engine is untouched): plan/install/update/repair/uninstall receipts
  and `status`/`doctor` health docs carry a derived closed-vocabulary
  `lifecycle.state` — `completed` never implies production-ready; only
  `verified`/`ready`/`certified` back a success claim. Persisted
  receipts carry the same block; older receipts still parse.
- `productforge mcp verify` — the verb `forge.json` already declared
  (`install.operations` includes `mcp-verify`): read-only handshake
  probe against the resolved argv; `FAIL`/`BLOCKED` exit 1.
- `repair --dry-run` is now truly read-only (previously it ran the
  write path and returned a "repaired" receipt): it emits a
  `repair_plan` with per-path `restore`/`reheal`/`skipped` actions.
- `status`/`doctor` reconcile docs-only installs: an empty kit ledger +
  a real `.forge/context` registry entry reports `healthy`
  (`context_registered: true`), not a false NOT_INSTALLED.
- Committed host-mirror hygiene: removed `.devin/skills/` — a stale,
  byte-identical duplicate of `.agents/skills/` from a pre-consolidation
  install (`.agents/` is the shared Devin/Codex/Copilot surface; §7.2).
- Docs: INSTALL.md gains the lifecycle receipt model, incremental
  reinstall and read-only repair plan; MCP.md/README document the
  resolved `.mcp.json` argv, `mcp verify` and the 17-tool count.

### Changed — install-2.1 (cycle-16 wave-06)

- Re-vendored the forge installkit 1.0.4 → 1.0.6 (`--root` precedence,
  gitless workspace-member discovery, `InstallContext.exclude` conflict
  skips, `manifest_for` declared-surface params) and `forge_bootstrap`
  with the matching registration passthrough.
- `forge.json` now declares the install-2.1 surface verbatim:
  `installation_kind: "content"`, the `install{}` surface (operations
  including `mcp-verify`, flags, hosts, scopes, profiles,
  `approval: "--yes"`), `mcp_verify_tool: "productforge_status"` and
  `depends_on: ["forge-agent-bridge"]` — install-order only; the wheel
  vendors the bridge, so it is an optional companion service, never a
  required prior install.
- **User-level provisioning decoupled from content install**: a
  `project`/`workspace` install no longer writes `~/.productforge`,
  `~/.forge-bridge` or reconciles the runtime backend. New opt-in flags
  `--init-app` / `--with-bridge` (default = `scope == "user"`); skipped
  steps report named `skipped` states in the receipt.
- Bridge provisioning is once-per-account: existing
  `~/.forge-bridge/components.json` reports `skipped` instead of
  rewriting providers/config/ledger snapshots. The vendored `verify-cli`
  PATH probe (unreachable — the wheel ships no `forge-bridge` script)
  is replaced by an import-based `verify-module` check.
- Uninstall is bridge-ownership-aware: a `bridge-provisioned` marker
  under this install's state dir proves what it provisioned; a
  registered standalone `forge-agent-bridge` or unknown-provenance
  state is preserved. `pair.token`, `events/` and `backups/` remain
  user content in every path.
- Declared fields (`installation_kind`, `install`, `depends_on`) now
  propagate to the `~/.forge/installations/product-forge.json`
  manifest.
- `uninstall --purge` is the canonical flag (sibling parity);
  `--purge-state` remains an alias.
- Docs: profile matrix is honest — `full` installs the same asset kinds
  as `recommended` today; `tui`/`graph-studio` are opt-in components,
  never profile-gated. INSTALL.md/README reflect `forge:*` doc blocks,
  `.agents/skills` host surface, scope-gated user state and the
  ownership-aware bridge lifecycle. MCP tool count corrected to 17.

## [0.2.4] - 2026-11-12

Cycle 2.7 patch release: federated SDD contracts and adapters, forge-context kind taxonomy, universal Obsidian export verbs, portal and install UX improvements, provider context-registry wiring, CI hardening and generated-artifact refresh.


## [0.2.3] - 2026-11-10

### Fixed

- Published the Cycle 2.7 release certification baseline.

## [0.2.2] - 2026-11-04

### Changed

- Prepared the release after `0.2.1` was already present on PyPI.

## [0.2.1] - 2026-11-04

### Fixed

- Added dynamic workspace context discovery for PRDs, briefs, knowledge and
  repository documents, with refreshed portal assets.

### Added
- **Guided install parity with sparkforge-aws** — bare `productforge install`
  on a TTY opens the shared wizard: scope (`project`/`workspace`/`user`),
  install profile, execution profile (`economy`/`balanced`/`deep`),
  components (`skills,agents,mcp,tui,graph-studio`), hosts, real dry-run
  plan → confirm → apply → doctor. Flags stay non-interactive JSON.
- **Bootstrap scripts** — `install.sh`, `install.windows.sh`, `install.ps1`
  + `scripts/forge_bootstrap.py` (generic, `forge.json`-driven): wheel →
  isolated venv → launcher → smoke → register.
- Content bundles (`rules/catalog`, `evals`, `knowledge`) shipped under
  `<state_dir>/bundle/`; `components.json` records the selection;
  `gateway_profile` persisted to app config.
- 16 `pf-*` skills refreshed via skill-creator for post-Cycle-15 capability
  (llm_runtime seam, semantic catalog `via`, metric catalog).

## Released cycle history

| Commit(s) | Cycles | Highlights |
|---|---|---|
| `d6a1930` | 16–17 | analysis notebooks; doc-store persistence fix |
| `26447cf` | 18 | 5-persona homologation; `PRODUCTION_READINESS_REPORT` (Ready w/ restrictions) |
| `ccf374a` | 17 | Experiment Studio, Meeting Intelligence, Decision Journal |
| `28ab31d` | 17 | Product Health Center, unified evidence graph |
| `3faf4a7` | 16 | semantic metrics catalog — KPIs as data |
| `c227b1d` | 15 | real LLM agent runtime via gateway provider (provider seam, tool loop, budget) |
| `9501cf4`, `c67e683` | 13–14 | durable job registry, workspace RBAC-lite; auth gap fix, KQL/DAX validators, migrations, audit IDs |
| `7131531` | factory | 4 specs archived — MCP HTTP transport, native agent templates, LLM gateway contract, delegation |
| `b4f8ea7` | — | own inter-forge delegation (subprocess + JSON) |
| `97def19`, `98c2e99` | — | agentic layer (coordinators + pf-* executors, rules catalog); installkit parity + MCP expansion |
| `e144f88` | 10–11 | product operations (reports, watches, alerts, approvals) + advanced agentic |
| `b784a62` | 8–9 | honest cloud intelligence + API/data-product intelligence |
| `7b3a447` | 6–7 | dashboard rendering + planning intelligence |
| `579df60` | 5 | analytics engine — validation, connectors, execution, spec/NL compile |
| `3f1c1f9` | 4 | agent runtime, policy engine, eval harness, publish gate |
| `68bab79` | 3 | entity extraction, knowledge graph, health, doc import API |
| `7a71e67` | 15.3 | 16 domain skills validated |
| `33fa3dc` | 12 | homologation — Payments E2E, negative scenarios, portal expansion |
| `07cf5c7` | 1–2 | forge-compatible core: API (`forge/PortalApi/1`), CLI, MCP, portal adapter |

## Hard invariants (never regressed)

- Honesty-first: `unverified`/`unavailable:*` are named states, never
  fabricated success.
- Deterministic core: ambiguity → `ambiguous`; no LLM/wall-clock in engines.
- Evidence-first: entity ids, rule_ids, run ids, chunk citations.
- Read-only analytics: sqlglot-validated; writes/multi-statements rejected.
- Gated mutations: publish eval ≥ 0.5 + `tools_allowed`; confirm/approval.
- Envelope `forge/PortalApi/1` + typed `PF-*` errors.
- Vendored `_forge_portal.py`/`_installkit.py` byte-parity.
- Persisted docs pass `security.redact`.
