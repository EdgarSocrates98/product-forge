# Product Forge — HTTP API reference

Serve locally: `productforge api serve` (binds `127.0.0.1`).
Token: `productforge api token --show` · rotate via `POST /api/v1/auth/rotate`.

## Envelope — `forge/PortalApi/1`

Every response:

```json
{
  "schema": "forge/PortalApi/1",
  "correlation_id": "req_…",
  "data": { }
}
```

Errors:

```json
{
  "schema": "forge/PortalApi/1",
  "correlation_id": "req_…",
  "error": {"code": "PF-NOT-FOUND", "message": "…"}
}
```

Typed `PF-*` codes on every failure; `correlation_id` echoes or mints.

## Auth guard

`Authorization: Bearer <api token>` on all `/api/v1/*` except
`/api/v1/health`. Mutating routes audit + may require
`confirmation: true` in the body or a product approval — the response names
the requirement.

## Route index

### Meta / ops

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/v1/health` | liveness (unauthenticated) |
| GET | `/api/v1/capabilities` | honest capability flags |
| GET | `/api/v1/agent-templates` | agent factory templates |
| GET | `/api/v1/audit` | audit events |
| GET·POST | `/api/v1/jobs` · `POST /jobs/drain` · `POST /jobs/{jid}/cancel` | background job queue |
| GET | `/api/v1/delegates` · `POST /delegates/{did}/call` | inter-forge delegation |
| POST | `/api/v1/auth/rotate` · `POST /auth/revoke` | token lifecycle |

### Workspaces & products

| Method | Path |
|---|---|
| GET·POST | `/api/v1/workspaces` · GET·PATCH `/workspaces/{wid}` |
| GET·POST | `/api/v1/products` · GET `/products/{pid}` |
| GET | `/products/{pid}/context` — Product Context Package |
| GET | `/products/{pid}/health` — product health center |
| GET | `/products/{pid}/routing` — routing/evidence view |
| GET | `/products/{pid}/budget` — budget state |

All product-scoped collections below live under `/api/v1/products/{pid}/…`.

### Knowledge

| Method | Path | Purpose |
|---|---|---|
| GET·POST | `/documents` | document list / import (content is redacted before persist) |
| POST | `/products/{pid}/documents/from-investigation` | confirmed The Forge `OrchestrationReport/v1` import; idempotent by correlation + content hash, starts as `draft`/`captured` |
| GET | `/documents/search` | backward-compatible indexed document search |
| GET | `/knowledge/search` | bounded body-free search across documents, sources, entities and relations |
| GET | `/products/{pid}/documents/url/preview?url=…&extractor=stdlib|defuddle` | safe URL preview; `defuddle` is optional |
| POST | `/products/{pid}/documents/from-url` | confirmed URL import; optional `extractor` is `stdlib` or `defuddle` |
| POST | `/knowledge/query` | FTS retrieval with chunk citations |
| POST | `/knowledge/extract` | entity/relation extraction |
| GET | `/knowledge-health` | coverage/citation health |
| GET | `/graph` | entity/relation graph |
| GET | `/evidence-graph` | evidence-first graph projection |
| GET | `/impact/{eid}` | impact/lineage for an entity |

URL capture always validates the public URL and downloads bounded HTML before
extraction. `stdlib` is the default, dependency-free extractor. `defuddle`
passes that already-validated HTML to the optional Defuddle CLI over stdin;
set `FORGE_DEFUDDLE_BIN` when the executable is not on `PATH`. It never passes
the remote URL to the optional process and never executes page scripts.

The investigation import is a trust-boundary adapter, not a second
orchestrator: it accepts only a completed, already-redacted
`theforge/OrchestrationReport/v1`, preserves correlation/provenance fields,
indexes a deterministic Markdown projection and refuses secret-shaped payloads.
It does not write the vault. Use the existing Obsidian sync-plan → reviewed
export flow when a human wants to materialize the projection in Obsidian.

### Obsidian interoperability

The stdlib vault adapter scans, imports and exports bounded Markdown without requiring
the Obsidian application or CLI. `GET /api/v1/products/{pid}/documents/obsidian/files`
returns a bounded, body-free Markdown path index for destination/import selection;
it skips hidden Forge/Obsidian internals, symlinks, hardlinks and oversized files.
`validate_canvas_document()` validates the
safe structural subset of JSON Canvas (unique node/edge IDs and existing edge
endpoints). `validate_base_document()` validates the official YAML container
and core sections (`properties`, `formulas`, `filters`, `summaries`, and
`views`), while `serialize_base_document()` emits deterministic `.base` YAML.
Both operations parse/serialize without rendering or executing filters or
formulas; Obsidian remains the execution engine. Product Forge does not claim
to implement a Canvas editor or a Bases formula evaluator.

### Agents (Agent Factory)

| Method | Path |
|---|---|
| GET·POST | `/agents` · GET `/agents/{aid}` |
| PATCH | `/agents/{aid}` |
| POST | `/agents/{aid}/run` — policy-checked, audited |
| GET | `/agents/{aid}/runs` · POST `/agents/{aid}/runs/{rid}/cancel` |
| POST | `/agents/{aid}/eval` — eval suite, persisted score |
| POST | `/agents/{aid}/publish` — **gated**: `tools_allowed` + eval ≥ 0.5 |
| POST | `/agents/{aid}/archive` |

### Analytics (read-only)

| Method | Path | Purpose |
|---|---|---|
| GET·POST | `/sources` · GET `/sources/{rid}` | registered data sources |
| GET·POST | `/data-sources` · GET `/data-sources/{rid}` | connectors |
| GET | `/data-sources/{sid}/schema` | introspected schema |
| POST | `/data-sources/{sid}/verify` | connectivity check (honest result) |
| GET | `/queries` · GET `/queries/{qid}` | saved queries |
| POST | `/queries/validate` | sqlglot read-only verdict |
| POST | `/queries/compile` | spec → SQL |
| POST | `/queries/nl` | natural language → SQL (`via: semantic-catalog` or `deterministic-nl`) |
| POST | `/queries/execute` | run read-only query |
| POST | `/queries/{qid}/cancel` | cancel run |
| GET·POST | `/metrics` · POST `/metrics/resolve` | semantic metric catalog |
| GET·POST | `/apis` · POST `/apis/import` · POST `/apis/{aid}/diff` | API intelligence |

### Dashboards & notebooks

| Method | Path |
|---|---|
| GET·POST | `/dashboards` · GET `/dashboards/{rid}` |
| POST | `/dashboards/{did}/render` — real-data render |
| GET·POST | `/notebooks` · GET `/notebooks/{rid}` · POST `/notebooks/{nid}/blocks` |

### Planning & discovery

| Method | Path |
|---|---|
| GET·POST | `/initiatives` · GET `/initiatives/{rid}` |
| POST | `/initiatives/{iid}/prioritize` — deterministic scoring |
| POST | `/initiatives/{iid}/prd` — grounded PRD |
| GET | `/roadmap` — now/next/later |
| GET·POST | `/decisions` · GET `/decisions/{rid}` · GET `/decisions/{did}/completeness` |
| GET·POST | `/experiments` · GET `/experiments/{rid}` · POST `/experiments/{eid}/conclude` |
| GET·POST | `/meetings` · GET `/meetings/{rid}` · POST `/meetings/{mid}/extract` · POST `/meetings/{mid}/publish` |
| GET·POST | `/workflows` · POST `/workflows/run` |
| POST | `/contracts` · POST `/contracts/{cid}/validate` — data product contracts |

### Product operations

| Method | Path |
|---|---|
| GET | `/reports` · POST `/reports/executive` |
| GET·POST | `/watches` · POST `/watches/{wid}/run` · POST `/watches/run-due` |
| GET | `/alerts` · POST `/alerts/{alid}/{action}` (`ack`/`close`) |
| GET·POST | `/approvals` · POST `/approvals/{apid}/{decision}` |
| POST | `/cloud/inventory` — cloud inventory; `unverified` without credentials |

## Hard rules (enforced server-side)

- **Read-only analytics** — `queries/execute` only runs statements that pass
  `queries/validate`; writes/multi-statements are rejected, never executed.
- **Gated mutations** — agent publish requires `tools_allowed` + eval ≥ 0.5;
  destructive ops require `confirmation` or an approval.
- **Honest cloud** — `cloud/inventory` returns `unverified` absent real
  credentials; never fabricates resource data.
- **Audit** — mutating routes append audit events (`GET /audit`).
