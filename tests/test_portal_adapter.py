from product_forge.portal.adapter import ProductForgePortal


def test_product_portal_exposes_pm_pa_navigation_and_chat() -> None:
    portal = ProductForgePortal()
    nav = {item["id"] for item in portal.nav()}
    assert {"products", "boards", "roadmaps", "knowledge", "chat"} <= nav
    capabilities = {item["id"] for item in portal.capabilities()}
    assert {"chat", "agent-bridge"} <= capabilities


def test_product_portal_exposes_workspace_discovery_and_preview(tmp_path) -> None:
    from product_forge._forge_portal import RequestContext

    repo = tmp_path / "repo"
    (repo / ".git").mkdir(parents=True)
    (repo / "docs").mkdir()
    (repo / "docs" / "prd.md").write_text("# Product requirements\n", encoding="utf-8")
    portal = ProductForgePortal()
    portal.workspace = str(repo)

    discovery = portal._workspace_discovery(RequestContext(None, {}, {}, None, "cid"))  # type: ignore[arg-type]
    preview = portal._workspace_preview(
        RequestContext(None, {}, {"path": ["docs/prd.md"]}, None, "cid")  # type: ignore[arg-type]
    )

    assert discovery["schema"] == "productforge/WorkspaceDiscovery/v1"
    assert discovery["documents"][0]["kind"] == "prd"
    assert preview["path"] == "docs/prd.md"
    assert "Product requirements" in preview["preview"]


def test_workspace_routes_are_registered_with_explicit_import_gate() -> None:
    portal = ProductForgePortal()
    routes = {(op.method, op.path, op.confirm) for op in portal.ops}
    assert ("GET", "/workspace/discovery", None) in routes
    assert ("GET", "/workspace/discovery/preview", None) in routes
    assert ("POST", "/products/{pid}/documents/from-workspace", "import") in routes


def test_url_routes_are_registered_and_preview_keeps_provenance(monkeypatch) -> None:
    from product_forge._forge_portal import RequestContext

    captured = {
        "schema": "productforge/UrlDocument/v1",
        "url": "https://example.com/docs",
        "title": "Docs",
        "content": "safe text",
        "content_hash": "a" * 64,
        "size": 9,
        "content_type": "text/plain",
        "extractor": "stdlib-text",
        "state": "ready_for_import",
        "warnings": [],
        "metrics": {"bytes_read": 9},
        "provenance": {"redirects_followed": 0},
    }
    monkeypatch.setattr(
        "product_forge.portal.adapter.fetch_url_document",
        lambda _url, **_kwargs: captured,
    )

    class StoreStub:
        def get(self, collection, key):
            assert collection == "products" and key == "p1"
            return {"id": key}

        def close(self):
            pass

    monkeypatch.setattr("product_forge.portal.adapter._store", lambda: StoreStub())
    portal = ProductForgePortal()
    routes = {(op.method, op.path, op.confirm) for op in portal.ops}
    assert ("GET", "/products/{pid}/documents/url/preview", None) in routes
    assert ("POST", "/products/{pid}/documents/from-url", "import") in routes
    result = portal._url_preview(
        RequestContext(None, {"pid": "p1"}, {"url": [captured["url"]]}, None, "cid")  # type: ignore[arg-type]
    )
    assert result["url"] == captured["url"]
    assert result["preview"] == "safe text"


def test_obsidian_routes_are_optional_and_explicitly_gated() -> None:
    portal = ProductForgePortal()
    routes = {(op.method, op.path, op.confirm) for op in portal.ops}
    assert ("GET", "/products/{pid}/documents/obsidian/preview", None) in routes
    assert ("GET", "/products/{pid}/documents/obsidian/status", None) in routes
    assert ("GET", "/products/{pid}/documents/obsidian/files", None) in routes
    assert ("POST", "/products/{pid}/documents/from-obsidian", "import") in routes
    assert ("POST", "/products/{pid}/documents/to-obsidian", "export") in routes
    assert ("POST", "/products/{pid}/documents/obsidian/sync-plan", None) in routes
    assert ("POST", "/products/{pid}/documents/obsidian/rollback", "rollback") in routes
    assert ("POST", "/products/{pid}/documents/obsidian/sync-skip", "skip") in routes


