# Forge Context — Routing

Regenerated deterministically from `.forge/context/registry.json`
(`forge/context-registry/v1`). Managed document — manual edits are lost.

## Domains

| Domain | Forge | State | Scope |
|---|---|---|---|
| agentic-workspaces | product-forge | available | project |
| analytics | product-forge | available | project |
| dashboards | product-forge | available | project |
| knowledge-management | product-forge | available | project |
| product-intelligence | product-forge | available | project |

## Ambiguity

_No domain is claimed by more than one forge._

## Forges

### product-forge — Product Forge 0.2.3

- state: available · scope: project · profile: recommended
- hosts: claude, codex, copilot, devin
- domains: agentic-workspaces, analytics, dashboards, knowledge-management, product-intelligence
- capabilities: agents(on), evals(on), knowledge(on), protocols(on), rules(on), skills(on)
- cli: `productforge`
- mcp: `product-forge`
- manifest: `capabilities/product-forge.json`

## Contract

- Capability manifest: `forge/context/v1` — `.forge/context/capabilities/<forge-id>.json`
- Workspace registry: `forge/context-registry/v1` — `.forge/context/registry.json`
- Ownership: shared docs regenerate from per-forge entries; a forge
  never deletes another forge's resources.
