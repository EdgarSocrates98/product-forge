# Codebase Concerns

## Core Sections (Required)

### 1) Top Risks (Prioritized)

| Severity | Concern | Evidence | Impact | Suggested action |
|----------|---------|----------|--------|------------------|
| high | No single composition owner for Portal + Product Forge + Bridge | `README.md`, Bridge `README.md`, Portal `README.md` | non-technical users must understand boot order and tokens | make `productforge install` own manifest, processes, health and browser launch |
| high | Cross-repo contract is tested mostly in isolation | `.github/workflows/ci.yml` in each repo | regressions can survive until manual integration | add installed-system E2E harness |
| high | Real provider validation is not the default release gate | Product Forge test config; Bridge live homologation docs | chat may work with fake but fail with Claude/Codex/Devin | nightly credentialed lane with redaction and explicit provider matrix |
| medium | Vendored Portal/installkit parity introduces drift risk | `pyproject.toml`, `_forge_portal.py`, `_installkit.py` | fixes land in one repo and silently lag elsewhere | generate/check compatibility artifact in one release workflow |
| medium | Installation has many choices before first value | `README.md` install profile/scope/host list | cognitive load for non-technical users | sensible recommended defaults, advanced mode later |
| high | The first portal slice is now packaged and launchable, but chat actions are still capability/status surfaces rather than a complete provider conversation UI | `src/product_forge/portal_assets/`, `src/product_forge/portal/adapter.py` | users can see hosts before the full session UX is complete | implement typed chat session proxy + installed-system E2E before calling portal complete |

### 2) Technical Debt

| Debt item | Why it exists | Where | Risk if ignored | Suggested fix |
|-----------|---------------|-------|-----------------|---------------|
| duplicated launch/config ownership | repos evolved independently | all three READMEs/CLI surfaces | startup and auth drift | one local gateway/composition manifest |
| separate user-visible concepts for chat/board/product | different contracts/surfaces | Portal/Product Forge docs | fragmented mental model | one workspace navigation and one domain API |
| optional integration paths can be skipped | extras and adapters are modular | `pyproject.toml`, Bridge providers | false confidence | explicit capability state + integration matrix in doctor/UI |

### 3) Security Concerns

| Risk | OWASP category | Evidence | Current mitigation | Gap |
|------|-----------------|----------|--------------------|-----|
| local service token/config drift | A07 | Bridge pairing docs; `.mcp.json` | bearer/pairing and local binding | unified rotation and ownership under Product Forge |
| provider secrets crossing logs/artifacts | A09 | Bridge audit/evidence paths | audit and redaction claims | prove redaction in system E2E |
| install writes host files | A08 | install ledger/receipts | plan/apply/doctor | clear rollback and user-facing recovery |

### 4) Performance and Scaling Concerns

| Concern | Evidence | Current symptom | Scaling risk | Suggested improvement |
|---------|----------|-----------------|-------------|-----------------------|
| multiple local servers/processes | three repo READMEs | startup/health coordination overhead | port conflicts and stale processes | one supervisor and gateway |
| replay/event history across boundaries | Bridge contracts and Portal event UI | duplicated buffering/translation | memory and ordering bugs | one event envelope/correlation ID |

### 5) Fragile/High-Churn Areas

| Area | Why fragile | Churn signal | Safe change strategy |
|------|-------------|--------------|----------------------|
| Bridge `local_bridge.py`/contracts | provider, SSE, auth and diagnostics converge here | Bridge recent history lists high churn | contract tests first, additive changes |
| Product Forge API/jobs/store | many resource mutations and lifecycle rules | current active deep-regression spec | preserve envelopes, expand integration tests |
| Portal vendor/build path | Angular + Python server + vendoring | Portal CI has multiple parity gates | release artifact check across repos |

### 6) `[ASK USER]` Questions

1. [ASK USER] Should the first-run default be a fully local “recommended” stack with no cloud accounts, or should it request a provider key during installation?
2. [ASK USER] Is Product Forge allowed to manage the Bridge process lifecycle and local token, or must Bridge remain independently operable?
3. [ASK USER] For the first production milestone, which real provider is the release blocker: Codex, Claude, Devin, or all three?

### 7) Evidence

- `README.md`, `.github/workflows/ci.yml`, `forge.json`, `.mcp.json`
- Bridge `README.md`, `src/forge_agent_bridge/contracts.py`
- Portal `README.md`, `scripts/vendor.py`
- `docs/codebase/.codebase-scan.txt`
