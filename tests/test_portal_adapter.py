from product_forge.portal.adapter import ProductForgePortal


def test_product_portal_exposes_pm_pa_navigation_and_chat() -> None:
    portal = ProductForgePortal()
    nav = {item["id"] for item in portal.nav()}
    assert {"products", "boards", "roadmaps", "knowledge", "chat"} <= nav
    capabilities = {item["id"] for item in portal.capabilities()}
    assert {"chat", "agent-bridge"} <= capabilities


def test_bridge_unavailable_is_honest(monkeypatch) -> None:
    monkeypatch.setenv("FORGE_BRIDGE_URL", "http://127.0.0.1:1")
    result = ProductForgePortal._bridge_get("/status")
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
            return iter([
                b"id: 7\n",
                b"event: turn.completed\n",
                b"data: {\"payload\": {\"ok\": true}}\n",
                b"\n",
            ])

        def close(self):
            pass

    monkeypatch.setattr("product_forge.portal.adapter.urllib.request.urlopen", lambda *a, **k: Response())
    token = "test-token"  # noqa: S105 - fixture credential
    result = ProductForgePortal._bridge_stream(
        "/agent-sessions/ses_1/stream?after_seq=6", token_override=token
    )
    assert list(result.events) == [{
        "payload": {"ok": True},
        "seq": 7,
        "type": "turn.completed",
        "sse_id": "7",
        "sse_event": "turn.completed",
    }]
