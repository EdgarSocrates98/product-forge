# Graph Report - product-forge  (2026-10-29)

## Corpus Check
- 162 files · ~55,875 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 1252 nodes · 1907 edges · 115 communities (106 shown, 9 thin omitted)
- Extraction: 95% EXTRACTED · 5% INFERRED · 0% AMBIGUOUS · INFERRED: 97 edges (avg confidence: 0.86)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `97def194`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- app.py
- LLM gateway integration for synthesis (replaces unavailable:no-llm-provider)
- run_agent
- cli/__init__.py
- security.py
- TokenStore
- engine.py
- test_negative.py
- fixture
- aws.py
- test_cycle89.py
- ProductForgePortal
- test_cycle1011.py
- IMPLEMENTATION_GAP_MATRIX — living status (final, Cycle 12)
- Agent Factory
- Path
- Analytics
- Apis
- Aws
- Azure
- Dashboards
- Data Products
- Finops
- Governance
- Knowledge
- Prioritization
- Product Discovery
- Product Strategy
- Reporting
- Requirements
- Sql
- MCP streamable-HTTP transport alongside stdio
- Product Forge
- Ctx
- create_app
- _installkit.py
- Any
- lifecycle.py
- InstallError
- plan
- Store
- tools.py
- Agent Factory
- Analytics
- Apis
- Aws
- Azure
- Dashboards
- Data Products
- Finops
- Governance
- Knowledge
- Prioritization
- Product Discovery
- Product Strategy
- Reporting
- Requirements
- Sql
- Agent Factory
- Analytics
- Apis
- Aws
- Azure
- Dashboards
- Data Products
- Finops
- Governance
- Knowledge
- Prioritization
- Product Discovery
- Product Strategy
- Reporting
- Requirements
- Sql
- Ledger
- datacontract.py
- sqlite.py
- call_tool
- watches.py
- runtime.py
- run_workflow
- record_usage
- Native agent templates (§6.3) — product-analyst, data-steward, api-guardian
- product-forge
- Product Forge — Agent Instructions
- product-forge
- External notification delivery for alerts (webhook/email)
- Angular module for Product Forge inside forge-portal
- PostgreSQL store backend alongside SQLite
- pf-extractor
- pf-judge
- pf-synthesizer
- pf-verifier
- pf-extractor
- pf-judge
- pf-synthesizer
- pf-verifier
- Product Forge — Agent Instructions
- Agent Ops Coordinator
- Agent Ops Coordinator
- Data Analyst Coordinator
- Integration Coordinator
- Planning Coordinator
- Product Intelligence Coordinator
- Data Analyst Coordinator
- Integration Coordinator
- Planning Coordinator
- Product Intelligence Coordinator
- mcp_verify
- Product Forge — agent rules (Claude mirror)
- factory/README.md
- backups/CLAUDE.md
- install/__init__.py
- Any
- Path

## God Nodes (most connected - your core abstractions)
1. `Store` - 57 edges
2. `_out()` - 36 edges
3. `_store()` - 28 edges
4. `apply_install()` - 24 edges
5. `ProductForgePortal` - 23 edges
6. `run_agent()` - 19 edges
7. `TokenStore` - 18 edges
8. `_store()` - 17 edges
9. `uninstall()` - 16 edges
10. `IMPLEMENTATION_GAP_MATRIX — living status (final, Cycle 12)` - 16 edges

## Surprising Connections (you probably didn't know these)
- `test_api_agent_flow()` --calls--> `create_app()`  [INFERRED]
  tests/test_cycle4.py → src/product_forge/api/app.py
- `test_mcp_tools_expanded()` --calls--> `Store`  [INFERRED]
  tests/test_install.py → src/product_forge/store/sqlite.py
- `test_schema_explorer()` --uses--> `SQLiteConnector`  [INFERRED]
  tests/test_cycle5.py → src/product_forge/analytics/connectors.py
- `_store()` --uses--> `Store`  [INFERRED]
  tests/test_cycle1011.py → src/product_forge/store/sqlite.py
- `_seed()` --uses--> `Store`  [INFERRED]
  tests/test_cycle3.py → src/product_forge/store/sqlite.py

## Import Cycles
- None detected.

## Communities (115 total, 9 thin omitted)

