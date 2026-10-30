---
id: postgres-backend
title: PostgreSQL store backend alongside SQLite
agent: codex
risk: high
grill: pending
verification: python -m pytest tests/ -k store && docker compose up -d pg && python -m pytest tests/ -k pg
---

# PostgreSQL store backend alongside SQLite

## Context
ADR-001 chose SQLite JSON-doc + FTS5 as the shipped store with a documented migration path. Postgres adds concurrent writers and scale-out FTS.

## Acceptance Criteria
- [ ] Store interface abstracted — sqlite.py and postgres.py behind one protocol
- [ ] All 61+ existing tests pass against sqlite unchanged
- [ ] New pg backend passes a mirrored contract-test subset
- [ ] Migration command `productforge store migrate --to postgres` with dry-run + rollback note
- [ ] Config key selects backend; default stays sqlite

## Constraints
- No behavior change for existing installs
- FTS5 → tsvector mapping must preserve citation fields
- redact() still applies to every persisted doc

## Grill Gate
<!-- complete before dispatch: decision owner? out of scope? riskiest assumption?
     smallest acceptable version? — do NOT invent answers autonomously -->

## Review Notes
Migration path per docs/adr/ADR-001.
