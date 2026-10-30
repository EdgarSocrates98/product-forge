"""Cycle 3: extraction, graph, knowledge health."""

import pytest


@pytest.fixture()
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("PRODUCT_FORGE_HOME", str(tmp_path / "pfhome"))
    return tmp_path / "pfhome"


def _seed(home):
    from product_forge.config import db_path, load_config
    from product_forge.domain.models import Document, DocumentStatus
    from product_forge.knowledge.ingest import chunk_text, sha256_text
    from product_forge.store.sqlite import Store

    st = Store(db_path(home, load_config(home)))
    text = ("# Payments API\n\nGET /api/v1/charges creates charges. "
            "Table payments.transactions stores them. Metric: error rate. "
            "Owner: Payments Team.\n\n"
            "# Retry Policy\n\nExponential backoff, event payment.retried.")
    doc = Document(id="doc_t", product_id="prd_t", title="payments.md",
                   content_hash=sha256_text(text), status=DocumentStatus.INDEXED)
    st.put("documents", doc)
    st.put_chunks("doc_t", "prd_t", chunk_text(text))
    return st


def test_extract_and_graph(home):
    from product_forge.knowledge.extract import build_relations, extract_entities
    from product_forge.knowledge.graph import product_graph

    st = _seed(home)
    chunks = st.list_chunks("prd_t")
    ents = extract_entities("prd_t", chunks)
    kinds = {e.kind.value for e in ents}
    assert "api" in kinds or any("/api/v1/charges" in e.name for e in ents)
    for e in ents:
        st.put("entities", e)
    for r in build_relations("prd_t", ents, chunks):
        st.put("relations", r)
    g = product_graph(st, "prd_t")
    assert g["schema"] == "productforge/KnowledgeGraph/v1"
    assert g["stats"]["nodes"] > 0 and g["stats"]["edges"] > 0
    assert all(n["provisional"] for n in g["nodes"])
    st.close()


def test_knowledge_health(home):
    from product_forge.knowledge.graph import knowledge_health

    st = _seed(home)
    h = knowledge_health(st, "prd_t")
    assert h["schema"] == "productforge/KnowledgeHealth/v1"
    assert "no documents imported" not in h["warnings"]
    st.close()


def test_api_knowledge_flow(home):
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
    r = c.post(f"/api/v1/products/{pid}/documents",
               json={"title": "d.md", "content": "GET /api/v1/x\n\nTable orders"}, headers=h)
    assert r.status_code == 201
    r = c.post(f"/api/v1/products/{pid}/knowledge/query",
               json={"question": "orders table"}, headers=h)
    assert r.status_code == 200 and r.json()["data"]["citations"]
    r = c.post(f"/api/v1/products/{pid}/knowledge/extract", headers=h)
    assert r.status_code == 200 and r.json()["data"]["entities"] > 0
    r = c.get(f"/api/v1/products/{pid}/graph", headers=h)
    assert r.json()["data"]["stats"]["nodes"] > 0
    r = c.get(f"/api/v1/products/{pid}/knowledge-health", headers=h)
    assert r.json()["data"]["schema"] == "productforge/KnowledgeHealth/v1"
