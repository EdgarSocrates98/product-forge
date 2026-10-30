---
name: pf-aws
description: AWS product intelligence — inventory, Athena/Glue/QuickSight states. Use for 'AWS resources', 'Athena', 'Glue catalog', 'QuickSight', 'AWS cost'.
metadata:
  version: "1.0.0"
  forge: product-forge
  manifest: forge/Skill/v1
---
# Aws

## Objetivo
Report AWS integration state honestly: real inventory when configured, `unverified` when not.

## Pré-condições
- AWS config/credentials present for real data

## Instruções
1. Inventory: `GET /products/{pid}/cloud/aws/inventory` — services grouped by provider.
2. Check each service status field: `ok|unverified|error` — never present unverified as fact.
3. On unverified: surface exactly which config is missing.

## Ferramentas
- `GET /products/{pid}/cloud/aws/inventory`
- `GET /cloud/aws/{service}`

## Exemplos
- No creds → `{status:'unverified', missing:['AWS_PROFILE']}`.

## Limitações
- NEVER fabricate resources — absent creds = unverified. This is a hard invariant.
- Read-only discovery; no provisioning/mutation.

## Evals
- Without creds → unverified; with bad creds → error; both recorded in audit.

## Referências
- API envelope: `forge/PortalApi/1` — `{correlation_id, data, error}`
- Docs: `docs/audit/IMPLEMENTATION_GAP_MATRIX.md`, `docs/adr/ADR-001-architecture-and-persistence.md`
- Source: `src/product_forge/`
