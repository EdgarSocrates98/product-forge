---
name: pf-agent-factory
description: Create, evaluate and publish product agents. Use for 'create agent', 'run agent', 'agent eval', 'publish agent', 'Agent Factory'.
metadata:
  version: "1.0.0"
  forge: product-forge
  manifest: forge/Skill/v1
---
# Agent Factory

## Objetivo
Build product-scoped agents with declared tools, pass evals, gate publication.

## Pré-condições
- Product exists; knowledge imported for knowledge-backed agents

## Instruções
1. Create: `productforge agent create <pid> '<name>' --tools knowledge_query`.
2. Run: `productforge agent run <pid> <aid> '<input>'` — deterministic + policy-checked.
3. Eval: `productforge agent eval <pid> <aid>` → persisted score.
4. Publish: `productforge agent publish` — requires tools_allowed AND eval score ≥ 0.5.

## Ferramentas
- `productforge agent create|run|eval|publish`
- `GET /agents/{aid}/runs`
- `POST /runs/{rid}/cancel`
- `POST /workflows/run` (multi-agent)

## Exemplos
- Agent w/ knowledge_query → run 'summarize onboarding' → cited template output.

## Limitações
- Injection attempts → run status=blocked (policy engine).
- Default runtime is deterministic template; real LLM loop (`llm_runtime.py`)
  activates only with a configured provider subprocess — tool calls remain
  policy-gated, tokens land in the budget ledger, no provider → honest
  deterministic fallback (never simulated).

## Evals
- No tools_allowed → publish 400; eval 0.3 → publish rejected; score 0.7 → ok.

## Referências
- API envelope: `forge/PortalApi/1` — `{correlation_id, data, error}`
- Docs: `docs/audit/IMPLEMENTATION_GAP_MATRIX.md`, `docs/adr/ADR-001-architecture-and-persistence.md`
- Source: `src/product_forge/`
