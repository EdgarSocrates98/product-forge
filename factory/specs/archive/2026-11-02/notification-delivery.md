---
id: notification-delivery
status: archived
closed_at: 2026-11-02
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
- [x] Channel registry: webhook (HTTPS URL + secret) and email (SMTP config) types
- [x] Alert state machine gains `delivered` transition only after provider 2xx
- [x] Failed deliveries retry with backoff and surface in alert detail
- [x] Secrets stored via env — never in entity docs
- [x] Delivery receipt is persisted for each attempt/result

## Constraints
- Delivery disabled by default; enabling needs an approval
- No credentials in logs (redact)
- Rate-limited per channel

## Grill Gate
<!-- complete before dispatch: decision owner? out of scope? riskiest assumption?
     smallest acceptable version? — do NOT invent answers autonomously -->

## Review Notes
Closed after webhook 2xx homologation and external Ethereal STARTTLS smoke.
Production SMTP relay credentials remain deployment configuration, not a spec
failure.
