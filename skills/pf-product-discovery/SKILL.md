---
name: pf-product-discovery
description: Run continuous product discovery — opportunities, hypotheses, initiatives. Use for 'discovery', 'opportunities', 'hypotheses', 'problem investigation'.
metadata:
  version: "1.0.0"
  forge: product-forge
  manifest: forge/Skill/v1
---
# Product Discovery

## Objetivo
Move opportunities → hypotheses → initiatives with evidence links into knowledge.

## Pré-condições
- Product exists with imported knowledge docs

## Instruções
1. Query knowledge for problem evidence: `productforge knowledge query <pid> '<question>'`.
2. Create initiative: `POST /api/v1/products/{pid}/initiatives` with hypothesis fields.
3. Extract entities from discovery docs: `POST /products/{pid}/knowledge/extract` to grow the graph.
4. Review impact before committing: `GET /products/{pid}/impact/{entity_id}`.

## Ferramentas
- `productforge knowledge query`
- `POST /initiatives`
- `POST /knowledge/extract`
- `GET /impact/{eid}`

## Exemplos
- 'Users churn at onboarding' → doc import → hypothesis initiative → evidence citation.

## Limitações
- Entity extraction is heuristic (deterministic) — review edges before relying on them.
- Hypothesis scoring is advisory only.

## Evals
- Initiative links to ≥1 citation; graph shows new entities after extract.

## Referências
- API envelope: `forge/PortalApi/1` — `{correlation_id, data, error}`
- Docs: `docs/audit/IMPLEMENTATION_GAP_MATRIX.md`, `docs/adr/ADR-001-architecture-and-persistence.md`
- Source: `src/product_forge/`
