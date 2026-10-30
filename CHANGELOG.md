# Changelog — Product Forge

All notable changes. Format follows the evolution cycles (see
`prompt_evo_pf_continue.md` / `prompt_evo_ai_workspace.md` programs).

## [Unreleased]

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
