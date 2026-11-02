# Product Forge ecosystem baseline — 2026-11-02

| Repository | HEAD | Current evidence | Classification |
|---|---|---|---|
| Product Forge | `b902a3b` | 122 tests, Ruff clean; managed PostgreSQL and install/runtime paths present | corrected and tested locally |
| Forge Agent Bridge | `24b6b7e` | 108 tests, Ruff clean; real adapter harness merged; Devin/Copilot real smoke | corrected and tested locally; Claude external block remains |
| Forge Portal | `b891b64` | 579 tests and production build; 21-route browser smoke previously passed | corrected and tested locally; gateway integration remains incomplete |

## Confirmed gaps against the ecosystem prompt

- Product Forge currently serves a legacy local HTML portal; Angular is a
  separate canonical surface in Forge Portal and is not yet the installed
  runtime's same-origin bundle.
- Angular API configuration still exposes an advanced override path; the
  default was changed to same-origin and persistent localStorage token use was
  removed, but a gateway is required to make the default operational in the
  installed composition.
- Boards currently render roadmap initiatives; the full Task/Column/Comment/
  Activity domain and drag/drop persistence are not yet complete.
- OIDC/PKCE and full multi-tenant authorization remain open; local bearer mode
  is still the supported installed mode.
- Claude remains blocked by external account/API/AWS credentials. The harness
  reports this honestly; it is not a code failure.

## Evidence

- Product Forge: `uv run ruff check src tests && uv run pytest -q` → 122 passed.
- Agent Bridge: `uv run ruff check src tests && uv run pytest -q` → 108 passed.
- Forge Portal: `npm test -- --watch=false` → 579 passed.
