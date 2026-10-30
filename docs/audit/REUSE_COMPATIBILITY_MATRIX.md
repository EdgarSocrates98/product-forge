# REUSE_COMPATIBILITY_MATRIX

| Component | Source repo | Reuse mode | Compatibility risk | Status |
|---|---|---|---|---|
| `_forge_portal.py` server | forge-portal/portal_core | vendored byte-parity | must re-vendor on upstream change | ✅ vendored (md5 parity verified) |
| PortalAdapter + Operation | forge-portal contract | subclass | stable contract `forge/PortalApi/1` | ✅ implemented |
| Envelope `forge/PortalApi/1` | forge-portal api.models.ts | implement | additive-only changes allowed | ✅ implemented |
| Specialist manifest | forge.agentic.json schema | implement | `forge/SpecialistAgenticManifest/v1` | ✅ implemented |
| forge.json ops descriptor | data-sentinel pattern | implement | keys verified against data-sentinel | ✅ implemented |
| Token store / redact / safe_path | data-sentinel api layer | adapted to `security.py` | none (our impl, same invariants) | ✅ implemented |
| FTS5 chunk+search | data-sentinel persistence | adapted | sqlite3 stdlib | ✅ implemented |
| Forge Protocol invocation | the-forge providers | CLI JSON subprocess | commands must be JSON-clean stdout | ✅ CLI emits JSON |
| the-forge adapter (adapters/productforge) | the-forge | new distribution | feature-freeze — needs ADR there | 🔲 planned Cycle 11 |
| Graph Studio export | the-forge graph contracts | emit ForgeKnowledge docs | contract mapping needed | 🔲 Cycle 3 |
| Angular module in forge-portal | forge-portal app | lazy-loaded route | portal is shared repo — PR needed | 🔲 Cycle 2 alt. |
| spark-forge-aws/azure signals | spark-forges | provider calls via the-forge | needs the-forge routing | 🔲 Cycle 8 |
| api-forge contract analysis | api-forge | provider call | OpenAPI/AsyncAPI tooling exists | 🔲 Cycle 9 |
| forge-lens tracing | forge-lens | emit execution events | `forge/PortalEvent/1` already wired | 🔲 Cycle 10+ |

## Independence invariants (preserved)

- Engine works fully without Portal: CLI + API + MCP are self-contained.
- Portal works with any forge adapter; Product Forge is one provider.
- No imports from other forge packages in `src/product_forge` (verified: only stdlib + declared deps).
