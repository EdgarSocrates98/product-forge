---
name: pf-apis
description: API intelligence — import OpenAPI/AsyncAPI, diff versions, detect breaking changes. Use for 'API spec', 'breaking change', 'API diff', 'import OpenAPI'.
metadata:
  version: "1.0.0"
  forge: product-forge
  manifest: forge/Skill/v1
---
# Apis

## Objetivo
Turn API specs into knowledge-graph entities + flag breaking changes across versions.

## Pré-condições
- OpenAPI/AsyncAPI spec file or URL

## Instruções
1. Import: `POST /products/{pid}/apis/import` {name, spec} → operations parsed to entities.
2. List: `GET /products/{pid}/apis`.
3. Diff: `POST /apis/{aid}/diff` {spec:new_version} → added/removed/breaking arrays.

## Ferramentas
- `POST /apis/import`
- `GET /apis`
- `POST /apis/{aid}/diff`
- `GET /impact/{eid}`

## Exemplos
- v2 removes `POST /charge` → diff flags breaking removal + impact lists dependents.

## Limitações
- JSON/YAML OpenAPI 3.x + AsyncAPI 2.x; exotic $ref forms flagged, not guessed.

## Evals
- Removed endpoint → appears in `breaking`; added → `added`; graph gains operation entities.

## Referências
- API envelope: `forge/PortalApi/1` — `{correlation_id, data, error}`
- Docs: `docs/audit/IMPLEMENTATION_GAP_MATRIX.md`, `docs/adr/ADR-001-architecture-and-persistence.md`
- Source: `src/product_forge/`
