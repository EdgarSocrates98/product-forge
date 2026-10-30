# INTEGRATION_CONTRACTS — Product Forge

## Published contracts

| Contract | Producer | Consumer | File/endpoint |
|---|---|---|---|
| `forge/SpecialistAgenticManifest/v1` | product-forge | the-forge, forge-cli | `forge.agentic.json` |
| `forge.json` ops descriptor | product-forge | forge-cli install/lifecycle | `forge.json` |
| `forge/PortalApi/1` envelope | product-forge API | Portal, CLI, SDK | all `/api/v1` responses |
| `productforge/ProductContextPackage/v1` | product-forge | agents, graph studio, hosts | `GET /api/v1/products/{id}/context`, `productforge product context` |
| `productforge/<Entity>/v1` | product-forge | all surfaces | `domain/models.py` (schema field on every entity) |
| `forge/PortalEvent/1` | portal adapter ops | observability sinks | `ctx.emit(...)` in adapter |

## Consumed contracts

| Contract | Provider | Use |
|---|---|---|
| `forge/PortalApi/1` | vendored `_forge_portal.py` | sessions, CSRF, rate limits, plan tokens, SSE |
| Forge Protocol (subprocess+JSON) | the-forge | invokes `productforge <workflow>` commands |
| PortalAdapter/Operation | forge-portal | typed ops under `/api/v1` |

## API surface (Cycle 1–2 real endpoints)

```
GET    /api/v1/health                      public
GET    /api/v1/capabilities                public
POST   /api/v1/auth/rotate|revoke          bearer
POST   /api/v1/workspaces                  bearer   201
GET    /api/v1/workspaces[/{id}]           public-ish local
PATCH  /api/v1/workspaces/{id}             bearer
POST   /api/v1/products                    bearer   201 (validates workspace)
GET    /api/v1/products[/{id}]             
GET    /api/v1/products/{id}/context       ProductContextPackage/v1
POST   /api/v1/products/{id}/sources|agents|data-sources|dashboards|initiatives|decisions   bearer 201
GET    /api/v1/products/{id}/<collection>[/{rid}]
GET    /api/v1/audit[?product_id=]
```

Errors: `PF-UNAUTHORIZED`, `PF-RATE-LIMIT`, `PF-PAYLOAD-TOO-LARGE`, `PORTAL-NOT-FOUND`, `PF-VALIDATION`, `PF-INTERNAL` — all inside the envelope with `correlation_id` echoed in `X-Correlation-Id`.

## MCP tools (stdio, `productforge mcp serve`)

`productforge_status`, `product_list`, `product_context`, `knowledge_query`, `agent_list` — all read-only.
