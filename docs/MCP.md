# Product Forge — MCP tools

`productforge mcp serve` exposes 14 tools over stdio (JSON-RPC). Hosts
register it via `.mcp.json` (the `mcp` install component writes the entry):

```json
{"mcpServers": {"product-forge": {"command": "productforge", "args": ["mcp", "serve"]}}}
```

HTTP transport is also available: `productforge mcp serve --transport http`.

## Tool reference

| Tool | Required args | What it returns |
|---|---|---|
| `productforge_status` | — | version, home, capability flags |
| `product_list` | — (`workspace_id`?) | products, optionally filtered |
| `product_context` | `product_id` | Product Context Package — entities, sources, agents, contracts |
| `knowledge_query` | `product_id`, `question` | FTS chunks **with citations** |
| `knowledge_health` | `product_id` | coverage/citation health |
| `product_graph` | `product_id` | entity/relation graph projection |
| `agent_list` | `product_id` | agent definitions |
| `agent_run` | `agent_id`, `input` | policy-checked, audited run result |
| `agent_eval` | `agent_id` | eval suite score (persisted) |
| `query_validate` | `statement` | read-only SQL verdict (sqlglot) — writes/multi-statements rejected |
| `dashboard_list` | `product_id` | dashboards for a product |
| `roadmap` | `product_id` | now/next/later lanes |
| `alerts_list` | `product_id` | open/acked alerts |
| `audit_list` | — (`product_id`?) | audit events |

## Contracts

- **Evidence-first** — `knowledge_query` returns chunk citations;
  `agent_run` returns `run_id`; answers cite ids, never bare prose.
- **Gated** — `agent_run` is policy-checked and audited; publishing is
  eval-gated (`agent_eval` ≥ 0.5 + `tools_allowed`).
- **Read-only analytics** — `query_validate` proves read-only before any
  execution path; mutating SQL is rejected, never run.
- **Honest absence** — missing capability is a named state
  (`unverified`/`unavailable:*`), not a fabricated result.
