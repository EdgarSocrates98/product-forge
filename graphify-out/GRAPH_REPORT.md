# Graph Report - product-forge  (2026-10-29)

## Corpus Check
- 69 files · ~25,952 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 382 nodes · 803 edges · 11 communities
- Extraction: 91% EXTRACTED · 9% INFERRED · 0% AMBIGUOUS · INFERRED: 69 edges (avg confidence: 0.86)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `e144f881`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- app.py
- build_relations
- Store
- __init__.py
- connectors.py
- run_agent
- engine.py
- TokenStore
- score_initiative
- aws.py
- test_cycle89.py

## God Nodes (most connected - your core abstractions)
1. `Store` - 54 edges
2. `_out()` - 33 edges
3. `_store()` - 29 edges
4. `create_app()` - 19 edges
5. `run_agent()` - 17 edges
6. `TokenStore` - 16 edges
7. `execute_query()` - 13 edges
8. `run_workflow()` - 11 edges
9. `ToolCtx` - 10 edges
10. `connector_for()` - 10 edges

## Surprising Connections (you probably didn't know these)
- `test_api_knowledge_flow()` --calls--> `create_app()`  [INFERRED]
  tests/test_cycle3.py → src/product_forge/api/app.py
- `test_api_agent_flow()` --calls--> `create_app()`  [INFERRED]
  tests/test_cycle4.py → src/product_forge/api/app.py
- `test_schema_explorer()` --uses--> `SQLiteConnector`  [INFERRED]
  tests/test_cycle5.py → src/product_forge/analytics/connectors.py
- `test_workflow_halts_on_cross_product()` --calls--> `run_workflow()`  [INFERRED]
  tests/test_cycle1011.py → src/product_forge/agents/workflows.py
- `test_workflow_multi_agent()` --calls--> `run_workflow()`  [INFERRED]
  tests/test_cycle1011.py → src/product_forge/agents/workflows.py

## Import Cycles
- None detected.

## Communities (11 total, 0 thin omitted)

### Community 0 - "app.py"
Cohesion: 0.06
Nodes (49): BaseModel, FastAPI, Request, Any, Model routing + cost ledger — gateway profiles and honest budgets. No provider…, Append to the product's daily budget ledger (audit-safe)., record_usage(), route() (+41 more)

### Community 1 - "build_relations"
Cohesion: 0.17
Nodes (13): KnowledgeEntity, Relation, build_relations(), extract_entities(), Deterministic entity extraction — no LLM required. Heuristics over chunk text…, chunks: [{id, text}] → dedup'd provisional entities with evidence., documented_in(entity→doc chunk) + co-occurrence related_to., home() (+5 more)

### Community 2 - "Store"
Cohesion: 0.06
Nodes (37): Entity, _context_package(), _data_sources(), _entities(), _graph_lookup(), _knowledge_health(), _knowledge_query(), Any (+29 more)

### Community 3 - "__init__.py"
Cohesion: 0.08
Nodes (61): command, ag_create(), ag_eval(), ag_list(), ag_publish(), ag_run(), api_serve(), api_token() (+53 more)

### Community 4 - "connectors.py"
Cohesion: 0.14
Nodes (14): Connection, Event, Protocol, Connector, connector_for(), DuckDBConnector, _mask(), Any (+6 more)

### Community 5 - "run_agent"
Cohesion: 0.14
Nodes (26): AgentDefinition, json_str(), Any, Agent evaluation harness — real runs against real knowledge. A case: {question,…, run_evals(), check_budget(), check_input(), check_tool() (+18 more)

### Community 6 - "engine.py"
Cohesion: 0.08
Nodes (36): parametrize, compile_spec(), execute_query(), _ident(), nl_to_sql(), Any, Query engine — validate → allowlist → execute → record. Every execution…, Deterministic NL→SQL for registered patterns — honest otherwise. (+28 more)

### Community 7 - "TokenStore"
Cohesion: 0.25
Nodes (3): Path, Local API bearer token — generated on first use, file 0600., TokenStore

### Community 8 - "score_initiative"
Cohesion: 0.09
Nodes (23): fixture, generate_prd(), Any, Store, PRD + roadmap generators — deterministic templates over real data. PRD pulls…, Any, Prioritization — RICE and WSJF scoring, deterministic and explainable., factors may carry rice{reach,impact,confidence,effort} and/or… (+15 more)

### Community 9 - "aws.py"
Cohesion: 0.24
Nodes (12): AthenaConnector, _boto3(), cost_summary(), glue_catalog(), Any, quicksight_inventory(), AWS intelligence — real boto3 connectors; honest unavailability. Every…, QuickSight dashboards/datasets inventory (read-only). (+4 more)

### Community 10 - "test_cycle89.py"
Cohesion: 0.08
Nodes (30): diff_openapi(), load_spec(), parse_asyncapi(), parse_openapi(), Any, OpenAPI/AsyncAPI parsing + breaking-change detection — real diffs., Extract the API surface: operations, params, schemas., Breaking-change detection between two parsed OpenAPI surfaces. (+22 more)

## Knowledge Gaps
- **1 isolated node(s):** `Tool`
  These have ≤1 connection - possible missing edges or undocumented components.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Store` connect `Store` to `app.py`, `build_relations`, `__init__.py`, `run_agent`, `test_cycle89.py`?**
  _High betweenness centrality (0.277) - this node is a cross-community bridge._
- **Why does `create_app()` connect `app.py` to `build_relations`, `Store`, `__init__.py`, `run_agent`, `engine.py`, `score_initiative`, `test_cycle89.py`?**
  _High betweenness centrality (0.119) - this node is a cross-community bridge._
- **Why does `TokenStore` connect `TokenStore` to `app.py`, `Store`, `__init__.py`, `engine.py`, `score_initiative`, `test_cycle89.py`?**
  _High betweenness centrality (0.060) - this node is a cross-community bridge._
- **Are the 4 inferred relationships involving `Store` (e.g. with `_store()` and `_seed()`) actually correct?**
  _`Store` has 4 INFERRED edges - model-reasoned connections that need verification._
- **Are the 5 inferred relationships involving `create_app()` (e.g. with `test_api_knowledge_flow()` and `test_api_agent_flow()`) actually correct?**
  _`create_app()` has 5 INFERRED edges - model-reasoned connections that need verification._
- **What connects `Tool` to the rest of the system?**
  _1 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `app.py` be split into smaller, more focused modules?**
  _Cohesion score 0.06328320802005012 - nodes in this community are weakly interconnected._