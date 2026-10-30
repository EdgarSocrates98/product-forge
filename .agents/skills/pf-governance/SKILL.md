---
name: pf-governance
description: Product governance — approvals, audit trail, policy gates. Use for 'approval', 'audit', 'who changed', 'governance'.
metadata:
  version: "1.0.0"
  forge: product-forge
  manifest: forge/Skill/v1
---
# Governance

## Objetivo
Keep mutating actions gated and every state change auditable.

## Pré-condições
- Product Forge API in use (audit events accumulate automatically)

## Instruções
1. Request approval: `POST /products/{pid}/approvals` {kind, subject_id, reason}.
2. Decide: `POST /approvals/{aid}/decision` {decision:approve|reject, actor}.
3. Inspect trail: `GET /api/v1/audit` — actor/action/resource/timestamp for every change.

## Ferramentas
- `POST /approvals`
- `POST /approvals/{aid}/decision`
- `GET /audit`

## Exemplos
- Publish-gated agent → approval request → approve → publish proceeds.

## Limitações
- Gates enforce within Product Forge only; external systems need their own controls.

## Evals
- Mutating call emits audit event; rejected decision blocks the gated action.

## Referências
- API envelope: `forge/PortalApi/1` — `{correlation_id, data, error}`
- Docs: `docs/audit/IMPLEMENTATION_GAP_MATRIX.md`, `docs/adr/ADR-001-architecture-and-persistence.md`
- Source: `src/product_forge/`
