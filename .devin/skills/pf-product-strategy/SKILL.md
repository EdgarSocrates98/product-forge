---
name: pf-product-strategy
description: Frame product strategy for a Product Forge product — vision, context package, decisions log, health. Use when asked 'what is this product', 'product strategy', 'product context'.
metadata:
  version: "1.0.0"
  forge: product-forge
  manifest: forge/Skill/v1
---
# Product Strategy

## Objetivo
Ground strategic claims in the Product Context Package and recorded decisions — never in invented facts.

## Pré-condições
- `productforge install` completed (PRODUCT_FORGE_HOME initialized)
- Product exists: `productforge product list`

## Instruções
1. Pull context: `productforge product context <pid>` — vision, docs, entities, metrics.
2. Read decisions: `GET /api/v1/products/{pid}/decisions` — recorded rationale.
3. Check knowledge health: `GET /api/v1/products/{pid}/knowledge-health` before trusting coverage.
4. Write findings as a decision or document: `POST /products/{pid}/documents/import` or `/decisions`.

## Ferramentas
- `productforge product context <pid>`
- `GET /api/v1/products/{pid}/context`
- `GET /api/v1/products/{pid}/decisions`
- `GET /api/v1/products/{pid}/knowledge-health`

## Exemplos
- Synthesize product positioning → cite context package fields, log gaps as knowledge docs.

## Limitações
- No LLM synthesis without a configured gateway — `synthesis: unavailable:no-llm-provider` is honest output.
- Strategy advice stays advisory; humans own decisions.

## Evals
- Given a product with 3 docs, context package includes their entities.
- No invented metrics — absent fields return null/empty.

## Referências
- API envelope: `forge/PortalApi/1` — `{correlation_id, data, error}`
- Docs: `docs/audit/IMPLEMENTATION_GAP_MATRIX.md`, `docs/adr/ADR-001-architecture-and-persistence.md`
- Source: `src/product_forge/`
