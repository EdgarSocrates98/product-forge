---
id: portal-angular-module
title: Angular module for Product Forge inside forge-portal
agent: claude
risk: medium
grill: pending
verification: cd forge-portal && npm run build && npm test
---

# Angular module for Product Forge inside forge-portal

## Context
Portal adapter contract `forge/PortalApi/1` is stable and served via `productforge portal`. The visual Angular surface lives in the separate forge-portal repo — a cross-repo change.

## Acceptance Criteria
- [ ] A `product-forge` module exists in forge-portal routing
- [ ] Home page lists workspaces/products via PortalApi envelope
- [ ] Knowledge query view renders citations from adapter `knowledge/query` op
- [ ] Mutating ops (query execute, agent run) require the confirm dialog per adapter contract
- [ ] No mock data — every view binds to a real adapter op

## Constraints
- Do not change the vendored `_forge_portal.py` (byte-parity)
- Do not weaken the adapter's mutating-op confirmation
- Match forge-portal's existing module structure and design tokens

## Grill Gate
<!-- complete before dispatch: decision owner? out of scope? riskiest assumption?
     smallest acceptable version? — do NOT invent answers autonomously -->

## Review Notes
Deferred from Cycle 2 — see IMPLEMENTATION_GAP_MATRIX.
