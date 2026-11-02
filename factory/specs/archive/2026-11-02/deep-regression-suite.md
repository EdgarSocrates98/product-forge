---
id: deep-regression-suite
status: archived
closed_at: 2026-11-02
title: Deep regression suite over the full /api/v1 surface
agent: claude
risk: high
grill: completed
verification: uv run pytest tests/ --cov=product_forge.api --cov=product_forge.analytics.engine --cov-fail-under=80 -q && uv run ruff check src tests
---

# Deep regression suite over the full /api/v1 surface

## Context
52 GET + ~55 mutating routes exist (real count from create_app).
`test_contract_sweep.py` now locks the envelope on every GET. Mutating
verbs, id-shaped routes, and failure paths still have smoke-level depth.

## Acceptance Criteria
- [x] Parameterized contract suite: every /api/v1 route×method emits
      `forge/PortalApi/1` + PF-* errors (401/404/422 paths each)
- [x] Per-domain negative tests: missing auth, wrong workspace, invalid
      body, expired job, cross-product access denied
- [x] Mutation round-trips for products/sources/knowledge/agents/queries/
      dashboards/plans: create → read → verify persisted → update → delete
- [x] Job lifecycle: enqueue → poll → terminal state → invalid transitions
      rejected
- [x] Coverage floor: pytest-cov ≥80% on `src/product_forge/api` and
      `src/product_forge/analytics/engine.py`
- [x] CI job `regression` runs the suite; no `|| true`

## Constraints
- No test may weaken an acceptance criterion to pass
- Envelope contract: schema + correlation_id + data|error + PF-* codes
- sqlite backend only for this spec (pg covered by postgres-backend)

## Grill Gate
<!-- decision owner? out of scope? riskiest assumption? smallest version? -->
- Decision owner: Edgar (answered 2026-10). Priority order: this spec first.
- Out of scope: pg backend, OIDC, live providers.
- Riskiest assumption: coverage floor ≥80% may expose unreachable code — record, don't inflate.
- Smallest acceptable version: parametric envelope sweep on all methods + per-domain negatives + round-trips on core entities.

## Verification Evidence
- `117 passed` with API coverage `80.06%` and analytics engine coverage `85%`.
- `ruff check src tests` passes.
- Validation errors now emit `PF-VALIDATION`; missing resources emit `PF-NOT-FOUND`.
- Jobs support expiration (`expired`) and reject transitions from terminal states.
- CI regression job runs the full suite with both coverage targets.
