# Neutral Obsidian interoperability library

`forge_obsidian` is the technical ownership boundary for safe Obsidian
interoperability. It contains the bounded Markdown/Canvas validation,
authorized-vault path checks, body-free scanning, import/export, sync planning,
conflict handling, receipts, rollback and skip operations.

The package has no dependency on the Product Forge application runtime. Its
only non-standard dependency is PyYAML, used for bounded frontmatter and
Canvas decoding. It never invokes the Obsidian application or CLI.

Product Forge keeps `product_forge.knowledge.obsidian` as a compatibility
facade, so existing adapters and integrations keep their import path while
using the canonical implementation. Other Forges should depend on this
technical package through a thin adapter rather than importing Product Forge.

## Public boundary

The stable surface is exported from `forge_obsidian` and includes the typed
protocols (`VaultLocator`, `VaultReader`, `VaultWriter`, `VaultScanner` and
the parser/resolver/projector/planner protocols), `ObsidianVaultError`, the
validators, vault discovery/import/export functions, sync operations and
receipt listing.

All filesystem operations remain bounded by an explicitly authorized vault
root. Traversal, hidden control directories, symlinks/reparse points,
hardlinks, binary files and oversized documents are refused. Scanning returns
metadata only and never reads document bodies.

## Extraction contract

The same canonical source is also packaged by the `forge-obsidian` subproject
(`forge-obsidian/src/forge_obsidian`) in this repository. The standalone wheel/sdist can be published independently
without copying the engine or making another user-facing Forge. Product Forge
continues to ship the namespace in its own wheel so its runtime remains
self-contained. The standalone release is governed by
`.github/workflows/publish-forge-obsidian.yml`: it builds once, verifies
checksums, publishes through PyPI Trusted Publishing/OIDC and installs the
published version in a clean environment. Before adoption by another Forge,
pin the published package version and run its adapter conformance suite
against the Forge's own authorization and receipt stores; until that release
has completed, adapters must keep the Obsidian feature optional.
