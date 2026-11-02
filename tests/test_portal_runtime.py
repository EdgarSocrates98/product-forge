from product_forge.portal.runtime import _assets_dir, _bridge_command, _free_loopback_port


def test_product_portal_assets_are_bundled() -> None:
    assets = _assets_dir()
    assert (assets / "index.html").is_file()
    # The installed portal must resolve to the compiled Angular bundle.  A
    # legacy app.js fallback is only allowed when no Angular bundle exists.
    assert any(assets.glob("main-*.js"))
    assert any(assets.glob("styles-*.css")) or (assets / "styles.css").is_file()


def test_bridge_command_is_loopback_service_command() -> None:
    command = _bridge_command(8471)
    assert command[-3:] == ["serve", "--port", "8471"]


def test_bridge_port_zero_is_ephemeral_and_bindable() -> None:
    port = _free_loopback_port()
    assert 0 < port <= 65535
