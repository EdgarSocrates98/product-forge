# Graph Report - product-forge  (2026-10-29)

## Corpus Check
- 132 files · ~49,876 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 1108 nodes · 1791 edges · 86 communities (82 shown, 4 thin omitted)
- Extraction: 95% EXTRACTED · 5% INFERRED · 0% AMBIGUOUS · INFERRED: 97 edges (avg confidence: 0.86)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `98c2e99a`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- app.py
- test_cycle3.py
- run_agent
- cli/__init__.py
- connectors.py
- TokenStore
- engine.py
- test_negative.py
- score_initiative
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
- create_app
- Product Forge
- .audit
- client
- _installkit.py
- Any
- lifecycle.py
- _load_json
- apply_install
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
- _repair_content
- datacontract.py
- sqlite.py
- call_tool
- watches.py
- runtime.py
- run_workflow
- record_usage
- load_components
- product-forge
- AGENTS.md
- product-forge

## God Nodes (most connected - your core abstractions)
1. `Store` - 57 edges
2. `_out()` - 36 edges
3. `_store()` - 28 edges
4. `apply_install()` - 24 edges
5. `ProductForgePortal` - 23 edges
6. `run_agent()` - 19 edges
7. `TokenStore` - 18 edges
8. `_store()` - 17 edges
9. `IMPLEMENTATION_GAP_MATRIX — living status (final, Cycle 12)` - 16 edges
10. `uninstall()` - 16 edges

## Surprising Connections (you probably didn't know these)
- `test_schema_explorer()` --uses--> `SQLiteConnector`  [INFERRED]
  tests/test_cycle5.py → src/product_forge/analytics/connectors.py
- `test_api_knowledge_flow()` --calls--> `create_app()`  [INFERRED]
  tests/test_cycle3.py → src/product_forge/api/app.py
- `test_mcp_tools_expanded()` --calls--> `Store`  [INFERRED]
  tests/test_install.py → src/product_forge/store/sqlite.py
- `_store()` --uses--> `Store`  [INFERRED]
  tests/test_cycle1011.py → src/product_forge/store/sqlite.py
- `_seed()` --uses--> `Store`  [INFERRED]
  tests/test_cycle3.py → src/product_forge/store/sqlite.py

## Import Cycles
- None detected.

## Communities (86 total, 4 thin omitted)

### Community 0 - "app.py"
Cohesion: 0.26
Nodes (12): BaseModel, CompileIn, ExecuteIn, NlIn, ProductIn, QueryIn, HTTP API — forge/PortalApi/1 envelope, bearer auth, audit. Every response uses…, Open body for product-scoped creates; fields whitelisted per route. (+4 more)

### Community 1 - "test_cycle3.py"
Cohesion: 0.38
Nodes (6): home(), Cycle 3: extraction, graph, knowledge health., _seed(), test_api_knowledge_flow(), test_extract_and_graph(), test_knowledge_health()

