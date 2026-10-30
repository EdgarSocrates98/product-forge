---
name: pf-azure
description: Azure product intelligence — Fabric, Power BI, KQL workspaces. Use for 'Azure resources', 'Fabric', 'Power BI', 'KQL', 'Log Analytics'.
metadata:
  version: "1.0.0"
  forge: product-forge
  manifest: forge/Skill/v1
---
# Azure

## Objetivo
Report Azure/Fabric/PowerBI/KQL state honestly — configured vs unverified vs error.

## Pré-condições
- Azure tenant/subscription configured for real data

## Instruções
1. Inventory: `GET /products/{pid}/cloud/azure/inventory`.
2. Per-service probes surface structured `status` + `missing` fields.
3. Never present unverified items as discovered resources.

## Ferramentas
- `GET /products/{pid}/cloud/azure/inventory`
- `GET /cloud/azure/{service}`

## Exemplos
- Missing tenant → `unverified` + which env vars to set.

## Limitações
- Same honesty invariant as AWS — no fabricated inventory.

## Evals
- No config → unverified with missing list; audit event recorded.

## Referências
- API envelope: `forge/PortalApi/1` — `{correlation_id, data, error}`
- Docs: `docs/audit/IMPLEMENTATION_GAP_MATRIX.md`, `docs/adr/ADR-001-architecture-and-persistence.md`
- Source: `src/product_forge/`
