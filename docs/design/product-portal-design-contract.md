# Product Forge portal design contract

Date: 2026-11-02

## Direction

**Editorial operational workspace**: a calm, high-trust surface for PMs and PAs that turns product context into decisions. The memorable anchor is the oversized editorial headline paired with a persistent “next step” signal and a local-context rail.

DFII: 13/15 — impact 4, context fit 5, feasibility 5, performance 4, consistency risk 5.

## Design rules

- Use Manrope for dense interface text and DM Mono for evidence, labels and system state.
- Use midnight navy as the working canvas, lime as the action/trust accent, and blue only for service/context emphasis.
- Keep a three-layer hierarchy: workspace rail → current decision context → action surface.
- Make AI trust visible: provider state, credential timing, citations, approvals and receipts are always explicit.
- Prefer one asymmetric focus composition over a generic grid of equal cards.
- All async surfaces need loading, empty, unavailable, error and success states.
- Native controls remain keyboard reachable; focus is visible; skip link and live regions are required.

## Relationship UX

- The workspace remembers the user’s product context and returns to the same conversation.
- Chat is connected to a product/workspace rather than floating as a generic assistant.
- The interface explains what the system knows, when credentials are needed, and which host is active.
- Provider autonomy increases only through explicit approval/replay/receipt patterns.

## Validation evidence

- `src/product_forge/portal_assets/index.html`
- `src/product_forge/portal_assets/app.js`
- `src/product_forge/portal_assets/style.css`
- Browser DOM audit: skip link, semantic landmarks, labelled controls, live regions and mobile viewport checked on 2026-11-02.
