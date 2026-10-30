---
name: pf-analytics
description: Explore product data sources, schemas and analytical queries without deep SQL. Use for 'explore data', 'what tables', 'metrics', 'analytics'.
metadata:
  version: "1.0.0"
  forge: product-forge
  manifest: forge/Skill/v1
---
# Analytics

## Objetivo
Let a PM/PA answer data questions via schema explorer + compiled/NL queries.

## Pré-condições
- Data source registered and verified (`POST /data-sources/{sid}/verify` → healthy)

## Instruções
1. Verify connectivity: `POST /data-sources/{sid}/verify`.
2. Check the metric catalog first: `GET /products/{pid}/metrics` — reuse
   governed metrics instead of re-deriving KPIs.
3. Browse schema: `GET /data-sources/{sid}/schema` → tables/columns/types.
4. Ask in NL: `POST /queries/nl` — `via: semantic-catalog` (metric match) or
   `deterministic-nl` fallback → review → execute.
5. Persist useful runs — every execution stores a query run with provenance.

## Ferramentas
- `productforge source list|add|verify|schema`
- `POST /queries/nl|compile|execute`

## Exemplos
- 'revenue by month' → NL scaffold SQL → execute → rows + run id.

## Limitações
- NL translation is deterministic scaffolding — always review generated SQL before execute.
- Missing/unreachable sources report error status, never fake rows.

## Evals
- Empty table → `rows: 0` honest result; bad locator → status=error.

## Referências
- API envelope: `forge/PortalApi/1` — `{correlation_id, data, error}`
- Docs: `docs/audit/IMPLEMENTATION_GAP_MATRIX.md`, `docs/adr/ADR-001-architecture-and-persistence.md`
- Source: `src/product_forge/`
