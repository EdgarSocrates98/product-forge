---
name: pf-prioritization
description: Prioritize product initiatives with deterministic scoring (reach/impact/confidence/effort). Use for 'prioritize', 'rank initiatives', 'RICE', 'WSJF'.
metadata:
  version: "1.0.0"
  forge: product-forge
  manifest: forge/Skill/v1
---
# Prioritization

## Objetivo
Produce reproducible priority scores from declared inputs — same inputs, same score.

## Pré-condições
- ≥1 initiative in the product

## Instruções
1. List initiatives: `GET /api/v1/products/{pid}/initiatives`.
2. Score one: `productforge plan prioritize <pid> <iid>` or `POST /initiatives/{iid}/prioritize` with factors.
3. Inspect roadmap placement: `GET /api/v1/products/{pid}/roadmap` (now/next/later lanes).

## Ferramentas
- `productforge plan prioritize`
- `POST /initiatives/{iid}/prioritize`
- `GET /roadmap`

## Exemplos
- Initiative w/ reach=1000, impact=2, confidence=0.8, effort=4 → deterministic score stored.

## Limitações
- Score quality = input quality; garbage inputs give precise-looking garbage — cite confidence.

## Evals
- Same factors twice → identical score; missing factors → explicit error, not defaults.

## Referências
- API envelope: `forge/PortalApi/1` — `{correlation_id, data, error}`
- Docs: `docs/audit/IMPLEMENTATION_GAP_MATRIX.md`, `docs/adr/ADR-001-architecture-and-persistence.md`
- Source: `src/product_forge/`
