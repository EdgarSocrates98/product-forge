# Product Forge — Agent Instructions

Specialist Forge for **product intelligence, analytics intelligence and agentic
workspaces** (PMs/PAs + developers). Engine (API/CLI/MCP) and Portal adapter are
independent surfaces over the same store.

## Commands

```bash
uv pip install -p .venv/bin/python -e ".[dev]"   # dev env
python -m pytest -q                             # tests
python -m ruff check src tests                  # lint (line-length 110)
productforge install --dry-run                  # install plan (installkit)
productforge doctor                             # env diagnostics
productforge mcp serve                          # MCP stdio (14 tools)
```

## Hard rules

- **Honesty-first**: no path reports success without a real execution result.
  Absent capability is a named state (`unverified`, `unavailable:*`, `error`),
  never fabricated data. Cloud inventory without credentials = `unverified`.
- **Deterministic core**: routing, scoring, extraction, validation are
  deterministic — ambiguity becomes `ambiguous`, never a guess. No wall-clock
  or LLM calls inside engine modules.
- **Evidence-first**: answers cite entity ids, rule_ids, run ids, chunk
  citations. `inferred` is never promoted to `observed`.
- **Read-only analytics**: SQL is validated read-only (sqlglot); writes and
  multi-statements are rejected, never executed.
- **Gated mutations**: publish requires `tools_allowed` + eval ≥ 0.5; mutating
  portal ops require confirmation; approval-gated actions need an approval.
- **Envelope contract**: every API response is `forge/PortalApi/1`
  (`schema` + `correlation_id` + `data|error`); errors use typed `PF-*` codes.
- **Vendored byte-parity**: `_forge_portal.py` and `_installkit.py` are
  vendored canonical files — never edit them in-place; fix upstream or wrap.
- **Persisted docs pass through `security.redact`**; credentials never reach
  provider envs or logs.

## Agentic layer (spark-forge-aws pattern)

- `agents/` — coordinator profiles (one per domain: intel, data, planning,
  integration, ops) + `agents/executors/` (pf-extractor → pf-judge →
  pf-verifier → pf-synthesizer), each with `## Não faz` / `## Pressupõe` /
  `## Entrega` contracts. Install ships them to host `agents/` dirs.
- `rules/catalog/` — versioned executable rules (PF-KNOW, PF-AGENT, PF-SQL,
  PF-CLOUD) with `action:` blocks; a `Finding` requires `rule_id` +
  non-empty evidence.
- `skills/pf-*` — 16 domain skills, install-gated by profile.
- `factory/` — Loop Factory assembly line: specs in `inbox/`, built in
  `active/`, accepted in `archive/`. Automate implementation + verification,
  never product decisions. Grill gate before dispatch; human acceptance to archive.
