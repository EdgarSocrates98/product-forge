"""SQLite persistence — stdlib, schema-versioned, append-only audit.

Entity rows are stored as canonical JSON keyed by (collection, id).
Collections map 1:1 to domain entities. Audit events are never updated.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from ..domain.models import Entity, utcnow
from ..errors import NotFoundError
from ..security import redact

SCHEMA_VERSION = 1

COLLECTIONS = (
    "workspaces",
    "products",
    "knowledge_sources",
    "documents",
    "entities",
    "relations",
    "agents",
    "data_sources",
    "query_runs",
    "dashboards",
    "initiatives",
    "decisions",
    "agent_runs",
    "api_specs",
    "contracts",
    "workflow_runs",
    "budget_ledger",
    "watches",
    "alerts",
    "reports",
    "approvals",
    "audit_events",
)

_DDL = """
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS entities (
    collection TEXT NOT NULL,
    id        TEXT NOT NULL,
    product_id TEXT,
    workspace_id TEXT,
    status    TEXT,
    name      TEXT,
    doc       TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (collection, id)
);
CREATE INDEX IF NOT EXISTS idx_entities_product ON entities(collection, product_id);
CREATE INDEX IF NOT EXISTS idx_entities_ws ON entities(collection, workspace_id);
CREATE TABLE IF NOT EXISTS chunks (
    id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL,
    product_id TEXT NOT NULL,
    seq INTEGER NOT NULL,
    text TEXT NOT NULL,
    tokens INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_chunks_doc ON chunks(document_id);
CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
    text, content='chunks', content_rowid='rowid', tokenize='unicode61'
);
CREATE TRIGGER IF NOT EXISTS chunks_ai AFTER INSERT ON chunks BEGIN
    INSERT INTO chunks_fts(rowid, text) VALUES (new.rowid, new.text);
END;
CREATE TRIGGER IF NOT EXISTS chunks_ad AFTER DELETE ON chunks BEGIN
    INSERT INTO chunks_fts(chunks_fts, rowid, text) VALUES('delete', old.rowid, old.text);
