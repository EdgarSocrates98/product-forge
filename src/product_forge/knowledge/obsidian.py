"""Compatibility facade for the neutral :mod:`forge_obsidian` library.

The public import path is retained for Product Forge integrations.  The
implementation lives in the dependency-light technical package so other
Forges can consume the same vault safety and sync behavior without importing
the Product Forge application runtime.
"""

from __future__ import annotations

import sys
import types

from forge_obsidian import obsidian as _implementation


class _CompatibilityModule(types.ModuleType):
    """Forward reads and test fault-injection writes to the canonical module."""

    def __getattribute__(self, name: str):
        if not name.startswith("__") and name not in {"_implementation", "_module"}:
            implementation = object.__getattribute__(self, "_implementation")
            if name in vars(implementation):
                return getattr(implementation, name)
        return super().__getattribute__(name)

    def __getattr__(self, name: str):
        return getattr(_implementation, name)

    def __setattr__(self, name: str, value: object) -> None:
        if name in vars(_implementation):
            setattr(_implementation, name, value)
            return
        super().__setattr__(name, value)

    def __delattr__(self, name: str) -> None:
        if name in vars(_implementation):
            delattr(_implementation, name)
            return
        super().__delattr__(name)


_module = sys.modules[__name__]
_module.__class__ = _CompatibilityModule
_module.__doc__ = __doc__
# Populate the facade dictionary so tools such as pytest's monkeypatch can
# observe the original private hooks before forwarding a replacement.  The
# values are intentionally references only; writes still go to the canonical
# module through ``_CompatibilityModule.__setattr__``.
for _name, _value in vars(_implementation).items():
    if not _name.startswith("__"):
        _module.__dict__.setdefault(_name, _value)
