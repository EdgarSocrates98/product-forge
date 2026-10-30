"""Analytical connectors — real execution for local sources.

sqlite/duckdb/csv work offline with read-only enforcement at the driver
level too. Remote engines (postgres/athena/…) report honest `unverified`
until a driver + credentials exist — no fake connections.
"""

from __future__ import annotations

import sqlite3
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from ..errors import SourceUnavailableError, UnsafeOperationError
from ..security import safe_path

MAX_ROWS = 5000
MAX_COLS = 100
SENSITIVE_COL = __import__("re").compile(
    r"(password|secret|token|ssn|cpf|card_number|cvv|api_key)", __import__("re").I)


@dataclass
class QueryResult:
    columns: list[str]
    rows: list[list[Any]]
    row_count: int
    truncated: bool
    duration_ms: float
    masked_columns: list[str] = field(default_factory=list)


class Connector(Protocol):
    def verify(self) -> dict[str, Any]: ...
    def schema(self) -> dict[str, Any]: ...
    def execute(self, sql: str, *, row_limit: int, timeout_s: float,
                cancel: threading.Event | None = None) -> QueryResult: ...


def _mask(columns: list[str], rows: list[list[Any]]) -> tuple[list[list[Any]], list[str]]:
    masked_idx = [i for i, c in enumerate(columns) if SENSITIVE_COL.search(c)]
    if not masked_idx:
        return rows, []
    names = [columns[i] for i in masked_idx]
    out = [[("[masked]" if i in masked_idx else v) for i, v in enumerate(r)] for r in rows]
    return out, names


class SQLiteConnector:
    def __init__(self, db_file: Path, allowed_roots: list[Path] | None = None) -> None:
        self.path = safe_path(db_file, allowed_roots or [Path.cwd(), Path.home()])

    def _conn(self) -> sqlite3.Connection:
        return sqlite3.connect(f"file:{self.path}?mode=ro", uri=True, timeout=5)

    def verify(self) -> dict[str, Any]:
        try:
            with self._conn() as c:
                c.execute("SELECT 1")
            return {"status": "healthy", "engine": "sqlite"}
        except sqlite3.Error as e:
            raise SourceUnavailableError(f"sqlite unavailable: {e}") from e

    def schema(self) -> dict[str, Any]:
        with self._conn() as c:
            tables = [r[0] for r in c.execute(
                "SELECT name FROM sqlite_master WHERE type IN ('table','view')")]
            cols = {t: [dict(zip(("name", "type"), (r[1], r[2]), strict=False))
                        for r in c.execute(f'PRAGMA table_info("{t}")')] for t in tables}
        return {"engine": "sqlite", "tables": [{"name": t, "columns": cols[t]} for t in tables]}

    def execute(self, sql: str, *, row_limit: int = MAX_ROWS, timeout_s: float = 30.0,
                cancel: threading.Event | None = None) -> QueryResult:
        start = time.perf_counter()
        conn = self._conn()
        deadline = start + timeout_s

        def progress() -> int:
            if cancel is not None and cancel.is_set():
                return 1
            return 1 if time.perf_counter() > deadline else 0

        try:
            conn.set_progress_handler(progress, 1000)
            cur = conn.execute(sql)
            columns = [d[0] for d in (cur.description or [])][:MAX_COLS]
            rows = cur.fetchmany(row_limit + 1)
            truncated = len(rows) > row_limit
            rows = rows[:row_limit]
        finally:
            conn.close()
        rows, masked = _mask(columns, rows)
        return QueryResult(columns=columns, rows=[list(r) for r in rows],
                           row_count=len(rows), truncated=truncated,
                           duration_ms=round((time.perf_counter() - start) * 1000, 1),
                           masked_columns=masked)


class DuckDBConnector:
    def __init__(self, db_file: Path | None = None, read_only: bool = True) -> None:
        self.db_file = db_file
        self.read_only = read_only

    def _conn(self):  # type: ignore[no-untyped-def]
        import duckdb

        return duckdb.connect(str(self.db_file) if self.db_file else ":memory:",
                              read_only=self.read_only and bool(self.db_file))

    def verify(self) -> dict[str, Any]:
        try:
            with self._conn() as c:
                c.execute("SELECT 1")
            return {"status": "healthy", "engine": "duckdb"}
        except Exception as e:
            raise SourceUnavailableError(f"duckdb unavailable: {e}") from e

    def schema(self) -> dict[str, Any]:
        with self._conn() as c:
            tables = [r[0] for r in c.execute("SHOW TABLES").fetchall()]
            cols = {t: [{"name": r[0], "type": r[1]} for r in
                        c.execute(f"DESCRIBE {t}").fetchall()] for t in tables}
        return {"engine": "duckdb", "tables": [{"name": t, "columns": cols[t]} for t in tables]}

    def execute(self, sql: str, *, row_limit: int = MAX_ROWS, timeout_s: float = 30.0,
                cancel: threading.Event | None = None) -> QueryResult:
        start = time.perf_counter()
        with self._conn() as c:
            cur = c.execute(sql)
            columns = [d[0] for d in cur.description][:MAX_COLS]
            rows = cur.fetchmany(row_limit + 1)
            truncated = len(rows) > row_limit
            rows = rows[:row_limit]
        rows, masked = _mask(columns, rows)
        return QueryResult(columns=columns, rows=[list(r) for r in rows],
                           row_count=len(rows), truncated=truncated,
                           duration_ms=round((time.perf_counter() - start) * 1000, 1),
                           masked_columns=masked)


def connector_for(ds: dict[str, Any], allowed_roots: list[Path] | None = None) -> Connector:
    kind = ds.get("connector")
    if kind == "sqlite":
        return SQLiteConnector(Path(ds["locator"]), allowed_roots)
    if kind in {"duckdb", "csv"}:
        return DuckDBConnector(Path(ds["locator"]) if ds.get("locator") else None)
    raise UnsafeOperationError(
        f"connector '{kind}' has no verified local driver — register credentials/driver first")
