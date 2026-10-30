"""SQL validation — read-only enforcement + dialect allowlist.

Primary path uses sqlglot (real parse, not regex). When sqlglot is
absent, a conservative tokenizer fallback still blocks DDL/DML —
deny-by-default either way. A statement passes only if it parses as
a single SELECT-family statement.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

ALLOWED_DIALECTS = {"sql", "sqlite", "postgres", "mysql", "tsql", "trino",
                    "athena", "spark", "duckdb", "dax", "kql"}

_ALLOWED_HEADS = {"select", "with", "show", "describe", "desc", "explain", "values", "pragma-read-only"}
_FORBIDDEN = re.compile(
    r"\b(insert|update|delete|drop|create|alter|truncate|merge|replace|grant|revoke|"
    r"attach|detach|copy|call|exec|execute|vacuum|reindex|analyze|set|use|pragma\s+\w+\s*=|"
    r"install|load|export|import|backup|restore)\b",
    re.I,
)


@dataclass
class Validation:
    ok: bool
    dialect: str
    statement_kind: str = ""
    tables: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    engine: str = "sqlglot"


def validate(statement: str, dialect: str = "sql") -> Validation:
    v = Validation(ok=False, dialect=dialect)
    if dialect not in ALLOWED_DIALECTS:
        v.errors.append(f"dialect-not-allowed:{dialect}")
        return v
    sql = statement.strip().rstrip(";")
    if not sql:
        v.errors.append("empty-statement")
        return v
    if dialect == "dax":
        return _dax_validate(sql, v)
    if dialect == "kql":
        return _kql_validate(sql, v)
    try:
        return _sqlglot_validate(sql, v)
    except ImportError:
        return _token_validate(sql, v)


def _sqlglot_validate(sql: str, v: Validation) -> Validation:
    import sqlglot
    from sqlglot import exp

    v.engine = "sqlglot"
    dialect = {"sql": None, "sqlite": "sqlite", "postgres": "postgres",
               "mysql": "mysql", "tsql": "tsql", "trino": "trino",
               "athena": "presto", "spark": "spark", "duckdb": "duckdb"}.get(v.dialect)
    try:
        parsed = sqlglot.parse(sql, read=dialect)
    except sqlglot.errors.ParseError as e:
        v.errors.append(f"parse-error:{str(e)[:120]}")
        return v
    statements = [p for p in parsed if p is not None]
    if len(statements) != 1:
        v.errors.append("multi-statement-not-allowed")
        return v
    node = statements[0]
    allowed = (exp.Select, exp.Union, exp.Subquery, exp.With, exp.Values,
               exp.Describe, exp.Show, exp.Pragma, exp.Summarize)
    if not isinstance(node, allowed):
        v.errors.append(f"statement-not-read-only:{type(node).__name__}")
        return v
    v.statement_kind = type(node).__name__
    v.tables = sorted({t.name for t in node.find_all(exp.Table)})
    v.ok = True
    return v


_KQL_FORBIDDEN = re.compile(
    r"\.\s*(alter|drop|create|ingest|set|append|replace|merge|move|rename|"
    r"clear|execute|revoke|grant)\b|\bexternaldata\b|\bhttp_request\b", re.I)
_DAX_FORBIDDEN = re.compile(r"\b(import|export|backup|restore)\b", re.I)


def _kql_validate(sql: str, v: Validation) -> Validation:
    """KQL: conservative — single tabular query, no .management commands."""
    v.engine = "kql-lite"
    if ";" in sql:
        v.errors.append("multi-statement-not-allowed")
        return v
    if _KQL_FORBIDDEN.search(sql):
        v.errors.append("kql-management-or-external-op-denied")
        return v
    head = sql.split(None, 1)[0].rstrip("|").lower()
    if head in {"let", "set", "print"} and head != "let":
        v.errors.append(f"kql-statement-not-read-only:{head}")
        return v
    v.statement_kind = "tabular"
    v.ok = True
    # §3.3: partial validation — mark unverified, provider must execute restricted
    v.engine = "kql-lite:unverified"
    return v


def _dax_validate(sql: str, v: Validation) -> Validation:
    """DAX: only EVALUATE queries pass; anything else is refused."""
    v.engine = "dax-lite"
    head = sql.split(None, 1)[0].upper()
    if head != "EVALUATE":
        v.errors.append(f"dax-must-start-with-evaluate:{head.lower()}")
        return v
    if _DAX_FORBIDDEN.search(sql):
        v.errors.append("dax-forbidden-keyword-detected")
        return v
    v.statement_kind = "evaluate"
    v.ok = True
    # §3.3: partial validation — mark unverified, provider must execute restricted
    v.engine = "dax-lite:unverified"
    return v


def _token_validate(sql: str, v: Validation) -> Validation:
    v.engine = "tokens"
    head = sql.split(None, 1)[0].lower()
    if ";" in sql:
        v.errors.append("multi-statement-not-allowed")
        return v
    if head not in _ALLOWED_HEADS:
        v.errors.append(f"statement-not-read-only:{head}")
        return v
    if _FORBIDDEN.search(sql):
        v.errors.append("forbidden-keyword-detected")
        return v
    v.statement_kind = head
    v.ok = True
    return v


def check_allowlist(tables: list[str], allowlist: list[str]) -> list[str]:
    """Return tables outside the catalog allowlist (empty allowlist = all allowed)."""
    if not allowlist:
        return []
    allowed = {a.lower() for a in allowlist}
    return [t for t in tables if t.lower() not in allowed
            and t.lower().split(".")[-1] not in allowed]
