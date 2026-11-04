# Workspace context discovery

Product Forge Portal exposes a local-first `productforge/WorkspaceDiscovery/v1`
surface for finding product context in the workspace where the Portal was
launched.

## Read flow

1. `GET /api/v1/workspace/discovery` returns bounded metadata for projects,
   repositories and eligible `prd`, `brief` and `knowledge` files.
2. `GET /api/v1/workspace/discovery/preview?path=...` reads one selected file
   only after path, symlink and sensitive-file checks.
3. The Chat Studio shows this inventory and keeps import explicit.

## Import flow

`POST /api/v1/products/{product_id}/documents/from-workspace` with
`{"confirm":"import","path":"repo/docs/brief.md"}` imports one selected
file into the product knowledge index. The operation is idempotent for the
same path and content hash and stores source provenance in document metadata.

Discovery does not traverse `.git`, dependency/build/cache directories,
symlinks or reparse points. Credential-like files (`.env*`, keys, certificates,
tokens and secrets) are refused. The default result is metadata-only; source
content is never returned by the inventory endpoint.

The launch directory is the default boundary. `FORGE_WORKSPACE_ROOT` may be
used by a controlled local installation to select an explicit workspace root.
