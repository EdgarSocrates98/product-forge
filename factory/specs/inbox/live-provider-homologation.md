---
id: live-provider-homologation
title: Live homologation — all Product Forge AI hosts + one cloud connector
agent: claude
risk: high
grill: completed
verification: python -m pytest tests/ -k homolog && cat docs/providers/HOMOLOGATION_EVIDENCE.md
---

# Live homologation — all Product Forge AI hosts + one cloud connector

## Context
LLM runtime seam, AWS/Azure connectors and capability states exist but
are not exercised with a complete real-provider matrix. Everything downstream
must remain honestly `unverified` until exercised — this spec turns Codex,
Claude, Devin and GitHub Copilot, plus one cloud connector, from unverified
to verified with transcripts as evidence.

## Acceptance Criteria
- [ ] Codex, Claude, Devin and GitHub Copilot each execute a real
      `agent run` end-to-end with recorded request/response artifacts under
      `docs/providers/evidence/`
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
- Decision owner: Edgar (answered 2026-11-02). Providers: Codex, Claude, Devin and GitHub Copilot. Cloud: AWS (local profile).
- Out of scope: Azure — stays unverified for this milestone.
- Riskiest assumption: all four host credentials and the AWS profile are usable from the authorized environment.
- Smallest acceptable version: one real run for each of the four hosts + one real AWS list call, with transcripts redacted under `docs/providers/evidence/`.
