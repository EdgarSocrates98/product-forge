# Cross-Repo Compatibility Matrix — Cycle-25 baseline

Contracts actually consumed (verified by reading both sides), not presumed.

## Portal ↔ Forge Agent Bridge

| Contract | Producer | Consumer | State |
|---|---|---|---|
| `forge/AgentBridgeEvent/v1` | bridge `events.py` | Portal `ChatStudioPage` via `PfBridgeService` | **compatible** — seq/dedupe/replay honored |
| bearer pair token auth | `~/.forge-bridge/pair.token` | Portal login field → `Authorization` | **compatible but insecure** — token in localStorage (Cycle-25 fix: session-scoped pairing) |
| `/agent-sessions` CRUD + actions | `local_bridge.py` | `PfBridgeService` | compatible |
| `/files/{op}` | bridge `files.py` | Portal files panel | compatible |
| CORS | — | browser fetch | **incompatible** — bridge emits no CORS headers; browser→bridge calls only work via non-browser clients (Cycle-25 fix) |
| `X-FAB-Principal` | Portal sets header | bridge collab/audit | **weak** — self-asserted (Cycle-25 fix) |

## Portal ↔ Product Forge

| Contract | Producer | Consumer | State |
|---|---|---|---|
| `forge/PortalApi/1` envelope | `api/app.py` | `PfApiService` | **compatible** — schema+correlation_id+data\|error on every response |
| `/api/v1/*` routes | FastAPI app | `PfApiService` methods | compatible — product health, metrics, NL query, meetings, experiments surfaces consume real endpoints |
| bearer API token | `api token` | PfApi auth header | compatible; workspace-scoped RBAC-lite enforced |

## Bridge ↔ Product Forge

| Contract | State |
|---|---|
| `mcp_servers` pass-through | **wired** — session create accepts map, adapters receive it; PF serves `productforge mcp serve` |
| product binding | **partial** — `product_id` recorded in metadata; not yet an authorization-enforcing context (Cycle-27) |

## Product Forge ↔ MCP hosts

| Contract | State |
|---|---|
| stdio JSON-RPC, 14 tools | compatible — `productforge mcp serve`, registered via `.mcp.json` |
| `forge.agentic.json` manifest | `forge/SpecialistAgenticManifest/v1` present |

## Versioning gaps

- No contract version pinning between repos → Cycle-30 contract tests add
  compatibility checks; `forge/AgentBridgeEvent/v1` and
  `forge/PortalApi/1` are the first versioned families.
