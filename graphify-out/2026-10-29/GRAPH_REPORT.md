# Graph Report - product-forge  (2026-10-29)

## Corpus Check
- 71 files · ~27,687 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 444 nodes · 903 edges · 16 communities (15 shown, 1 thin omitted)
- Extraction: 91% EXTRACTED · 9% INFERRED · 0% AMBIGUOUS · INFERRED: 79 edges (avg confidence: 0.86)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `33fa3dcb`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- app.py
- build_relations
- Store
- __init__.py
- engine.py
- test_cycle4.py
- execute_query
- TokenStore
- score_initiative
- aws.py
- test_cycle89.py
- ProductForgePortal
- watches.py
- IMPLEMENTATION_GAP_MATRIX — living status (final, Cycle 12)
- azure.py
- Path

## God Nodes (most connected - your core abstractions)
1. `Store` - 54 edges
2. `_out()` - 33 edges
3. `_store()` - 29 edges
4. `ProductForgePortal` - 22 edges
5. `TokenStore` - 18 edges
6. `run_agent()` - 18 edges
7. `_store()` - 17 edges
8. `IMPLEMENTATION_GAP_MATRIX — living status (final, Cycle 12)` - 15 edges
9. `execute_query()` - 14 edges
10. `create_app()` - 13 edges

## Surprising Connections (you probably didn't know these)
- `test_schema_explorer()` --uses--> `SQLiteConnector`  [INFERRED]
  tests/test_cycle5.py → src/product_forge/analytics/connectors.py
- `test_api_knowledge_flow()` --calls--> `create_app()`  [INFERRED]
  tests/test_cycle3.py → src/product_forge/api/app.py
- `test_api_agent_flow()` --calls--> `create_app()`  [INFERRED]
  tests/test_cycle4.py → src/product_forge/api/app.py
- `test_api_analytics()` --calls--> `create_app()`  [INFERRED]
  tests/test_cycle5.py → src/product_forge/api/app.py
- `test_api_dashboard_planning()` --calls--> `create_app()`  [INFERRED]
  tests/test_cycle67.py → src/product_forge/api/app.py

## Import Cycles
- None detected.

## Communities (16 total, 1 thin omitted)

### Community 0 - "app.py"
Cohesion: 0.10
Nodes (25): BaseModel, FastAPI, Path, Request, _cid(), CompileIn, create_app(), Ctx (+17 more)

### Community 1 - "build_relations"
Cohesion: 0.21
Nodes (11): KnowledgeEntity, Relation, build_relations(), extract_entities(), Deterministic entity extraction — no LLM required. Heuristics over chunk text…, chunks: [{id, text}] → dedup'd provisional entities with evidence., documented_in(entity→doc chunk) + co-occurrence related_to., Cycle 3: extraction, graph, knowledge health. (+3 more)

