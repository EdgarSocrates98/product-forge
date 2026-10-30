"""Spec: mcp-http-transport — same JSON-RPC over POST /mcp + bearer auth."""

import pytest

pytestmark = pytest.mark.skipif(
    __import__("importlib.util").util.find_spec("fastapi") is None,
    reason="fastapi not installed")


def test_dispatch_shared_shape():
    from product_forge.mcp.server import dispatch, tool_specs

    r = dispatch({"jsonrpc": "2.0", "id": 1, "method": "initialize"})
    assert r["result"]["protocolVersion"] == "2024-11-05"
    assert dispatch({"jsonrpc": "2.0", "method": "notifications/initialized"}) is None
    assert dispatch({"jsonrpc": "2.0", "id": 2, "method": "tools/list"}
                    )["result"]["tools"] == tool_specs()
    assert dispatch({"jsonrpc": "2.0", "id": 3, "method": "ping"})["result"] == {}
    assert dispatch({"jsonrpc": "2.0", "id": 4, "method": "nope"})["error"]["code"] == -32601


def test_http_transport_auth_and_calls(tmp_path, monkeypatch):
    monkeypatch.setenv("PRODUCT_FORGE_HOME", str(tmp_path / "pf"))
    import threading
    import time

    import httpx
    import uvicorn
    from fastapi import FastAPI, Request
    from fastapi.responses import JSONResponse

    from product_forge.config import home_dir, load_config
    from product_forge.mcp.server import dispatch
    from product_forge.security import TokenStore

    home = home_dir("user")
    (home / "state" / "objects").mkdir(parents=True, exist_ok=True)
    cfg = load_config(home)
    tok = TokenStore(home / str(cfg["api"]["token_file"])).token

    app = FastAPI()

    @app.post("/mcp")
    async def mcp(req: Request):
        if req.headers.get("authorization") != f"Bearer {tok}":
            return JSONResponse({"error": "unauthorized"}, status_code=401)
        return JSONResponse(dispatch(await req.json()))

    srv = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=18471,
                                        log_level="error"))
    t = threading.Thread(target=srv.run, daemon=True)
    t.start()
    time.sleep(0.8)
    try:
        h = {"Authorization": f"Bearer {tok}"}
        r = httpx.post("http://127.0.0.1:18471/mcp",
                       json={"jsonrpc": "2.0", "id": 1, "method": "initialize"},
                       headers=h)
        assert r.json()["result"]["serverInfo"]["name"] == "product-forge"
        r = httpx.post("http://127.0.0.1:18471/mcp",
                       json={"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
                       headers=h)
        assert len(r.json()["result"]["tools"]) == 14
        assert httpx.post("http://127.0.0.1:18471/mcp",
                          json={"jsonrpc": "2.0", "id": 3, "method": "ping"}
                          ).status_code == 401
    finally:
        srv.should_exit = True
        t.join(timeout=3)
