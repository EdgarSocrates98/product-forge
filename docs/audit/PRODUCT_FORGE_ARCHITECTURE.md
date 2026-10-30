# PRODUCT_FORGE_ARCHITECTURE — Cycle 1 baseline

## Layering (modular monolith, forge-style)

```
surfaces:   CLI (typer)  |  HTTP API (FastAPI /api/v1)  |  MCP stdio  |  Forge Portal (vendored)
                └──────────── all call the same services ───────────┘
domain:     domain/models.py — pydantic entities, states, permission catalog
services:   knowledge/ agents/ analytics/ dashboards/ planning/ integrations/ reports/ operations/
store:      store/sqlite.py — JSON-doc entities + FTS5 chunks + append-only audit
core:       config.py (layered cfg)  security.py (redact, safe_path, TokenStore)  errors.py (stable codes)
```

## Key decisions

1. **SQLite-first store** (stdlib `sqlite3`, FTS5 built in) with repository-pattern `Store`. Postgres adapter possible later; no ORM dependency in core. ADR-001.
2. **JSON-doc entities**: each domain entity is canonical JSON in `entities(collection,id)` — schema evolves without migrations for additive fields; `meta.schema_version` gates breaking changes.
3. **Single envelope** `forge/PortalApi/1` everywhere; errors are stable `code`s, never stack traces.
4. **Read-only default**: GETs open to local session; mutations require bearer token (file 0600, rotate/revoke endpoints); audit on every mutation.
5. **Product-scoped tenancy**: every resource carries `product_id`; cross-product reads are impossible by construction (queries filter product_id).
6. **No LLM in core**: `knowledge query` returns retrieval + citations without synthesis; LLM providers plug in later via gateway profile (economy|balanced|deep).

## Cycles → modules

| Cycle | Module | State |
|---|---|---|
| 1 | config, security, store, domain, CLI, API, tests, manifests | ✅ baseline |
| 2 | portal adapter + Studio nav | ✅ adapter; ⏳ Angular module |
| 3 | knowledge.ingest (FTS done), entities, graph, RAG citations | 🟡 partial |
| 4 | agents registry done; runtime/policies/evals | 🟡 registry only |
| 5 | analytics: sources registry done; validation/execution | 🟡 registry only |
| 6 | dashboards CRUD done; builder/charts | 🟡 CRUD only |
| 7 | initiatives/decisions CRUD; PRD/roadmap generators | 🟡 CRUD only |
| 8–11 | cloud intel, api/data-product intel, ops, advanced agentic | 🔲 planned |
| 12 | hardening + homologation | 🔲 planned |
