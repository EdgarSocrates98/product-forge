---
name: pf-finops
description: Product FinOps — agent run budgets, cloud cost honesty. Use for 'cost', 'budget', 'FinOps', 'spend'.
metadata:
  version: "1.0.0"
  forge: product-forge
  manifest: forge/Skill/v1
---
# Finops

## Objetivo
Track agent/token budgets in the ledger and report cloud costs only when verifiable.

## Pré-condições
- Agents running (ledger auto-records); cloud config for cost probes

## Instruções
1. Budgets: `GET /products/{pid}/budgets` → ledger of per-run token/cost estimates.
2. Cloud cost: via `GET /cloud/{aws|azure}/cost` — unverified without creds.
3. Set routing profile so expensive models are chosen only for complex task classes.

## Ferramentas
- `GET /products/{pid}/budgets`
- `GET /cloud/{p}/cost`
- `POST /routing/route`

## Exemplos
- 5 agent runs → ledger shows 5 entries with model + token estimate.

## Limitações
- Estimates are declared/config-derived, not metered billing; cloud costs unverified w/o creds.

## Evals
- Each run appends a ledger entry; no creds → cost probe returns unverified.

## Referências
- API envelope: `forge/PortalApi/1` — `{correlation_id, data, error}`
- Docs: `docs/audit/IMPLEMENTATION_GAP_MATRIX.md`, `docs/adr/ADR-001-architecture-and-persistence.md`
- Source: `src/product_forge/`
