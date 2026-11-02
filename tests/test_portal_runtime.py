from product_forge.portal.runtime import _assets_dir, _bridge_command


def test_product_portal_assets_are_bundled() -> None:
    assets = _assets_dir()
    assert (assets / "index.html").is_file()
    assert (assets / "app.js").is_file()
    assert (assets / "style.css").is_file()


def test_bridge_command_is_loopback_service_command() -> None:
    command = _bridge_command(8471)
    assert command[-3:] == ["serve", "--port", "8471"]
