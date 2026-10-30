# Product Forge

**Product Intelligence, Analytics Intelligence & Agentic Workspace** — a specialist Forge in the Forge ecosystem for Product Managers, Product Analysts and technical teams.

## What it is

Product Forge turns scattered product knowledge (docs, metrics, APIs, data sources, decisions) into a governed, queryable, agent-ready context:

- **Product Context Packages** — curated per-product context: entities, sources, agents, data contracts.
- **Knowledge & Graph** — ingestion → chunking → FTS retrieval with citations → entity/relation graph.
- **Agent Factory** — define, evaluate, publish product-specialist agents with scoped permissions.
- **Analytics Studio** — read-only-by-default governed SQL over registered data sources (NL, visual builder, advanced editor sharing one contract).
- **Dashboard Studio** — real-data KPI cards, charts, filters, sharing.
- **Planning & Discovery** — opportunities, hypotheses, prioritization, PRDs, roadmaps, decisions with evidence traceability.
- **Product Operations** — scheduled reports, watches, alerts, approvals.

Surfaces: **CLI** (`productforge`), **HTTP API** (`/api/v1`, `forge/PortalApi/1` envelope), **MCP server** (`productforge mcp serve`), **Forge Portal** (`productforge portal`).

## Install

```bash
uv venv .venv && uv pip install -p .venv/bin/python -e ".[dev]"
# or: pip install -e ".[api,mcp,analytics]"
productforge install --yes
productforge status
```

## Quickstart

```bash
productforge workspace create "My Company"
productforge product create <workspace_id> "Payments" --domain fintech
productforge knowledge import <product_id> docs/payments.md
productforge knowledge query <product_id> "retry policy"
productforge agent create <product_id> "Payments Analyst" --template product-analyst
productforge api serve            # local API on 127.0.0.1
productforge portal               # visual studio
productforge mcp serve            # MCP tools for agent hosts
```

## Ecosystem compatibility

- `forge/SpecialistAgenticManifest/v1` → `forge.agentic.json` (Forge Protocol provider).
- `forge/PortalApi/1` envelope on every API response (`schema` + `correlation_id` + `data|error`).
- Vendored `_forge_portal.py` (byte-parity with `forge-portal/portal_core/forge_portal.py`) + `ProductForgePortal` adapter.
- Read-only by default; mutations need the local bearer token (`productforge api token --show`).

## Skills

`skills/` ships 16 domain skills (§15.3: strategy, discovery, prioritization, requirements, SQL, analytics, dashboards, AWS, Azure, APIs, data products, governance, FinOps, reporting, knowledge, agent factory) — each validated with `skill-creator` (`agents/openai.yaml` + `quick_validate` clean). Index: `skills/index.json`.

## Status

Beta — Cycles 1–12 complete: foundation → knowledge/graph → agent runtime → analytics → dashboards → planning → cloud/API/data-product intelligence → operations → advanced agentic → homologation. The Payments Product Intelligence scenario runs end-to-end (`tests/test_homologation.py`, 30 steps) plus a negative-scenario suite. See `docs/audit/` for the ecosystem audit, ADRs and the final implementation gap matrix; deferred items are listed there explicitly.
