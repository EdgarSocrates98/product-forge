# Loop continuation — resume from here

## Done (verified: ruff clean, 7 tests green, CLI+MCP+API smoke OK)
- Cycle 1 baseline: packaging, CLI, config, security, domain, sqlite+FTS5 store, audit
- API /api/v1 (envelope forge/PortalApi/1, bearer, rate/payload limits): workspaces, products, context pkg, sources/agents/data-sources/dashboards/initiatives/decisions CRUD, auth rotate/revoke, audit
- MCP stdio server (5 read-only tools), portal adapter (ProductForgePortal), vendored _forge_portal.py
- Audit deliverables all in docs/audit/ + docs/adr/ADR-001
- venv: .venv via `uv pip install -p .venv/bin/python -e ".[dev]"`; test: `.venv/bin/python -m pytest -q`

## Next priority order (from IMPLEMENTATION_GAP_MATRIX)
1. Cycle 3: entity extraction (heuristic, no LLM) → entities+relations → graph endpoint; knowledge health
2. Cycle 4: agent runtime (local executor, policies, tool registry), eval harness, publish flow
3. Cycle 5: sqlglot SQL validation (read-only enforcement, dialect allowlist), sqlite/duckdb connector, query_runs with timeout/cancel
4. Cycle 6: dashboard widgets bound to query_runs (real data only)
5. Cycle 7: RICE/WSJF prioritization, PRD/roadmap generators (deterministic templates), decisions w/ evidence
6. Cycle 2 remainder: onboarding UX, forge-portal Angular module OR standalone assets
7. Cycles 8-11, then Cycle 12 homologation + 30-step Payments scenario
8. Commit per completed cycle; keep `docs/audit/IMPLEMENTATION_GAP_MATRIX.md` updated
