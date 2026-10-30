"""`productforge install` — guided wizard + flag path.

Bare `productforge install` on a TTY runs the shared wizard (scope →
install profile → execution profile → components → hosts → real dry-run
plan → confirm → apply → doctor) — the same UX contract as
`sparkforge-aws install`. With flags the command stays non-interactive
JSON for CI and scripts.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from ..install import lifecycle


def _tty() -> bool:
    return sys.stdin.isatty() and sys.stdout.isatty()


def _hosts_tuple(host: str | None) -> tuple[str, ...]:
    """Wizard/flag contract: 'all' | csv | 'none' → hosts tuple."""
    if host in (None, "all"):
        return ("all",)
    if host in ("none", ""):
        return ()
    return tuple(h.strip() for h in host.split(",") if h.strip())


def run_guided_install() -> int:
    """Run the shared install wizard against the real lifecycle.

    The wizard's ``install_fn`` contract is keyword-based
    (``host``/``scope``/``profile``/``gateway_profile``/``components``/
    ``dry_run``/``yes``); this adapter maps it onto
    ``lifecycle.install`` without inspecting signatures.
    """
    from ..ui.kit import UIContext
    from ..ui.wizard import run_wizard

    def _install(**kw: Any) -> dict[str, Any]:
        return lifecycle.install(
            scope=kw.get("scope", "project"),
            profile=kw.get("profile", "recommended"),
            hosts=_hosts_tuple(kw.get("host")),
            components=kw.get("components"),
            gateway_profile=kw.get("gateway_profile"),
            dry_run=bool(kw.get("dry_run")),
            yes=bool(kw.get("yes")),
        )

    def _doctor(**kw: Any) -> dict[str, Any]:
        return lifecycle.doctor(scope=kw.get("scope", "project"))

    return run_wizard(
        forge_name="product-forge",
        install_fn=_install,
        doctor_fn=_doctor,
        ctx=UIContext.detect(),
    )


def run_flag_install(*, scope: str, profile: str, host: str,
                     root: str | None, components: str | None,
                     gateway_profile: str | None,
                     dry_run: bool, yes: bool) -> dict[str, Any]:
    """Non-interactive flag path — returns the receipt doc."""
    comps = (tuple(c.strip() for c in components.split(",") if c.strip())
             if components else None)
    return lifecycle.install(
        scope=scope, profile=profile, hosts=_hosts_tuple(host),
        root=Path(root) if root else None, components=comps,
        gateway_profile=gateway_profile, dry_run=dry_run, yes=yes)


def guided_install_available() -> bool:
    """Bare `install` may route to the wizard only on a real TTY."""
    return _tty()
