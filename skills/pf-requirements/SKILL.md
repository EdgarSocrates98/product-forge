---
name: pf-requirements
description: Generate requirements and PRDs grounded in product knowledge. Use for 'write PRD', 'requirements', 'user stories'.
metadata:
  version: "1.0.0"
  forge: product-forge
  manifest: forge/Skill/v1
---
# Requirements

## Objetivo
Draft PRD sections citing knowledge chunks and linked decisions — every claim traceable.

## Pré-condições
- Initiative exists; product has knowledge docs

## Instruções
1. Generate: `productforge plan prd <pid> <iid>` or `POST /initiatives/{iid}/prd`.
2. PRD pulls context package + citations — verify `sources` array is non-empty.
3. Record outcome decision: `POST /products/{pid}/decisions`.

## Ferramentas
- `productforge plan prd`
- `POST /initiatives/{iid}/prd`
- `POST /decisions`

## Exemplos
- PRD for 'checkout retry' initiative → sections with problem/scope/citations.

## Limitações
- Output is a draft — PM review required; no fake acceptance criteria are invented.

## Evals
- PRD contains ≥1 citation; empty knowledge → explicit `insufficient_context` flag.

## Referências
- API envelope: `forge/PortalApi/1` — `{correlation_id, data, error}`
- Docs: `docs/audit/IMPLEMENTATION_GAP_MATRIX.md`, `docs/adr/ADR-001-architecture-and-persistence.md`
- Source: `src/product_forge/`