def test_document_explorer_route_is_product_scoped() -> None:
    portal = ProductForgePortal()
    routes = {(op.method, op.path, op.confirm) for op in portal.ops}
    assert ("GET", "/products/{pid}/documents/{did}", None) in routes
    assert ("GET", "/products/{pid}/documents/search", None) in routes
    assert ("GET", "/products/{pid}/knowledge/search", None) in routes
    assert ("POST", "/products/{pid}/documents/{did}/knowledge-state", "transition") in routes


def test_bridge_unavailable_is_honest(monkeypatch) -> None:
    monkeypatch.setenv("FORGE_BRIDGE_URL", "http://127.0.0.1:1")
    result = ProductForgePortal()._bridge_get("/status")
    assert result["state"] == "unavailable"


def test_chat_requires_an_explicit_provider() -> None:
    portal = ProductForgePortal()
    from product_forge._forge_portal import RequestContext

    try:
        portal._chat_create(RequestContext(None, {}, {}, {}, "cid"))  # type: ignore[arg-type]
    except Exception as exc:  # PortalError is intentionally typed by the adapter
        assert getattr(exc, "code", "") == "PROVIDER-REQUIRED"
    else:
        raise AssertionError("chat silently selected the fake provider")


def test_bridge_stream_relay_preserves_sse_metadata(monkeypatch) -> None:
    class Response:
        def __iter__(self):
            return iter(
                [
                    b"id: 7\n",
                    b"event: turn.completed\n",
                    b'data: {"payload": {"ok": true}}\n',
                    b"\n",
                ]
            )

        def close(self):
            pass

    monkeypatch.setattr("product_forge.portal.adapter.urllib.request.urlopen", lambda *a, **k: Response())
    token = "test-token"  # noqa: S105 - fixture credential
    result = ProductForgePortal._bridge_stream(
        "/agent-sessions/ses_1/stream?after_seq=6", token_override=token
    )
    assert list(result.events) == [
        {
            "payload": {"ok": True},
            "seq": 7,
            "type": "turn.completed",
            "sse_id": "7",
            "sse_event": "turn.completed",
        }
    ]


def test_health_reports_unverified_bridge_without_supervisor() -> None:
    portal = ProductForgePortal()
    assert portal.health()["bridge"]["state"] == "unverified"


def test_health_surfaces_supervised_bridge_status() -> None:
    portal = ProductForgePortal()
    portal.bridge_status = lambda: {"state": "running", "pid": 42, "restarts": 1}
    bridge = portal.health()["bridge"]
    assert bridge["state"] == "running"
    assert bridge["restarts"] == 1


class _Ctx:
    def __init__(self, body=None):
        self.body = body or {}
        self.events = []

    def emit(self, event_type, **fields):
        self.events.append((event_type, fields))


def _patch_bridge(monkeypatch, listing, delete_result=None):
    deleted = []
    monkeypatch.setattr(ProductForgePortal, "_bridge_get", staticmethod(lambda path: listing))

    def fake_request(path, *, method="GET", body=None, token_override=""):
        deleted.append((path, method))
        return delete_result or {"closed": True, "archived": True}

    monkeypatch.setattr(ProductForgePortal, "_bridge_request", staticmethod(fake_request))
    return deleted


