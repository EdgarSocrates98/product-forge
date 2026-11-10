# forge-obsidian

`forge-obsidian` is the neutral technical distribution for safe Obsidian
interoperability across Forge adapters. Its `src/forge_obsidian` package is the
canonical source; Product Forge embeds that same package in its own wheel
without copying or reimplementing the engine.

The library provides bounded Markdown/Canvas validation, authorized-vault path
safety, body-free scanning, import/export, sync planning, conflict handling,
atomic writes, receipts, rollback and skip operations. It has no dependency on
the Product Forge application runtime and never invokes the Obsidian CLI.

This package is technical infrastructure, not a seventh user-facing Forge.
Adapters must still enforce their own workspace, principal, classification and
approval policy before calling mutating operations.
