---
name: pf-dashboards
description: Build and render product dashboards from real query runs. Use for 'create dashboard', 'KPI card', 'chart', 'dashboard'.
metadata:
  version: "1.0.0"
  forge: product-forge
  manifest: forge/Skill/v1
---
# Dashboards

## Objetivo
Compose KPI/chart widgets bound to executed query runs — rendered data is real data.

## Pré-condições
- ≥1 completed query run for the product

## Instruções
1. Create: `POST /products/{pid}/dashboards` with widgets [{type,title,query_run_id,config}].
2. Render: `POST /dashboards/{did}/render` → each widget resolved against its stored run.
3. Types: `kpi`, `line`, `bar`, `table`; filters in config.

## Ferramentas
- `productforge dashboard create|list`
- `POST /dashboards`
- `POST /dashboards/{did}/render`

## Exemplos
- KPI 'MAU' bound to run q_abc → render returns value + refreshed_at.

## Limitações
- Widgets render from stored runs only — no live source hits at render time.
- Missing run → widget error state, not zeros.

## Evals
- Render of 2 widgets → 2 resolved blocks; deleted run → widget shows error.

## Referências
- API envelope: `forge/PortalApi/1` — `{correlation_id, data, error}`
- Docs: `docs/audit/IMPLEMENTATION_GAP_MATRIX.md`, `docs/adr/ADR-001-architecture-and-persistence.md`
- Source: `src/product_forge/`
