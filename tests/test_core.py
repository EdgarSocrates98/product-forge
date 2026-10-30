"""Cycle-1 acceptance: install, store, domain, security, CLI smoke."""

import json

import pytest

from product_forge.errors import NotFoundError


@pytest.fixture()
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("PRODUCT_FORGE_HOME", str(tmp_path / "pfhome"))
    return tmp_path / "pfhome"


def test_store_crud(home):
    from product_forge.config import db_path, load_config
    from product_forge.domain.models import Product, Workspace, new_id
    from product_forge.store.sqlite import Store

    st = Store(db_path(home, load_config(home)))
    ws = Workspace(id=new_id("ws"), name="w1")
    st.put("workspaces", ws)
    assert st.get("workspaces", ws.id)["name"] == "w1"
    p = Product(id=new_id("prd"), workspace_id=ws.id, name="Payments")
    st.put("products", p)
    items = st.list("products", workspace_id=ws.id)
    assert len(items) == 1 and items[0]["name"] == "Payments"
    st.delete("products", p.id)
    with pytest.raises(NotFoundError):
        st.get("products", p.id)
    st.close()


def test_chunking_and_fts(home):
    from product_forge.config import db_path, load_config
    from product_forge.knowledge.ingest import chunk_text, sha256_text
    from product_forge.store.sqlite import Store

    text = "Payments API.\n\n" + ("Retries are exponential. " * 30 + "\n\n") * 5
    chunks = chunk_text(text)
    assert len(chunks) > 1
    st = Store(db_path(home, load_config(home)))
    st.put_chunks("doc1", "prd_x", chunks)
    hits = st.search_fts("prd_x", "retries exponential")
    assert hits and hits[0]["document_id"] == "doc1"
    assert sha256_text("abc") == sha256_text("abc")
    st.close()


def test_redact():
    from product_forge.security import redact

    doc = {"name": "x", "api_key": "sekret", "nested": [{"password": "p"}], "ok": 1}
    out = redact(doc)
    assert out["api_key"] == "[redacted]"
    assert out["nested"][0]["password"] == "[redacted]"  # noqa: S105
    assert out["ok"] == 1


def test_safe_path(home):
    from product_forge.errors import PermissionDeniedError
    from product_forge.security import safe_path

    root = home / "allowed"
    root.mkdir(parents=True)
    inside = root / "f.txt"
    inside.write_text("x")
    assert safe_path(str(inside), [root]) == inside.resolve()
    with pytest.raises(PermissionDeniedError):
        safe_path("/etc/passwd", [root])


def test_cli_smoke(home, capsys):
    from typer.testing import CliRunner

    from product_forge.cli import app

    r = CliRunner()
    assert r.invoke(app, ["version"]).exit_code == 0
    res = r.invoke(app, ["install", "--yes"])
    assert res.exit_code == 0, res.output
    res = r.invoke(app, ["workspace", "create", "WS1"])
    assert res.exit_code == 0
    ws = json.loads(res.output)
    res = r.invoke(app, ["product", "create", ws["id"], "Payments", "--domain", "fintech"])
    assert res.exit_code == 0, res.output
    prd = json.loads(res.output)
    res = r.invoke(app, ["product", "context", prd["id"]])
    assert res.exit_code == 0
    ctx = json.loads(res.output)
    assert ctx["schema"] == "productforge/ProductContextPackage/v1"


def test_envelope_and_errors(home):
    from product_forge.api.app import envelope
    from product_forge.errors import NotFoundError, ValidationError

    env = envelope({"a": 1})
    assert env["schema"] == "forge/PortalApi/1" and env["data"]["a"] == 1
    err = NotFoundError("nope")
    assert err.body()["code"] == "PORTAL-NOT-FOUND"
    assert ValidationError("bad").http_status == 422


def test_api_endpoints(home):
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    from product_forge.api.app import create_app
    from product_forge.config import load_config
    from product_forge.security import TokenStore

    cfg = load_config(home)
    token = TokenStore(home / str(cfg["api"]["token_file"])).token
    client = TestClient(create_app(home))
    h = {"Authorization": f"Bearer {token}"}

    r = client.get("/api/v1/health")
    assert r.status_code == 200 and r.json()["data"]["status"] == "healthy"

    r = client.post("/api/v1/workspaces", json={"name": "WS"}, headers=h)
    assert r.status_code == 201, r.text
    wid = r.json()["data"]["id"]

    r = client.post("/api/v1/products", json={"workspace_id": wid, "name": "Payments"}, headers=h)
    assert r.status_code == 201
    pid = r.json()["data"]["id"]

    r = client.get(f"/api/v1/products/{pid}/context")
    assert r.status_code == 200
    assert r.json()["data"]["schema"] == "productforge/ProductContextPackage/v1"

    # unauthorized mutation blocked
    r = client.post("/api/v1/workspaces", json={"name": "WS2"})
    assert r.status_code == 401

    # audit written
    r = client.get("/api/v1/audit")
    assert any(e["action"] == "product.create" for e in r.json()["data"]["items"])
