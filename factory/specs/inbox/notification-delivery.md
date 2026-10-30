---
id: notification-delivery
title: External notification delivery for alerts (webhook/email)
agent: claude
risk: medium
grill: pending
verification: python -m pytest tests/ -k notify
---

# External notification delivery for alerts (webhook/email)

## Context
Watches produce alerts persisted in-store; delivery to external channels is currently deferred. Spec adds a delivery pipeline with approval-safe defaults.

## Acceptance Criteria
- [ ] Channel registry: webhook (HTTPS URL + secret) and email (SMTP config) types
- [ ] Alert state machine gains `delivered` transition only after provider 2xx
- [ ] Failed deliveries retry with backoff and surface in alert detail
- [ ] Secrets stored via TokenStore / env — never in entity docs
- [ ] Audit event per delivery attempt

## Constraints
- Delivery disabled by default; enabling needs an approval
- No credentials in logs (redact)
- Rate-limited per channel

## Grill Gate
<!-- complete before dispatch: decision owner? out of scope? riskiest assumption?
     smallest acceptable version? — do NOT invent answers autonomously -->

## Review Notes
Deferred item from Cycle 10 — alerts persist, delivery absent.
