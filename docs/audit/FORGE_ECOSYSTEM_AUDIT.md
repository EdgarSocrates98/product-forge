# FORGE_ECOSYSTEM_AUDIT — Product Forge Cycle 1

Date: 2025 (Cycle 1). Scope: `/home/edgar/Documentos/projetos/forjas/*`. Method: source inspection of manifests, packaging, API/CLI surfaces.

## Ecosystem shape

- **the-forge** — control plane (WHO/WHEN/HOW). Python ≥3.11, runtime **stdlib-only**. Providers invoked via **Forge Protocol (subprocess + JSON)** — never imported into core. Routing deterministic; ambiguity → `ambiguous`. Everything persisted passes `security.redact` except `.forge/runs/<id>/work/`. Contracts `theforge/<Name>/v1` with JSON schemas under `schemas/` (60+ schemas observed). Phase: feature-freeze + dogfooding.
- **forge-cli** (`theforge-cli` npm) — TypeScript/Node ≥20 installer/lifecycle CLI (tsup, vitest, eslint). Modules: integrations, compatibility, safety, registries, healing, preflight, reporting.
- **forge-portal** — Angular 22 standalone UI + `portal_core/forge_portal.py`: **stdlib-only HTTP server vendored byte-parity** into each forge as `<pkg>/_forge_portal.py` (md5 verified identical in the-forge and forge-portal). Contract `forge/PortalApi/1`: envelope `{schema, correlation_id, data|error{code,message,severity,retryable}}`. `PortalAdapter` + `Operation` registry; paths relative to `/api/v1`; mutating ops need `confirm` literal + optional `plan_token`; 1 MiB payload cap, 10 mutating POST/min; 127.0.0.1 + session token + Origin/CSRF guards; `forge/PortalEvent/1` SSE telemetry.
- **data-sentinel-forge** — best specialist template. hatchling, `src/data_sentinel`, deps {pydantic, typer, sqlglot, pyyaml} + extras {aws, stats, api, mcp, dev}. CLI `data-sentinel` (typer). FastAPI `/api/v1`: bearer token (rotate/revoke), rate limit, payload cap, request-id, `_redact`, `_safe_path`, audit, investigations+snapshots+watches+alerts+remediation-approval endpoints. `forge.json` + `forge.agentic.json` (`forge/SpecialistAgenticManifest/v1`: provider/version/cli/cli_entry/workflows/mcp_command/host_adapters/read_only_default/requires_*).
- **api-forge, platform-forge, forge-doctor-***, **code-atlas-forge** — same manifest + CLI + MCP + portal-adapter pattern; domain analyzers exposed as declarative workflows (`analyze`, `doctor`, `capabilities`).
- **spark-forge-aws / spark-forge-azure** — cloud specialists; provider of AWS/Azure domain signals to the-forge (not imported).
- **forge-lens** — observability/trace capture.

## Contracts that bind Product Forge

1. `forge/SpecialistAgenticManifest/v1` → `forge.agentic.json` (done).
2. `forge.json` operations descriptor (forge_id, package, cli, mcp_command, extras, install_command) (done).
3. `forge/PortalApi/1` envelope on every API response (done in `api/app.py`).
4. Vendored `_forge_portal.py` byte-parity + `ProductForgePortal` adapter (done).
5. Forge Protocol provider invocation = `productforge <cmd>` subprocess with JSON stdout (done via CLI JSON output).
6. Read-only-by-default; mutations require bearer token; secrets never persisted (redact on store.audit/put).

## Reusable capabilities (copy/adapt, never import across package boundaries for core)

- Security middleware stack (data-sentinel api/app.py): token store, rate/payload limits, safe_path, redact → adapted in `security.py` + `api/app.py`.
- Vendored portal server + adapter contract → `_forge_portal.py` + `portal/adapter.py`.
- Manifest shape + workflow declaration → `forge.agentic.json`.
- FTS knowledge pattern: sqlite FTS5 with triggers (used by data-sentinel persistence layer) → `store/sqlite.py`.

## Open items for later cycles

- the-forge adapter distribution for product-forge (`adapters/productforge` in the-forge) — deferred; requires the-forge change (feature-freeze → needs ADR or follow existing adapter pattern).
- Graph-studio integration (the-forge `graph_studio`) consumes `ForgeKnowledge`/capability documents — map Product Context Package → those contracts in Cycle 3.
- TokenSaver context optimization — evaluate for Cycle 11 model routing.
