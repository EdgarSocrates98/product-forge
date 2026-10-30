# Graph Report - product-forge  (2026-10-29)

## Corpus Check
- 63 files · ~23,676 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 339 nodes · 706 edges · 12 communities
- Extraction: 92% EXTRACTED · 8% INFERRED · 0% AMBIGUOUS · INFERRED: 57 edges (avg confidence: 0.86)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `b784a626`
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
- test_cycle67.py
- aws.py
- azure.py
- score_initiative

## God Nodes (most connected - your core abstractions)
1. `Store` - 40 edges
2. `_out()` - 33 edges
3. `_store()` - 29 edges
4. `create_app()` - 17 edges
5. `TokenStore` - 16 edges
6. `run_agent()` - 16 edges
7. `execute_query()` - 12 edges
8. `connector_for()` - 10 edges
9. `ToolCtx` - 9 edges
10. `validate()` - 9 edges

## Surprising Connections (you probably didn't know these)
- `test_api_knowledge_flow()` --calls--> `create_app()`  [INFERRED]
  tests/test_cycle3.py → src/product_forge/api/app.py
- `test_schema_explorer()` --uses--> `SQLiteConnector`  [INFERRED]
  tests/test_cycle5.py → src/product_forge/analytics/connectors.py
- `test_api_agent_flow()` --calls--> `create_app()`  [INFERRED]
  tests/test_cycle4.py → src/product_forge/api/app.py
- `test_api_analytics()` --calls--> `create_app()`  [INFERRED]
  tests/test_cycle5.py → src/product_forge/api/app.py
- `test_api_dashboard_planning()` --calls--> `create_app()`  [INFERRED]
  tests/test_cycle67.py → src/product_forge/api/app.py

## Import Cycles
- None detected.

## Communities (12 total, 0 thin omitted)

### Community 0 - "app.py"
Cohesion: 0.06
Nodes (46): BaseModel, FastAPI, Request, _cid(), CompileIn, create_app(), Ctx, envelope() (+38 more)

### Community 1 - "build_relations"
Cohesion: 0.19
Nodes (12): KnowledgeEntity, Relation, build_relations(), extract_entities(), Deterministic entity extraction — no LLM required. Heuristics over chunk text…, chunks: [{id, text}] → dedup'd provisional entities with evidence., documented_in(entity→doc chunk) + co-occurrence related_to., Cycle 3: extraction, graph, knowledge health. (+4 more)

### Community 2 - "Store"
Cohesion: 0.12
Nodes (19): _context_package(), _data_sources(), _entities(), _graph_lookup(), _knowledge_health(), _knowledge_query(), Any, Agent tool registry — every tool is a real store-backed function. Tools receive… (+11 more)

### Community 3 - "__init__.py"
Cohesion: 0.09
Nodes (59): command, ag_create(), ag_eval(), ag_list(), ag_publish(), ag_run(), api_serve(), api_token() (+51 more)

### Community 4 - "connectors.py"
Cohesion: 0.14
Nodes (14): Connection, Event, Protocol, Connector, connector_for(), DuckDBConnector, _mask(), Any (+6 more)

### Community 5 - "run_agent"
Cohesion: 0.15
Nodes (25): AgentDefinition, json_str(), Any, Agent evaluation harness — real runs against real knowledge. A case: {question,…, run_evals(), check_budget(), check_input(), check_tool() (+17 more)

### Community 6 - "engine.py"
Cohesion: 0.08
Nodes (35): parametrize, compile_spec(), execute_query(), _ident(), nl_to_sql(), Any, Query engine — validate → allowlist → execute → record. Every execution…, Deterministic NL→SQL for registered patterns — honest otherwise. (+27 more)

### Community 7 - "TokenStore"
Cohesion: 0.13
Nodes (9): Entity, Path, Security primitives: secret redaction, path confinement, token store.…, Deep-scrub secret-shaped values before persistence or transport., Local API bearer token — generated on first use, file 0600., redact(), _secretish(), TokenStore (+1 more)

### Community 8 - "test_cycle67.py"
Cohesion: 0.12
Nodes (16): fixture, generate_prd(), Any, Store, PRD + roadmap generators — deterministic templates over real data. PRD pulls…, home(), home(), dbfile() (+8 more)

### Community 9 - "aws.py"
Cohesion: 0.24
Nodes (12): AthenaConnector, _boto3(), cost_summary(), glue_catalog(), Any, quicksight_inventory(), AWS intelligence — real boto3 connectors; honest unavailability. Every…, QuickSight dashboards/datasets inventory (read-only). (+4 more)

### Community 10 - "azure.py"
Cohesion: 0.23
Nodes (9): _credential(), fabric_inventory(), KQLConnector, powerbi_inventory(), Any, Azure intelligence — KQL (Log Analytics) + Fabric/Power BI inventory. Same…, Log Analytics KQL execution via azure-monitor-query., Power BI REST inventory — workspaces + datasets. Token required. (+1 more)

### Community 11 - "score_initiative"
Cohesion: 0.18
Nodes (11): Any, Prioritization — RICE and WSJF scoring, deterministic and explainable., factors may carry rice{reach,impact,confidence,effort} and/or…, score_initiative(), score_rice(), score_wsjf(), build_roadmap(), Any (+3 more)

## Knowledge Gaps
- **1 isolated node(s):** `Tool`
  These have ≤1 connection - possible missing edges or undocumented components.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Store` connect `Store` to `app.py`, `build_relations`, `__init__.py`, `run_agent`, `engine.py`, `TokenStore`?**
  _High betweenness centrality (0.219) - this node is a cross-community bridge._
- **Why does `create_app()` connect `app.py` to `test_cycle67.py`, `build_relations`, `__init__.py`, `engine.py`?**
  _High betweenness centrality (0.113) - this node is a cross-community bridge._
- **Why does `TokenStore` connect `TokenStore` to `app.py`, `test_cycle67.py`, `__init__.py`, `engine.py`?**
  _High betweenness centrality (0.064) - this node is a cross-community bridge._
- **Are the 3 inferred relationships involving `Store` (e.g. with `_seed()` and `_agent()`) actually correct?**
  _`Store` has 3 INFERRED edges - model-reasoned connections that need verification._
- **Are the 5 inferred relationships involving `create_app()` (e.g. with `test_api_knowledge_flow()` and `test_api_agent_flow()`) actually correct?**
  _`create_app()` has 5 INFERRED edges - model-reasoned connections that need verification._
- **What connects `Tool` to the rest of the system?**
  _1 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `app.py` be split into smaller, more focused modules?**
  _Cohesion score 0.06313497822931785 - nodes in this community are weakly interconnected._