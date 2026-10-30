"""Cycle 5: SQL validation, connectors, execution, spec compile, NL→SQL."""

import sqlite3

import pytest


@pytest.fixture()
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("PRODUCT_FORGE_HOME", str(tmp_path / "pfhome"))
    return tmp_path / "pfhome"


@pytest.fixture()
def dbfile(tmp_path):
    p = tmp_path / "analytics.db"
    c = sqlite3.connect(p)
    c.execute("CREATE TABLE transactions (id INT, amount REAL, card_token TEXT)")
    c.executemany("INSERT INTO transactions VALUES (?,?,?)",
                  [(i, i * 9.9, "tok_secret") for i in range(10)])
    c.commit()
    c.close()
    return p


def test_validate_select_ok():
    from product_forge.analytics.sqlvalidate import validate

    v = validate("SELECT id, amount FROM transactions WHERE amount > 10", "sqlite")
    assert v.ok and v.tables == ["transactions"]


@pytest.mark.parametrize("bad", [
    "DROP TABLE transactions",
    "DELETE FROM transactions",
    "INSERT INTO transactions VALUES (1,2)",
    "SELECT 1; DROP TABLE t",
    "UPDATE t SET a=1",
    "CREATE TABLE x (a int)",
    "ATTACH DATABASE 'x' AS y",
])
def test_validate_blocks_ddl_dml(bad):
    from product_forge.analytics.sqlvalidate import validate

    assert not validate(bad, "sqlite").ok


def test_dialect_allowlist():
    from product_forge.analytics.sqlvalidate import validate

    assert not validate("SELECT 1", "not-a-dialect").ok


def test_execute_real_query(home, dbfile):
    from product_forge.analytics.engine import execute_query
    from product_forge.config import db_path, load_config
    from product_forge.domain.models import ConnectorType, DataSource
    from product_forge.store.sqlite import Store

    st = Store(db_path(home, load_config(home)))
    ds = DataSource(id="src_1", product_id="prd_q", name="local",
                    connector=ConnectorType.SQLITE, locator=str(dbfile), read_only=True)
    st.put("data_sources", ds)
    run = execute_query(st, "prd_q", "src_1", "SELECT * FROM transactions ORDER BY id")
    assert run["status"] == "completed" and run["rows"] == 10
    # sensitive column masked
    assert run["masked_columns"] == ["card_token"]
    assert all(r[2] == "[masked]" for r in run["result_preview"])
    st.close()


def test_execute_rejected_persists(home, dbfile):
    from product_forge.analytics.engine import execute_query
    from product_forge.config import db_path, load_config
    from product_forge.domain.models import ConnectorType, DataSource
    from product_forge.store.sqlite import Store

    st = Store(db_path(home, load_config(home)))
    st.put("data_sources", DataSource(id="src_2", product_id="prd_q", name="l",
                                      connector=ConnectorType.SQLITE, locator=str(dbfile)))
    run = execute_query(st, "prd_q", "src_2", "DROP TABLE transactions")
    assert run["status"] == "rejected"
    assert st.get("query_runs", run["id"])["status"] == "rejected"
    st.close()


def test_allowlist_enforced(home, dbfile):
    from product_forge.analytics.engine import execute_query
    from product_forge.config import db_path, load_config
    from product_forge.domain.models import ConnectorType, DataSource
    from product_forge.store.sqlite import Store

    st = Store(db_path(home, load_config(home)))
    st.put("data_sources", DataSource(id="src_3", product_id="prd_q", name="l",
                                      connector=ConnectorType.SQLITE, locator=str(dbfile),
                                      catalog_allowlist=["other_table"]))
    run = execute_query(st, "prd_q", "src_3", "SELECT * FROM transactions")
    assert run["status"] == "rejected" and "allowlist" in run["error"]
    st.close()


def test_compile_spec_and_nl():
    from product_forge.analytics.engine import compile_spec, nl_to_sql

    sql = compile_spec({"table": "transactions", "aggregate": {"fn": "count"},
                        "filters": [{"column": "amount", "op": ">", "value": 10}]})
    assert "COUNT(*)" in sql and "amount > 10" in sql
    res = nl_to_sql("how many transactions?", ["transactions"])
    assert res["ok"]
    res = nl_to_sql("show me the flux capacitor", ["transactions"])
    assert not res["ok"]


def test_schema_explorer(home, dbfile):
    from product_forge.analytics.connectors import SQLiteConnector

    schema = SQLiteConnector(dbfile, [dbfile.parent]).schema()
    assert schema["tables"][0]["name"] == "transactions"
    assert {c["name"] for c in schema["tables"][0]["columns"]} == {"id", "amount", "card_token"}


def test_api_analytics(home, dbfile):
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    from product_forge.api.app import create_app
    from product_forge.config import load_config
    from product_forge.security import TokenStore

    cfg = load_config(home)
    tok = TokenStore(home / str(cfg["api"]["token_file"])).token
    c = TestClient(create_app(home))
    h = {"Authorization": f"Bearer {tok}"}
    wid = c.post("/api/v1/workspaces", json={"name": "W"}, headers=h).json()["data"]["id"]
    pid = c.post("/api/v1/products", json={"workspace_id": wid, "name": "P"},
                 headers=h).json()["data"]["id"]
    sid = c.post(f"/api/v1/products/{pid}/data-sources",
                 json={"name": "local", "connector": "sqlite", "locator": str(dbfile)},
                 headers=h).json()["data"]["id"]
    r = c.post(f"/api/v1/products/{pid}/queries/validate",
               json={"statement": "SELECT * FROM transactions"}, headers=h)
    assert r.json()["data"]["ok"]
    r = c.post(f"/api/v1/products/{pid}/queries/execute",
               json={"source_id": sid, "statement": "SELECT count(*) AS n FROM transactions"},
               headers=h)
    assert r.json()["data"]["status"] == "completed"
    r = c.post(f"/api/v1/products/{pid}/queries/execute",
               json={"source_id": sid, "spec": {"table": "transactions",
                                              "aggregate": {"fn": "sum", "column": "amount"}}},
               headers=h)
    assert r.json()["data"]["status"] == "completed"
