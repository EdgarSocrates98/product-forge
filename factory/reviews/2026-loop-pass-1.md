# Loop Factory — review pass (agent-built, awaiting human acceptance)

Date: $(date -Iseconds) | Scope: 3 active specs | Gate: STOP before archive.

## mcp-http-transport — verification evidence
- `POST /mcp` streamable-HTTP on `--transport http`, local bearer required.
- Shared `dispatch(req)` for stdio+HTTP: identical JSON-RPC (initialize,
  tools/list, tools/call, ping, errors).
- tests/test_mcp_http.py: 2 passed (401 unauth + 14 tools via POST).
- Limitation documented: request/response POST, no SSE.

## native-agent-templates — verification evidence
- 4 native templates with mission/tools/steps/skill/knowledge_scope/eval_cases
  (product-analyst, product-researcher, api-analyst, data-steward).
- `GET /api/v1/agent-templates` + `productforge agent templates`.
- `run_evals` prefers template eval cases, DEFAULT_SUITE fallback kept.
- tests/test_templates.py: 3 passed (listing, eval→publishable path).
- Publish gate unchanged: tools_allowed + score required.

## llm-gateway-integration — verification evidence (contract-only per grill gate)
- `gateway/synthesis.py`: productforge/SynthesisRequest|Result/v1, provider is
  external subprocess+JSON (Forge Protocol), never an SDK import.
- Config seam: `gateway.provider_cmd` + `gateway_profile` (economy|balanced|deep).
- No provider → `unavailable:no-provider-adapter` (honest, per user decision).
- Budget ledger records tokens_in/out only on `status: ok`.
- Security fix: `tokens_in/out` added to REDACT_EXEMPT (counts, not secrets).
- tests/test_gateway.py: 4 passed (unavailable, provider ok + ledger,
  provider failure, API states).
- OPEN (needs product decision before provider ships): which provider_cmd to
  bless, credential provisioning path, cost ceilings per profile.

Suite: 70 passed · ruff clean. Specs remain in active/ — archive requires
human `--accepted`.