### Community 2 - "Store"
Cohesion: 0.06
Nodes (50): json_str(), Any, Agent evaluation harness — real runs against real knowledge. A case: {question,…, run_evals(), cancel_run(), get_run(), _persist(), Any (+42 more)

### Community 3 - "__init__.py"
Cohesion: 0.07
Nodes (64): command, ag_create(), ag_eval(), ag_list(), ag_publish(), ag_run(), api_serve(), api_token() (+56 more)

### Community 4 - "engine.py"
Cohesion: 0.09
Nodes (21): Connection, Entity, Event, Protocol, Connector, connector_for(), DuckDBConnector, _mask() (+13 more)

### Community 5 - "test_cycle4.py"
Cohesion: 0.23
Nodes (13): AgentDefinition, check_budget(), check_input(), check_tool(), PolicyReport, Agent policy engine — checked before every run and every tool call. Covers:…, _agent(), Cycle 4: agent runtime, policy, evals, publish gate. (+5 more)

### Community 6 - "execute_query"
Cohesion: 0.09
Nodes (33): parametrize, compile_spec(), execute_query(), _ident(), nl_to_sql(), Any, Deterministic NL→SQL for registered patterns — honest otherwise., Visual Query Builder → SQL. Shared contract with NL and editor. (+25 more)

### Community 7 - "TokenStore"
Cohesion: 0.08
Nodes (9): Path, Local API bearer token — generated on first use, file 0600., TokenStore, client(), fixture, Cycle 12 homologation — Payments Product Intelligence (30 steps). Full user…, client(), fixture (+1 more)

### Community 8 - "score_initiative"
Cohesion: 0.11
Nodes (19): fixture, Any, Prioritization — RICE and WSJF scoring, deterministic and explainable., factors may carry rice{reach,impact,confidence,effort} and/or…, score_initiative(), score_rice(), score_wsjf(), env() (+11 more)

### Community 9 - "aws.py"
Cohesion: 0.24
Nodes (12): AthenaConnector, _boto3(), cost_summary(), glue_catalog(), Any, quicksight_inventory(), AWS intelligence — real boto3 connectors; honest unavailability. Every…, QuickSight dashboards/datasets inventory (read-only). (+4 more)

### Community 10 - "test_cycle89.py"
Cohesion: 0.13
Nodes (19): diff_openapi(), load_spec(), parse_asyncapi(), parse_openapi(), Any, OpenAPI/AsyncAPI parsing + breaking-change detection — real diffs., Extract the API surface: operations, params, schemas., Breaking-change detection between two parsed OpenAPI surfaces. (+11 more)

### Community 11 - "ProductForgePortal"
Cohesion: 0.15
Nodes (12): PortalAdapter, RequestContext, build_roadmap(), Any, Store, Roadmap builder — now/next/later lanes from real initiatives., ProductForgePortal, Any (+4 more)

### Community 12 - "watches.py"
Cohesion: 0.16
Nodes (19): Any, Model routing + cost ledger — gateway profiles and honest budgets. No provider…, Append to the product's daily budget ledger (audit-safe)., record_usage(), route(), create_watch(), evaluate_watch(), Any (+11 more)

### Community 13 - "IMPLEMENTATION_GAP_MATRIX — living status (final, Cycle 12)"
Cohesion: 0.12
Nodes (15): Cycle 10 — Product Operations ✅, Cycle 11 — Advanced Agentic ✅, Cycle 12 — Hardening & Homologation ✅, Cycle 1 — Foundation ✅, Cycle 2 — Studio foundation ✅ (adapter) / 🟡 (Angular surface), Cycle 3 — Knowledge/Context/Graph ✅, Cycle 4 — Agent Runtime & Factory ✅, Cycle 5 — Analytics ✅ (+7 more)

### Community 14 - "azure.py"
Cohesion: 0.19
Nodes (11): _credential(), fabric_inventory(), KQLConnector, powerbi_inventory(), Any, Azure intelligence — KQL (Log Analytics) + Fabric/Power BI inventory. Same…, Log Analytics KQL execution via azure-monitor-query., Power BI REST inventory — workspaces + datasets. Token required. (+3 more)

## Knowledge Gaps
- **15 isolated node(s):** `Cycle 1 — Foundation ✅`, `Cycle 2 — Studio foundation ✅ (adapter) / 🟡 (Angular surface)`, `Cycle 3 — Knowledge/Context/Graph ✅`, `Cycle 4 — Agent Runtime & Factory ✅`, `Cycle 5 — Analytics ✅` (+10 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **1 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Store` connect `Store` to `app.py`, `build_relations`, `__init__.py`, `engine.py`, `test_cycle4.py`, `test_cycle89.py`, `ProductForgePortal`, `watches.py`?**
  _High betweenness centrality (0.287) - this node is a cross-community bridge._
- **Why does `create_app()` connect `app.py` to `__init__.py`, `execute_query`, `TokenStore`, `score_initiative`, `test_cycle89.py`?**
  _High betweenness centrality (0.106) - this node is a cross-community bridge._
- **Why does `TokenStore` connect `TokenStore` to `app.py`, `__init__.py`, `engine.py`, `execute_query`, `score_initiative`, `test_cycle89.py`?**
  _High betweenness centrality (0.077) - this node is a cross-community bridge._
- **Are the 4 inferred relationships involving `Store` (e.g. with `_store()` and `_seed()`) actually correct?**
  _`Store` has 4 INFERRED edges - model-reasoned connections that need verification._
- **What connects `Cycle 1 — Foundation ✅`, `Cycle 2 — Studio foundation ✅ (adapter) / 🟡 (Angular surface)`, `Cycle 3 — Knowledge/Context/Graph ✅` to the rest of the system?**
  _15 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `app.py` be split into smaller, more focused modules?**
  _Cohesion score 0.10344827586206896 - nodes in this community are weakly interconnected._
- **Should `Store` be split into smaller, more focused modules?**
  _Cohesion score 0.05962732919254658 - nodes in this community are weakly interconnected._