# Codebase Structure

## Core Sections (Required)

### 1) Top-Level Map

| Path | Purpose | Evidence |
|------|---------|----------|
| `src/product_forge/` | Python package, CLI, API, analytics, jobs, storage | scan tree; `pyproject.toml` |
| `src/product_forge/portal/` and `portal_assets/` | Product Forge PM/PA portal adapter, runtime and packaged static UI | `src/product_forge/portal/runtime.py`, `pyproject.toml` |
| `tests/` | unit, API, regression and contract tests | `pyproject.toml`, scan tree |
| `.agents/`, `.devin/` | bundled skills and agent profiles | scan tree; wheel force-include |
| `factory/` | Loop Factory specs, prompts, reviews | scan tree; `.loop/NEXT.md` |
| `.product-forge/` | install ledger, receipts and backups | scan tree; `forge.json` |
| `schemas/`, `knowledge/`, `rules/` | schemas and product/agent knowledge assets | `pyproject.toml` sdist include |

### 2) Entry Points

- Main runtime entry: `product_forge.cli:app` exposed as `productforge`.
- Secondary entry points: HTTP API under `src/product_forge/api/`; MCP command is `productforge mcp serve`; portal compatibility is vendored in `src/product_forge/_forge_portal.py`.
- Install entry: `productforge install [--yes]`, described in `README.md` and `forge.json`.
- Portal entry: `productforge portal`, which serves the packaged Product Forge UI and manages the local Bridge process (`src/product_forge/portal/runtime.py`).

### 3) Module Boundaries

| Boundary | What belongs here | What must not be here |
|----------|-------------------|------------------------|
| CLI | user-facing orchestration and flags | duplicated domain persistence |
| API | HTTP envelopes, validation, resource routes | host installation side effects outside explicit commands |
| jobs/store | lifecycle and persistence | UI-specific state |
| skills/agents | distributable AI instructions | runtime secrets |
| `.product-forge` | generated installation state | source-of-truth code |

### 4) Naming and Organization Rules

- Python modules use `snake_case`; tests use `tests/test_*.py`.
- Organization is primarily by technical capability (`api`, `analytics`, `jobs`, `store`) with domain entities represented inside those modules.
- Vendored files are explicitly excluded from Ruff in `pyproject.toml` and must not be edited directly.

### 5) Evidence

- `pyproject.toml`
- `forge.json`
- `README.md`
- `.product-forge/components.json`
