"""Cycles 10-11: watches/alerts/approvals/reports + workflows/routing."""

import sqlite3

import pytest


@pytest.fixture()
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("PRODUCT_FORGE_HOME", str(tmp_path / "h"))
    db = tmp_path / "m.db"
    c = sqlite3.connect(db)
    c.execute("CREATE TABLE err_rate (day TEXT, v REAL)")
    c.executemany("INSERT INTO err_rate VALUES (?,?)", [("d1", 0.02), ("d2", 0.15)])
    c.commit()
    c.close()
    return tmp_path / "h", db


def _store(h):
    from product_forge.config import db_path, load_config
    from product_forge.store.sqlite import Store

    return Store(db_path(h, load_config(h)))


def test_watch_breach_opens_alert(env):
    h, db = env
    from product_forge.domain.models import ConnectorType, DataSource
    from product_forge.operations.watches import create_watch, evaluate_watch, run_due

    st = _store(h)
    st.put("data_sources", DataSource(id="s1", product_id="p", name="m",
                                    connector=ConnectorType.SQLITE, locator=str(db)))
    w = create_watch(st, "p", {"name": "error-rate", "source_id": "s1",
                               "statement": "SELECT max(v) FROM err_rate",
                               "op": ">", "value": 0.10, "interval_s": 0})
    res = evaluate_watch(st, w)
    assert res["breached"] and res["value"] == 0.15
    alerts = st.list("alerts", product_id="p")
    assert len(alerts) == 1 and "error-rate" in alerts[0]["message"]
    res2 = run_due(st, "p")
    assert res2["evaluated"] >= 1
    st.close()


def test_approvals_gate(env):
    h, _ = env
    from product_forge.errors import UnsafeOperationError
    from product_forge.operations.approvals import check_gate, decide, request_approval

    st = _store(h)
    rec = request_approval(st, "p", "agent.publish", {"resource_id": "agt_1"})
    g = check_gate(st, "p", "agent.publish", "agt_1")
    assert g["gated"] and not g["approved"]
    rec = decide(st, rec["id"], True, reviewer="pm")
    assert rec["state"] == "approved"
    g = check_gate(st, "p", "agent.publish", "agt_1")
    assert g["approved"]
    with pytest.raises(UnsafeOperationError):
        decide(st, rec["id"], True)
    st.close()


def test_executive_report(env):
    h, _ = env
    from product_forge.domain.models import Product, Workspace
    from product_forge.operations.reports import generate_executive

    st = _store(h)
    st.put("workspaces", Workspace(id="w1", name="W"))
    st.put("products", Product(id="p", workspace_id="w1", name="Pay"))
    rec = generate_executive(st, "p")
    assert "Executive Report — Pay" in rec["markdown"]
    assert st.get("reports", rec["id"])
    st.close()


def test_workflow_multi_agent(env):
    h, db = env
    from product_forge.agents.workflows import run_workflow
    from product_forge.domain.models import (
        AgentDefinition,
        ConnectorType,
        DataSource,
        Document,
        DocumentStatus,
    )
    from product_forge.knowledge.ingest import sha256_text

    st = _store(h)
    doc = Document(id="d1", product_id="p", title="t", content_hash=sha256_text("x"),
                   status=DocumentStatus.INDEXED)
    st.put("documents", doc)
    st.put_chunks("d1", "p", ["retry policy is exponential backoff"])
    st.put("agents", AgentDefinition(id="a1", product_id="p", name="A",
                                   template="product-analyst",
                                   tools_allowed=["knowledge_query"]))
    st.put("data_sources", DataSource(id="s1", product_id="p", name="m",
                                    connector=ConnectorType.SQLITE, locator=str(db)))
    spec = {"name": "investigate", "steps": [
        {"id": "ask", "kind": "agent", "agent_id": "a1", "input": "retry policy?"},
        {"id": "verify", "kind": "tool", "tool": "knowledge_health"}]}
    rec = run_workflow(st, "p", spec)
    assert rec["status"] == "completed" and len(rec["steps"]) == 2
    st.close()


def test_workflow_halts_on_cross_product(env):
    h, _ = env
    from product_forge.agents.workflows import run_workflow
    from product_forge.domain.models import AgentDefinition

    st = _store(h)
    st.put("agents", AgentDefinition(id="aX", product_id="OTHER", name="X"))
    rec = run_workflow(st, "p", {"steps": [{"id": "s", "kind": "agent",
                                            "agent_id": "aX", "input": "hi"}]})
    assert rec["status"] == "halted" and rec["steps"][0]["status"] == "denied"
    st.close()


def test_routing_and_budget(env):
    h, _ = env
    from product_forge.agents.routing import record_usage, route

    r = route("synthesis", "economy")
    assert r["fallback"] and not r["llm_used"]
    st = _store(h)
    doc = record_usage(st, "p", {"tokens_in": 100, "tool_calls": 2})
    assert doc["tokens_in"] == 100 and doc["runs"] == 1
    st.close()
