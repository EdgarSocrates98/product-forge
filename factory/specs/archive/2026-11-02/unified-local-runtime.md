---
id: unified-local-runtime
status: archived
closed_at: 2026-11-02
title: One-command local runtime for Product Forge, Portal and Agent Bridge
agent: codex
risk: high
grill: completed
verification:
  - python -m pytest tests/ -q
  - python -m ruff check src tests
  - python -m pytest tests/system/ -q
---

# Context

The three repositories expose compatible pieces but require users to understand separate installation, process, token and health concepts. Product Forge must become the single entry point for a non-technical user. `productforge install` prepares the local Product Forge + Portal + Forge Agent Bridge composition without asking for provider credentials. `productforge portal` is the explicit command that starts/repairs the Product Forge portal and its managed Bridge runtime, then serves the dedicated PM/PA workspace.

# Acceptance Criteria

1. `productforge install` with no advanced flags chooses a documented recommended local profile and completes without requiring the user to run a second repository-specific installer or enter provider credentials.
2. The installer writes one versioned composition manifest containing component versions, state directory, ports/URLs, ownership, token references, and health status. Secrets are never stored in plaintext in receipts.
3. Re-running the command is idempotent: it detects the existing installation, repairs drift safely, and does not duplicate host entries or processes.
4. `productforge portal` owns the lifecycle of the dedicated Product Forge portal and Bridge processes: start, health-check, repair, restart and graceful shutdown. Standalone developer commands remain available as an explicit advanced path.
5. The command performs post-install probes for Product Forge API, Portal UI/static server, Bridge diagnostics, and MCP configuration; failures are actionable and identify the exact component.
6. A clean temporary-home integration test installs the wheel into an isolated environment, executes the command, starts the composition, verifies the health graph, and tears it down without touching the developer checkout.
7. Existing `--scope`, `--profile`, `--execution-profile`, `--components`, `--hosts`, `--dry-run` and `--yes` paths remain backward-compatible.
8. The portal has a Product Forge-specific PM/PA navigation and does not present itself as a generic forge portal: workspace, products, roadmap/board, knowledge, analytics, agent chat and execution receipts are first-class areas.

# Constraints

- Reuse the existing vendored installkit and receipt/ledger machinery; do not create a second installer framework.
- Preserve loopback binding, pairing, origin and approval security boundaries from Portal and Bridge.
- Do not silently choose a cloud provider or spend money. Provider configuration remains a separate explicit step.
- Keep the implementation additive and version the manifest/health contract.

# Grill Gate

- Decision owner: Edgar (answered 2026-11-02).
- Product Forge may start/stop/repair Portal and Agent Bridge, but only when `productforge portal` is requested.
- `productforge install` must not open the browser and must not ask provider credentials; credentials are requested at first provider use.
- `productforge portal` is the explicit browser-facing command.
- The portal must be product-specific for PM/PA workflows and integrate chats with Devin, Codex, Claude and GitHub Copilot.

# Review Notes

- The product decisions are answered; implementation parameters such as provider budgets and supported host runtime details remain review items.
- Evidence: Product Forge `README.md`, `forge.json`, `.mcp.json`; Bridge `README.md`, `install.sh`, `forge.json`; Portal `README.md`, `.github/workflows/ci.yml`.
