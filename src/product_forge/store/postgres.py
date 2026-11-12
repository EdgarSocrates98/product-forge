"""PostgreSQL JSON-document store compatible with :mod:`store.sqlite`.

The domain deliberately stores canonical documents, so the PostgreSQL
backend keeps the same collection contract while using JSONB and a
GIN-backed full-text index. It is opt-in through ``PRODUCT_FORGE_DATABASE_URL``
or ``PRODUCT_FORGE_DB_BACKEND=postgres`` and never embeds credentials.
"""

from __future__ import annotations

import json
import threading
from collections.abc import Iterable
from contextlib import contextmanager
from typing import Any

from ..domain.models import Entity, new_id, utcnow
from ..errors import NotFoundError
from ..security import redact
from .sqlite import COLLECTIONS


class _CompatConnection:
    """Tiny qmark adapter for the durable job registry's shared SQL seam."""

    def __init__(self, connection: Any) -> None:
        self._connection = connection

    def execute(self, query: str, params: tuple[Any, ...] = ()):
        return self._connection.execute(query.replace("?", "%s"), params)

    def commit(self) -> None:
        self._connection.commit()

    def rollback(self) -> None:
        self._connection.rollback()

    def close(self) -> None:
        self._connection.close()


class PostgresStore:
    """Thread-safe PostgreSQL implementation of the Product Forge store."""

    def __init__(self, dsn: str) -> None:
        if not dsn:
            raise RuntimeError("PostgreSQL backend requires PRODUCT_FORGE_DATABASE_URL")
        try:
            import psycopg
            from psycopg.rows import dict_row
        except ImportError as exc:
            raise RuntimeError("Install productforge[postgres] to use the PostgreSQL backend") from exc
        self._lock = threading.RLock()
        self._tx_depth = 0
        self._psycopg = psycopg
        raw_connection = psycopg.connect(dsn, row_factory=dict_row)
        self._conn = _CompatConnection(raw_connection)
        self._conn.execute("SET application_name = 'productforge'")
        self._conn.execute("SELECT set_config('statement_timeout', '30000', false)")
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS pf_entities (
                collection TEXT NOT NULL,
                id TEXT NOT NULL,
                product_id TEXT,
                workspace_id TEXT,
                status TEXT,
                name TEXT,
                doc JSONB NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (collection, id)
            )
            """
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS pf_entities_product ON pf_entities(collection, product_id)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS pf_entities_workspace ON pf_entities(collection, workspace_id)"
        )
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS pf_chunks (
                id TEXT PRIMARY KEY,
                document_id TEXT NOT NULL,
                product_id TEXT NOT NULL,
                seq INTEGER NOT NULL,
                text TEXT NOT NULL,
                tokens INTEGER NOT NULL DEFAULT 0
            )
            """
        )
        self._conn.execute("CREATE INDEX IF NOT EXISTS pf_chunks_product ON pf_chunks(product_id)")
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY,
                kind TEXT NOT NULL,
                product_id TEXT,
                status TEXT NOT NULL,
                payload TEXT NOT NULL,
                idempotency_key TEXT,
                attempt INTEGER NOT NULL DEFAULT 0,
                checkpoint TEXT,
                result TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                expires_at TEXT
            )
            """
        )
        self._conn.execute("CREATE INDEX IF NOT EXISTS jobs_status ON jobs(status, created_at)")
        self._conn.commit()

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    @contextmanager
    def transaction(self):
        with self._lock:
            self._tx_depth += 1
            try:
                yield self
                if self._tx_depth == 1:
                    self._conn.commit()
            except Exception:
                if self._tx_depth == 1:
                    self._conn.rollback()
                raise
            finally:
                self._tx_depth -= 1

    def migrate(self) -> list[int]:
        return []

    def integrity_check(self) -> bool:
        with self._lock:
            row = self._conn.execute("SELECT 1 AS ok").fetchone()
        return bool(row and row["ok"] == 1)

    def put(self, collection: str, entity: Entity) -> Entity:
        entity.updated_at = utcnow()
        return (
            self.put_doc(
                collection,
                entity.model_dump(mode="json", by_alias=True),
                status=getattr(entity, "status", None),
                name=getattr(entity, "name", None) or getattr(entity, "title", None),
            )
            and entity
        )

    def put_doc(
        self, collection: str, doc: dict[str, Any], *, status: str | None = None, name: str | None = None
    ) -> dict[str, Any]:
        if collection not in COLLECTIONS:
            raise ValueError(f"unknown collection: {collection}")
        doc["updated_at"] = utcnow()
        blob = redact(doc)
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO pf_entities(collection,id,product_id,workspace_id,status,name,doc,updated_at)
                VALUES(%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT(collection,id) DO UPDATE SET
                  product_id=EXCLUDED.product_id, workspace_id=EXCLUDED.workspace_id,
                  status=EXCLUDED.status, name=EXCLUDED.name, doc=EXCLUDED.doc,
                  updated_at=EXCLUDED.updated_at
                """,
                (
                    collection,
                    doc["id"],
                    doc.get("product_id"),
                    doc.get("workspace_id"),
                    status or doc.get("status"),
                    name or doc.get("name"),
                    json.dumps(blob),
                    doc["updated_at"],
                ),
            )
            if self._tx_depth == 0:
                self._conn.commit()
        return doc

    def get(self, collection: str, entity_id: str) -> dict[str, Any]:
        with self._lock:
            row = self._conn.execute(
                "SELECT doc FROM pf_entities WHERE collection=%s AND id=%s",
                (collection, entity_id),
            ).fetchone()
        if not row:
            raise NotFoundError(f"{collection}/{entity_id} not found")
        return row["doc"] if isinstance(row["doc"], dict) else json.loads(row["doc"])

    def delete(self, collection: str, entity_id: str) -> None:
        with self._lock:
            cur = self._conn.execute(
                "DELETE FROM pf_entities WHERE collection=%s AND id=%s",
                (collection, entity_id),
            )
            if self._tx_depth == 0:
                self._conn.commit()
        if cur.rowcount == 0:
            raise NotFoundError(f"{collection}/{entity_id} not found")

    def list(
        self,
        collection: str,
        *,
        product_id: str | None = None,
        workspace_id: str | None = None,
        limit: int = 500,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        clauses = ["collection=%s"]
        params: list[Any] = [collection]
        if product_id:
            clauses.append("product_id=%s")
            params.append(product_id)
        if workspace_id:
            clauses.append("workspace_id=%s")
            params.append(workspace_id)
        params.extend([limit, offset])
        with self._lock:
            rows = self._conn.execute(
                f"SELECT doc FROM pf_entities WHERE {' AND '.join(clauses)} "  # noqa: S608
                "ORDER BY updated_at DESC LIMIT %s OFFSET %s",
                params,
            ).fetchall()
        return [r["doc"] if isinstance(r["doc"], dict) else json.loads(r["doc"]) for r in rows]

    def put_chunks(self, document_id: str, product_id: str, chunks: Iterable[str]) -> int:
        with self._lock:
            self._conn.execute("DELETE FROM pf_chunks WHERE document_id=%s", (document_id,))
            count = 0
            for seq, text in enumerate(chunks):
                self._conn.execute(
                    "INSERT INTO pf_chunks(id,document_id,product_id,seq,text,tokens) "
                    "VALUES(%s,%s,%s,%s,%s,%s)",
                    (new_id("chk"), document_id, product_id, seq, text, max(1, len(text) // 4)),
                )
                count += 1
            self._conn.commit()
        return count

    def list_chunks(self, product_id: str, limit: int = 5000) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT id,document_id,seq,text FROM pf_chunks "
                "WHERE product_id=%s ORDER BY document_id,seq LIMIT %s",
                (product_id, limit),
            ).fetchall()
        return [dict(r) for r in rows]

    def doc_title(self, document_id: str) -> str:
        try:
            return str(self.get("documents", document_id).get("title", document_id))
        except NotFoundError:
            return document_id

    def search_fts(self, product_id: str, query: str, limit: int = 20) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT id, document_id, seq, text AS snip,
                       ts_rank(to_tsvector('simple', text), plainto_tsquery('simple', %s)) AS score
                FROM pf_chunks
                WHERE product_id=%s AND to_tsvector('simple', text) @@ plainto_tsquery('simple', %s)
                ORDER BY score DESC LIMIT %s
                """,
                (query, product_id, query, limit),
            ).fetchall()
        return [dict(r) for r in rows]

    def audit(self, event: dict[str, Any]) -> None:
        self.put_doc("audit_events", redact(event), status=event.get("action"), name=event.get("action"))
