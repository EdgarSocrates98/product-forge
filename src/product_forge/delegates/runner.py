"""Delegate runner — invoke a sibling forge workflow via subprocess+JSON.

Contract: the sibling CLI is called as ``<cli> <workflow> [args...]`` and must
emit one JSON document on stdout (Forge Protocol shape). Product-forge never
imports sibling packages, never passes secrets in env, and reports
unavailable/error honestly — output is redacted before persistence.
"""

from __future__ import annotations

import contextlib
import json
import subprocess
from typing import Any

from ..security import redact
from .catalog import find


def call(cfg: dict[str, Any], store: Any, product_id: str | None,
         delegate_id: str, workflow: str, args: list[str] | None = None,
         timeout_s: int = 60) -> dict[str, Any]:
    """Invoke one declared delegate workflow. Never raises for capability."""
    d = find(cfg, delegate_id)
    if d is None:
        return {"status": "unavailable", "reason": "delegate-not-declared",
                "delegate": delegate_id}
    if workflow not in d["workflows"]:
        return {"status": "refused", "reason": "workflow-not-allowed",
                "delegate": delegate_id, "workflow": workflow,
                "allowed": d["workflows"]}
    if d["status"] != "available":
        return {"status": "unavailable", "reason": "cli-not-found",
                "delegate": delegate_id, "cli": d["cli"]}
    cmd = [d["resolved"], workflow, *(args or [])]
    try:
        proc = subprocess.run(  # noqa: S603 — operator-declared allowlist, not user input
            cmd, capture_output=True, text=True, timeout=timeout_s,
            env={"PATH": "/usr/bin:/bin:/usr/local/bin"}, check=False)
    except subprocess.TimeoutExpired:
        return {"status": "error", "error": f"timeout after {timeout_s}s",
                "delegate": delegate_id, "workflow": workflow}
    except OSError as e:
        return {"status": "unavailable", "reason": "spawn-failed",
                "error": str(e)[:200], "delegate": delegate_id}
    if proc.returncode != 0:
        return {"status": "error",
                "error": (proc.stderr or f"exit {proc.returncode}")[:200],
                "delegate": delegate_id, "workflow": workflow}
    try:
        payload = json.loads(proc.stdout.strip().splitlines()[-1])
    except (json.JSONDecodeError, IndexError):
        return {"status": "error", "error": "non-JSON output from delegate",
                "delegate": delegate_id, "workflow": workflow}
    # audit-safe record of the call (redacted before persistence); an audit
    # failure must never hide the delegate's result
    with contextlib.suppress(Exception):
        from ..domain.models import new_id, utcnow
        store.audit({"id": new_id("aud"), "created_at": utcnow(),
                     "actor": "delegate", "actor_kind": "system",
                     "action": "delegate.call", "resource_type": "delegate",
                     "resource_id": delegate_id, "correlation_id": "",
                     "product_id": product_id, "workflow": workflow,
                     "outcome": "ok"})
    return {"status": "ok", "delegate": delegate_id, "workflow": workflow,
            "result": redact(payload)}
