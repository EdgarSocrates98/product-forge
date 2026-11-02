# Testing Patterns

## Core Sections (Required)

### 1) Test Stack and Commands

- Primary test framework: pytest >=8.
- Assertion/mocking tools: pytest fixtures, HTTPX/FastAPI test support; fake provider adapters are used for deterministic paths.
- Commands:

```bash
python -m pytest -q
python -m pytest tests/ --cov=product_forge.api --cov=product_forge.analytics.engine --cov-fail-under=80 -q
python -m ruff check src tests
```

### 2) Test Layout

- Tests are centralized in `tests/` and named `test_*.py`.
- Regression/contract tests are split into cycle/regression files.
- CI has a general matrix and a focused API/analytics regression job.

### 3) Test Scope Matrix

| Scope | Covered? | Typical target | Notes |
|-------|----------|----------------|-------|
| Unit | yes | domain/store/analytics | broad pytest suite |
| Integration | partial | FastAPI/SQLite/MCP | provider and cross-repo path not one mandatory gate |
| E2E | partial | API/Portal compatibility | `[TODO]` for one installed system journey |

### 4) Mocking and Isolation Strategy

- Main approach: local fakes/fixtures and in-process API clients.
- Isolation: temporary state and test database fixtures where defined.
- Common failure mode: a suite can pass while the separately installed Portal/Bridge composition is broken, because the current CI gates are repo-local.

### 5) Coverage and Quality Signals

- Coverage tool: pytest-cov; CI floor 80% for API/analytics regression.
- Last verified local result in this workspace: 117 passed, total 80.59%, Ruff clean (2026-11-02).
- Known gap: no required CI lane currently proves `productforge install` followed by Portal + Bridge + real provider session.

### 6) Evidence

- `pyproject.toml`
- `.github/workflows/ci.yml`
- `tests/`
- `docs/codebase/.codebase-scan.txt`
