Review Loop Factory spec `ecosystem-p0-hardening` against current working tree.

        Native adapter: `codex`
        Spec path: `/home/edgar/Documentos/projetos/forjas/product-forge/factory/specs/active/ecosystem-p0-hardening.md`

        Review stance:
        - Findings first. Focus correctness, regressions, tests, security, maintainability.
        - Compare implementation against acceptance criteria.
        - Run or inspect verification evidence:
        - `uv run pytest -q`
- `cd ../forge-agent-bridge && uv run pytest -q`
- `cd ../forge-portal && npm test -- --watch=false`
        - If accepted, say `ACCEPTED`.
        - If not accepted, say `CHANGES_REQUESTED` and list blocking items.
        - Do not move files. Operator or CLI archive step moves accepted specs.

        Spec:
        ---
        # Context

The ecosystem prompt requires one dependable product, not three independently
configured services. The current baseline has real adapters and a working
Angular Product Forge surface, but still has high-risk seams around durable
Bridge identity, session authorization, usage replay, and browser-side service
configuration.

# Acceptance Criteria

- [x] Bridge device pairing/revocation/rotation survives restart without
      persisting bearer secrets and uses atomic state writes.
- [x] Session list, metadata mutation, deletion, event replay, cancellation,
      artifacts and streaming enforce the authenticated collaboration policy.
- [x] Usage ledger records only new usage events and ignores duplicate event
      ids after replay or restart.
- [x] Product Forge Angular API defaults to the gateway origin and does not
      persist bearer tokens in localStorage; explicit service URLs remain an
      advanced override.
- [ ] Product Forge runtime serves the Angular bundle as the canonical UI and
      exposes same-origin API/Bridge gateway routes without manual pairing.
- [ ] Complete board/task domain and chat↔board approval workflow are
      persisted and covered by integrated browser tests.
- [ ] OIDC/PKCE mode and full cross-tenant authorization are implemented and
      exercised; local bearer mode remains supported.

# Constraints

- Preserve existing local bearer and fake-provider test paths.
- Never log or persist raw tokens, provider credentials, prompts or responses
  as release artifacts.
- Do not mark provider capabilities verified without real evidence.
- Do not silently switch database backends or erase existing state.

# Grill Gate

- Decision owner: Edgar (answered 2026-11-02).
- Canonical UI: Forge Portal Angular; legacy Product Forge HTML is recovery
  fallback only.
- Default browser experience: same-origin gateway; technical URL/token
  configuration is advanced-only.
- Required providers: Codex, Claude, Devin and GitHub Copilot; missing auth is
  an explicit blocked state.
- Local persistence: SQLite without DSN; managed/advanced PostgreSQL remains
  supported and durable.
- Smallest acceptable increment: security hardening and durable state first,
  then gateway, task domain, chat/board approvals and OIDC as separate review
  gates.

# Review Notes

Implemented increment in the 2026-11-02 working pass. Remaining unchecked
criteria intentionally stay active; they require cross-repository gateway and
domain work rather than documentation-only closure.
