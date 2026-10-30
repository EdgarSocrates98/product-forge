---
name: pf-data-products
description: Data product contracts — define schemas, validate payloads, lineage/impact. Use for 'data contract', 'schema validation', 'lineage', 'data product'.
metadata:
  version: "1.0.0"
  forge: product-forge
  manifest: forge/Skill/v1
---
# Data Products

## Objetivo
Enforce declared data contracts and trace impact through the knowledge graph.

## Pré-condições
- Product exists

## Instruções
1. Define: `POST /products/{pid}/contracts` {name, schema{fields:[{name,type,required}]}}.
2. Validate payload: `POST /contracts/{cid}/validate` {payload} → errors[] field-level.
3. Impact: `GET /products/{pid}/impact/{eid}` → graph traversal of dependents.

## Ferramentas
- `POST /contracts`
- `POST /contracts/{cid}/validate`
- `GET /impact/{eid}`

## Exemplos
- Contract requires `user_id:string` → payload missing it → explicit error entry.

## Limitações
- Validation is structural (types/required); semantic rules are advisory.

## Evals
- Type mismatch → error naming field+expected; valid payload → `{valid:true}`

## Referências
- API envelope: `forge/PortalApi/1` — `{correlation_id, data, error}`
- Docs: `docs/audit/IMPLEMENTATION_GAP_MATRIX.md`, `docs/adr/ADR-001-architecture-and-persistence.md`
- Source: `src/product_forge/`