END;
"""


class Store:
    """Thread-safe JSON-document store over SQLite."""

    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(str(path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_DDL)
        self._conn.execute(
            "INSERT OR REPLACE INTO meta(key, value) VALUES('schema_version', ?)",
            (str(SCHEMA_VERSION),),
        )
        self._conn.commit()

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    # -- generic CRUD -----------------------------------------------------

    def put(self, collection: str, entity: Entity) -> Entity:
        if collection not in COLLECTIONS:
            raise ValueError(f"unknown collection: {collection}")
        entity.updated_at = utcnow()
        doc = json.dumps(redact(entity.model_dump(mode="json", by_alias=True)), ensure_ascii=False)
        with self._lock:
            self._conn.execute(
                "INSERT OR REPLACE INTO entities"
                "(collection,id,product_id,workspace_id,status,name,doc,updated_at)"
                " VALUES(?,?,?,?,?,?,?,?)",
                (
                    collection,
                    entity.id,
                    getattr(entity, "product_id", None),
                    getattr(entity, "workspace_id", None),
                    getattr(entity, "status", None) or None,
                    getattr(entity, "name", None) or getattr(entity, "title", None),
                    doc,
                    entity.updated_at,
                ),
            )
            self._conn.commit()
        return entity

    def put_doc(self, collection: str, doc: dict[str, Any], *,
                status: str | None = None, name: str | None = None) -> dict[str, Any]:
        """Persist a raw dict document (non-pydantic, e.g. run records)."""
        if collection not in COLLECTIONS:
            raise ValueError(f"unknown collection: {collection}")
        doc["updated_at"] = utcnow()
        blob = json.dumps(redact(doc), ensure_ascii=False)
        with self._lock:
            self._conn.execute(
                "INSERT OR REPLACE INTO entities"
                "(collection,id,product_id,workspace_id,status,name,doc,updated_at)"
                " VALUES(?,?,?,?,?,?,?,?)",
                (collection, doc["id"], doc.get("product_id"), doc.get("workspace_id"),
                 status or doc.get("status"), name or doc.get("name"),
                 blob, doc["updated_at"]),
            )
            self._conn.commit()
        return doc

    def get(self, collection: str, entity_id: str) -> dict[str, Any]:
        with self._lock:
            row = self._conn.execute(
                "SELECT doc FROM entities WHERE collection=? AND id=?", (collection, entity_id)
            ).fetchone()
        if not row:
            raise NotFoundError(f"{collection}/{entity_id} not found")
        return json.loads(row["doc"])

    def delete(self, collection: str, entity_id: str) -> None:
        with self._lock:
            cur = self._conn.execute(
                "DELETE FROM entities WHERE collection=? AND id=?", (collection, entity_id)
            )
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
        q = "SELECT doc FROM entities WHERE collection=?"
        params: list[Any] = [collection]
        if product_id:
            q += " AND product_id=?"
            params.append(product_id)
        if workspace_id:
            q += " AND workspace_id=?"
            params.append(workspace_id)
        q += " ORDER BY updated_at DESC LIMIT ? OFFSET ?"
        params += [limit, offset]
        with self._lock:
            rows = self._conn.execute(q, params).fetchall()
        return [json.loads(r["doc"]) for r in rows]

    # -- chunks + FTS -----------------------------------------------------

    def put_chunks(self, document_id: str, product_id: str, chunks: Iterable[str]) -> int:
        from ..domain.models import new_id

        n = 0
        with self._lock:
            self._conn.execute("DELETE FROM chunks WHERE document_id=?", (document_id,))
            for seq, text in enumerate(chunks):
                self._conn.execute(
                    "INSERT INTO chunks(id,document_id,product_id,seq,text,tokens) VALUES(?,?,?,?,?,?)",
                    (new_id("chk"), document_id, product_id, seq, text, max(1, len(text) // 4)),
                )
                n += 1
            self._conn.commit()
        return n

    def list_chunks(self, product_id: str, limit: int = 5000) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT id, document_id, seq, text FROM chunks WHERE product_id=?"
                " ORDER BY document_id, seq LIMIT ?",
                (product_id, limit),
            ).fetchall()
        return [dict(r) for r in rows]

    def doc_title(self, document_id: str) -> str:
        with self._lock:
            row = self._conn.execute(
                "SELECT doc FROM entities WHERE collection='documents' AND id=?", (document_id,)
            ).fetchone()
        return json.loads(row["doc"]).get("title", document_id) if row else document_id

    def search_fts(self, product_id: str, query: str, limit: int = 20) -> list[dict[str, Any]]:
        import re

        terms = re.findall(r"[\w]+", query.lower())
        if not terms:
            return []
        match = " OR ".join(f'"{t}"' for t in terms[:12])
        with self._lock:
            rows = self._conn.execute(
                "SELECT c.id, c.document_id, c.seq, snippet(chunks_fts,0,'','','…',12) AS snip,"
                " bm25(chunks_fts) AS score FROM chunks_fts"
                " JOIN chunks c ON c.rowid=chunks_fts.rowid"
                " WHERE chunks_fts MATCH ? AND c.product_id=? LIMIT ?",
                (match, product_id, limit),
            ).fetchall()
        return [dict(r) for r in rows]

    def audit(self, event: dict[str, Any]) -> None:
        event = redact(event)
        doc = json.dumps(event, ensure_ascii=False)
        with self._lock:
            self._conn.execute(
                "INSERT OR REPLACE INTO entities"
                "(collection,id,product_id,workspace_id,status,name,doc,updated_at)"
                " VALUES('audit_events',?,?,?,?,NULL,?,?)",
                (
                    event["id"],
                    event.get("product_id"),
                    event.get("workspace_id"),
                    event.get("action", ""),
                    doc,
                    event.get("created_at", utcnow()),
                ),
            )
            self._conn.commit()