def test_chat_cleanup_archives_inactive_and_keeps_active(monkeypatch) -> None:
    listing = {
        "items": [
            {"id": "s1", "state": "active"},
            {"id": "s2", "state": "closed"},
            {"id": "s3", "state": "ended"},
            {"no_id": True},
        ]
    }
    deleted = _patch_bridge(monkeypatch, listing)
    ctx = _Ctx()
    result = ProductForgePortal()._chat_cleanup(ctx)
    assert result["closed"] == ["s2", "s3"]
    assert result["kept"] == ["s1"]
    assert deleted == [("/agent-sessions/s2", "DELETE"), ("/agent-sessions/s3", "DELETE")]
    assert ctx.events and ctx.events[0][0] == "chat.sessions_cleaned"


def test_chat_cleanup_include_active_closes_everything(monkeypatch) -> None:
    listing = {"items": [{"id": "s1", "state": "active"}]}
    _patch_bridge(monkeypatch, listing)
    result = ProductForgePortal()._chat_cleanup(_Ctx({"include_active": True}))
    assert result["closed"] == ["s1"]
    assert result["kept"] == []


def test_chat_cleanup_reports_bridge_unavailable(monkeypatch) -> None:
    listing = {"state": "unavailable", "reason": "connection refused"}
    _patch_bridge(monkeypatch, listing)
    result = ProductForgePortal()._chat_cleanup(_Ctx())
    assert result["state"] == "unavailable"
    assert result["closed"] == []


def test_chat_cleanup_reports_failed_deletes(monkeypatch) -> None:
    listing = {"items": [{"id": "s9", "state": "closed"}]}
    _patch_bridge(monkeypatch, listing, delete_result={"error": "denied"})
    result = ProductForgePortal()._chat_cleanup(_Ctx())
    assert result["closed"] == []
    assert result["errors"][0]["id"] == "s9"


def _capture_bridge(monkeypatch):
    calls = []

    def fake_request(path, *, method="GET", body=None, token_override="", timeout=2.0):
        calls.append({"path": path, "method": method, "body": body, "timeout": timeout})
        return {"accepted": True}

    monkeypatch.setattr(ProductForgePortal, "_bridge_request", staticmethod(fake_request))
    return calls


def test_chat_prompt_requires_text() -> None:
    from product_forge._forge_portal import RequestContext

    portal = ProductForgePortal()
    try:
        portal._chat_prompt(RequestContext(None, {"sid": "s1"}, {}, {"text": "  "}, "cid"))  # type: ignore[arg-type]
    except Exception as exc:
        assert getattr(exc, "code", "") == "PROMPT-REQUIRED"
    else:
        raise AssertionError("empty prompt reached the bridge")


def test_chat_prompt_forwards_text(monkeypatch) -> None:
    from product_forge._forge_portal import RequestContext

    calls = _capture_bridge(monkeypatch)
    ProductForgePortal()._chat_prompt(RequestContext(None, {"sid": "s1"}, {}, {"text": "hello"}, "cid"))  # type: ignore[arg-type]
    assert calls[0]["path"] == "/agent-sessions/s1/prompt"
    assert calls[0]["body"]["text"] == "hello"


def test_chat_cancel_posts_to_bridge(monkeypatch) -> None:
    from product_forge._forge_portal import RequestContext

    calls = _capture_bridge(monkeypatch)
    ProductForgePortal()._chat_cancel(RequestContext(None, {"sid": "s1"}, {}, {"confirm": "cancel"}, "cid"))  # type: ignore[arg-type]
    assert calls[0]["path"] == "/agent-sessions/s1/cancel"
    assert calls[0]["method"] == "POST"
    assert calls[0]["body"] == {}


def test_chat_approve_validates_fields() -> None:
    from product_forge._forge_portal import RequestContext

    portal = ProductForgePortal()
    for body, code in [
        ({"approved": True}, "APPROVAL-REQUIRED"),
        ({"approval_id": "a1", "approved": "yes"}, "APPROVAL-REQUIRED"),
    ]:
        try:
            portal._chat_approve(RequestContext(None, {"sid": "s1"}, {}, body, "cid"))  # type: ignore[arg-type]
        except Exception as exc:
            assert getattr(exc, "code", "") == code
        else:
            raise AssertionError(f"invalid approve body accepted: {body}")


