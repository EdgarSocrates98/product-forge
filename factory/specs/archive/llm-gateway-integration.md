---
id: llm-gateway-integration
title: LLM gateway integration for synthesis (replaces unavailable:no-llm-provider)
agent: claude
risk: high
grill: completed
verification: python -m pytest tests/ -k gateway
---

# LLM gateway integration for synthesis (replaces unavailable:no-llm-provider)

## Context
Knowledge query returns `synthesis: unavailable:no-llm-provider` honestly. A gateway profile (economy/balanced/deep) should route to a configured provider when present — never silently.

## Acceptance Criteria
- [ ] Gateway config section exists (provider, model, profile) with no credentials in repo
- [ ] knowledge/query returns real synthesis when gateway configured
- [ ] Still returns unavailable:* when unconfigured — honest, not an error
- [ ] Budget ledger records tokens/cost per synthesis call
- [ ] Provider credentials never reach logs or persisted state (redact verified)

## Constraints
- Deterministic routing per existing agents/routing.py
- No provider import in core paths (subprocess or HTTP boundary only)
- Missing provider → named refusal, never fabricated answer

## Grill Gate
- decision owner: usuário (sessão loop-factory) — selecionado explicitamente
- out of scope: ver Constraints; nada além dos acceptance criteria
- riskiest assumption: API/engine contrato estável; mudanças são aditivas
- smallest acceptable version: critérios mínimos já listados nos ACs

## Review Notes
§15.5 gateway profiles: economy/balanced/deep.
