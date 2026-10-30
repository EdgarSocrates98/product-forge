---
id: live-provider-homologation
title: Live homologation — one LLM provider + one cloud connector
agent: claude
risk: high
grill: pending
verification: python -m pytest tests/ -k homolog && cat docs/providers/HOMOLOGATION_EVIDENCE.md
---

# Live homologation — one LLM provider + one cloud connector

## Context
LLM runtime seam, AWS/Azure connectors and capability states exist but
were never exercised with real credentials. Everything downstream is
honestly `unverified` — this spec turns exactly one provider + one cloud
from unverified to verified, with transcripts as evidence.

## Acceptance Criteria
- [ ] One LLM provider (Anthropic/OpenAI/Bedrock — owner's pick) executes
      a real `agent run` end-to-end with recorded request/response
      artifacts under `docs/providers/evidence/`
- [ ] One cloud connector (AWS or Azure) lists real resources in an
      authorized test account; inventory states flip `unverified→verified`
      only for exercised APIs
- [ ] Auth check → session → prompt → streamed answer → tool call →
      denied op → approved op → usage/cost numbers recorded
- [ ] Every unexercised capability stays `unverified` with named reason
- [ ] `docs/providers/HOMOLOGATION_EVIDENCE.md` records versions, regions,
      redacted principals, commands, timestamps

## Constraints
- Credentials come from env/OS keychain — never committed, never in logs
- Redact secrets in every persisted artifact (security.redact)
- Synthetic/test data only; no production tenant access

## Open Questions (human answers required — do NOT invent)
- Which provider + which cloud account is authorized for homologation?
- Which credentials profile should be used, and who approves spend?
- What data is allowed to leave the machine (prompts, queries)?

## Grill Gate
<!-- decision owner? out of scope? riskiest assumption? smallest version? -->