def test_chat_approve_forwards_decision(monkeypatch) -> None:
    from product_forge._forge_portal import RequestContext

    calls = _capture_bridge(monkeypatch)
    ProductForgePortal()._chat_approve(
        RequestContext(None, {"sid": "s1"}, {}, {"approval_id": "a1", "approved": False}, "cid")
    )  # type: ignore[arg-type]
    assert calls[0]["path"] == "/agent-sessions/s1/approve"
    assert calls[0]["body"] == {"approval_id": "a1", "approved": False}


def test_chat_resume_requires_session_ref() -> None:
    from product_forge._forge_portal import RequestContext

    portal = ProductForgePortal()
    try:
        portal._chat_resume(RequestContext(None, {"sid": "s1"}, {}, {"session_ref": " "}, "cid"))  # type: ignore[arg-type]
    except Exception as exc:
        assert getattr(exc, "code", "") == "SESSION-REF-REQUIRED"
    else:
        raise AssertionError("resume without session_ref reached the bridge")


def test_chat_stream_delegates_to_gateway_proxy(monkeypatch) -> None:
    import types

    portal = ProductForgePortal()
    portal._gateway_bridge_token = "fake-session"  # noqa: S105 - test fixture
    captured = {}

    def fake_stream(path, **k):
        captured["path"] = path
        return "SSE"

    monkeypatch.setattr(ProductForgePortal, "_bridge_stream", staticmethod(fake_stream))
    ctx = types.SimpleNamespace(
        params={"sid": "s9"}, query={}, body=None, handler=types.SimpleNamespace(headers={})
    )
    assert portal._chat_stream(ctx) == "SSE"
    assert captured["path"] == "/agent-sessions/s9/stream"


def test_capabilities_follow_supervised_bridge_state() -> None:
    portal = ProductForgePortal()
    caps = {c["id"]: c["state"] for c in portal.capabilities()}
    assert caps["chat"] == "unverified" and caps["agent-bridge"] == "unverified"
    portal.bridge_status = lambda: {"state": "running"}
    caps = {c["id"]: c["state"] for c in portal.capabilities()}
    assert caps["chat"] == "supported" and caps["agent-bridge"] == "supported"
    portal.bridge_status = lambda: {"state": "degraded"}
    caps = {c["id"]: c["state"] for c in portal.capabilities()}
    assert caps["chat"] == "degraded" and caps["agent-bridge"] == "degraded"
    portal.bridge_status = lambda: {"state": "stopped"}
    caps = {c["id"]: c["state"] for c in portal.capabilities()}
    assert caps["chat"] == "unverified" and caps["agent-bridge"] == "stopped"


def test_agent_health_merges_managed_bridge(monkeypatch) -> None:
    from product_forge._forge_portal import RequestContext

    monkeypatch.setattr(ProductForgePortal, "_bridge_get", staticmethod(lambda path: {"overall": "ok"}))
    portal = ProductForgePortal()
    portal.bridge_status = lambda: {"state": "running", "restarts": 2}
    out = portal._agent_health(RequestContext(None, {}, {}, None, "cid"))  # type: ignore[arg-type]
    assert out["overall"] == "ok"
    assert out["managed"] == {"state": "running", "restarts": 2}


