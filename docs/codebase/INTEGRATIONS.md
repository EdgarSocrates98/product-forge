# External Integrations

## Core Sections (Required)

### 1) Integration Inventory

| System | Type (API/DB/Queue/etc) | Purpose | Auth model | Criticality | Evidence |
|--------|---------------------------|---------|------------|-------------|----------|
| Forge Portal | local HTTP/UI contract | product, board and chat presentation | Portal bearer/compatibility contract | high | `README.md`, `_forge_portal.py` |
| Forge Agent Bridge | local HTTP agent runtime | provider sessions/events/approvals | paired local bearer token | high | `README.md` in Bridge; `forge.json` integration metadata |
| MCP hosts | stdio process integration | expose Product Forge tools | host-managed config | high | `.mcp.json`, `forge.json` |
| SQLite/filesystem | local store | products, jobs, receipts and install ledger | filesystem permissions | high | `src/product_forge/store/`, `.product-forge/` |
| AWS/Azure extras | cloud SDK integrations | optional analytics/data workflows | environment/provider credentials | medium | `pyproject.toml` |

### 2) Data Stores

| Store | Role | Access layer | Key risk | Evidence |
|-------|------|--------------|----------|----------|
| SQLite | application state | `store` modules | process ownership/concurrency | `src/product_forge/store/` |
| Filesystem | bundles, receipts, backups | installkit/CLI | drift and partial install | `.product-forge/`, `forge.json` |

### 3) Secrets and Credentials Handling

- Credential sources: provider/host environment and paired local tokens; exact variable inventory is `[TODO]` because no env template was found.
- Hardcoding checks: no claim of absence without a full secret scan; `[TODO]`.
- Rotation/lifecycle: receipts and install ledger exist; provider-token rotation policy is `[TODO]`.

### 4) Reliability and Failure Behavior

- Install path has dry-run/confirm/apply/doctor and receipts.
- Bridge provider sessions expose honest capability states and cancellation/replay semantics (Bridge README).
- Cross-process retry, timeout and recovery policy between Product Forge and Bridge is `[TODO]`.

### 5) Observability for Integrations

- Receipts, audit events and diagnostics exist in the ecosystem.
- A single correlation ID across Portal → Product Forge → Bridge is not established in the public contract; this is a high-priority gap.

### 6) Evidence

- `README.md`
- `.mcp.json`
- `forge.json`
- `.product-forge/install-ledger.json`
- Bridge `README.md` and `src/forge_agent_bridge/contracts.py`