### Community 2 - "run_agent"
Cohesion: 0.19
Nodes (18): AgentDefinition, json_str(), Any, Agent evaluation harness — real runs against real knowledge. A case: {question,…, run_evals(), check_budget(), check_input(), check_tool() (+10 more)

### Community 3 - "cli/__init__.py"
Cohesion: 0.06
Nodes (77): command, KnowledgeEntity, Relation, ag_create(), ag_eval(), ag_list(), ag_publish(), ag_run() (+69 more)

### Community 4 - "connectors.py"
Cohesion: 0.10
Nodes (20): Connection, Entity, Event, Protocol, Connector, connector_for(), DuckDBConnector, _mask() (+12 more)

### Community 5 - "TokenStore"
Cohesion: 0.25
Nodes (3): Path, Local API bearer token — generated on first use, file 0600., TokenStore

### Community 6 - "engine.py"
Cohesion: 0.05
Nodes (47): fixture, parametrize, compile_spec(), execute_query(), _ident(), nl_to_sql(), Any, Query engine — validate → allowlist → execute → record. Every execution… (+39 more)

### Community 7 - "test_negative.py"
Cohesion: 0.17
Nodes (3): client(), fixture, Negative scenarios — required failure modes all verified.

### Community 8 - "score_initiative"
Cohesion: 0.18
Nodes (11): Any, Prioritization — RICE and WSJF scoring, deterministic and explainable., factors may carry rice{reach,impact,confidence,effort} and/or…, score_initiative(), score_rice(), score_wsjf(), build_roadmap(), Any (+3 more)

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
Cohesion: 0.22
Nodes (13): check_gate(), decide(), Any, Approvals — gate sensitive actions behind human review., Look up the latest approval for (action, resource)., request_approval(), Cycles 10-11: watches/alerts/approvals/reports + workflows/routing., _store() (+5 more)

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

### Community 31 - "create_app"
Cohesion: 0.25
Nodes (7): FastAPI, Path, create_app(), Ctx, Shared runtime: home, config, store, token, rate buckets, audit., test_api_agent_flow(), test_api_analytics()

### Community 32 - "Product Forge"
Cohesion: 0.22
Nodes (8): Ecosystem compatibility, Install, MCP, Product Forge, Quickstart, Skills, Status, What it is

### Community 33 - ".audit"
Cohesion: 0.29
Nodes (6): Request, _cid(), envelope(), Any, Rebuild an OpenAPI paths dict from a stored parsed surface., _surface_to_paths()

### Community 34 - "client"
Cohesion: 0.40
Nodes (3): client(), fixture, Cycle 12 homologation — Payments Product Intelligence (30 steps). Full user…

### Community 35 - "_installkit.py"
Cohesion: 0.10
Nodes (39): apply_marker_block(), cli_version(), deregister_installation(), discover_projects(), _find_state_root(), _find_vcs_root(), _find_workspace_root(), forge_home() (+31 more)

### Community 36 - "Any"
Cohesion: 0.13
Nodes (21): _atomic_write(), doctor(), forge_portal_presence(), _json_bytes(), Ledger, _mcp_handshake(), mcp_unset(), mcp_verify() (+13 more)

### Community 37 - "lifecycle.py"
Cohesion: 0.19
Nodes (24): _ctx(), doctor(), _init_app_home(), install(), Any, Path, productforge install lifecycle — thin ForgeSpec wiring over the vendored forge…, The runtime home (config/db/token) — separate from the project install. (+16 more)

### Community 38 - "_load_json"
Cohesion: 0.13
Nodes (11): Exception, component_options(), InstallError, _load_json(), _Lock, LockError, _pid_alive(), Best-effort liveness; ``None`` = cannot determine (do not steal). (+3 more)

### Community 39 - "apply_install"
Cohesion: 0.16
Nodes (18): apply_install(), _asset_kind(), asset_kinds_for(), _created_by(), InstallContext, marker_sha(), plan(), _prune_empty_dirs() (+10 more)

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

### Community 74 - "_repair_content"
Cohesion: 0.22
Nodes (8): _entry_intact(), mcp_set(), Canonical bytes for a drifted *managed* entry, or ``None`` when the entry…, Per-file verdict. When ``spec`` is given the check is kind-aware: ``marker``…, Kind-aware health check for one ledger entry. Marker entries verify the managed…, Set ``mcpServers.<key>`` inside a managed sub-block. Other servers and top-…, _repair_content(), _sha_file()

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
Cohesion: 0.40
Nodes (5): Any, Model routing + cost ledger — gateway profiles and honest budgets. No provider…, Append to the product's daily budget ledger (audit-safe)., record_usage(), route()

### Community 82 - "load_components"
Cohesion: 0.50
Nodes (4): components_path(), load_components(), Where the optional-component selection is persisted., {} when never recorded — absence means default (all enabled).

## Knowledge Gaps
- **410 isolated node(s):** `Objetivo`, `Pré-condições`, `Instruções`, `Ferramentas`, `Exemplos` (+405 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **4 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Store` connect `Store` to `test_cycle3.py`, `run_agent`, `cli/__init__.py`, `connectors.py`, `lifecycle.py`, `tools.py`, `datacontract.py`, `sqlite.py`, `call_tool`, `test_cycle1011.py`, `runtime.py`, `run_workflow`, `watches.py`, `ProductForgePortal`, `create_app`?**
  _High betweenness centrality (0.070) - this node is a cross-community bridge._
- **Why does `_init_app_home()` connect `lifecycle.py` to `Store`, `TokenStore`?**
  _High betweenness centrality (0.045) - this node is a cross-community bridge._
- **Why does `TokenStore` connect `TokenStore` to `client`, `cli/__init__.py`, `connectors.py`, `lifecycle.py`, `engine.py`, `test_negative.py`, `test_cycle89.py`, `create_app`?**
  _High betweenness centrality (0.040) - this node is a cross-community bridge._
- **Are the 6 inferred relationships involving `Store` (e.g. with `_init_app_home()` and `_store()`) actually correct?**
  _`Store` has 6 INFERRED edges - model-reasoned connections that need verification._
- **What connects `Objetivo`, `Pré-condições`, `Instruções` to the rest of the system?**
  _410 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `cli/__init__.py` be split into smaller, more focused modules?**
  _Cohesion score 0.058333333333333334 - nodes in this community are weakly interconnected._
- **Should `connectors.py` be split into smaller, more focused modules?**
  _Cohesion score 0.1 - nodes in this community are weakly interconnected._