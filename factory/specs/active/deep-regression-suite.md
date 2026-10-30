---
id: deep-regression-suite
title: Deep regression suite over the full /api/v1 surface
agent: claude
risk: high
grill: completed
verification: python -m pytest tests/ -q && python -m ruff check src tests
---

# Deep regression suite over the full /api/v1 surface

## Context
52 GET + ~55 mutating routes exist (real count from create_app).
`test_contract_sweep.py` now locks the envelope on every GET. Mutating
verbs, id-shaped routes, and failure paths still have smoke-level depth.

## Acceptance Criteria
- [ ] Parameterized contract suite: every /api/v1 route×method emits
      `forge/PortalApi/1` + PF-* errors (401/404/422 paths each)
- [ ] Per-domain negative tests: missing auth, wrong workspace, invalid
      body, expired job, cross-product access denied
- [ ] Mutation round-trips for products/sources/knowledge/agents/queries/
      dashboards/plans: create → read → verify persisted → update → delete
- [ ] Job lifecycle: enqueue → poll → terminal state → invalid transitions
      rejected
- [ ] Coverage floor: pytest-cov ≥80% on `src/product_forge/api` and `engine`
- [ ] CI job `regression` runs the suite; no `|| true`

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