def test_chat_sessions_enriches_product_names(monkeypatch) -> None:
    import product_forge.portal.adapter as adapter_mod
    from product_forge._forge_portal import RequestContext

    listing = {
        "items": [
            {"id": "s1", "state": "active", "meta": {"product_id": "p1"}},
            {"id": "s2", "state": "active", "meta": {"product_id": "p1"}},
            {"id": "s3", "state": "active", "meta": {"product_id": "missing"}},
            {"id": "s4", "state": "active"},
        ]
    }
    monkeypatch.setattr(ProductForgePortal, "_bridge_get", staticmethod(lambda path: listing))

    class _FakeStore:
        def get(self, coll, pid):
            if pid == "p1":
                return {"name": "Atlas"}
            raise KeyError(pid)

        def close(self):
            pass

    monkeypatch.setattr(adapter_mod, "_store", lambda: _FakeStore())
    out = ProductForgePortal()._chat_sessions(RequestContext(None, {}, {}, None, "cid"))  # type: ignore[arg-type]
    items = {i["id"]: i for i in out["items"]}
    assert items["s1"]["product_name"] == "Atlas"
    assert items["s2"]["product_name"] == "Atlas"
    assert "product_name" not in items["s3"]
    assert "product_name" not in items["s4"]


def _op(portal, method, path):
    for op in portal.ops:
        if op.method == method and op.path == path:
            return op
    raise AssertionError(f"op not registered: {method} {path}")


def _req(params=None, body=None):
    from product_forge._forge_portal import RequestContext

    return RequestContext(None, params or {}, {}, body, "cid")  # type: ignore[arg-type]


class _FakeStore:
    def __init__(self, docs=None):
        self.docs = docs or {}

    def get(self, collection, key):
        if key in self.docs:
            return self.docs[key]
        raise KeyError(key)

    def list(self, *a, **k):
        return []

    def close(self):
        pass


def _fake_store(monkeypatch, docs=None):
    import product_forge.portal.adapter as adapter_mod

    monkeypatch.setattr(adapter_mod, "_store", lambda: _FakeStore(docs))


def test_missing_product_is_typed_404_not_500(monkeypatch) -> None:
    _fake_store(monkeypatch)
    op = _op(ProductForgePortal(), "GET", "/products/{pid}")
    try:
        op.handler(_req({"pid": "nope"}))
    except Exception as exc:
        assert getattr(exc, "code", "") == "PORTAL-NOT-FOUND"
        assert getattr(exc, "http", 0) == 404
    else:
        raise AssertionError("missing product should be a typed 404")


def test_product_create_requires_workspace_and_name(monkeypatch) -> None:
    _fake_store(monkeypatch)
    op = _op(ProductForgePortal(), "POST", "/products")
    for body in [{"name": "x"}, {"workspace_id": "w1"}]:
        try:
            op.handler(_req(body=body))
        except Exception as exc:
            assert getattr(exc, "code", "") == "PORTAL-MISSING-FIELD"
        else:
            raise AssertionError(f"missing field accepted: {body}")


def test_task_create_requires_title(monkeypatch) -> None:
    _fake_store(monkeypatch, {"p1": {"id": "p1", "workspace_id": "w1", "name": "Prod"}})
    op = _op(ProductForgePortal(), "POST", "/products/{pid}/tasks")
    try:
        op.handler(_req({"pid": "p1"}, {"title": "  "}))
    except Exception as exc:
        assert getattr(exc, "code", "") == "PORTAL-MISSING-FIELD"
    else:
        raise AssertionError("task without title accepted")


def test_query_execute_requires_source_and_statement(monkeypatch) -> None:
    _fake_store(monkeypatch)
    op = _op(ProductForgePortal(), "POST", "/products/{pid}/queries/execute")
    try:
        op.handler(_req({"pid": "p1"}, {"statement": "select 1"}))
    except Exception as exc:
        assert getattr(exc, "code", "") == "PORTAL-MISSING-FIELD"
    else:
        raise AssertionError("source_id was not required")
    try:
        op.handler(_req({"pid": "p1"}, {"source_id": "s1"}))
    except Exception as exc:
        assert getattr(exc, "code", "") == "PORTAL-VALIDATION"
    else:
        raise AssertionError("missing statement/spec was not rejected")


