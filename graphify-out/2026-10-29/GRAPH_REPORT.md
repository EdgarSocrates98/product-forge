# Graph Report - product-forge  (2026-10-29)

## Corpus Check
- 88 files · ~30,871 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 612 nodes · 1054 edges · 35 communities (34 shown, 1 thin omitted)
- Extraction: 93% EXTRACTED · 7% INFERRED · 0% AMBIGUOUS · INFERRED: 79 edges (avg confidence: 0.86)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `7a71e67c`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- app.py
- build_relations
- Store
- __init__.py
- connectors.py
- TokenStore
- engine.py
- test_negative.py
- score_initiative
- aws.py
- test_cycle89.py
- ProductForgePortal
- watches.py
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
- `_store()` --uses--> `Store`  [INFERRED]
  tests/test_cycle1011.py → src/product_forge/store/sqlite.py
- `_seed()` --uses--> `Store`  [INFERRED]
  tests/test_cycle3.py → src/product_forge/store/sqlite.py
- `test_impact_analysis()` --uses--> `Store`  [INFERRED]
  tests/test_cycle89.py → src/product_forge/store/sqlite.py

## Import Cycles
- None detected.

## Communities (35 total, 1 thin omitted)

### Community 0 - "app.py"
Cohesion: 0.26
Nodes (12): BaseModel, CompileIn, ExecuteIn, NlIn, ProductIn, QueryIn, HTTP API — forge/PortalApi/1 envelope, bearer auth, audit. Every response uses…, Open body for product-scoped creates; fields whitelisted per route. (+4 more)

### Community 1 - "build_relations"
Cohesion: 0.19
Nodes (12): KnowledgeEntity, Relation, build_relations(), extract_entities(), Deterministic entity extraction — no LLM required. Heuristics over chunk text…, chunks: [{id, text}] → dedup'd provisional entities with evidence., documented_in(entity→doc chunk) + co-occurrence related_to., Cycle 3: extraction, graph, knowledge health. (+4 more)

### Community 2 - "Store"
Cohesion: 0.06
Nodes (56): AgentDefinition, json_str(), Any, Agent evaluation harness — real runs against real knowledge. A case: {question,…, run_evals(), check_budget(), check_input(), check_tool() (+48 more)

### Community 3 - "__init__.py"
Cohesion: 0.07
Nodes (64): command, ag_create(), ag_eval(), ag_list(), ag_publish(), ag_run(), api_serve(), api_token() (+56 more)

### Community 4 - "connectors.py"
Cohesion: 0.10
Nodes (20): Connection, Entity, Event, Protocol, Connector, connector_for(), DuckDBConnector, _mask() (+12 more)

### Community 5 - "TokenStore"
Cohesion: 0.25
Nodes (3): Path, Local API bearer token — generated on first use, file 0600., TokenStore

### Community 6 - "engine.py"
Cohesion: 0.09
Nodes (33): parametrize, compile_spec(), execute_query(), _ident(), nl_to_sql(), Any, Query engine — validate → allowlist → execute → record. Every execution…, Deterministic NL→SQL for registered patterns — honest otherwise. (+25 more)

### Community 7 - "test_negative.py"
Cohesion: 0.17
Nodes (3): client(), fixture, Negative scenarios — required failure modes all verified.

### Community 8 - "score_initiative"
Cohesion: 0.09
Nodes (23): fixture, Any, Prioritization — RICE and WSJF scoring, deterministic and explainable., factors may carry rice{reach,impact,confidence,effort} and/or…, score_initiative(), score_rice(), score_wsjf(), build_roadmap() (+15 more)

### Community 9 - "aws.py"
Cohesion: 0.24
Nodes (12): AthenaConnector, _boto3(), cost_summary(), glue_catalog(), Any, quicksight_inventory(), AWS intelligence — real boto3 connectors; honest unavailability. Every…, QuickSight dashboards/datasets inventory (read-only). (+4 more)

### Community 10 - "test_cycle89.py"
Cohesion: 0.08
Nodes (30): diff_openapi(), load_spec(), parse_asyncapi(), parse_openapi(), Any, OpenAPI/AsyncAPI parsing + breaking-change detection — real diffs., Extract the API surface: operations, params, schemas., Breaking-change detection between two parsed OpenAPI surfaces. (+22 more)

### Community 11 - "ProductForgePortal"
Cohesion: 0.20
Nodes (8): PortalAdapter, RequestContext, ProductForgePortal, Any, _q1(), PortalAdapter for the vendored _forge_portal server. Ops paths are RELATIVE…, Product Forge adapter — workspaces, products, context package., _store()

### Community 12 - "watches.py"
Cohesion: 0.11
Nodes (26): Any, Model routing + cost ledger — gateway profiles and honest budgets. No provider…, Append to the product's daily budget ledger (audit-safe)., record_usage(), route(), check_gate(), decide(), Any (+18 more)

### Community 13 - "IMPLEMENTATION_GAP_MATRIX — living status (final, Cycle 12)"
Cohesion: 0.12
Nodes (15): Cycle 10 — Product Operations ✅, Cycle 11 — Advanced Agentic ✅, Cycle 12 — Hardening & Homologation ✅, Cycle 1 — Foundation ✅, Cycle 2 — Studio foundation ✅ (adapter) / 🟡 (Angular surface), Cycle 3 — Knowledge/Context/Graph ✅, Cycle 4 — Agent Runtime & Factory ✅, Cycle 5 — Analytics ✅ (+7 more)

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
Cohesion: 0.25
Nodes (7): Ecosystem compatibility, Install, Product Forge, Quickstart, Skills, Status, What it is

### Community 33 - ".audit"
Cohesion: 0.29
Nodes (6): Request, _cid(), envelope(), Any, Rebuild an OpenAPI paths dict from a stored parsed surface., _surface_to_paths()

### Community 34 - "client"
Cohesion: 0.40
Nodes (3): client(), fixture, Cycle 12 homologation — Payments Product Intelligence (30 steps). Full user…

## Knowledge Gaps
- **149 isolated node(s):** `What it is`, `Install`, `Quickstart`, `Ecosystem compatibility`, `Skills` (+144 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **1 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Store` connect `Store` to `build_relations`, `__init__.py`, `connectors.py`, `test_cycle89.py`, `ProductForgePortal`, `watches.py`, `create_app`?**
  _High betweenness centrality (0.151) - this node is a cross-community bridge._
- **Why does `create_app()` connect `create_app` to `app.py`, `build_relations`, `client`, `__init__.py`, `test_negative.py`, `score_initiative`, `test_cycle89.py`?**
  _High betweenness centrality (0.056) - this node is a cross-community bridge._
- **Why does `TokenStore` connect `TokenStore` to `client`, `__init__.py`, `connectors.py`, `test_negative.py`, `score_initiative`, `test_cycle89.py`, `create_app`?**
  _High betweenness centrality (0.040) - this node is a cross-community bridge._
- **Are the 4 inferred relationships involving `Store` (e.g. with `_store()` and `_seed()`) actually correct?**
  _`Store` has 4 INFERRED edges - model-reasoned connections that need verification._
- **What connects `What it is`, `Install`, `Quickstart` to the rest of the system?**
  _149 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Store` be split into smaller, more focused modules?**
  _Cohesion score 0.05649122807017544 - nodes in this community are weakly interconnected._
- **Should `__init__.py` be split into smaller, more focused modules?**
  _Cohesion score 0.0741745816372682 - nodes in this community are weakly interconnected._