### Community 0 - "app.py"
Cohesion: 0.22
Nodes (14): BaseModel, _cid(), CompileIn, envelope(), ExecuteIn, NlIn, ProductIn, QueryIn (+6 more)

### Community 1 - "LLM gateway integration for synthesis (replaces unavailable:no-llm-provider)"
Cohesion: 0.29
Nodes (6): Acceptance Criteria, Constraints, Context, Grill Gate, LLM gateway integration for synthesis (replaces unavailable:no-llm-provider), Review Notes

### Community 2 - "run_agent"
Cohesion: 0.18
Nodes (19): AgentDefinition, json_str(), Any, Agent evaluation harness — real runs against real knowledge. A case: {question,…, run_evals(), check_budget(), check_input(), check_tool() (+11 more)

### Community 3 - "cli/__init__.py"
Cohesion: 0.07
Nodes (72): command, KnowledgeEntity, Relation, ag_create(), ag_eval(), ag_list(), ag_publish(), ag_run() (+64 more)

### Community 4 - "security.py"
Cohesion: 0.29
Nodes (6): Entity, Security primitives: secret redaction, path confinement, token store.…, Deep-scrub secret-shaped values before persistence or transport., redact(), _secretish(), _T

### Community 5 - "TokenStore"
Cohesion: 0.25
Nodes (3): Path, Local API bearer token — generated on first use, file 0600., TokenStore

### Community 6 - "engine.py"
Cohesion: 0.06
Nodes (47): Connection, Event, parametrize, Protocol, Connector, connector_for(), DuckDBConnector, _mask() (+39 more)

### Community 7 - "test_negative.py"
Cohesion: 0.17
Nodes (3): client(), fixture, Negative scenarios — required failure modes all verified.

### Community 8 - "fixture"
Cohesion: 0.05
Nodes (33): fixture, generate_prd(), Any, Store, PRD + roadmap generators — deterministic templates over real data. PRD pulls…, Any, Prioritization — RICE and WSJF scoring, deterministic and explainable., factors may carry rice{reach,impact,confidence,effort} and/or… (+25 more)

### Community 9 - "aws.py"
Cohesion: 0.24
Nodes (12): AthenaConnector, _boto3(), cost_summary(), glue_catalog(), Any, quicksight_inventory(), AWS intelligence — real boto3 connectors; honest unavailability. Every…, QuickSight dashboards/datasets inventory (read-only). (+4 more)

### Community 10 - "test_cycle89.py"
Cohesion: 0.10
Nodes (23): diff_openapi(), load_spec(), parse_asyncapi(), parse_openapi(), Any, OpenAPI/AsyncAPI parsing + breaking-change detection — real diffs., Extract the API surface: operations, params, schemas., Breaking-change detection between two parsed OpenAPI surfaces. (+15 more)

### Community 11 - "ProductForgePortal"
Cohesion: 0.20
Nodes (8): PortalAdapter, RequestContext, ProductForgePortal, Any, _q1(), PortalAdapter for the vendored _forge_portal server. Ops paths are RELATIVE…, Product Forge adapter — workspaces, products, context package., _store()

### Community 12 - "test_cycle1011.py"
Cohesion: 0.21
Nodes (13): check_gate(), decide(), Any, Approvals — gate sensitive actions behind human review., Look up the latest approval for (action, resource)., request_approval(), env(), Cycles 10-11: watches/alerts/approvals/reports + workflows/routing. (+5 more)

### Community 13 - "IMPLEMENTATION_GAP_MATRIX — living status (final, Cycle 12)"
Cohesion: 0.12
Nodes (16): Cycle 10 — Product Operations ✅, Cycle 11 — Advanced Agentic ✅, Cycle 12 — Hardening & Homologation ✅, Cycle 1 — Foundation ✅, Cycle 2 — Studio foundation ✅ (adapter) / 🟡 (Angular surface), Cycle 3 — Knowledge/Context/Graph ✅, Cycle 4 — Agent Runtime & Factory ✅, Cycle 5 — Analytics ✅ (+8 more)

### Community 14 - "Agent Factory"
Cohesion: 0.20
Nodes (9): Agent Factory, Evals, Exemplos, Ferramentas, Instruções, Limitações, Objetivo, Pré-condições (+1 more)

### Community 16 - "Analytics"
Cohesion: 0.20
Nodes (9): Analytics, Evals, Exemplos, Ferramentas, Instruções, Limitações, Objetivo, Pré-condições (+1 more)

### Community 17 - "Apis"
Cohesion: 0.20
Nodes (9): Apis, Evals, Exemplos, Ferramentas, Instruções, Limitações, Objetivo, Pré-condições (+1 more)

### Community 18 - "Aws"
Cohesion: 0.20
Nodes (9): Aws, Evals, Exemplos, Ferramentas, Instruções, Limitações, Objetivo, Pré-condições (+1 more)

### Community 19 - "Azure"
Cohesion: 0.20
Nodes (9): Azure, Evals, Exemplos, Ferramentas, Instruções, Limitações, Objetivo, Pré-condições (+1 more)

### Community 20 - "Dashboards"
Cohesion: 0.20
Nodes (9): Dashboards, Evals, Exemplos, Ferramentas, Instruções, Limitações, Objetivo, Pré-condições (+1 more)

### Community 21 - "Data Products"
Cohesion: 0.20
Nodes (9): Data Products, Evals, Exemplos, Ferramentas, Instruções, Limitações, Objetivo, Pré-condições (+1 more)

### Community 22 - "Finops"
Cohesion: 0.20
Nodes (9): Evals, Exemplos, Ferramentas, Finops, Instruções, Limitações, Objetivo, Pré-condições (+1 more)

### Community 23 - "Governance"
Cohesion: 0.20
Nodes (9): Evals, Exemplos, Ferramentas, Governance, Instruções, Limitações, Objetivo, Pré-condições (+1 more)

### Community 24 - "Knowledge"
Cohesion: 0.20
Nodes (9): Evals, Exemplos, Ferramentas, Instruções, Knowledge, Limitações, Objetivo, Pré-condições (+1 more)

### Community 25 - "Prioritization"
Cohesion: 0.20
Nodes (9): Evals, Exemplos, Ferramentas, Instruções, Limitações, Objetivo, Prioritization, Pré-condições (+1 more)

### Community 26 - "Product Discovery"
Cohesion: 0.20
Nodes (9): Evals, Exemplos, Ferramentas, Instruções, Limitações, Objetivo, Product Discovery, Pré-condições (+1 more)

### Community 27 - "Product Strategy"
Cohesion: 0.20
Nodes (9): Evals, Exemplos, Ferramentas, Instruções, Limitações, Objetivo, Product Strategy, Pré-condições (+1 more)

### Community 28 - "Reporting"
Cohesion: 0.20
Nodes (9): Evals, Exemplos, Ferramentas, Instruções, Limitações, Objetivo, Pré-condições, Referências (+1 more)

### Community 29 - "Requirements"
Cohesion: 0.20
Nodes (9): Evals, Exemplos, Ferramentas, Instruções, Limitações, Objetivo, Pré-condições, Referências (+1 more)

### Community 30 - "Sql"
Cohesion: 0.20
Nodes (9): Evals, Exemplos, Ferramentas, Instruções, Limitações, Objetivo, Pré-condições, Referências (+1 more)

### Community 31 - "MCP streamable-HTTP transport alongside stdio"
Cohesion: 0.29
Nodes (6): Acceptance Criteria, Constraints, Context, Grill Gate, MCP streamable-HTTP transport alongside stdio, Review Notes

### Community 32 - "Product Forge"
Cohesion: 0.22
Nodes (8): Ecosystem compatibility, Install, MCP, Product Forge, Quickstart, Skills, Status, What it is

### Community 33 - "Ctx"
Cohesion: 0.22
Nodes (6): Request, Ctx, Any, Rebuild an OpenAPI paths dict from a stored parsed surface., Shared runtime: home, config, store, token, rate buckets, audit., _surface_to_paths()

### Community 34 - "create_app"
Cohesion: 0.22
Nodes (7): FastAPI, create_app(), test_api_knowledge_flow(), test_api_analytics(), client(), fixture, Cycle 12 homologation — Payments Product Intelligence (30 steps). Full user…

### Community 35 - "_installkit.py"
Cohesion: 0.11
Nodes (37): cli_version(), deregister_installation(), discover_projects(), _find_state_root(), _find_vcs_root(), _find_workspace_root(), forge_home(), forge_portal_presence() (+29 more)

### Community 36 - "Any"
Cohesion: 0.13
Nodes (32): apply_install(), _atomic_write(), components_path(), _created_by(), doctor(), InstallContext, _json_bytes(), load_components() (+24 more)

### Community 37 - "lifecycle.py"
Cohesion: 0.15
Nodes (29): Any, ForgeSpec, InstallContext, Path, _agents_root(), _bundle_files(), _ctx(), doctor() (+21 more)

### Community 38 - "InstallError"
Cohesion: 0.14
Nodes (10): Exception, component_options(), InstallError, _Lock, LockError, _pid_alive(), Best-effort liveness; ``None`` = cannot determine (do not steal)., O_EXCL lockfile carrying ``{pid, created_at}``. Stale locks — dead holder or… (+2 more)

### Community 39 - "plan"
Cohesion: 0.33
Nodes (6): _asset_kind(), asset_kinds_for(), plan(), profile_asset_kinds(), Profile kinds narrowed by the component selection, when present., Pure plan — what *would* change. Never writes.

### Community 40 - "Store"
Cohesion: 0.17
Nodes (5): Any, Path, Persist a raw dict document (non-pydantic, e.g. run records)., Thread-safe JSON-document store over SQLite., Store

### Community 41 - "tools.py"
Cohesion: 0.29
Nodes (12): _context_package(), _data_sources(), _entities(), _graph_lookup(), _knowledge_health(), _knowledge_query(), Any, Agent tool registry — every tool is a real store-backed function. Tools receive… (+4 more)

### Community 42 - "Agent Factory"
Cohesion: 0.20
Nodes (9): Agent Factory, Evals, Exemplos, Ferramentas, Instruções, Limitações, Objetivo, Pré-condições (+1 more)

### Community 43 - "Analytics"
Cohesion: 0.20
Nodes (9): Analytics, Evals, Exemplos, Ferramentas, Instruções, Limitações, Objetivo, Pré-condições (+1 more)

### Community 44 - "Apis"
Cohesion: 0.20
Nodes (9): Apis, Evals, Exemplos, Ferramentas, Instruções, Limitações, Objetivo, Pré-condições (+1 more)

### Community 45 - "Aws"
Cohesion: 0.20
Nodes (9): Aws, Evals, Exemplos, Ferramentas, Instruções, Limitações, Objetivo, Pré-condições (+1 more)

### Community 46 - "Azure"
Cohesion: 0.20
Nodes (9): Azure, Evals, Exemplos, Ferramentas, Instruções, Limitações, Objetivo, Pré-condições (+1 more)

### Community 47 - "Dashboards"
Cohesion: 0.20
Nodes (9): Dashboards, Evals, Exemplos, Ferramentas, Instruções, Limitações, Objetivo, Pré-condições (+1 more)

### Community 48 - "Data Products"
Cohesion: 0.20
Nodes (9): Data Products, Evals, Exemplos, Ferramentas, Instruções, Limitações, Objetivo, Pré-condições (+1 more)

### Community 49 - "Finops"
Cohesion: 0.20
Nodes (9): Evals, Exemplos, Ferramentas, Finops, Instruções, Limitações, Objetivo, Pré-condições (+1 more)

### Community 50 - "Governance"
Cohesion: 0.20
Nodes (9): Evals, Exemplos, Ferramentas, Governance, Instruções, Limitações, Objetivo, Pré-condições (+1 more)

### Community 51 - "Knowledge"
Cohesion: 0.20
Nodes (9): Evals, Exemplos, Ferramentas, Instruções, Knowledge, Limitações, Objetivo, Pré-condições (+1 more)

### Community 52 - "Prioritization"
Cohesion: 0.20
Nodes (9): Evals, Exemplos, Ferramentas, Instruções, Limitações, Objetivo, Prioritization, Pré-condições (+1 more)

### Community 53 - "Product Discovery"
Cohesion: 0.20
Nodes (9): Evals, Exemplos, Ferramentas, Instruções, Limitações, Objetivo, Product Discovery, Pré-condições (+1 more)

### Community 54 - "Product Strategy"
Cohesion: 0.20
Nodes (9): Evals, Exemplos, Ferramentas, Instruções, Limitações, Objetivo, Product Strategy, Pré-condições (+1 more)

### Community 55 - "Reporting"
Cohesion: 0.20
Nodes (9): Evals, Exemplos, Ferramentas, Instruções, Limitações, Objetivo, Pré-condições, Referências (+1 more)

### Community 56 - "Requirements"
Cohesion: 0.20
Nodes (9): Evals, Exemplos, Ferramentas, Instruções, Limitações, Objetivo, Pré-condições, Referências (+1 more)

### Community 57 - "Sql"
Cohesion: 0.20
Nodes (9): Evals, Exemplos, Ferramentas, Instruções, Limitações, Objetivo, Pré-condições, Referências (+1 more)

### Community 58 - "Agent Factory"
Cohesion: 0.20
Nodes (9): Agent Factory, Evals, Exemplos, Ferramentas, Instruções, Limitações, Objetivo, Pré-condições (+1 more)

### Community 59 - "Analytics"
Cohesion: 0.20
Nodes (9): Analytics, Evals, Exemplos, Ferramentas, Instruções, Limitações, Objetivo, Pré-condições (+1 more)

### Community 60 - "Apis"
Cohesion: 0.20
Nodes (9): Apis, Evals, Exemplos, Ferramentas, Instruções, Limitações, Objetivo, Pré-condições (+1 more)

### Community 61 - "Aws"
Cohesion: 0.20
Nodes (9): Aws, Evals, Exemplos, Ferramentas, Instruções, Limitações, Objetivo, Pré-condições (+1 more)

### Community 62 - "Azure"
Cohesion: 0.20
Nodes (9): Azure, Evals, Exemplos, Ferramentas, Instruções, Limitações, Objetivo, Pré-condições (+1 more)

### Community 63 - "Dashboards"
Cohesion: 0.20
Nodes (9): Dashboards, Evals, Exemplos, Ferramentas, Instruções, Limitações, Objetivo, Pré-condições (+1 more)

### Community 64 - "Data Products"
Cohesion: 0.20
Nodes (9): Data Products, Evals, Exemplos, Ferramentas, Instruções, Limitações, Objetivo, Pré-condições (+1 more)

### Community 65 - "Finops"
Cohesion: 0.20
Nodes (9): Evals, Exemplos, Ferramentas, Finops, Instruções, Limitações, Objetivo, Pré-condições (+1 more)

### Community 66 - "Governance"
Cohesion: 0.20
Nodes (9): Evals, Exemplos, Ferramentas, Governance, Instruções, Limitações, Objetivo, Pré-condições (+1 more)

### Community 67 - "Knowledge"
Cohesion: 0.20
Nodes (9): Evals, Exemplos, Ferramentas, Instruções, Knowledge, Limitações, Objetivo, Pré-condições (+1 more)

### Community 68 - "Prioritization"
Cohesion: 0.20
Nodes (9): Evals, Exemplos, Ferramentas, Instruções, Limitações, Objetivo, Prioritization, Pré-condições (+1 more)

### Community 69 - "Product Discovery"
Cohesion: 0.20
Nodes (9): Evals, Exemplos, Ferramentas, Instruções, Limitações, Objetivo, Product Discovery, Pré-condições (+1 more)

### Community 70 - "Product Strategy"
Cohesion: 0.20
Nodes (9): Evals, Exemplos, Ferramentas, Instruções, Limitações, Objetivo, Product Strategy, Pré-condições (+1 more)

### Community 71 - "Reporting"
Cohesion: 0.20
Nodes (9): Evals, Exemplos, Ferramentas, Instruções, Limitações, Objetivo, Pré-condições, Referências (+1 more)

### Community 72 - "Requirements"
Cohesion: 0.20
Nodes (9): Evals, Exemplos, Ferramentas, Instruções, Limitações, Objetivo, Pré-condições, Referências (+1 more)

### Community 73 - "Sql"
Cohesion: 0.20
Nodes (9): Evals, Exemplos, Ferramentas, Instruções, Limitações, Objetivo, Pré-condições, Referências (+1 more)

### Community 74 - "Ledger"
Cohesion: 0.12
Nodes (12): apply_marker_block(), _entry_intact(), Ledger, marker_sha(), _markers(), Records every managed write under a target root. ``entries[path] = {sha256,…, Per-file verdict. When ``spec`` is given the check is kind-aware: ``marker``…, Kind-aware health check for one ledger entry. Marker entries verify the managed… (+4 more)

### Community 75 - "datacontract.py"
Cohesion: 0.25
Nodes (8): impact_analysis(), Any, Data contracts + impact analysis over the entity/relation graph., contract: {fields:[{name,type,required}], quality:[{field,rule}]}, BFS over relations: what breaks if `entity_id` changes?, validate_payload(), test_contract_validation(), test_impact_analysis()

### Community 76 - "sqlite.py"
Cohesion: 0.28
Nodes (6): knowledge_health(), Graph projection + knowledge health — computed views over the store., generate_executive(), Any, Executive reports — deterministic composition over real product data., SQLite persistence — stdlib, schema-versioned, append-only audit. Entity rows…

### Community 77 - "call_tool"
Cohesion: 0.36
Nodes (8): call_tool(), Any, MCP server (stdio) — exposes productforge tools to agent hosts. Tools are read-…, Minimal JSON-RPC stdio loop (MCP handshake + tools/list + tools/call)., serve(), _store(), tool_specs(), test_mcp_tools_expanded()

### Community 78 - "watches.py"
Cohesion: 0.44
Nodes (8): create_watch(), evaluate_watch(), Any, Watches — scheduled metric checks over governed queries. A watch runs its…, run_due(), _touch(), _ts(), test_watch_breach_opens_alert()

### Community 79 - "runtime.py"
Cohesion: 0.43
Nodes (7): cancel_run(), get_run(), _persist(), Any, Agent runtime — deterministic executor with full trace. A run = ordered…, resume_run(), _run_doc()

### Community 80 - "run_workflow"
Cohesion: 0.36
Nodes (7): _interpolate(), plan_is_deterministic(), Any, Multi-agent workflows — deterministic DAG over agents and tools. Steps run in…, spec: {name, steps:[{id, kind:agent|tool, agent_id|tool, input?}]}, Workflows are deterministic by construction: declared steps only., run_workflow()

### Community 81 - "record_usage"
Cohesion: 0.38
Nodes (6): Any, Model routing + cost ledger — gateway profiles and honest budgets. No provider…, Append to the product's daily budget ledger (audit-safe)., record_usage(), route(), test_routing_and_budget()

### Community 82 - "Native agent templates (§6.3) — product-analyst, data-steward, api-guardian"
Cohesion: 0.29
Nodes (6): Acceptance Criteria, Constraints, Context, Grill Gate, Native agent templates (§6.3) — product-analyst, data-steward, api-guardian, Review Notes

### Community 84 - "Product Forge — Agent Instructions"
Cohesion: 0.33
Nodes (5): Agentic layer (spark-forge-aws pattern), Commands, Hard rules, Product Forge, Product Forge — Agent Instructions

### Community 86 - "External notification delivery for alerts (webhook/email)"
Cohesion: 0.29
Nodes (6): Acceptance Criteria, Constraints, Context, External notification delivery for alerts (webhook/email), Grill Gate, Review Notes

### Community 87 - "Angular module for Product Forge inside forge-portal"
Cohesion: 0.29
Nodes (6): Acceptance Criteria, Angular module for Product Forge inside forge-portal, Constraints, Context, Grill Gate, Review Notes

### Community 88 - "PostgreSQL store backend alongside SQLite"
Cohesion: 0.29
Nodes (6): Acceptance Criteria, Constraints, Context, Grill Gate, PostgreSQL store backend alongside SQLite, Review Notes

### Community 89 - "pf-extractor"
Cohesion: 0.40
Nodes (4): Entrega, Não faz, pf-extractor, Pressupõe

### Community 90 - "pf-judge"
Cohesion: 0.40
Nodes (4): Entrega, Não faz, pf-judge, Pressupõe

### Community 91 - "pf-synthesizer"
Cohesion: 0.40
Nodes (4): Entrega, Não faz, pf-synthesizer, Pressupõe

### Community 92 - "pf-verifier"
Cohesion: 0.40
Nodes (4): Entrega, Não faz, pf-verifier, Pressupõe

### Community 93 - "pf-extractor"
Cohesion: 0.40
Nodes (4): Entrega, Não faz, pf-extractor, Pressupõe

### Community 94 - "pf-judge"
Cohesion: 0.40
Nodes (4): Entrega, Não faz, pf-judge, Pressupõe

### Community 95 - "pf-synthesizer"
Cohesion: 0.40
Nodes (4): Entrega, Não faz, pf-synthesizer, Pressupõe

### Community 96 - "pf-verifier"
Cohesion: 0.40
Nodes (4): Entrega, Não faz, pf-verifier, Pressupõe

### Community 97 - "Product Forge — Agent Instructions"
Cohesion: 0.40
Nodes (4): Agentic layer (spark-forge-aws pattern), Commands, Hard rules, Product Forge — Agent Instructions

### Community 98 - "Agent Ops Coordinator"
Cohesion: 0.50
Nodes (3): Agent Ops Coordinator, Não faz, Playbook

### Community 99 - "Agent Ops Coordinator"
Cohesion: 0.50
Nodes (3): Agent Ops Coordinator, Não faz, Playbook

### Community 100 - "Data Analyst Coordinator"
Cohesion: 0.50
Nodes (3): Data Analyst Coordinator, Não faz, Playbook

### Community 101 - "Integration Coordinator"
Cohesion: 0.50
Nodes (3): Integration Coordinator, Não faz, Playbook

### Community 102 - "Planning Coordinator"
Cohesion: 0.50
Nodes (3): Não faz, Planning Coordinator, Playbook

### Community 103 - "Product Intelligence Coordinator"
Cohesion: 0.50
Nodes (3): Não faz, Playbook, Product Intelligence Coordinator

### Community 104 - "Data Analyst Coordinator"
Cohesion: 0.50
Nodes (3): Data Analyst Coordinator, Não faz, Playbook

### Community 105 - "Integration Coordinator"
Cohesion: 0.50
Nodes (3): Integration Coordinator, Não faz, Playbook

### Community 106 - "Planning Coordinator"
Cohesion: 0.50
Nodes (3): Não faz, Planning Coordinator, Playbook

### Community 107 - "Product Intelligence Coordinator"
Cohesion: 0.50
Nodes (3): Não faz, Playbook, Product Intelligence Coordinator

### Community 108 - "mcp_verify"
Cohesion: 0.50
Nodes (4): _mcp_handshake(), mcp_verify(), JSON-RPC stdio handshake: initialize → notifications/initialized → tools/list.…, initialize → initialized → tools/list (+ tools/call when the spec declares a…

## Knowledge Gaps
- **493 isolated node(s):** `Playbook`, `Não faz`, `Playbook`, `Não faz`, `Pressupõe` (+488 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **9 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Store` connect `Store` to `Ctx`, `run_agent`, `cli/__init__.py`, `security.py`, `lifecycle.py`, `fixture`, `tools.py`, `datacontract.py`, `sqlite.py`, `call_tool`, `test_cycle1011.py`, `runtime.py`, `run_workflow`, `watches.py`, `ProductForgePortal`?**
  _High betweenness centrality (0.061) - this node is a cross-community bridge._
- **Why does `_init_app_home()` connect `lifecycle.py` to `Store`, `TokenStore`?**
  _High betweenness centrality (0.029) - this node is a cross-community bridge._
- **Why does `TokenStore` connect `TokenStore` to `Ctx`, `create_app`, `cli/__init__.py`, `security.py`, `lifecycle.py`, `test_negative.py`, `fixture`, `test_cycle89.py`?**
  _High betweenness centrality (0.025) - this node is a cross-community bridge._
- **Are the 6 inferred relationships involving `Store` (e.g. with `_init_app_home()` and `_store()`) actually correct?**
  _`Store` has 6 INFERRED edges - model-reasoned connections that need verification._
- **What connects `Playbook`, `Não faz`, `Playbook` to the rest of the system?**
  _493 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `cli/__init__.py` be split into smaller, more focused modules?**
  _Cohesion score 0.06558558558558558 - nodes in this community are weakly interconnected._
- **Should `engine.py` be split into smaller, more focused modules?**
  _Cohesion score 0.057342657342657345 - nodes in this community are weakly interconnected._