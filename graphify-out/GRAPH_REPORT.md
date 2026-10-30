# Graph Report - product-forge  (2026-10-29)

## Corpus Check
- 53 files · ~19,209 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 243 nodes · 528 edges · 8 communities
- Extraction: 93% EXTRACTED · 7% INFERRED · 0% AMBIGUOUS · INFERRED: 36 edges (avg confidence: 0.86)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `579df604`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- app.py
- build_relations
- Store
- __init__.py
- connector_for
- run_agent
- execute_query
- TokenStore

## God Nodes (most connected - your core abstractions)
1. `Store` - 36 edges
2. `_out()` - 28 edges
3. `_store()` - 24 edges
4. `create_app()` - 16 edges
5. `TokenStore` - 16 edges
6. `run_agent()` - 16 edges
7. `execute_query()` - 14 edges
8. `connector_for()` - 13 edges
9. `compile_spec()` - 9 edges
10. `validate()` - 9 edges

## Surprising Connections (you probably didn't know these)
- `test_schema_explorer()` --uses--> `SQLiteConnector`  [INFERRED]
  tests/test_cycle5.py → src/product_forge/analytics/connectors.py
- `test_api_knowledge_flow()` --calls--> `create_app()`  [INFERRED]
  tests/test_cycle3.py → src/product_forge/api/app.py
- `test_allowlist_enforced()` --calls--> `execute_query()`  [INFERRED]
  tests/test_cycle5.py → src/product_forge/analytics/engine.py
- `test_execute_real_query()` --calls--> `execute_query()`  [INFERRED]
  tests/test_cycle5.py → src/product_forge/analytics/engine.py
- `test_execute_rejected_persists()` --calls--> `execute_query()`  [INFERRED]
  tests/test_cycle5.py → src/product_forge/analytics/engine.py

## Import Cycles
- None detected.

## Communities (8 total, 0 thin omitted)

### Community 0 - "app.py"
Cohesion: 0.07
Nodes (41): BaseModel, FastAPI, Request, cancel_query(), compile_spec(), _ident(), nl_to_sql(), Any (+33 more)

### Community 1 - "build_relations"
Cohesion: 0.17
Nodes (13): KnowledgeEntity, Relation, build_relations(), extract_entities(), Deterministic entity extraction — no LLM required. Heuristics over chunk text…, chunks: [{id, text}] → dedup'd provisional entities with evidence., documented_in(entity→doc chunk) + co-occurrence related_to., home() (+5 more)

### Community 2 - "Store"
Cohesion: 0.10
Nodes (21): Entity, _context_package(), _data_sources(), _entities(), _graph_lookup(), _knowledge_health(), _knowledge_query(), Any (+13 more)

### Community 3 - "__init__.py"
Cohesion: 0.10
Nodes (50): command, ag_create(), ag_eval(), ag_list(), ag_publish(), ag_run(), api_token(), doctor() (+42 more)

### Community 4 - "connector_for"
Cohesion: 0.14
Nodes (14): Connection, Event, Protocol, Connector, connector_for(), DuckDBConnector, _mask(), Any (+6 more)

### Community 5 - "run_agent"
Cohesion: 0.15
Nodes (25): AgentDefinition, json_str(), Any, Agent evaluation harness — real runs against real knowledge. A case: {question,…, run_evals(), check_budget(), check_input(), check_tool() (+17 more)

### Community 6 - "execute_query"
Cohesion: 0.12
Nodes (23): fixture, parametrize, execute_query(), check_allowlist(), SQL validation — read-only enforcement + dialect allowlist. Primary path uses…, Return tables outside the catalog allowlist (empty allowlist = all allowed)., _sqlglot_validate(), _token_validate() (+15 more)

### Community 7 - "TokenStore"
Cohesion: 0.25
Nodes (3): Path, Local API bearer token — generated on first use, file 0600., TokenStore

## Knowledge Gaps
- **1 isolated node(s):** `Tool`
  These have ≤1 connection - possible missing edges or undocumented components.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Store` connect `Store` to `app.py`, `build_relations`, `__init__.py`, `run_agent`?**
  _High betweenness centrality (0.224) - this node is a cross-community bridge._
- **Why does `connector_for()` connect `connector_for` to `app.py`, `__init__.py`, `execute_query`?**
  _High betweenness centrality (0.103) - this node is a cross-community bridge._
- **Why does `execute_query()` connect `execute_query` to `app.py`, `__init__.py`, `connector_for`?**
  _High betweenness centrality (0.092) - this node is a cross-community bridge._
- **Are the 2 inferred relationships involving `Store` (e.g. with `_seed()` and `_agent()`) actually correct?**
  _`Store` has 2 INFERRED edges - model-reasoned connections that need verification._
- **Are the 3 inferred relationships involving `create_app()` (e.g. with `test_api_knowledge_flow()` and `test_api_agent_flow()`) actually correct?**
  _`create_app()` has 3 INFERRED edges - model-reasoned connections that need verification._
- **What connects `Tool` to the rest of the system?**
  _1 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `app.py` be split into smaller, more focused modules?**
  _Cohesion score 0.06845513413506013 - nodes in this community are weakly interconnected._