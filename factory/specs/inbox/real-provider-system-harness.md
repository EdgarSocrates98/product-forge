---
id: real-provider-system-harness
title: Installed-system integration harness with real AI provider lanes
agent: codex
risk: high
verification:
  - python -m pytest tests/system/ -q
  - python -m ruff check src tests
---

# Context

Repo-local tests and fake adapters cover important behavior, but they do not prove the installed Portal → Product Forge → Agent Bridge → provider journey. The project needs deterministic tests for every change and credentialed real-provider tests on an explicit lane.

# Acceptance Criteria

1. Add a system test harness that creates a temporary home/workspace, installs the Product Forge wheel, runs `productforge install --yes`, invokes `productforge portal`, and starts the managed composition.
2. The harness exercises one complete user journey: open Portal, create/select workspace and product, create a board item, start a chat session, receive an event, inspect history, and verify a receipt.
3. The default CI lane uses the fake provider and fails on any contract, auth, process, event-ordering or cleanup regression.
4. A separate opt-in/nightly lane runs all four real provider adapters — Codex, Claude, Devin and GitHub Copilot — using injected credentials, records provider/capability/version evidence, redacts prompts/tokens, and never treats an unavailable provider as a false pass.
5. The matrix reports `ready`, `unverified`, `unavailable`, `error` and `passed` distinctly, with actionable diagnostics.
6. The test proves restart/reconnect, cancellation, approval and replay behavior across the installed composition.
7. The harness is portable across Linux/macOS/Windows where the supported installer claims compatibility, or documents an explicit unsupported platform.

# Constraints

- No secrets in git, snapshots, screenshots or receipts.
- Real-provider tests must be opt-in or nightly and must enforce budgets/timeouts.
- Do not weaken existing repo-local tests; the system test is an additional release signal.

# Grill Gate

- Decision owner: Edgar (answered 2026-11-02).
- All four providers are release blockers: Codex, Claude, Devin and GitHub Copilot.
- Credentials are injected only for the real-provider lane and requested at first use in the product flow, never by install.
- Execution cadence and spend/time budgets remain `[ASK USER]` implementation parameters.

# Review Notes

- Evidence: Bridge `tests/test_install.py`, `scripts/e2e_cycle30_1.py`, provider capability/audit docs; Portal `e2e/`; Product Forge `.github/workflows/ci.yml` and `tests/`.
