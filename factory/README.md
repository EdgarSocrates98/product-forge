# Loop Factory — product-forge

Assembly line: `specs/inbox` → `specs/active` → `specs/archive`.
Automate implementation and verification — never product decisions.

Specs here encode the deferred roadmap (see `docs/audit/IMPLEMENTATION_GAP_MATRIX.md`):

| spec | risk | verification |
|---|---|---|
| portal-angular-module | medium | forge-portal build+test |
| llm-gateway-integration | high | `pytest -k gateway` |
| postgres-backend | high | `pytest -k store` + pg subset |
| notification-delivery | medium | `pytest -k notify` |
| native-agent-templates | medium | `pytest -k templates` |
| mcp-http-transport | low | `pytest -k mcp` + curl |

Flow: grill the spec (complete `# Grill Gate`) → `loop-factory dispatch --stage` →
implement acceptance criteria → run `verification:` → review → `archive --accepted`
(human decision). If `loop-factory` CLI is absent, the folders and spec format are
the contract — move files manually in the same state order.
