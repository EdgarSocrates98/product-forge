# Graph Report - product-forge  (2026-10-29)

## Corpus Check
- 58 files · ~20,892 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 281 nodes · 598 edges · 8 communities
- Extraction: 92% EXTRACTED · 8% INFERRED · 0% AMBIGUOUS · INFERRED: 47 edges (avg confidence: 0.86)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `7b3a4477`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- app.py
- test_cycle67.py
- Store
- __init__.py
- connectors.py
- run_agent
- engine.py
- TokenStore

## God Nodes (most connected - your core abstractions)
1. `Store` - 36 edges
2. `_out()` - 33 edges
3. `_store()` - 29 edges
4. `run_agent()` - 16 edges
5. `TokenStore` - 15 edges
6. `create_app()` - 14 edges
7. `execute_query()` - 12 edges
8. `score_initiative()` - 10 edges
9. `connector_for()` - 10 edges
10. `render_dashboard()` - 9 edges

## Surprising Connections (you probably didn't know these)
- `test_api_knowledge_flow()` --calls--> `create_app()`  [INFERRED]
  tests/test_cycle3.py → src/product_forge/api/app.py
- `test_schema_explorer()` --uses--> `SQLiteConnector`  [INFERRED]
  tests/test_cycle5.py → src/product_forge/analytics/connectors.py
- `test_api_agent_flow()` --calls--> `create_app()`  [INFERRED]
  tests/test_cycle4.py → src/product_forge/api/app.py
- `test_api_dashboard_planning()` --calls--> `create_app()`  [INFERRED]
  tests/test_cycle67.py → src/product_forge/api/app.py
- `test_dashboard_render_real_data()` --calls--> `render_dashboard()`  [INFERRED]
  tests/test_cycle67.py → src/product_forge/dashboards/render.py

## Import Cycles
- None detected.

## Communities (8 total, 0 thin omitted)

### Community 0 - "app.py"
Cohesion: 0.06
Nodes (39): BaseModel, FastAPI, Request, _cid(), CompileIn, create_app(), Ctx, envelope() (+31 more)

### Community 1 - "test_cycle67.py"
Cohesion: 0.10
Nodes (23): fixture, KnowledgeEntity, Relation, build_relations(), extract_entities(), Deterministic entity extraction — no LLM required. Heuristics over chunk text…, chunks: [{id, text}] → dedup'd provisional entities with evidence., documented_in(entity→doc chunk) + co-occurrence related_to. (+15 more)

### Community 2 - "Store"
Cohesion: 0.10
Nodes (21): Entity, _context_package(), _data_sources(), _entities(), _graph_lookup(), _knowledge_health(), _knowledge_query(), Any (+13 more)

### Community 3 - "__init__.py"
Cohesion: 0.09
Nodes (59): command, ag_create(), ag_eval(), ag_list(), ag_publish(), ag_run(), api_serve(), api_token() (+51 more)

### Community 4 - "connectors.py"
Cohesion: 0.15
Nodes (12): Connection, Event, Protocol, Connector, connector_for(), DuckDBConnector, _mask(), Any (+4 more)

### Community 5 - "run_agent"
Cohesion: 0.15
Nodes (25): AgentDefinition, json_str(), Any, Agent evaluation harness — real runs against real knowledge. A case: {question,…, run_evals(), check_budget(), check_input(), check_tool() (+17 more)

### Community 6 - "engine.py"
Cohesion: 0.09
Nodes (33): parametrize, compile_spec(), execute_query(), _ident(), nl_to_sql(), Any, Query engine — validate → allowlist → execute → record. Every execution…, Deterministic NL→SQL for registered patterns — honest otherwise. (+25 more)

### Community 7 - "TokenStore"
Cohesion: 0.14
Nodes (10): Path, Security primitives: secret redaction, path confinement, token store.…, Deep-scrub secret-shaped values before persistence or transport., Resolve ``raw`` and require it to live inside one of ``roots``., Local API bearer token — generated on first use, file 0600., redact(), safe_path(), _secretish() (+2 more)

## Knowledge Gaps
- **1 isolated node(s):** `Tool`
  These have ≤1 connection - possible missing edges or undocumented components.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Store` connect `Store` to `app.py`, `test_cycle67.py`, `__init__.py`, `run_agent`?**
  _High betweenness centrality (0.204) - this node is a cross-community bridge._
- **Why does `create_app()` connect `app.py` to `test_cycle67.py`, `__init__.py`, `engine.py`?**
  _High betweenness centrality (0.085) - this node is a cross-community bridge._
- **Why does `TokenStore` connect `TokenStore` to `app.py`, `test_cycle67.py`, `__init__.py`?**
  _High betweenness centrality (0.080) - this node is a cross-community bridge._
- **Are the 2 inferred relationships involving `Store` (e.g. with `_seed()` and `_agent()`) actually correct?**
  _`Store` has 2 INFERRED edges - model-reasoned connections that need verification._
- **Are the 5 inferred relationships involving `run_agent()` (e.g. with `ag_run()` and `test_cancel_run()`) actually correct?**
  _`run_agent()` has 5 INFERRED edges - model-reasoned connections that need verification._
- **What connects `Tool` to the rest of the system?**
  _1 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `app.py` be split into smaller, more focused modules?**
  _Cohesion score 0.06183574879227053 - nodes in this community are weakly interconnected._