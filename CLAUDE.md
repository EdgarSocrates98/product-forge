# Product Forge — agent rules (Claude mirror)

Same hard rules as AGENTS.md — kept in sync manually (edit both).

- Honesty-first: no success without a real execution result; `unverified`/
  `unavailable:*` are named states, not errors to hide.
- Deterministic core: ambiguity → `ambiguous`; no LLM/wall-clock in engines.
- Evidence-first: cite entity ids, rule_ids, run ids, chunk citations.
- Read-only analytics; gated mutations (publish gate, confirm, approvals).
- Envelope `forge/PortalApi/1` + typed `PF-*` errors on every response.
- Vendored `_forge_portal.py`/`_installkit.py`: byte-parity, never edit.
- Agentic layer: `agents/` profiles, `rules/catalog/`, `skills/pf-*`,
  `factory/` loop (inbox → active → archive; human decides).

Commands: `python -m pytest -q` · `python -m ruff check src tests` ·
`productforge install --dry-run` · `productforge doctor`.


<!-- product-forge:managed:begin -->
## Product Forge

Specialist Forge for product intelligence, analytics and agentic workspaces.

- CLI: `productforge` (status, doctor, workspace, product, knowledge, agent,
  query, source, dashboard, plan, api, mcp, portal).
- Knowledge: `productforge knowledge import|query <pid>` — FTS5 with citations.
- Agents: `productforge agent create|run|eval|publish` — eval-gated publishing.
- Analytics: `productforge source|query` — read-only SQL (sqlglot validated).
- MCP: `productforge mcp serve` exposes productforge_* tools to hosts.
- Skills: `skills/pf-*` — 16 domain skills (strategy, SQL, dashboards, APIs,
  cloud, governance, FinOps, reporting, knowledge, agent factory).
- API envelope: `forge/PortalApi/1` (schema + correlation_id + data|error).
<!-- product-forge:managed:end -->
