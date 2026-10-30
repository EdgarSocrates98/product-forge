---
id: inter-forge-delegation
title: Product-forge delegate mechanism for sibling forges
agent: devin
risk: high
grill: completed
verification: ".venv/bin/python -m pytest tests/test_delegates.py -q"
---

# Grill Gate
- Which mechanism? **Own mechanism (option B)** — product-forge calls sibling
  forges directly via subprocess+JSON, not through the-forge control plane.
  Decided by user 2026-10-30.
- Trust model: operator-declared allowlist in config (`delegates` section).
  No auto-discovery of arbitrary CLIs — deterministic, auditable.
- Missing decisions recorded as open questions below; not invented.

## Context
Product-forge is a leaf specialist but the user wants it to consume sibling
forges (data-sentinel inventory → product context, forge-doctor costs →
FinOps). Sibling forges expose `forge/SpecialistAgenticManifest/v1` workflows
over their CLIs (subprocess+JSON = Forge Protocol native).

## Acceptance criteria
- Config `delegates` section: list of {id, cli, workflows allowlist} —
  operator declares which forges product-forge may call.
- `delegates/catalog.py`: status per delegate — available (CLI found via
  shutil.which + manifest workflows declared) or unavailable:cli-not-found.
- `delegates/runner.py`: subprocess+JSON call `cli workflow args`, timeout,
  redact applied to stored output, honest unavailable/error never faked.
- API: `GET /api/v1/delegates` (catalog+status), `POST /delegates/{id}/call`
  (audited, record_usage tool_calls++).
- CLI: `productforge delegates` (list + status).
- tests/test_delegates.py: unavailable state, successful call against a fake
  specialist script, allowlist refusal for undeclared workflow.

## Constraints
- Never import sibling forge packages (Forge Protocol: subprocess+JSON only).
- Secrets never reach delegate env; stored output passes security.redact.
- Workflows not in the delegate's allowlist are refused, never attempted.

## Open questions (not blocking this slice)
- Budget ceiling per delegate call (tokens unavailable for subprocess CLIs).
- Whether delegates appear in agent tools_allowed (deferred — keep manual).
