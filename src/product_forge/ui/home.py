"""Bare-command home for Product Forge."""

from __future__ import annotations

from product_forge.ui.kit import NonInteractive, UIContext
from product_forge.ui.tui import run_tui


def run_home(*, ctx: UIContext | None = None) -> int:
    if ctx is not None and not ctx.interactive:
        raise NonInteractive("Product Forge home requires a TTY")
    return run_tui(ctx=ctx)


__all__ = ["run_home"]
