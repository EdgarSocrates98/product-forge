"""Cycles 8-9: cloud honesty + api/data-product intelligence."""

import pytest

OLD_SPEC = """
openapi: 3.0.0
info: {title: Payments API}
paths:
  /charges:
    get:
      operationId: listCharges
      parameters:
        - {name: limit, in: query, required: false, schema: {type: integer}}
        - {name: cursor, in: query, required: true, schema: {type: string}}
      responses: {"200": {}}
    post:
      operationId: createCharge
      requestBody: {required: true}
      responses: {"201": {}}
components:
  schemas:
    Charge:
      type: object
      required: [id, amount]
      properties: {id: {}, amount: {}, status: {}}
"""

NEW_SPEC = """
openapi: 3.0.1
info: {title: Payments API}
paths:
  /charges:
    get:
      operationId: listCharges
      parameters:
        - {name: limit, in: query, required: false, schema: {type: integer}}
        - {name: region, in: query, required: true, schema: {type: string}}
      responses: {"200": {}}
  /refunds:
    post:
      operationId: createRefund
      responses: {"201": {}}
components:
  schemas:
    Charge:
      type: object
      required: [id, amount, currency]
      properties: {id: {}, amount: {}}
"""


def test_openapi_parse():
    from product_forge.integrations.apispec import load_spec, parse_openapi

    p = parse_openapi(load_spec(OLD_SPEC))
    assert len(p["operations"]) == 2
    assert any(o["method"] == "POST" for o in p["operations"])
    assert p["schemas"]["Charge"]["required"] == ["amount", "id"]


def test_breaking_change_diff():
    from product_forge.integrations.apispec import diff_openapi

    rep = diff_openapi(OLD_SPEC, NEW_SPEC)
    types = {b["type"] for b in rep["breaking"]}
    assert rep["is_breaking"]
    assert "operation-removed" in types          # POST /charges gone
    assert "required-param-added" in types       # region required
    assert "param-removed" in types              # cursor removed
    assert "schema-required-added" in types      # currency
    assert "schema-property-removed" in types    # status
    assert "POST /refunds" in rep["additions"]


def test_contract_validation():
    from product_forge.integrations.datacontract import validate_payload

    ctr = {"id": "c1", "fields": [{"name": "id", "type": "string", "required": True},
                                  {"name": "amount", "type": "number", "required": True},
                                  {"name": "status", "type": "string"}],
           "quality": [{"field": "status", "rule": "in:paid|pending|failed"}]}
    ok = validate_payload(ctr, {"id": "x", "amount": 9.9, "status": "paid"})
    assert ok["valid"]
    bad = validate_payload(ctr, {"amount": "NaN-str", "status": "weird"})
    rules = {v["rule"] for v in bad["violations"]}
    assert not bad["valid"] and {"required", "type", "enum"} <= rules


def test_impact_analysis(home=None, tmp_path=None, monkeypatch=None):
    import os
    import tempfile

    os.environ["PRODUCT_FORGE_HOME"] = tempfile.mkdtemp()
    from product_forge.config import db_path, load_config
    from product_forge.domain.models import KnowledgeEntity, Relation, RelKind
    from product_forge.integrations.datacontract import impact_analysis
    from product_forge.store.sqlite import Store

    st = Store(db_path(None or __import__("pathlib").Path(os.environ["PRODUCT_FORGE_HOME"]),
                       load_config()))
    a = KnowledgeEntity(id="e_a", product_id="p", kind="table", name="orders")
    b = KnowledgeEntity(id="e_b", product_id="p", kind="dataset", name="orders_ds")
    c = KnowledgeEntity(id="e_c", product_id="p", kind="api", name="GET /orders")
    for e in (a, b, c):
        st.put("entities", e)
    st.put("relations", Relation(id="r1", product_id="p", from_entity="e_a",
                                 to_entity="e_b", kind=RelKind.READS_FROM))
    st.put("relations", Relation(id="r2", product_id="p", from_entity="e_b",
                                 to_entity="e_c", kind=RelKind.EXPOSED_VIA))
    res = impact_analysis(st, "p", "e_a")
    assert res["count"] == 2 and res["impacted"][-1]["name"] == "GET /orders"
    st.close()


def test_cloud_honest_unavailable(monkeypatch, tmp_path):
    """No boto3/creds → typed SourceUnavailableError, never fake data."""
    monkeypatch.setenv("PRODUCT_FORGE_HOME", str(tmp_path / "h"))
    from product_forge.errors import SourceUnavailableError

    try:
        from product_forge.integrations.aws import glue_catalog
        glue_catalog()
        pytest.skip("aws creds present in env")
    except SourceUnavailableError as e:
        assert "unavailable" in str(e).lower() or "not installed" in str(e).lower()
    try:
        from product_forge.integrations.azure import powerbi_inventory
        powerbi_inventory(None)
    except SourceUnavailableError as e:
        assert "token" in str(e).lower()


def test_api_import_and_diff_endpoint(home=None):
    import os
    import tempfile

    os.environ["PRODUCT_FORGE_HOME"] = tempfile.mkdtemp()
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    from product_forge.api.app import create_app
    from product_forge.config import load_config
    from product_forge.security import TokenStore

    cfg = load_config()
    tok = TokenStore(__import__("pathlib").Path(os.environ["PRODUCT_FORGE_HOME"])
                     / str(cfg["api"]["token_file"])).token
    c = TestClient(create_app())
    h = {"Authorization": f"Bearer {tok}"}
    wid = c.post("/api/v1/workspaces", json={"name": "W"}, headers=h).json()["data"]["id"]
    pid = c.post("/api/v1/products", json={"workspace_id": wid, "name": "P"},
                 headers=h).json()["data"]["id"]
    r = c.post(f"/api/v1/products/{pid}/apis/import",
               json={"name": "Payments", "spec": OLD_SPEC}, headers=h)
    assert r.status_code == 201 and r.json()["data"]["entities_created"] == 2
    aid = r.json()["data"]["api_spec_id"]
    r = c.post(f"/api/v1/products/{pid}/apis/{aid}/diff",
               json={"spec": NEW_SPEC}, headers=h)
    assert r.json()["data"]["is_breaking"]
    r = c.post(f"/api/v1/products/{pid}/contracts",
               json={"name": "charge", "fields": [{"name": "id", "type": "string",
                                                  "required": True}]}, headers=h)
    cid = r.json()["data"]["id"]
    r = c.post(f"/api/v1/products/{pid}/contracts/{cid}/validate",
               json={"payload": {}}, headers=h)
    assert not r.json()["data"]["valid"]
