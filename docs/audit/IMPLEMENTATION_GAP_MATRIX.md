# IMPLEMENTATION_GAP_MATRIX — living status (final, Cycle 12)

Legend: ✅ done+tested · 🟡 partial · 🔲 deferred (documented, not silently absent)

## Cycle 1 — Foundation ✅
| Requirement | Status | Evidence |
|---|---|---|
| Repo structure + packaging | ✅ | pyproject (hatchling), editable install works |
| CLI foundation | ✅ | `productforge` typer app: install/status/doctor/workspace/product/knowledge/agent/api/mcp/portal |
| Profiles + config | ✅ | `config.py` layered cfg, install/gateway profiles |
| Logging/security baseline | ✅ | `security.py` redact/safe_path/TokenStore; audit table |
| Domain model | ✅ | `domain/models.py` entities, permission catalog |
| Tests + CI | ✅ | `tests/`; `.github/workflows/ci.yml` |
| Forge compatibility | ✅ | forge.json, forge.agentic.json (`forge/SpecialistAgenticManifest/v1`), `forge/PortalApi/1` envelope, vendored portal server byte-parity |

## Cycle 2 — Studio foundation ✅ (adapter) / 🟡 (Angular surface)
- Portal adapter: ✅ ops registered (read + mutating w/ confirm), served via `productforge portal`
- Angular module inside forge-portal repo: 🔲 deferred — requires cross-repo change; adapter contract is the stable surface

## Cycle 3 — Knowledge/Context/Graph ✅
- Ingestion → chunks → FTS5 with triggers: ✅ `knowledge/ingest.py`
- Citations: ✅ chunk-level; LLM synthesis: `unavailable:no-llm-provider` (honest, not fabricated)
- Entity extraction → graph: ✅ `knowledge/extract.py`, `knowledge/graph.py` (heuristic, deterministic)
- Product Context Package: ✅ endpoint + CLI
- Knowledge health: ✅ `GET /products/{pid}/knowledge-health`

## Cycle 4 — Agent Runtime & Factory ✅
- Registry/definitions CRUD: ✅
- Deterministic runtime, policy engine (injection blocked, tool allowlist): ✅ `agents/policy.py`, `agents/runtime.py`
- Tools registry: ✅ `agents/tools.py`; MCP stdio: ✅ `mcp/server.py`
- Evals + publish gate (tools_allowed + score ≥ 0.5): ✅ `agents/evals.py`
- Run cancel/list: ✅

## Cycle 5 — Analytics ✅
- Data source registry + schema/verify: ✅
- sqlglot read-only validation (rejects writes/multiple statements): ✅ `analytics/sqlvalidate.py`
- Real execution: SQLite/DuckDB connectors, row limits, timeouts, path allowlist: ✅ `analytics/connectors.py`, `analytics/engine.py`
- Visual spec compile + deterministic NL→query scaffolding: ✅
- Query cancel/list/get + persisted runs: ✅

## Cycle 6 — Dashboards ✅
- CRUD + render against stored analytics: ✅ `dashboards/render.py`
- Chart/KPI widget types, filters: ✅

## Cycle 7 — Planning & Discovery ✅
- Prioritization (deterministic score): ✅ `planning/prioritize.py`
- PRD generation grounded in product context: ✅ `planning/prd.py`
- Roadmap lanes (now/next/later): ✅ `planning/roadmap.py`
- Initiatives/decisions CRUD: ✅

## Cycle 8 — AWS/Azure Intelligence ✅ (honest)
- AWS/Azure inventory endpoints: ✅ `integrations/aws.py`, `integrations/azure.py`
- Missing creds/config → `unverified`/error states, never fake inventory: ✅

## Cycle 9 — API & Data Product Intelligence ✅
- OpenAPI/AsyncAPI parsing + import → knowledge entities: ✅ `integrations/apispec.py`
- API diff / breaking-change analysis: ✅
- Data contracts + payload validation: ✅ `integrations/datacontract.py`
- Impact analysis via graph: ✅

## Cycle 10 — Product Operations ✅
- Watches create/list/run/due→alerts: ✅ `operations/watches.py`
- Alert lifecycle (ack/resolve/reopen): ✅
- Executive report generation: ✅ `operations/reports.py`
- Approvals request/decide with gate: ✅ `operations/approvals.py`

## Cycle 11 — Advanced Agentic ✅
- Multi-agent deterministic workflows: ✅ `agents/workflows.py`
- Model/task routing (deterministic, `ambiguous` on ambiguity): ✅ `agents/routing.py`
- Budget ledger persisted: ✅

## Cycle 12 — Hardening & Homologation ✅
- Payments Product Intelligence 30-step E2E: ✅ `tests/test_homologation.py`
- Negative scenarios (401, injection, destructive SQL, cross-product, empty-honest, publish gate, 404): ✅ `tests/test_negative.py`
- Data-source verify/schema root-authorization fix: ✅ `api/app.py`
- Portal adapter expanded (knowledge query, graph, health, query exec w/ confirm, agent run w/ confirm, roadmap, alerts): ✅
- 56 tests green, ruff clean.

## Post-Cycle 12 — Installkit parity + MCP expansion ✅
- Vendored `src/product_forge/_installkit.py` (canonical the-forge/scripts/installkit): `install --profile minimal|recommended|full --host <hosts> --scope user|project`, plan/dry-run, ledger ownership, AGENTS.md markers, `.mcp.json`, drift → `repair`, `update`, `uninstall`. Same engine as spark-forge-aws: ✅ `install/lifecycle.py`, `tests/test_install.py`
- MCP expanded 5 → 14 tools (graph, knowledge health, query validate, dashboards, roadmap, alerts, audit, agent run/eval): ✅ `mcp/server.py`
- Skills shipped in wheel via `force-include` → installed into host skills dirs: ✅
- 61 tests green, ruff clean.

## Deferred (explicitly, not silently)
- Angular module inside forge-portal repo (cross-repo PR required)
- LLM-backed synthesis (returns `unavailable:no-llm-provider` until gateway configured)
- Postgres backend (SQLite is the shipped store; migration path in ADR-001)
- Notifications to external channels (alerts persisted; delivery not implemented)

## Known cosmetic debt
- `agents` `_crud` id prefix → "ag" (cosmetic only)
