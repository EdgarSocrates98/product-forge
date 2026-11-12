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
    import sys

    assert command[:2] == [sys.executable, "-m"]


def test_bridge_port_zero_is_ephemeral_and_bindable() -> None:
    port = _free_loopback_port()
    assert 0 < port <= 65535


class _FakeProc:
    """Minimal Popen stand-in: poll/returncode/pid plus stop helpers."""

    def __init__(self, pid: int = 1234) -> None:
        self.pid = pid
        self.returncode: int | None = None

    def poll(self):
        return self.returncode

    def terminate(self) -> None:
        self.returncode = 0

    def wait(self, timeout: float | None = None) -> int:
        self.returncode = 0
        return 0

    def kill(self) -> None:
        self.returncode = -9


def _supervisor(tmp_path):
    from product_forge.portal import runtime as rt

    return rt._BridgeSupervisor(
        port=18471, home=tmp_path, env={}, quiet=True, token_file=tmp_path / "pair.token"
    )


def test_lifecycle_log_appends_jsonl(tmp_path) -> None:
    import json

    from product_forge.portal import runtime as rt

    rt._log_event(tmp_path, "portal.running", url="http://127.0.0.1:9")
    rt._log_event(tmp_path, "bridge.exited", exit_code=1)
    lines = rt._lifecycle_log(tmp_path).read_text(encoding="utf-8").splitlines()
    events = [json.loads(line)["event"] for line in lines]
    assert events == ["portal.running", "bridge.exited"]


def test_supervisor_status_is_honest_without_proc(tmp_path) -> None:
    status = _supervisor(tmp_path).status()
    assert status["state"] == "stopped"
    assert status["pid"] is None
    assert status["restarts"] == 0


def test_supervisor_restarts_dead_bridge_and_repairs(monkeypatch, tmp_path) -> None:
    from product_forge.portal import runtime as rt

    sup = _supervisor(tmp_path)
    dead = _FakeProc(1111)
    dead.returncode = 1
    sup.proc = dead
    sup.state = "running"
    live = _FakeProc(2222)
    monkeypatch.setattr(sup, "_spawn", lambda: live)
    monkeypatch.setattr(rt, "_wait_bridge_ready", lambda *a, **k: None)
    monkeypatch.setattr(sup, "_repair_gateway", lambda adapter: None)
    status = sup.check()
    assert status["state"] == "running"
    assert status["restarts"] == 1
    assert status["last_exit"] == 1
    assert status["pid"] == 2222
    events = rt._lifecycle_log(tmp_path).read_text(encoding="utf-8")
    assert "bridge.exited" in events and "bridge.restarted" in events


def test_supervisor_stays_degraded_after_restart_cap(monkeypatch, tmp_path) -> None:
    sup = _supervisor(tmp_path)
    dead = _FakeProc()
    dead.returncode = -1
    sup.proc = dead
    sup.state = "running"
    sup.restarts = sup.MAX_RESTARTS
    monkeypatch.setattr(sup, "_spawn", lambda: _FakeProc())
    status = sup.check()
    assert status["state"] == "degraded"
    assert status["restarts"] == sup.MAX_RESTARTS
    assert status["pid"] is None


def test_supervisor_stop_is_idempotent(tmp_path) -> None:
    sup = _supervisor(tmp_path)
    sup.proc = _FakeProc()
    sup.stop()
    assert sup.state == "stopped"
    sup.stop()
    assert sup.state == "stopped"
