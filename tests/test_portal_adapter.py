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
