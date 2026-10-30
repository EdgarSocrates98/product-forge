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
