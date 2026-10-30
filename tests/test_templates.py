"""Spec: native-agent-templates — roster mapped to pf-* skills, publish-gate evals."""

import pytest

from product_forge.agents.tools import TEMPLATES, list_templates


def test_roster_mapped_to_skills():
    roster = {t["name"]: t for t in list_templates()}
    native = {n for n in roster if n != "custom"}
    assert len(native) >= 3
    for name in native:
        t = roster[name]
        assert t["skill"] and t["skill"].startswith("pf-")
        assert t["tools"] and t["knowledge_scope"]
        assert t["eval_cases"] >= 2  # real evals, not stubbed
        for tool in t["tools"]:
            assert tool in {tt for t2 in TEMPLATES.values() for tt in t2["tools"]}


def test_templates_eval_to_publishable(tmp_path, monkeypatch):
    monkeypatch.setenv("PRODUCT_FORGE_HOME", str(tmp_path / "pf"))
    from product_forge.agents.evals import run_evals
    from product_forge.config import db_path, home_dir, load_config
    from product_forge.domain.models import AgentDefinition, Document, Product
    from product_forge.knowledge.ingest import chunk_text, sha256_text
    from product_forge.store.sqlite import Store

    home = home_dir("user")
    (home / "state" / "objects").mkdir(parents=True, exist_ok=True)
    st = Store(db_path(home, load_config(home)))
    st.put("products", Product(id="p1", workspace_id="w1", name="Pay"))
    text = "# Payments\nError E42 means insufficient funds. Retry with backoff."
    st.put("documents", Document(id="d1", product_id="p1", title="runbook.md",
                                 sha256=sha256_text(text)))
    st.put_chunks("d1", "p1", chunk_text(text))

    for name in ("product-analyst", "product-researcher", "api-analyst", "data-steward"):
        agent = AgentDefinition(id=f"a_{name}", product_id="p1", name=name,
                                template=name,
                                tools_allowed=TEMPLATES[name]["tools"])
        report = run_evals(st, agent)
        assert report["total"] == len(TEMPLATES[name]["eval_cases"])
        assert report["score"] >= 0.5, f"{name} eval {report['score']} below publish gate"
    st.close()


def test_templates_api(tmp_path, monkeypatch):
    pytest.importorskip("fastapi")
    monkeypatch.setenv("PRODUCT_FORGE_HOME", str(tmp_path / "pf"))
    from fastapi.testclient import TestClient

    from product_forge.api.app import create_app
    from product_forge.config import home_dir, load_config
    from product_forge.security import TokenStore

    home = home_dir("user")
    (home / "state" / "objects").mkdir(parents=True, exist_ok=True)
    cfg = load_config(home)
    tok = TokenStore(home / str(cfg["api"]["token_file"])).token
    c = TestClient(create_app(home))
    items = c.get("/api/v1/agent-templates",
                  headers={"Authorization": f"Bearer {tok}"}).json()["data"]["items"]
    assert any(i["name"] == "data-steward" and i["skill"] == "pf-data-products"
               for i in items)
