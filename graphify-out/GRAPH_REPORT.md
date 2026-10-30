# Graph Report - product-forge  (2026-10-29)

## Corpus Check
- 49 files · ~16,441 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 150 nodes · 329 edges · 12 communities (9 shown, 3 thin omitted)
- Extraction: 93% EXTRACTED · 7% INFERRED · 0% AMBIGUOUS · INFERRED: 23 edges (avg confidence: 0.86)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `3f1c1f98`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- app.py
- build_relations
- Store
- _out
- __init__.py
- run_agent
- command
- kn_import
- ag_eval
- install
- kn_health
- kn_extract

## God Nodes (most connected - your core abstractions)
1. `Store` - 38 edges
2. `_out()` - 21 edges
3. `run_agent()` - 19 edges
4. `_store()` - 19 edges
5. `create_app()` - 11 edges
6. `run_evals()` - 10 edges
7. `ToolCtx` - 9 edges
8. `_agent()` - 8 edges
9. `cancel_run()` - 7 edges
10. `kn_extract()` - 7 edges

## Surprising Connections (you probably didn't know these)
- `test_api_knowledge_flow()` --calls--> `create_app()`  [INFERRED]
  tests/test_cycle3.py → src/product_forge/api/app.py
- `test_eval_and_publish_gate()` --calls--> `run_evals()`  [INFERRED]
  tests/test_cycle4.py → src/product_forge/agents/evals.py
- `test_api_agent_flow()` --calls--> `create_app()`  [INFERRED]
  tests/test_cycle4.py → src/product_forge/api/app.py
- `_seed()` --uses--> `Store`  [INFERRED]
  tests/test_cycle3.py → src/product_forge/store/sqlite.py
- `_agent()` --uses--> `Store`  [INFERRED]
  tests/test_cycle4.py → src/product_forge/store/sqlite.py

## Import Cycles
- None detected.

## Communities (12 total, 3 thin omitted)

### Community 0 - "app.py"
Cohesion: 0.10
Nodes (24): BaseModel, FastAPI, Request, json_str(), Any, Agent evaluation harness — real runs against real knowledge. A case: {question,…, run_evals(), _cid() (+16 more)

### Community 1 - "build_relations"
Cohesion: 0.12
Nodes (19): fixture, KnowledgeEntity, Relation, build_relations(), extract_entities(), Deterministic entity extraction — no LLM required. Heuristics over chunk text…, chunks: [{id, text}] → dedup'd provisional entities with evidence., documented_in(entity→doc chunk) + co-occurrence related_to. (+11 more)

### Community 2 - "Store"
Cohesion: 0.11
Nodes (17): Entity, _context_package(), _data_sources(), _entities(), _graph_lookup(), _knowledge_health(), _knowledge_query(), Any (+9 more)

### Community 3 - "_out"
Cohesion: 0.29
Nodes (11): ag_create(), ag_list(), kn_graph(), kn_query(), _out(), prd_create(), prd_list(), Retrieve grounded chunks with citations (FTS5 retrieval, no LLM). (+3 more)

### Community 4 - "__init__.py"
Cohesion: 0.25
Nodes (6): api_token(), mcp_serve(), productforge CLI — typer app:…, Show (preview) or rotate the local API token., Start the MCP server (stdio). Requires product-forge[mcp]., version()

### Community 5 - "run_agent"
Cohesion: 0.18
Nodes (21): AgentDefinition, check_budget(), check_input(), check_tool(), PolicyReport, Agent policy engine — checked before every run and every tool call. Covers:…, cancel_run(), get_run() (+13 more)

### Community 6 - "command"
Cohesion: 0.22
Nodes (9): command, doctor(), portal(), prd_context(), Serve the Forge Portal (127.0.0.1) with the Product Forge adapter., Show installation and state status., Environment health diagnostics — read-only., status() (+1 more)

### Community 7 - "kn_import"
Cohesion: 0.67
Nodes (3): kn_import(), Path, Import a text/markdown document and index chunks (FTS5).

### Community 8 - "ag_eval"
Cohesion: 0.29
Nodes (7): ag_eval(), ag_publish(), ag_run(), _load_agent(), Any, Execute an agent run (deterministic template + policy checks)., Run the default eval suite and persist the score.

## Knowledge Gaps
- **1 isolated node(s):** `Tool`
  These have ≤1 connection - possible missing edges or undocumented components.
- **3 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Store` connect `Store` to `app.py`, `build_relations`, `_out`, `__init__.py`, `run_agent`?**
  _High betweenness centrality (0.394) - this node is a cross-community bridge._
- **Why does `run_agent()` connect `run_agent` to `app.py`, `ag_eval`, `Store`, `__init__.py`?**
  _High betweenness centrality (0.135) - this node is a cross-community bridge._
- **Why does `create_app()` connect `app.py` to `build_relations`, `__init__.py`, `run_agent`?**
  _High betweenness centrality (0.074) - this node is a cross-community bridge._
- **Are the 2 inferred relationships involving `Store` (e.g. with `_seed()` and `_agent()`) actually correct?**
  _`Store` has 2 INFERRED edges - model-reasoned connections that need verification._
- **Are the 4 inferred relationships involving `run_agent()` (e.g. with `test_cancel_run()` and `test_injection_blocked()`) actually correct?**
  _`run_agent()` has 4 INFERRED edges - model-reasoned connections that need verification._
- **What connects `Tool` to the rest of the system?**
  _1 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `app.py` be split into smaller, more focused modules?**
  _Cohesion score 0.09852216748768473 - nodes in this community are weakly interconnected._