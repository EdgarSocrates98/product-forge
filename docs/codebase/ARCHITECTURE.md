# Architecture

## Core Sections (Required)

### 1) Architectural Style

- Primary style: layered local application with CLI/API/MCP adapters and persisted SQLite-backed state.
- Why: `product_forge.cli` is the public command surface, `product_forge.api` exposes HTTP resources, and `product_forge.jobs`/`store` own lifecycle and persistence.
- Primary constraints: local-first installation; compatibility with host agent directories; vendored Portal/installkit parity.

### 2) System Flow

```text
productforge install -> host assets/config/receipts
productforge portal -> Product Forge portal runtime -> PortalApi adapter -> SQLite/filesystem
                                  └-> managed forge-bridge -> provider capability/session events
```

1. The console script resolves to `product_forge.cli:app`.
2. Install commands select scope/profile/components/hosts and build a plan before applying it (`README.md`, `forge.json`).
3. API routes validate request models and return structured envelopes (`src/product_forge/api/`).
4. Jobs and resource records are persisted through the store layer.
5. `productforge portal` serves the Product Forge-specific PM/PA static shell and exposes the adapter contract.
6. The portal runtime starts the loopback Bridge only for the explicit portal command; provider credentials remain deferred until first use.
7. Host assets/MCP configuration are written through installkit and recorded in `.product-forge/` receipts/ledger.

### 3) Layer/Module Responsibilities

| Layer or module | Owns | Must not own | Evidence |
|-----------------|------|-------------|----------|
| CLI/install | plan/apply/doctor and user interaction | provider-specific chat state | `src/product_forge/cli`, `README.md` |
| API | resource contracts and HTTP behavior | Angular rendering | `src/product_forge/api/` |
| Store/jobs | durable local state and transitions | host installation policy | `src/product_forge/store`, `src/product_forge/jobs` |
| Skills/agents | prompt/instruction distribution | secrets or process supervision | `.agents/`, `pyproject.toml` |
| Portal adapter | compatibility with Portal contract | second source of truth for products/chats | `src/product_forge/_forge_portal.py` |
| Portal runtime | foreground composition and Bridge lifecycle | installation-time provider startup | `src/product_forge/portal/runtime.py` |

### 4) Reused Patterns

| Pattern | Where found | Why it exists |
|---------|-------------|---------------|
| Adapter/compatibility layer | `_forge_portal.py`, MCP surface | preserve cross-repo contracts |
| Plan → apply → receipt | installkit, `.product-forge/receipts` | make host mutations auditable |
| Registry/lifecycle | jobs registry | represent asynchronous work and terminal state |

### 5) Known Architectural Risks

- The README still presents a multi-command quickstart after install, which conflicts with the desired non-technical first-run experience.
- Portal and Bridge are separate runtime surfaces; no single composition owner is evident in the public CLI contract.
- Vendored parity can preserve compatibility while allowing behavior to diverge between source repositories.

### 6) Evidence

- `README.md`
- `forge.json`
- `src/product_forge/cli/`
- `src/product_forge/api/`
- `.product-forge/install-ledger.json`
