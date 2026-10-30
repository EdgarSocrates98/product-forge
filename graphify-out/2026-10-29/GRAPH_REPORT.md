# Graph Report - product-forge  (2026-10-29)

## Corpus Check
- 44 files · ~14,190 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 99 nodes · 195 edges · 12 communities (8 shown, 4 thin omitted)
- Extraction: 96% EXTRACTED · 4% INFERRED · 0% AMBIGUOUS · INFERRED: 7 edges (avg confidence: 0.86)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `68bab799`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- app.py
- build_relations
- Store
- command
- __init__.py
- knowledge_health
- status
- kn_import
- api_token
- install
- kn_health
- kn_query

## God Nodes (most connected - your core abstractions)
1. `Store` - 21 edges
2. `_out()` - 18 edges
3. `_store()` - 15 edges
4. `create_app()` - 11 edges
5. `build_relations()` - 9 edges
6. `extract_entities()` - 8 edges
7. `product_graph()` - 8 edges
8. `knowledge_health()` - 8 edges
9. `kn_extract()` - 7 edges
10. `Ctx` - 6 edges

## Surprising Connections (you probably didn't know these)
- `test_api_knowledge_flow()` --calls--> `create_app()`  [INFERRED]
  tests/test_cycle3.py → src/product_forge/api/app.py
- `test_extract_and_graph()` --calls--> `product_graph()`  [INFERRED]
  tests/test_cycle3.py → src/product_forge/knowledge/graph.py
- `test_knowledge_health()` --calls--> `knowledge_health()`  [INFERRED]
  tests/test_cycle3.py → src/product_forge/knowledge/graph.py
- `_seed()` --uses--> `Store`  [INFERRED]
  tests/test_cycle3.py → src/product_forge/store/sqlite.py
- `test_extract_and_graph()` --calls--> `extract_entities()`  [INFERRED]
  tests/test_cycle3.py → src/product_forge/knowledge/extract.py

## Import Cycles
- None detected.

## Communities (12 total, 4 thin omitted)

### Community 0 - "app.py"
Cohesion: 0.12
Nodes (19): BaseModel, FastAPI, Request, _cid(), create_app(), Ctx, envelope(), ProductIn (+11 more)

### Community 1 - "build_relations"
Cohesion: 0.15
Nodes (15): fixture, KnowledgeEntity, Relation, kn_extract(), Extract provisional entities + relations from indexed chunks., build_relations(), extract_entities(), Deterministic entity extraction — no LLM required. Heuristics over chunk text… (+7 more)

### Community 2 - "Store"
Cohesion: 0.19
Nodes (4): Any, Path, Thread-safe JSON-document store over SQLite., Store

### Community 3 - "command"
Cohesion: 0.40
Nodes (11): command, ag_create(), ag_list(), _out(), prd_context(), prd_create(), prd_list(), Any (+3 more)

### Community 4 - "__init__.py"
Cohesion: 0.20
Nodes (8): doctor(), mcp_serve(), portal(), productforge CLI — typer app:…, Start the MCP server (stdio). Requires product-forge[mcp]., Serve the Forge Portal (127.0.0.1) with the Product Forge adapter., Environment health diagnostics — read-only., version()

### Community 5 - "knowledge_health"
Cohesion: 0.25
Nodes (7): kn_graph(), Project the product knowledge graph., knowledge_health(), product_graph(), Any, Graph projection + knowledge health — computed views over the store., SQLite persistence — stdlib, schema-versioned, append-only audit. Entity rows…

### Community 6 - "status"
Cohesion: 0.50
Nodes (3): Entity, Show installation and state status., status()

### Community 7 - "kn_import"
Cohesion: 0.67
Nodes (3): kn_import(), Path, Import a text/markdown document and index chunks (FTS5).

## Knowledge Gaps
- **4 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Store` connect `Store` to `app.py`, `build_relations`, `command`, `__init__.py`, `knowledge_health`, `status`?**
  _High betweenness centrality (0.311) - this node is a cross-community bridge._
- **Why does `create_app()` connect `app.py` to `build_relations`, `__init__.py`, `knowledge_health`?**
  _High betweenness centrality (0.090) - this node is a cross-community bridge._
- **Should `app.py` be split into smaller, more focused modules?**
  _Cohesion score 0.11857707509881422 - nodes in this community are weakly interconnected._