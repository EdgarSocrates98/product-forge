# Product Ecosystem Definitive — Cycle 49–58 Review

Baseline: 2026-11-02. This receipt records executable evidence for the
Product Forge, Forge Agent Bridge and Forge Portal composition. A capability
is not marked verified from a unit test alone when it depends on a provider or
external account.

## Evidence

| Gate | Result | Evidence |
|---|---|---|
| Installed CLI entry point | COMPLETED | Built wheel exposes `productforge = product_forge.cli:main`; bare TTY dispatch is reachable. |
| Managed runtime | COMPLETED | `productforge portal` started Angular + Bridge with SQLite/offline mode, dynamic loopback ports and a readiness health check. |
| Bridge gateway | COMPLETED | Same-origin bootstrap succeeded; browser-facing master/pair tokens were not used. |
| SSE | COMPLETED | Explicit `fake` contract test crossed Portal → gateway → Bridge and emitted incremental `forge/AgentBridgeEvent/v1` frames with sequence numbers. |
| Board and proposals | COMPLETED | Canonical Portal adapter now exposes task proposal create/list/decide and Angular sends the required mutation confirmations. |
| Persistence | COMPLETED | Product Forge suite: 126 passed; SQLite remains the local default without a DSN. |
| Angular quality | COMPLETED | Portal unit suite: 579 passed; production Angular build passed; the current bundle is embedded in the Product Forge package assets. |
| Bridge quality | COMPLETED | Bridge suite: 110 passed; lint passed. |
| Provider matrix | COMPLETED WITH RESTRICTIONS | Devin real prompt passed; Copilot real prompt passed; Codex real prompt passed in a dedicated 75s probe; Claude is blocked by missing subscription/API key or valid Bedrock session. |

## Commands executed

```text
product-forge: 126 passed; ruff check passed
forge-agent-bridge: 110 passed; ruff check passed
forge-portal: 579 passed; npm run build passed
product_forge wheel: productforge = product_forge.cli:main
```

The real provider harness produced a redacted artifact with Devin and
Copilot passed, Claude blocked by authentication, and Codex timing out at the
25-second harness budget. A dedicated Codex run with a 75-second bound then
returned the exact `FORGE_CODEX_PING` message and 35 normalized events.

## Honest external boundary

Claude cannot be marked `VERIFIED` on this machine until the user completes
the official subscription/API-key login or refreshes the AWS Bedrock session.
The runtime reports that state and does not fabricate a connected provider.
The bridge package is still resolved from the installed `forge-bridge`
executable or the sibling checkout during development; a standalone Product
Forge wheel without that distribution must continue to report the composition
as incomplete rather than silently downloading code.

## Review decision

`COMPLETED WITH RESTRICTIONS`: the local integrated product path is executable
and tested. Provider authentication and standalone bridge distribution remain
external release gates and must not be converted into a green claim without
their own evidence.
