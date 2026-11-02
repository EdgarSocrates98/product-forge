---
id: portal-angular-module
title: Product Forge PM/PA portal with multi-host AI chat
agent: claude
risk: medium
grill: pending
verification: cd forge-portal && npm run build && npm test
---

# Product Forge PM/PA portal with multi-host AI chat

## Context
Product Forge needs its own opinionated PM/PA portal experience. It may reuse the stable PortalApi transport and compatible Angular infrastructure, but the navigation, language, information architecture and chat experience must be Product Forge-specific rather than a generic Forge portal. `productforge portal` is the user-facing command and manages the local Portal + Agent Bridge runtime.

## Acceptance Criteria
- [ ] A Product Forge-specific PM/PA shell exists with workspace, product, board/roadmap, knowledge, analytics and chat navigation
- [ ] Home page lists workspaces/products via PortalApi envelope
- [ ] Chat view integrates Codex, Claude, Devin and GitHub Copilot through the Bridge contract
- [ ] Provider readiness, first-use credential request, approval, streaming, reconnect and receipt states are explicit
- [ ] Knowledge query view renders citations from adapter `knowledge/query` op
- [ ] Mutating ops (query execute, agent run and provider actions) require the confirm dialog per adapter contract
- [ ] No mock data — every view binds to a real adapter op

## Constraints
- Do not change the vendored `_forge_portal.py` (byte-parity)
- Do not weaken the adapter's mutating-op confirmation
- Match forge-portal's existing module structure and design tokens

## Grill Gate
<!-- complete before dispatch: decision owner? out of scope? riskiest assumption?
     smallest acceptable version? — do NOT invent answers autonomously -->
- Decision owner: Edgar (answered 2026-11-02).
- Product Forge portal is intentionally distinct from other Forge portals and focuses on PM/PA workflows.
- All four providers are required: Codex, Claude, Devin and GitHub Copilot.
- `productforge install` does not open the browser; `productforge portal` is the explicit launcher.
- Out of scope: provider credential collection during installation.

## Review Notes
Deferred from Cycle 2 — see IMPLEMENTATION_GAP_MATRIX.
