# Product Forge — agent rules (Claude mirror)

Same hard rules as AGENTS.md — kept in sync manually (edit both).

- Honesty-first: no success without a real execution result; `unverified`/
  `unavailable:*` are named states, not errors to hide.
- Deterministic core: ambiguity → `ambiguous`; no LLM/wall-clock in engines.
- Evidence-first: cite entity ids, rule_ids, run ids, chunk citations.
- Read-only analytics; gated mutations (publish gate, confirm, approvals).
- Envelope `forge/PortalApi/1` + typed `PF-*` errors on every response.
- Vendored `_forge_portal.py`/`_installkit.py`: byte-parity, never edit.
- Agentic layer: `agents/` profiles, `rules/catalog/`, `skills/pf-*`,
  `factory/` loop (inbox → active → archive; human decides).

Commands: `python -m pytest -q` · `python -m ruff check src tests` ·
`productforge install --dry-run` · `productforge doctor`.

<!-- forge:ecosystem:begin -->
## Forge Ecosystem

Forge specialists are installed here. The agent contract is
`AGENTS.md`; the operating protocol is `AGENT_PROTOCOL.md`; the
registry is `.forge/context/registry.json` and routing is
`.forge/context/ROUTING.md`.

@AGENTS.md

Managed block — regenerated on install/repair; never overrides
system, developer or host policies.
<!-- forge:ecosystem:end -->
