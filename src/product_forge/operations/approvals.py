"""Approvals — gate sensitive actions behind human review."""

from __future__ import annotations

from typing import Any

from ..domain.models import new_id, utcnow
from ..errors import UnsafeOperationError
from ..store.sqlite import Store

GATED_ACTIONS = {"agent.publish", "source.register-remote", "watch.activate",
                 "report.distribute", "contract.breaking-ack"}


def request_approval(store: Store, product_id: str, action: str,
                     payload: dict[str, Any], requester: str = "api") -> dict[str, Any]:
    rec = {"id": new_id("apr"), "schema": "productforge/Approval/v1",
           "product_id": product_id, "action": action, "payload": payload,
           "requester": requester, "state": "pending",
           "created_at": utcnow(), "updated_at": utcnow()}
    return store.put_doc("approvals", rec, status="pending")


def decide(store: Store, approval_id: str, approve: bool,
           reviewer: str = "api") -> dict[str, Any]:
    rec = store.get("approvals", approval_id)
    if rec["state"] != "pending":
        raise UnsafeOperationError(f"approval {approval_id} already {rec['state']}")
    rec["state"] = "approved" if approve else "rejected"
    rec["reviewer"] = reviewer
    rec["reviewed_at"] = utcnow()
    return store.put_doc("approvals", rec, status=rec["state"])


def check_gate(store: Store, product_id: str, action: str,
               resource_id: str) -> dict[str, Any]:
    """Look up the latest approval for (action, resource)."""
    ap = [a for a in store.list("approvals", product_id=product_id, limit=200)
          if a.get("action") == action
          and a.get("payload", {}).get("resource_id") == resource_id]
    if not ap:
        return {"gated": action in GATED_ACTIONS, "approved": False, "approval": None}
    latest = ap[0]
    return {"gated": action in GATED_ACTIONS,
            "approved": latest["state"] == "approved",
            "approval": {"id": latest["id"], "state": latest["state"]}}
