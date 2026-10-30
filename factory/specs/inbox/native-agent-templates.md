---
id: native-agent-templates
title: Native agent templates (§6.3) — product-analyst, data-steward, api-guardian
agent: claude
risk: medium
grill: pending
verification: python -m pytest tests/ -k templates
---

# Native agent templates (§6.3) — product-analyst, data-steward, api-guardian

## Context
Agent factory supports templates; only `product-analyst` is exercised. Prompt §6.3 expects a native roster aligned to the pf-* skills.

## Acceptance Criteria
- [ ] >=3 native templates registered with tools_allowed + eval cases + knowledge_scope guidance
- [ ] Each template maps to its pf-* skill (single source of truth)
- [ ] Eval suite per template passes publish gate on a seeded product
- [ ] Templates listed via `productforge agent templates` and API

## Constraints
- No fake tools — every tool in tools_allowed exists in agents/tools.py
- Evals must execute (not stubbed)

## Grill Gate
<!-- complete before dispatch: decision owner? out of scope? riskiest assumption?
     smallest acceptable version? — do NOT invent answers autonomously -->

## Review Notes
§6.3 native agents roster.
