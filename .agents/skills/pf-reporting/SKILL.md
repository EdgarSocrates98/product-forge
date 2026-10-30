---
name: pf-reporting
description: Executive and periodic product reports from real state. Use for 'executive report', 'weekly report', 'status report', 'report'.
metadata:
  version: "1.0.0"
  forge: product-forge
  manifest: forge/Skill/v1
---
# Reporting

## Objetivo
Generate reports composed of real product state: KPIs, alerts, decisions, initiative status.

## Pré-condições
- Product with initiatives/alerts/decisions populated

## Instruções
1. Generate: `POST /products/{pid}/reports/generate` {kind:executive|weekly}.
2. List/get: `GET /products/{pid}/reports` — sections cite source collections.
3. Schedule via watch: `POST /products/{pid}/watches` {kind:report, cadence}.

## Ferramentas
- `POST /reports/generate`
- `GET /reports`
- `POST /watches`

## Exemplos
- Executive report → sections: health, KPIs, open alerts, recent decisions.

## Limitações
- Reports reflect stored state — stale sources produce stale reports (honestly dated).

## Evals
- Generated report contains only real entity refs; empty product → empty sections flagged.

## Referências
- API envelope: `forge/PortalApi/1` — `{correlation_id, data, error}`
- Docs: `docs/audit/IMPLEMENTATION_GAP_MATRIX.md`, `docs/adr/ADR-001-architecture-and-persistence.md`
- Source: `src/product_forge/`
