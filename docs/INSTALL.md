# Product Forge — install guide

Two layers, one engine. **Bootstrap** gets the `productforge` CLI onto your
machine (wheel → venv → launcher). **Lifecycle install** places the Forge's
assets into your scope (skills, agents, MCP registration, bundles). Both use
the same vendored installkit spark-forge-aws uses — ledger-tracked
ownership, drift detection, honest plans.

## 1. Bootstrap — get the CLI

```bash
./install.sh          # POSIX (Linux/macOS) — wheel install into ~/.forge/installs/product-forge
./install.windows.sh  # Windows Git Bash route
./install.ps1         # Windows PowerShell route
```

All three are thin adapters over `scripts/forge_bootstrap.py` (driven by
`forge.json`): detect Python ≥3.11 → build wheel → create isolated venv →
write launcher → smoke test → register. `--dry-run` prints the JSON plan
with zero writes. After install, open a new shell or `source
~/.config/forjas/env.sh`.

Development flow instead:

```bash
uv venv .venv && uv pip install -p .venv/bin/python -e ".[dev]"
# or: pip install -e ".[api,mcp,analytics]"
```

## 2. `productforge install` — lifecycle

### Guided (bare command on a TTY)

```bash
productforge install
```

Opens the wizard — same contract as `sparkforge-aws install`:

1. **Scope** — `project` | `workspace` | `user`
2. **Install profile** — `minimal` | `recommended` | `full`
3. **Execution profile** (context gateway) — `economy` | `balanced` | `deep`
4. **Components** — `skills`, `agents`, `mcp`, `tui`, `graph-studio` (multi)
5. **Hosts** — `claude`, `devin`, `codex`, `copilot` | `all` | `none`
6. **Plan review** — real dry-run plan → confirm → apply → doctor

### Flag path (CI / scripts — always non-interactive JSON)

```bash
productforge install --yes \
  --scope project --profile recommended \
  --host claude,devin --components skills,agents,mcp \
  --gateway-profile balanced
productforge install --dry-run          # plan only, zero writes
productforge install --host none --yes  # runtime home only, no host writes
```

## What lands where

| Selection | Destination |
|---|---|
| `skills` component | `skills/pf-*` (16 domain skills) → each host's skills dir (`.claude/skills/`, `.devin/skills/`, `.agents/skills/`, `.codex/…`) |
| `agents` component | `agents/*.md` coordinators + `agents/executors/pf-*` → host agents dirs |
| `mcp` component | `.mcp.json` → `product-forge` server entry (`productforge mcp serve`) |
| `graph-studio` | graph studio assets flag in `components.json` |
| `tui` | TUI assets flag |
| marker block | `<!-- product-forge:managed -->` section in `AGENTS.md`/`CLAUDE.md` |
| content bundles | `rules/catalog/`, `evals/`, `knowledge/` → `<state_dir>/bundle/` (self-contained; code packages never bundled, `.pyc`/`__pycache__` excluded) |
| ledger | `<state_dir>/ledger.json` — every owned write tracked for uninstall/repair/drift |
| selection | `<state_dir>/components.json` — `asset_kinds`, `gateway_profile`, `profile` |
| app home | `~/.productforge/` — config (`gateway_profile` persisted), db, API token |

### Scopes

| Scope | Root | State dir |
|---|---|---|
| `project` | VCS root (or `--root`) | `.product-forge/` |
| `workspace` | workspace dir (or `--root`) | `.product-forge/` |
| `user` | `~` | `.product-forge/` |

### Profiles

- `minimal` — marker + MCP only (no skills).
- `recommended` — skills + agents + MCP.
- `full` — everything including `tui`/`graph-studio` assets.

### Execution profile (`--gateway-profile`)

Context gateway budgets: `economy` (8 caps / ~6KB), `balanced` (16 / ~16KB),
`deep` (32 / ~30KB). Persisted in `components.json` and app config.

## Lifecycle verbs

```bash
productforge status                 # installed state + drift
productforge repair                 # restore owned files to ledger state
productforge update --yes           # re-apply current assets (upgrades)
productforge uninstall              # removes only ledger-owned files
productforge doctor                 # env diagnostics (python, deps, home)
```

Uninstall removes **only files the ledger owns** — your edits outside marker
blocks and unmanaged paths survive.

## Troubleshooting

| Symptom | Check |
|---|---|
| wizard doesn't open | not a TTY → use flags; or pass `--yes` |
| `E-PROFILE` error | invalid `--profile`/`--gateway-profile` — see enums above |
| skills missing in host | `--host` didn't include it, or profile `minimal` |
| drift detected | `productforge repair` restores ledger state |
| bootstrap refuses | JSON report names the stage (`E-*` code) — fix and re-run |
