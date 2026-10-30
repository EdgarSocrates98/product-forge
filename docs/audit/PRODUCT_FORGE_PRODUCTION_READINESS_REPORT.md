# Product Forge — Production Readiness Report

**Date**: 2026-10-30 · **Branch**: `main` · **Suite**: 95 tests green · ruff clean · CI green

## Verdict: **Ready with restrictions**

Product Forge evolved from a promising foundation into a coherent product-
intelligence platform: a PM/PA can create a product, build its knowledge
base, connect data, run governed analytics, generate dashboards, publish
specialized agents and produce auditable results. The restrictions below
are real and named — none are hidden.

## Persona homologation (Cycle 18 evidence)

| Persona | Journey | Result |
|---|---|---|
| **PM** | workspace → product → docs → APIs → source → knowledge → graph → agent → eval → publish → SQL → dashboard → planning → ops → audit (`test_homologation.py`, 30 steps) | ✅ Homologated |
| **PA** | metric catalog → NL question → validated SQL → dashboard → executive report | ✅ Homologated |
| **Technical PM** | OpenAPI import → diff → contract → evidence graph → health | ✅ Homologated |
| **Data Product Mgr** | contract → payload validation → schema discovery → audit trail | ✅ Homologated |
| **Agent Creator** | template catalog → create → tools_allowed → eval → publish gate → run → budget | ✅ Homologated |
| **Analyst (notebooks)** | markdown + SQL block run → version bump → render w/ provenance; DELETE block rejected | ✅ Homologated |
| **Failure modes** | unauth 401, DROP/DELETE rejected, unknown metric clarification, empty result honest, no-provider named state, typed 404 | ✅ Homologated |

## Feature classification

| Area | Status | Evidence |
|---|---|---|
| AuthN/AuthZ | ✅ Implemented+Tested | Bearer on all private routes incl. GET; RBAC-lite workspace scope |
| Security headers | ✅ | nosniff/DENY/no-referrer/no-store on every response |
| Persistence | ✅ | SQLite WAL+FK, incremental migrations, `backup()`, `integrity_check()` |
| Durable jobs | ✅ | registry: idempotency, checkpoint, cancel, boot-recovery, dead-letter |
| SQL safety | ✅ | sqlglot read-only; KQL/DAX conservative validators + `:unverified` |
| Knowledge | ✅ | FTS5 with chunk citations; entity/relation extraction |
| Semantic metrics | ✅ | catalog → resolve → operator-formula SQL (`via: semantic-catalog`) |
| NL-to-SQL | ✅ | metric-first, deterministic fallback, honest `no-known-table` |
| Agents | ✅ | templates+skills+evals, publish gate (tools_allowed + eval ≥ 0.5) |
| LLM runtime | ✅ Integrated | subprocess+JSON provider seam, tool loop, turn caps, budget ledger; **no provider configured by default → deterministic fallback** |
| Health Center | ✅ | 8 dimensions, every score carries evidence |
| Evidence Graph | ✅ | entities/relations + 11 typed collections unified |
| Experiments | ✅ | guardrails/baseline verdicts; no causal claims |
| Meeting Intel | ✅ | draft extraction; publish requires `reviewed=true` (PF-REVIEW-REQUIRED) |
| Decision Journal | ✅ | completeness checklist, missing-field honesty |
| Analysis Notebooks | ✅ | versioned markdown/sql blocks; SQL runs through the same read-only gate; render carries statement SHA + provenance |
| Product Ops | ✅ | alerts, watches/run-due, scheduled reports |
| MCP | ✅ | stdio + `POST /mcp` HTTP, 14 tools |
| Delegation | ✅ | operator allowlist → subprocess+JSON; refused/unavailable named states |
| Portal Studio | ✅ Integrated | `/pf` Angular module in forge-portal `2e37ccd`; build clean, 579/579 specs |
| CI | ✅ | GitHub Actions green (billing resolved; `.[dev]` dep fix) |

## Restrictions (named, honest)

1. **No LLM provider configured** — `llm.provider=none` default; the seam
   (`gateway.provider_cmd`) is ready but real-LLM behavior requires an
   operator-chosen provider. Fallbacks are deterministic and honest.
2. **Cloud connectors** — AWS/Azure inventory is `unverified` without
   credentials; capability seams exist but provider execution is not claimed.
3. **Portal E2E** — Angular unit tests green; Playwright browser-level E2E
   is Partial (not run in this environment).
4. **Postgres backend** — deferred spec; SQLite is the production store.
5. **Meeting extraction** — deterministic marker scan; rich transcript
   understanding needs the LLM seam configured.

## Security posture

Redaction before persistence (with explicit non-secret exemptions), no
credentials in provider envs, audit trail on every mutation, publish/approve/
review gates enforced server-side, destructive SQL never executed.

## Release readiness

- Engine usable standalone (CLI + API + MCP) and via Portal.
- `productforge install --dry-run` + `doctor` verified.
- Restrictions documented for operators; none block the core PM/PA journeys.
