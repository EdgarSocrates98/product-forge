# Ecosystem Cycle-25 Baseline — 2026-10-30T09:31Z

Baseline executed per `prompt_evo_pf_continuos.md` §2. Effective state
verified locally; SHAs recorded.

## Effective baseline

| Repo | HEAD | Branch | Tests | CI workflow |
|---|---|---|---|---|
| product-forge | `56074b8` | main | **99 passed** (13.7s), ruff clean | `.github/workflows/ci.yml` |
| forge-agent-bridge | `f729a3d` | main | **35 passed** (10.9s), ruff clean | `.github/workflows/ci.yml` |
| forge-portal | `3ac402c` | main | **579/579 passed** (11s), build clean | **none — no workflow file** |

No commits after the §2 reference SHAs on any of the three mains.
No open PRs affecting the baseline (checked `gh pr list` per repo scope).

## Known issues revalidated — classification

### Forge Agent Bridge

| # | Finding (§5) | Class | Evidence |
|---|---|---|---|
| B1 | `POST /sessions` executes arbitrary `cmd` lists from client | **Confirmed** — P0 | `local_bridge.py` spawns any string list |
| B2 | file `upload`/`restore` authz = client `approved: true` boolean | **Confirmed** — P0 | `files.py` gates on body flag |
| B3 | `X-FAB-Principal` self-asserted identity grants ownership | **Confirmed** — P0 | default `local`, no binding to token |
| B4 | runner health accepts caller-supplied endpoint, no identity check | **Confirmed** — P0 | `runners.py` probe hits body URL |
| B5 | no request body size limit | **Confirmed** | `_body()` reads full `Content-Length` |
| B6 | no rate limit / no origin-CORS policy / no host check | **Confirmed** | handler has none |
| B7 | EventBuffer in-memory — events lost on restart | **Confirmed** | `events.py` buffer per orchestrator |
| B8 | real providers not homologated under auth | **Unverified** — honest | binaries on PATH (`claude`, `codex`, `devin`); auth untested |
| B9 | Windows process lifecycle undemonstrated | **Unverified** | POSIX-only tests |
| B10 | remote runner: register+health exist, isolated execution unproven | **Confirmed** | placement refused when unverified (honest) |
| B11 | streaming = poll-after-turn | **Confirmed** | no SSE/WebSocket endpoint |

### Forge Portal

| # | Finding (§6) | Class |
|---|---|---|
| P1 | pair token persisted in `localStorage` | **Confirmed** — P0 |
| P2 | browser→bridge CORS/preflight unhomologated | **Confirmed** — bridge sends no CORS headers → browser calls fail |
| P3 | approvals UI never E2E'd vs real providers | **Unverified** |
| P4 | no CI workflow (regression coverage gap) | **Confirmed** — **New** |
| P5 | PF context binding not verifiably linked to sessions | **Confirmed** — picker is cosmetic vs backend |

### Product Forge

| # | Finding (§4 special points) | Class |
|---|---|---|
| F1 | publish gate = flat `eval ≥ 0.5`, no risk tiers | **Confirmed** — needs risk-based gates |
| F2 | LLM runtime provider seam exists; live provider calls `unverified` | **Unverified** |
| F3 | no security test suite (abuse cases) | **Confirmed** |
| F4 | product isolation is per-store scope; cross-product API authz = single bearer token | **Confirmed** — documented limit |

## Cycle-25 blocking P0s (must clear before release)

B1, B2, B3, B4, P1, P2, F1 — all addressed in Cycle 25 implementation.
