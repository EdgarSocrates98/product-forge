"""Human-in-the-loop task proposals produced from chat or agent output."""

from __future__ import annotations

import threading
from collections import defaultdict
from typing import Any

from ..domain.models import Task, new_id, utcnow
from ..errors import UnsafeOperationError
from ..store.sqlite import Store

_APPROVAL_LOCKS: defaultdict[str, threading.RLock] = defaultdict(threading.RLock)


def create_proposal(store: Store, product_id: str, tasks: list[dict[str, Any]],
                    *, source: str = "chat", session_id: str = "",
                    idempotency_key: str | None = None) -> dict[str, Any]:
    """Persist a reviewable proposal; no task is created at this stage."""
    if not tasks or any(not str(item.get("title", "")).strip() for item in tasks):
        raise ValueError("at least one task title is required")
    if idempotency_key:
        for existing in store.list("task_proposals", product_id=product_id, limit=500):
            if existing.get("idempotency_key") == idempotency_key:
                return existing
    board = next(iter(store.list("boards", product_id=product_id, limit=1)), None)
    proposal = {
        "id": new_id("tpr"), "schema": "productforge/TaskProposal/v1",
        "product_id": product_id, "board_id": board.get("id") if board else None,
        "source": source, "session_id": session_id,
        "tasks": [dict(item) for item in tasks], "state": "proposed",
        "idempotency_key": idempotency_key, "created_at": utcnow(),
        "updated_at": utcnow(),
    }
    return store.put_doc("task_proposals", proposal, status="proposed")


def approve_proposal(store: Store, proposal_id: str, *, reviewer: str = "api",
                     idempotency_key: str | None = None) -> dict[str, Any]:
    with _APPROVAL_LOCKS[proposal_id]:
        with store.transaction():
            proposal = store.get("task_proposals", proposal_id)
            if proposal.get("state") == "approved":
                return proposal
            if proposal.get("state") != "proposed":
                raise UnsafeOperationError(f"proposal {proposal_id} already {proposal.get('state')}")
            product = store.get("products", proposal["product_id"])
            board = proposal.get("board_id")
            if not board:
                boards = store.list("boards", product_id=product["id"], limit=1)
                if boards:
                    board = boards[0]["id"]
                else:
                    from ..domain.models import Board
                    board = new_id("brd")
                    store.put("boards", Board(id=board, workspace_id=product["workspace_id"],
                                               product_id=product["id"], name=f"{product['name']} board"))
            task_ids: list[str] = []
            for item in proposal["tasks"]:
                task = Task(id=new_id("tsk"), workspace_id=product["workspace_id"],
                            product_id=product["id"], board_id=board,
                            title=str(item["title"]).strip(), description=str(item.get("description", "")),
                            type=item.get("type", "task"), priority=item.get("priority", "medium"),
                            acceptance_criteria=list(item.get("acceptance_criteria") or []),
                            session_refs=[proposal.get("session_id")] if proposal.get("session_id") else [])
                store.put("tasks", task)
                task_ids.append(task.id)
            proposal.update({"state": "approved", "reviewer": reviewer,
                             "approved_at": utcnow(), "task_ids": task_ids,
                             "approval_idempotency_key": idempotency_key,
                             "updated_at": utcnow()})
            return store.put_doc("task_proposals", proposal, status="approved")
