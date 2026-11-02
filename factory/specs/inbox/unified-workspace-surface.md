---
id: unified-workspace-surface
title: Unified chat, board and product workspace surface
agent: codex
risk: high
verification:
  - python -m pytest tests/ -q
  - python -m ruff check src tests
---

# Context

Users currently have to understand which surface owns chats, boards and products. Product Forge should own the domain model and Portal should render one coherent workspace, with Bridge events appearing as chat activity rather than a second product.

# Acceptance Criteria

1. Define and implement one canonical Product Forge portal navigation model for PM/PA work: products, boards/roadmaps, knowledge, analytics, agents and chats, with stable deep links and refresh/reconnect behavior.
2. Product Forge is the only source of truth for product/board/workspace records; Portal does not create a parallel persistence model.
3. Chat sessions reference workspace/product context and expose lifecycle, provider capability, approval, event and receipt state through one API envelope. The provider selector includes Devin, Codex, Claude and GitHub Copilot.
4. Board items can link to chat sessions and artifacts without duplicating event history.
5. Empty, loading, unavailable, error, permission and offline states are explicit and accessible in the UI.
6. Add browser E2E covering product → board → chat → receipt, plus reconnect after Bridge restart.

# Constraints

- Preserve Portal's plan → review → confirm → execute → verify → receipt principle for consequential actions.
- Preserve Bridge's honest capability states; never show an AI action as available when the provider is unverified/unavailable.
- Prefer additive contract versioning over breaking PortalApi changes.

# Grill Gate

- Decision owner: Edgar (answered 2026-11-02).
- The portal is Product Forge-specific, focused on PM/PA tools, and is intentionally different from generic Forge portals.
- Chat must integrate Devin, Codex, Claude and GitHub Copilot.
- Whether chat is top-level or product-scoped, and the canonical board entity, remain `[ASK USER]` implementation decisions.

# Review Notes

- Evidence: Portal `README.md`, `docs/fase0/contracts.md`, `docs/observability/execution-events.md`; Product Forge `README.md` and API modules; Bridge `contracts.py` and event/replay docs.
