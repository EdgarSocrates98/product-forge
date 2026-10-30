# Release Readiness Baseline — Cycle-25

Unified gate per §30.8 — status **before** Cycle-25 work.

| Gate | Status | Evidence |
|---|---|---|
| CI green on 3 repos | ❌ | portal has no workflow; PF+bridge green |
| No open P0 | ❌ | GAP-01..08 open (see CRITICAL_GAPS_REGISTER) |
| Critical security validated | ❌ | abuse suite absent |
| Integrated E2E approved | ❌ | no cross-repo E2E |
| Providers classified honestly | ✅ | `docs/CAPABILITY_MATRIX.md` — all `unverified` until auth-tested |
| Sessions/events trustworthy | ⚠️ | replay works; in-memory only (restart loses) |
| Approvals secure | ❌ | boolean flag, not bound to op |
| Artifacts preserved | ⚠️ | file snapshots yes; artifact metadata in-memory |
| Docs current | ✅ | README + API + PROVIDERS + SECURITY + HOMOLOGATION (bridge); INSTALL/API/MCP/CHANGELOG (PF) |
| Compatibility verified | ⚠️ | contracts consumed correctly; no automated contract tests |

## Verdict: **NOT READY**

Blocking: 8 P0 gaps (arbitrary exec, boolean approvals, self-asserted
identity, runner SSRF, no request hardening, no CORS, token in localStorage,
flat eval gate). Cycle 25 clears all P0s before any release claim.
