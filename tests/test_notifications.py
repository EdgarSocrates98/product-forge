from product_forge.notifications import register_channel


def test_webhook_channel_is_disabled_and_secret_is_reference_only(tmp_path, monkeypatch):
    from product_forge.config import db_path, load_config
    from product_forge.store.sqlite import Store

    monkeypatch.setenv("PRODUCT_FORGE_HOME", str(tmp_path / "pf"))
    home = tmp_path / "pf"
    st = Store(db_path(home, load_config(home)))
    try:
        ch = register_channel(st, kind="webhook", name="ops",
                              config={"url": "https://example.test/hook", "secret_env": "PF_HOOK"})
        assert ch["enabled"] is False
        assert "PF_HOOK" in ch["config"]["secret_env"]
        assert st.list("notifications", limit=10)[0]["enabled"] is False
    finally:
        st.close()
