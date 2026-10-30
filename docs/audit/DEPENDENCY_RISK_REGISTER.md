# DEPENDENCY_RISK_REGISTER

| Dependency | Scope | Risk | Mitigation |
|---|---|---|---|
| pydantic ≥2.7 | core | low — ubiquitous, stable v2 API | pinned range <3 |
| typer ≥0.12 | core | low | CLI only |
| pyyaml | core | low | config parsing |
| fastapi + uvicorn | extra `api` | medium — heavy for a forge | isolated extra; core runs without |
| mcp ≥1.9 | extra `mcp` | medium — protocol churn | stdio fallback implemented in server.py (minimal JSON-RPC works without the sdk) |
| sqlglot ≥25 | extra `analytics` | low-medium | dialect validation only; parser swapped if needed |
| duckdb ≥1.0 | extra `analytics` | medium | optional local execution engine; sources still work via remote connectors |
| boto3 | extra `aws` | high surface | optional; credentials never in config (secret refs) |
| azure-identity/monitor | extra `azure` | high surface | optional extra |
| pypdf/python-docx/openpyxl | extra `docs` | medium | optional parsers; text/markdown work without |

## Policy

- Core runtime: pydantic + typer + pyyaml only. Everything else behind extras (ecosystem pattern).
- No heavy dep without justification in this register.
- Secrets: never stored — `locator` fields hold paths/hosts; credentials via OS env or future secret-store refs.
- Supply chain: versions pinned with floor+ceiling; `uv pip install` in `.venv` per repo convention.
