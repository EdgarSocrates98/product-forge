"""Durable job registry — state lives in the `jobs` table, not memory.

States: queued → running → done | failed | dead_letter | cancelled.
`recover()` on boot re-queues jobs left `running` by a crash — reconciliation,
not pretend-resume. Retry is bounded (`max_attempts` → dead_letter).
Idempotent enqueue: same (kind, idempotency_key) returns the existing job.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

from ..domain.models import new_id, utcnow

MAX_ATTEMPTS = 3


class JobRegistry:
    def __init__(self, store: Any) -> None:
        self.store = store
        self._handlers: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {}

    def register(self, kind: str, handler: Callable[[dict[str, Any]], dict[str, Any]]) -> None:
        self._handlers[kind] = handler

    def _rows(self, where: str = "", params: tuple = (),
              limit: int | None = None) -> list[dict[str, Any]]:
        sql = f"SELECT * FROM jobs {where} ORDER BY created_at"  # noqa: S608 — clauses are internal constants
        if limit:
            sql += f" LIMIT {int(limit)}"
        cur = self.store._conn.execute(sql, params)  # noqa: SLF001
        return [dict(r) for r in cur.fetchall()]

    def enqueue(self, kind: str, payload: dict[str, Any] | None = None,
                product_id: str | None = None,
                idempotency_key: str | None = None) -> dict[str, Any]:
        if idempotency_key:
            existing = self._rows("WHERE idempotency_key=? AND kind=?",
                                  (idempotency_key, kind))
            if existing:
                return existing[0]
        jid = new_id("job")
        now = utcnow()
        self.store._conn.execute(  # noqa: SLF001
            "INSERT INTO jobs(id,kind,product_id,status,payload,idempotency_key,"
            "created_at,updated_at) VALUES(?,?,?,?,?,?,?,?)",
            (jid, kind, product_id, "queued", json.dumps(payload or {}),
             idempotency_key, now, now))
        self.store._conn.commit()  # noqa: SLF001
        return self.get(jid)

    def get(self, jid: str) -> dict[str, Any]:
        rows = self._rows("WHERE id=?", (jid,))
        if not rows:
            from ..errors import NotFoundError
            raise NotFoundError(f"jobs/{jid} not found")
        return rows[0]

    def list(self, status: str | None = None,
             product_id: str | None = None) -> list[dict[str, Any]]:
        where, params = [], []
        if status:
            where.append("status=?")
            params.append(status)
        if product_id:
            where.append("product_id=?")
            params.append(product_id)
        clause = "WHERE " + " AND ".join(where) if where else ""
        return self._rows(clause, tuple(params))

    def _transition(self, jid: str, status: str, **fields: Any) -> dict[str, Any]:
        sets, params = ["status=?", "updated_at=?"], [status, utcnow()]
        for k, v in fields.items():
            sets.append(f"{k}=?")
            params.append(json.dumps(v) if isinstance(v, (dict, list)) else v)
        params.append(jid)
        self.store._conn.execute(  # noqa: SLF001
            f"UPDATE jobs SET {', '.join(sets)} WHERE id=?", tuple(params))  # noqa: S608 — set names internal
        self.store._conn.commit()  # noqa: SLF001
        return self.get(jid)

    def checkpoint(self, jid: str, checkpoint: dict[str, Any]) -> dict[str, Any]:
        return self._transition(jid, "running", checkpoint=checkpoint)

    def cancel(self, jid: str) -> dict[str, Any]:
        return self._transition(jid, "cancelled")

    def recover(self) -> int:
        """On boot: jobs left `running` by a crash go back to queued."""
        cur = self.store._conn.execute(  # noqa: SLF001
            "UPDATE jobs SET status='queued', updated_at=? WHERE status='running'",
            (utcnow(),))
        self.store._conn.commit()  # noqa: SLF001
        return cur.rowcount

    def run_next(self) -> dict[str, Any] | None:
        """Execute the oldest queued job once. Returns terminal job or None."""
        rows = self._rows("WHERE status='queued'", limit=1)
        if not rows:
            return None
        job = rows[0]
        handler = self._handlers.get(job["kind"])
        if handler is None:
            return self._transition(job["id"], "dead_letter",
                                    result={"error": f"no-handler:{job['kind']}"})
        attempt = int(job["attempt"]) + 1
        self._transition(job["id"], "running", attempt=attempt)
        try:
            result = handler(json.loads(job["payload"]))
            return self._transition(job["id"], "done", result=result)
        except Exception as e:  # noqa: BLE001 — failure recorded, job retried or dead-lettered
            status = "queued" if attempt < MAX_ATTEMPTS else "dead_letter"
            return self._transition(job["id"], status,
                                    result={"error": str(e)[:300], "attempt": attempt})
