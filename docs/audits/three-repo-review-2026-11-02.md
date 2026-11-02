# Three-repository product and integration review

Date: 2026-11-02

## Executive finding

The projects are not missing capability in isolation; they are missing one product-shaped runtime boundary. Forge Portal is the presentation/control-center layer, Product Forge is the product/data/installation layer, and Forge Agent Bridge is the provider/session execution layer. Each has a credible contract and tests, but the user still has to understand their independent installation and lifecycle concepts.

The correct target is a single local composition owned by `productforge`: one install command, one state/health manifest, one local gateway/control plane, one workspace model, and one system E2E release signal. The repositories can remain separately usable for development and provider-specific maintenance.

## Evidence-backed current state

| Area | Current reality | Consequence |
|------|-----------------|-------------|
| Portal | Angular 22 frontend, Python local server, PortalApi/vendor parity and browser E2E | UI is a good shell but is not the lifecycle owner |
| Product Forge | `productforge` CLI, HTTP API, MCP, installkit/ledger/receipts, bundled skills/agents | already the natural control-plane owner, but README still describes many manual quickstart commands |
| Agent Bridge | typed provider-agnostic local HTTP bridge, pairing, diagnostics, sessions, replay, approvals and provider adapters | strong execution runtime, but standalone installation/startup adds a second lifecycle |
| Spark Forge AWS | one-command install philosophy, packaged bundles/manifests and evidence-first install gates | useful reference for user-facing installation, not a reason to duplicate its installer |

## Target topology

```text
user
  ↓ one command / one local URL
productforge control plane
  ├─ composition manifest + state directory + receipts
  ├─ Product Forge domain/API (workspace, product, board, chat context)
  ├─ Portal UI/API gateway (presentation only)
  └─ managed Forge Agent Bridge (sessions, providers, approvals, events)
       ├─ fake provider lane for deterministic CI
       └─ real provider lanes for explicit/nightly homologation
```

### Non-negotiable boundaries

1. Product Forge owns installation, process lifecycle, cross-component health and the canonical workspace/product/board state.
2. Portal owns navigation, rendering, accessibility and plan/review/confirm UX; it does not become a second persistence layer.
3. Bridge owns provider execution, typed events, approvals, replay and provider capability truth; it does not own product/board data.
4. The browser talks to one gateway/API contract. It should not discover three ports, tokens or processes.
5. Every cross-component request carries a correlation ID and returns a common envelope with component/capability state.

## User journey that should replace the current mental model

1. User runs `productforge install`.
2. Installer applies recommended local defaults, verifies Python/runtime prerequisites, installs the packaged components, starts the composition and opens or prints one URL.
3. User sees a health panel that explains “ready”, “needs sign-in”, “unavailable” and “error” in plain language.
4. User selects/creates a product; the same workspace contains board items and contextual chats.
5. A chat action shows provider readiness, approval needs, streaming events, replay and receipt without exposing Bridge internals.
6. Restarting the app returns the user to the same workspace and reconnects to the session/history.

## What must be tested for real

- Clean temporary-home install from the built wheel.
- Idempotent rerun and drift repair.
- Portal → Product Forge → Bridge authentication and health.
- Product/board/chat creation and cross-links.
- Fake provider streaming, cancellation, approval, replay and restart.
- At least one credentialed real provider lane with budgets, redaction and honest unavailable/error states.
- Browser journey against the installed, managed composition — not only in-process fixtures.

## Prioritized delivery sequence

1. `unified-local-runtime`: compose and supervise the three components behind `productforge install`.
2. `real-provider-system-harness`: make installed-system integration measurable and repeatable.
3. `unified-workspace-surface`: remove the chat/board/product mental-model split in the Portal/API.
4. Only then expand provider breadth, cloud extras and advanced install profiles.

## Intent vs. reality

- Intent: the README presents an install flow governed by an existing installkit and a guided wizard. Reality: the quickstart still teaches multiple commands and the Bridge/Portal retain separate installers and runtime surfaces.
- Intent: Portal contract/vendor parity enables ecosystem independence. Reality: byte/contract parity does not prove one installed, supervised three-repository journey.
- Intent: real provider capability states are honest. Reality: they are well represented in Bridge evidence, but Product Forge release verification does not yet make the installed cross-repo real-provider journey a single mandatory signal.

## Confirmed product decisions (2026-11-02)

1. Product Forge may start, stop and repair Portal and Agent Bridge automatically, but this happens when the user explicitly runs `productforge portal`.
2. The portal is a Product Forge-specific PM/PA product, distinct from generic Forge portals, and includes chat with Devin, Codex, Claude and GitHub Copilot.
3. All four AI hosts are release blockers.
4. `productforge install` never asks for provider credentials; credentials are requested when a provider is first used.
5. `productforge install` does not open a browser. `productforge portal` is the explicit browser-opening command.

## Remaining implementation decisions

1. [ASK USER] What spend/time budget should each real-provider homologation run enforce?
2. [ASK USER] Should chat be top-level, product-scoped, or both in the first PM/PA release?
3. [ASK USER] Which existing Product Forge entity is the canonical board item: initiative, task, roadmap item, or another model?

## Evidence

- `product-forge/README.md`, `product-forge/forge.json`, `product-forge/.mcp.json`, `product-forge/.github/workflows/ci.yml`
- `forge-agent-bridge/README.md`, `forge-agent-bridge/forge.json`, `forge-agent-bridge/install.sh`, `forge-agent-bridge/src/forge_agent_bridge/contracts.py`
- `forge-portal/README.md`, `forge-portal/scripts/vendor.py`, `forge-portal/.github/workflows/ci.yml`
- `spark-forge-aws/README.md`, `spark-forge-aws/forge.json`
- `docs/codebase/` in each reviewed repository
