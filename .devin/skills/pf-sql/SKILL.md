---
name: pf-sql
description: Author and run safe read-only SQL against registered sources. Use for 'run query', 'validate SQL', 'write a query', 'SQL help'.
metadata:
  version: "1.0.0"
  forge: product-forge
  manifest: forge/Skill/v1
---
# Sql

## Objetivo
Get correct read-only SQL executed — never mutate, never bypass validation.

## Pré-condições
- Data source registered: `productforge source add` / `POST /data-sources`

## Instruções
1. Inspect schema first: `productforge source schema <pid> <sid>`.
2. Validate: `POST /queries/validate` (sqlglot — rejects writes/multi-statements).
3. Execute: `productforge query run <pid> <sid> '<sql>'` — row limits + timeout enforced.
4. For non-SQL users: `POST /queries/compile` (visual spec) or `POST /queries/nl` (NL scaffold).

## Ferramentas
- `productforge source schema`
- `productforge query run|validate`
- `POST /queries/execute|validate|compile|nl`
- `POST /queries/{qid}/cancel`

## Exemplos
- `SELECT date, count(*) FROM events GROUP BY 1 LIMIT 100` → validated → rows + provenance.

## Limitações
- Read-only: INSERT/UPDATE/DELETE/DDL rejected with `PF-UNSAFE`.
- SQLite/DuckDB connectors only; locator paths must sit under allowed roots.

## Evals
- `DELETE FROM t` → status=rejected; valid SELECT → completed with row_count.

## Referências
- API envelope: `forge/PortalApi/1` — `{correlation_id, data, error}`
- Docs: `docs/audit/IMPLEMENTATION_GAP_MATRIX.md`, `docs/adr/ADR-001-architecture-and-persistence.md`
- Source: `src/product_forge/`