def test_kn_query_requires_question(monkeypatch) -> None:
    _fake_store(monkeypatch)
    op = _op(ProductForgePortal(), "POST", "/products/{pid}/knowledge/query")
    try:
        op.handler(_req({"pid": "p1"}, {}))
    except Exception as exc:
        assert getattr(exc, "code", "") == "PORTAL-MISSING-FIELD"
    else:
        raise AssertionError("knowledge query without question accepted")


def test_value_error_maps_to_422(monkeypatch) -> None:
    _fake_store(
        monkeypatch,
        {
            "t1": {
                "id": "t1",
                "product_id": "p1",
                "workspace_id": "w1",
                "board_id": "b1",
                "title": "t",
                "version": 1,
            }
        },
    )
    op = _op(ProductForgePortal(), "POST", "/products/{pid}/tasks/{tid}/move")
    try:
        op.handler(_req({"pid": "p1", "tid": "t1"}, {"expected_version": "abc"}))
    except Exception as exc:
        assert getattr(exc, "code", "") == "PORTAL-VALIDATION"
        assert getattr(exc, "http", 0) == 422
    else:
        raise AssertionError("non-integer expected_version accepted")


def test_error_translator_maps_pydantic_and_value_error() -> None:
    from product_forge.domain.models import Workspace
    from product_forge.portal.adapter import _translate_handler_errors

    def bad_model(ctx):
        Workspace.model_validate({"name": ["not-a-string"]})

    def bad_int(ctx):
        raise ValueError("expected_version must be an integer")

    for handler in (bad_model, bad_int):
        try:
            _translate_handler_errors(handler)(_req())
        except Exception as exc:
            assert getattr(exc, "code", "") == "PORTAL-VALIDATION"
            assert getattr(exc, "http", 0) == 422
        else:
            raise AssertionError(f"{handler.__name__} was not translated")


def test_error_translator_passes_portal_error() -> None:
    from product_forge._forge_portal import PortalError
    from product_forge.portal.adapter import _translate_handler_errors

    def typed(ctx):
        raise PortalError("CUSTOM-CODE", "already typed", http=409)

    try:
        _translate_handler_errors(typed)(_req())
    except Exception as exc:
        assert getattr(exc, "code", "") == "CUSTOM-CODE"
        assert getattr(exc, "http", 0) == 409
    else:
        raise AssertionError("typed error was swallowed")


def test_bridge_call_surfaces_upstream_error_as_envelope(monkeypatch) -> None:
    seen = {}

    def fake_request(path, *, method="GET", body=None, token_override="", timeout=2.0):
        seen["timeout"] = timeout
        return {"state": "error", "status": 422, "error": {"code": "FAB-VALIDATION", "message": "bad"}}

    monkeypatch.setattr(ProductForgePortal, "_bridge_request", staticmethod(fake_request))
    try:
        ProductForgePortal()._bridge_call("/x", method="POST", timeout=280.0)
    except Exception as exc:
        assert getattr(exc, "code", "") == "BRIDGE-UPSTREAM"
        assert getattr(exc, "http", 0) == 422
    else:
        raise AssertionError("upstream 4xx was not translated")
    assert seen["timeout"] == 280.0


def test_bridge_call_maps_unavailable_to_503(monkeypatch) -> None:
    monkeypatch.setattr(
        ProductForgePortal,
        "_bridge_request",
        staticmethod(lambda *a, **k: {"state": "unavailable", "reason": "connection refused"}),
    )
    try:
        ProductForgePortal()._bridge_call("/status")
    except Exception as exc:
        assert getattr(exc, "code", "") == "BRIDGE-UPSTREAM"
        assert getattr(exc, "http", 0) == 503
        assert getattr(exc, "retryable", False) is True
    else:
        raise AssertionError("unavailable bridge did not raise 503")


def test_bridge_call_passes_success_through(monkeypatch) -> None:
    monkeypatch.setattr(
        ProductForgePortal, "_bridge_request", staticmethod(lambda *a, **k: {"accepted": True})
    )
    assert ProductForgePortal()._bridge_call("/ok") == {"accepted": True}
