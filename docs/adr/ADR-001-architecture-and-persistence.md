# ADR-001 — Product Forge architecture & persistence baseline

## Status
Accepted (Cycle 1)

## Context

The master prompt suggests "PostgreSQL + SQLAlchemy + Alembic" as a stack candidate but explicitly says the list is not definitive and demands ecosystem analysis. The Forge ecosystem invariants are: lightweight runtimes, stdlib-first cores, extras for heavy deps, local-first operation, per-forge `.venv`, subprocess isolation between forges, and everything persisted passing through `redact`.

## Decision

1. **Modular monolith** in `src/product_forge` — no microservices; surfaces (CLI/API/MCP/Portal) share one in-process service/store layer. Justification: a specialist forge runs locally per user; network boundaries would only add failure modes.
2. **SQLite JSON-doc store** (`store/sqlite.py`) instead of Postgres+ORM:
   - stdlib `sqlite3` + FTS5 covers relational metadata AND full-text search with zero infra;
   - entities as canonical JSON avoids migration churn while the domain model is still landing (12 cycles);
   - `meta.schema_version` + `Store` abstraction leave room for a Postgres adapter later if multi-user server deployment is ever required;
   - matches how data-sentinel-forge persists snapshots/history.
3. **Core deps**: pydantic, typer, pyyaml only. FastAPI/uvicorn, mcp, sqlglot, duckdb, boto3, azure-*, pypdf etc. behind extras (see DEPENDENCY_RISK_REGISTER).
4. **Security**: bearer `TokenStore` (0600, rotatable), `redact` on all persistence, `safe_path` confinement, product-scoped tenancy, append-only audit, read-only default — same invariants as the-forge core.
5. **No LLM required for baseline**: retrieval + citations work offline; LLM gateway is a later-cycle plugin behind `gateway_profile` (economy|balanced|deep).

## Consequences

+ Zero-infra install (`productforge install` creates home + db, done); offline-capable; trivially testable.
+ Homologation flows can run end-to-end on a laptop.
− Concurrent multi-writer scale is limited (documented; single-user studio is the target).
− A Postgres adapter is deferred work if server deployment emerges (mitigated by Store abstraction).

## Alternatives rejected

- Postgres+SQLAlchemy+Alembic from day 1 — violates ecosystem lightness, adds infra to a local-first tool, premature for a 12-cycle build.
- Importing sibling forge packages — prohibited by Forge Protocol isolation.
- Remote-first API — local 127.0.0.1 + token is the ecosystem security model.
