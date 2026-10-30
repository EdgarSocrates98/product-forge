---
id: real-authz-multi-tenant
title: Real authorization — OIDC + workspace isolation for multi-team use
agent: claude
risk: high
grill: pending
verification: python -m pytest tests/ -k authz && python -m pytest tests/ -k isolation
---

# Real authorization — OIDC + workspace isolation

## Context
Current auth is bearer tokens + `X-PF-Principal` headers — dev-grade,
single-operator. Multi-team production needs verifiable identity and
enforced isolation. Depends on: `postgres-backend` (concurrent writers)
or can land on sqlite with documented single-writer limits.

## Acceptance Criteria
- [ ] OIDC middleware (Authorization Code + PKCE for the Portal; client
      assertions/refresh for service callers) behind a config flag —
      bearer-token mode stays for local dev
- [ ] `principal` resolved from verified JWT claims (iss/aud/exp/sub),
      never from a spoofable header when OIDC mode is on
- [ ] Workspace isolation enforced server-side on every product/source/
      knowledge/agent route — cross-workspace access = PF-FORBIDDEN
- [ ] Role ladder (viewer < editor < admin) gates mutating routes
- [ ] IdP-mocked integration tests (httpx MockTransport) covering:
      expired token, wrong aud, cross-workspace attempt, role escalation
- [ ] Docs: `docs/AUTHZ.md` with mode matrix + migration path

## Constraints
- No third-party auth SDK without a pinned version + license check
- Honest states preserved: unknown IdP config → `unverified`, not silent
- Backward compat: existing `productforge` CLI flows keep working in
      local-bearer mode

## Open Questions (human answers required — do NOT invent)
- Which IdP is the target (Keycloak local? Auth0? Entra? Cognito)?
- Is workspace == tenant, or is there an org layer above?
- Who owns the role→route matrix sign-off?

## Grill Gate
<!-- decision owner? out of scope? riskiest assumption? smallest version? -->
