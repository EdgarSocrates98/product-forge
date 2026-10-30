# IMPLEMENTATION_GAP_MATRIX — living status (updated per cycle)

Legend: ✅ done+tested · 🟡 partial · 🔲 planned

## Cycle 1 — Foundation ✅ baseline landed
| Requirement | Status | Evidence |
|---|---|---|
| Repo structure + packaging | ✅ | pyproject (hatchling), `.venv` install works |
| CLI foundation | ✅ | `productforge` typer app: install/status/doctor/workspace/product/knowledge/agent/api/mcp/portal |
| Profiles + config | ✅ | `config.py` layered cfg, install/gateway profiles |
| Logging/security baseline | ✅ | `security.py` redact/safe_path/TokenStore; audit table |
| Domain model | ✅ | `domain/models.py` 15 entities, permission catalog |
| Tests + CI | ✅ 7 tests green | `tests/test_core.py`; CI workflow pending |
| Forge compatibility | ✅ | forge.json, forge.agentic.json, PortalApi/1, vendored portal server |

## Cycle 2 — Studio foundation 🟡
- Portal adapter + nav: ✅ ops registered, served via `productforge portal`
- Angular module in forge-portal: 🔲 (needs shared-repo PR or standalone bundle)
- Onboarding flow, i18n, a11y pass: 🔲

## Cycle 3 — Knowledge/Context/Graph 🟡
- Ingestion pipeline (text/md → chunks → FTS5): ✅ `knowledge import/query`
- Citations: ✅ chunk-level; LLM synthesis: 🔲 (needs gateway)
- Entity extraction → graph: 🔲 (model exists; extractor pending)
- Product Context Package: ✅ endpoint + CLI
- Knowledge health/versioning: 🔲

## Cycle 4 — Agent Factory 🟡
- Registry/definitions CRUD: ✅
- Runtime, policies, MCP tools, evals, publishing: 🔲

## Cycle 5 — Analytics 🟡
- Data source registry: ✅; connectors, sqlglot validation, execution, NL→SQL, visual builder: 🔲

## Cycle 6 — Dashboards 🟡
- CRUD: ✅; widgets/charts/filters/templates/sharing/AI assist: 🔲

## Cycle 7 — Planning 🟡
- Initiatives/decisions CRUD: ✅; hypotheses, prioritization (RICE/WSJF), PRD/stories/roadmap generators, risks: 🔲

## Cycles 8–11 🔲
AWS/Azure intel, API & data-product intel, ops automation, multi-agent workflows — scaffolding exists (module dirs), implementation pending.

## Cycle 12 🔲 Hardening + homologation + 30-step Payments scenario.

## Debt & risks
- `agents` `_crud` id prefix uses `p.rstrip("s")[:3]` → "ag" (cosmetic).
- API PATCH only for workspaces; extend per collection in later cycles.
- Portal Angular module path needs decision: PR into forge-portal vs standalone assets_dir.
