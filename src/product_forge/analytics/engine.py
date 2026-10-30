"""Query engine — validate → allowlist → execute → record.

Every execution produces a persisted `productforge/QueryRun` record with
status, rows, duration and errors. Cancellation supported via event flags
wired into sqlite progress handler.
"""

from __future__ import annotations

import threading
from typing import Any

from ..domain.models import new_id, utcnow
from ..errors import UnsafeOperationError, ValidationError
from ..store.sqlite import Store
from . import sqlvalidate
from .connectors import QueryResult, connector_for

_cancels: dict[str, threading.Event] = {}
_cancels_lock = threading.Lock()


def validate_query(statement: str, dialect: str) -> dict[str, Any]:
    v = sqlvalidate.validate(statement, dialect)
    return {"schema": "productforge/QueryValidation/v1", "ok": v.ok,
            "dialect": v.dialect, "kind": v.statement_kind,
            "tables": v.tables, "errors": v.errors, "engine": v.engine}


def execute_query(store: Store, product_id: str, source_id: str,
                  statement: str, *, row_limit: int = 1000,
                  timeout_s: float = 30.0, allowed_roots: list | None = None) -> dict[str, Any]:
    ds = store.get("data_sources", source_id)
    if ds.get("product_id") != product_id:
        raise UnsafeOperationError("data source not in product scope")
    if not ds.get("read_only", True):
        raise UnsafeOperationError("source not marked read_only — refusing")
    v = sqlvalidate.validate(statement, ds.get("dialect", "sql"))
    run = {"id": new_id("qry"), "schema": "productforge/QueryRun/v1",
           "product_id": product_id, "source_id": source_id, "dialect": v.dialect,
           "statement": statement, "status": "validated", "created_at": utcnow(),
           "updated_at": utcnow(), "rows": 0, "duration_ms": 0.0}
    if not v.ok:
        run["status"] = "rejected"
        run["error"] = "; ".join(v.errors)
        store.put_doc("query_runs", run, status="rejected")
        return run
    outside = sqlvalidate.check_allowlist(v.tables, ds.get("catalog_allowlist", []))
    if outside:
        run["status"] = "rejected"
        run["error"] = f"tables outside catalog allowlist: {outside}"
        store.put_doc("query_runs", run, status="rejected")
        return run

    cancel = threading.Event()
    with _cancels_lock:
        _cancels[run["id"]] = cancel
    run["status"] = "running"
    store.put_doc("query_runs", run, status="running")
    try:
        # registered locator is pre-authorized: confine to its own directory
        from pathlib import Path

        roots = allowed_roots or [Path(ds.get("locator", ".")).parent]
        result: QueryResult = connector_for(ds, roots).execute(
            statement, row_limit=row_limit, timeout_s=timeout_s, cancel=cancel)
        run.update({"status": "cancelled" if cancel.is_set() else "completed",
                    "rows": result.row_count, "duration_ms": result.duration_ms,
                    "truncated": result.truncated,
                    "columns": result.columns,
                    "masked_columns": result.masked_columns,
                    "result_preview": result.rows[:100]})
    except TimeoutError:
        run["status"] = "timeout"
    except Exception as e:  # connector errors recorded on the run
        run["status"] = "failed"
        run["error"] = f"{type(e).__name__}: {str(e)[:200]}"
    finally:
        with _cancels_lock:
            _cancels.pop(run["id"], None)
    run["updated_at"] = utcnow()
    store.put_doc("query_runs", run, status=run["status"])
    return run


def cancel_query(run_id: str) -> bool:
    with _cancels_lock:
        ev = _cancels.get(run_id)
        if ev:
            ev.set()
            return True
    return False


def compile_spec(spec: dict[str, Any]) -> str:
    """Visual Query Builder → SQL. Shared contract with NL and editor."""
    table = spec.get("table")
    if not table or not str(table).replace("_", "").replace(".", "").isalnum():
        raise ValidationError("invalid table identifier")
    cols = spec.get("columns") or ["*"]
    select = ", ".join(_ident(c) for c in cols)
    agg = spec.get("aggregate")
    if agg:
        fn = str(agg.get("fn", "count")).lower()
        if fn not in {"count", "sum", "avg", "min", "max"}:
            raise ValidationError(f"aggregate not allowed: {fn}")
        col = _ident(agg.get("column", "*")) if fn != "count" else "*"
        select = f"{fn.upper()}({col}) AS {fn}_{agg.get('column', 'all')}"
    sql = f"SELECT {select} FROM {_ident(table)}"  # noqa: S608 — identifiers/literals escaped; downstream validator enforces read-only
    where = []
    for f in spec.get("filters", [])[:10]:
        op = str(f.get("op", "="))
        if op not in {"=", "!=", ">", "<", ">=", "<=", "LIKE", "IS NULL", "IS NOT NULL"}:
            raise ValidationError(f"operator not allowed: {op}")
        col = _ident(f["column"])
        if op in {"IS NULL", "IS NOT NULL"}:
            where.append(f"{col} {op}")
        else:
            val = f.get("value")
            lit = f"'{str(val).replace(chr(39), chr(39) * 2)}'" if isinstance(val, str) else str(val)
            where.append(f"{col} {op} {lit}")
    if where:
        sql += " WHERE " + " AND ".join(where)
    if gb := spec.get("group_by"):
        sql += " GROUP BY " + ", ".join(_ident(c) for c in gb[:10])
    if ob := spec.get("order_by"):
        direction = "DESC" if str(ob.get("direction", "")).upper() == "DESC" else "ASC"
        sql += f" ORDER BY {_ident(ob['column'])} {direction}"
    limit = min(int(spec.get("limit", 1000)), 5000)
    sql += f" LIMIT {limit}"
    return sql


def _ident(name: Any) -> str:
    s = str(name)
    if s == "*":
        return "*"
    if not s.replace("_", "").replace(".", "").isalnum() or s[0].isdigit():
        raise ValidationError(f"invalid identifier: {name}")
    return s


def nl_to_sql(question: str, tables: list[str]) -> dict[str, Any]:
    """Deterministic NL→SQL for registered patterns — honest otherwise."""
    import re

    q = question.lower()
    table = next((t for t in tables if t.lower() in q), None)
    if not table:
        return {"ok": False, "reason": "no-known-table-in-question",
                "tables_available": tables[:20]}
    if m := re.search(r"(?:top|primeir\w+|maiores)\s+(\d+)", q):
        return {"ok": True, "spec": {"table": table, "columns": ["*"],
                                     "limit": int(m.group(1))},
                "explain": f"top {m.group(1)} rows from {table}"}
    if re.search(r"(how many|count|quantos|quantas|total)", q):
        return {"ok": True, "spec": {"table": table, "aggregate": {"fn": "count"}},
                "explain": f"count rows in {table}"}
    if re.search(r"(list|show|mostr|listar)", q):
        return {"ok": True, "spec": {"table": table, "columns": ["*"], "limit": 100},
                "explain": f"sample rows from {table}"}
    return {"ok": False, "reason": "pattern-not-recognized",
            "hint": "try: 'how many <table>', 'top N <table>', 'list <table>'"}
