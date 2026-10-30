# Cycle 13 — Baseline Audit

HEAD: 7131531 (start) → Cycle-13 branch work on `main` | Timestamp: 2026-10-30

## Environment finding — CI is red for billing, not code
`gh run view 40986638095`: all 3 matrix jobs failed in ~2s with
*"recent account payments have failed or your spending limit needs to be
increased"*. No code failure — local gates (pytest 80 green, ruff clean)
are the verification surface until GitHub billing is resolved by the owner.

## §1.1 issue re-check (against HEAD)
| Issue | Verdict |
|---|---|
| CI failure | **Environmental** — billing, not code. Documented; local gates green |
| GET auth gap (middleware mutating-only) | **Fixed** — all private routes now require bearer; `/health` only public; test proves 401/200 matrix |
| KQL/DAX passthrough unvalidated | **Fixed** — conservative validators: KQL refuses `.cmd` management + `externaldata`; DAX requires `EVALUATE`; both marked `*:unverified` for provider-restricted execution |
| `SCHEMA_VERSION=1`, no migrations | **Fixed** — `MIGRATIONS` list + `schema_migrations` table (version, applied_at, checksum), transactional apply, WAL + FK pragmas, `backup()`/`integrity_check()` |
| Agent runtime deterministic-only | **Partially** — deterministic path remains; LLM runtime is Cycle 15 scope (gateway contract already shipped) |
| Evals shallow | **Present** — template eval cases exist; enterprise suites are Cycle 15 scope |
| Delegate audit-ID collision `aud_del_{id}` | **Fixed** — `new_id("aud")` + `utcnow()` + outcome; test proves no overwrite |
| Analytics cloud connectors thin | **Present** — honest `unverified` states; deepening is Cycle 16 |
| Portal adapter only, no Angular Studio | **Present** — Cycle 14 scope |
| CI small for multi-user needs | **Partially** — security headers added; full RBAC/OIDC + durable jobs continuing this cycle |

## Fixed in this pass
- API middleware: bearer required for ALL methods (GET included), `health` only public
- Security headers: `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, `Cache-Control: no-store`
- `sqlvalidate`: `_kql_validate` + `_dax_validate` conservative, `unverified` engine marker
- `store/sqlite`: incremental migration engine (v1→2 adds `schema_migrations` + `jobs` table), WAL, FK, `backup()`, `integrity_check()`
- `delegates/runner`: unique audit IDs, `outcome` field
- 5 legacy tests updated for authenticated GETs (expected security fallout)

## Still open (Cycle 13 continuation)
- RBAC/workspace-product membership abstraction (auth beyond single local token)
- Durable job registry on the new `jobs` table (enqueue/checkpoint/resume/reconcile)
- Postgres adapter (deferred per prior decision — spec in inbox)
- OIDC shared-mode auth (needs IdP decision — grill gate)
- Dependency audit / SBOM / SAST in CI workflow (blocked on billing)

## New risks
- None introduced; auth change is the only behavior break (clients must send token) — documented.
