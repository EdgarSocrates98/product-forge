# Critical Gaps Register — Cycle-25 baseline

P0 = blocks secure use. P1 = blocks homologation claims. P2 = quality/UX.

| ID | Repo | Gap | Sev | Cycle |
|---|---|---|---|---|
| GAP-01 | bridge | arbitrary shell exec via `POST /sessions` `cmd` list | **P0** | 25.2 |
| GAP-02 | bridge | approval = client boolean, reusable, unbound to op digest | **P0** | 25.4 |
| GAP-03 | bridge | identity via self-asserted `X-FAB-Principal` header | **P0** | 25.3/25.6 |
| GAP-04 | bridge | runner SSRF — health probe hits caller URL unchecked | **P0** | 25.7 |
| GAP-05 | bridge | no body size limit / rate limit / request timeout | **P0** | 25.5 |
| GAP-06 | bridge | no CORS/origin policy → browser can't call it (Portal breaks) | **P0** | 25.5 |
| GAP-07 | portal | master pair token in localStorage (XSS-exfiltratable) | **P0** | 25.6 |
| GAP-08 | product-forge | flat `eval ≥ 0.5` publish gate, no risk tiers, no security-failure override | **P0** | 25/§4 evals |
| GAP-09 | portal | no CI workflow | **P1** | 25.1/25.9 |
| GAP-10 | bridge | events in-memory — restart loses history/replay | **P1** | 28.3 |
| GAP-11 | bridge | providers `unverified` — no authenticated homologation | **P1** | 26.3–26.5 |
| GAP-12 | bridge | no streaming endpoint (SSE/WS) — poll-only | **P1** | 26.6 |
| GAP-13 | bridge | no durable persistence (sessions/turns/approvals/artifacts) | **P1** | 28.1 |
| GAP-14 | product-forge | session↔product context binding not authorization-enforced | **P1** | 27.1 |
| GAP-15 | product-forge | no MCP federation registry | **P1** | 27.5 |
| GAP-16 | all | no contract tests across repos | **P1** | 30.1 |
| GAP-17 | all | no security E2E (abuse cases) | **P1** | 30.4 |
| GAP-18 | bridge | no secrets abstraction (keychain/secret store) | **P2** | 25.8 |
| GAP-19 | bridge | pair token: no rotation/expiry/device revocation | **P0** | 25.5/25.6 |
| GAP-20 | portal | Chat Studio: cosmetic context picker, no search/history/workflows | **P2** | 29 |
| GAP-21 | bridge | Windows process lifecycle undemonstrated | **P2** | 28.4 |
| GAP-22 | all | no SBOM / dependency audit / secret scanning in CI | **P1** | 25.9 |
| GAP-23 | all | no release artifacts/checksums/GitHub releases | **P2** | 30.7 |

## Resolved at baseline (don't redo)

- private-session non-owner prompt → fixed in C24 (`assert_can_act` owner-only)
- malformed JSON creating sessions → fixed in C24 (`_body` raises `FAB-VALIDATION`)
- snapshot collisions → fixed in C23 (monotonic suffix)
- HTTP body double-read deadlock → fixed in C20
