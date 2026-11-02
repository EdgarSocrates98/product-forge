# Technology Stack

## Core Sections (Required)

### 1) Runtime Summary

| Area | Value | Evidence |
|------|-------|----------|
| Primary language | Python | `pyproject.toml`, `src/product_forge/` |
| Runtime + version | Python >=3.11; CI 3.11/3.12/3.13 | `pyproject.toml`, `.github/workflows/ci.yml` |
| Package manager | uv in CI; pip-compatible wheel | `.github/workflows/ci.yml`, `pyproject.toml` |
| Module/build system | Hatchling wheel with bundled skills/agents | `pyproject.toml` |

### 2) Production Frameworks and Dependencies

| Dependency | Version | Role in system | Evidence |
|------------|---------|----------------|----------|
| Pydantic | >=2.7,<3 | contracts and validation | `pyproject.toml` |
| Typer | >=0.12 | `productforge` CLI | `pyproject.toml` |
| PyYAML | >=6.0 | configuration/catalog data | `pyproject.toml` |
| FastAPI/Uvicorn | optional >=0.110/0.29 | HTTP API | `pyproject.toml`, `src/product_forge/api/` |
| MCP | optional >=1.9 | MCP server surface | `pyproject.toml`, `.mcp.json` |
| DuckDB/sqlglot | optional | analytics/query execution | `pyproject.toml` |

### 3) Development Toolchain

| Tool | Purpose | Evidence |
|------|---------|----------|
| pytest + pytest-cov | tests and coverage | `pyproject.toml`, `.github/workflows/ci.yml` |
| Ruff | lint | `pyproject.toml`, `.github/workflows/ci.yml` |
| mypy | optional static checking | `pyproject.toml` |

### 4) Key Commands

```bash
uv pip install -p .venv/bin/python -e ".[dev]"
productforge install --yes
python -m pytest -q
python -m ruff check src tests
```

### 5) Environment and Config

- Config sources: `pyproject.toml`, `forge.json`, `.mcp.json`, `.product-forge/`, CLI flags.
- Required env vars: `[TODO]` — no `.env.example` was found by the scan.
- Deployment/runtime constraints: local Python >=3.11; install writes host integration state and uses a vendored installkit.

### 6) Evidence

- `pyproject.toml`
- `forge.json`
- `.github/workflows/ci.yml`
- `docs/codebase/.codebase-scan.txt`
