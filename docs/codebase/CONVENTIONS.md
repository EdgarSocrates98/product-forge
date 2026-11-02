# Coding Conventions

## Core Sections (Required)

### 1) Naming Rules

| Item | Rule | Example | Evidence |
|------|------|---------|----------|
| Files | snake_case Python files | `src/product_forge/api/app.py` | source tree |
| Functions/methods | snake_case | `run_next`, route handlers | `src/`, tests |
| Types/interfaces | PascalCase | Pydantic request/response models | `src/product_forge/api/` |
| Constants/env vars | uppercase constants; env names documented where used | `[TODO]` | `src/`, no env template |

### 2) Formatting and Linting

- Formatter: Ruff formatting is not declared as a separate command; `[TODO]`.
- Linter: Ruff, line length 110, selected E/F/I/B/UP/S/W in `pyproject.toml`.
- Run commands: `python -m ruff check src tests`; `python -m pytest -q`.

### 3) Import and Module Conventions

- Imports are Python module imports; Ruff controls import diagnostics.
- No repository-wide alias policy is declared; `[TODO]`.
- Vendored `_forge_portal.py` and `_installkit.py` are excluded from lint and treated as parity artifacts.

### 4) Error and Logging Conventions

- API errors use structured response envelopes and typed domain errors; regression tests cover validation and not-found behavior.
- Logging/redaction policy: `[TODO]` — inspect runtime logging and provider boundary before claiming completeness.
- Installation generates receipts and a ledger, which is the main audit signal.

### 5) Testing Conventions

- Tests live under `tests/` and use `test_*.py`.
- Mocking uses fixtures and local fake adapters; real external provider coverage is marked as integration territory.
- API/analytics regression gate requires at least 80% in CI (`.github/workflows/ci.yml`).

### 6) Evidence

- `pyproject.toml`
- `.github/workflows/ci.yml`
- `tests/test_core.py`
- `tests/test_regression_methods.py`
