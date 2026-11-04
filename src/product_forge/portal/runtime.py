"""Foreground Product Forge portal composition.

The portal command is the explicit user action that starts the local UI and
the Agent Bridge. Install remains side-effect limited: it prepares assets and
configuration but never starts provider processes or requests credentials.
"""

from __future__ import annotations

import json
import os
import re
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from .._forge_portal import PortalServer
from ..config import home_dir, load_config
from ..portal.adapter import ProductForgePortal


def _assets_dir() -> Path:
    """Return the validated UI bundle shipped with the installed product.

    Angular CLI emits ``browser/index.html`` in current application builds.
    Older releases placed the file directly under ``angular`` and the legacy
    server assets live directly under ``portal_assets``.  Keep those paths as
    explicit compatibility fallbacks, but always prefer the production
    Angular bundle and never silently select the legacy UI when a valid Angular
    bundle is present.
    """
    def valid(candidate: Path) -> bool:
        index = candidate / "index.html"
        if not candidate.is_dir() or not index.is_file():
            return False
        # A compiled Angular bundle must be self-contained.  Fail at startup
        # with a useful install error instead of serving a page that later
        # fails with a cascade of opaque 404s.
        if candidate.name == "browser":
            manifest = candidate / "manifest.json"
            if not manifest.is_file():
                return False
            try:
                metadata = json.loads(manifest.read_text(encoding="utf-8"))
                if metadata.get("schema") != "forge/ProductForgePortalManifest/v1":
                    return False
                html = index.read_text(encoding="utf-8")
            except (OSError, json.JSONDecodeError, UnicodeDecodeError):
                return False
            resources = [
                resource for resource in re.findall(r'(?:src|href)="([^"?#]+)', html)
                if resource not in {"/", ""}
            ]
            return all((candidate / resource.lstrip("/")).is_file() for resource in resources)
        return True

    angular_override = os.environ.get("PRODUCT_FORGE_ANGULAR_ASSETS")
    if angular_override:
        candidate = Path(angular_override).expanduser().resolve()
        if valid(candidate):
            return candidate
    bundled = Path(__file__).resolve().parents[1] / "portal_assets"
    embedded_angular = bundled / "angular"
    for candidate in (embedded_angular / "browser", embedded_angular):
        if valid(candidate):
            return candidate
    override = os.environ.get("PRODUCT_FORGE_PORTAL_ASSETS")
    if override:
        candidate = Path(override).expanduser().resolve()
        if valid(candidate):
            return candidate
    raise RuntimeError(
        "Product Forge portal assets are not installed; reinstall product-forge "
        "or set PRODUCT_FORGE_PORTAL_ASSETS"
    )


def _manifest_path(home: Path) -> Path:
    return home / "portal" / "composition.json"


def _pid_alive(pid: int) -> bool:
    """Liveness probe that is honest on Windows too.

    ``os.kill(pid, 0)`` is not a reliable liveness check there — its signal-0
    behaviour has changed across CPython versions and can either error out on
    a live process or terminate it.  ``OpenProcess`` +
    ``GetExitCodeProcess`` (STILL_ACTIVE) is the stable contract.
    """
    if pid <= 0:
        return False
    if os.name == "nt":
        try:
            import ctypes

            kernel32 = ctypes.windll.kernel32
            handle = kernel32.OpenProcess(0x1000, False, pid)  # QUERY_LIMITED_INFORMATION
            if not handle:
                return False
            try:
                code = ctypes.c_ulong()
                if not kernel32.GetExitCodeProcess(handle, ctypes.byref(code)):
                    return False
                return code.value == 259  # STILL_ACTIVE
            finally:
                kernel32.CloseHandle(handle)
        except (AttributeError, OSError):
            return False
    try:
        os.kill(pid, 0)
    except (OSError, ProcessLookupError):
        return False
    return True


def _terminate_pid(pid: int) -> None:
    """Best-effort cleanup for a stale *bridge-owned* child.

    A stale manifest can outlive the launcher, but a PID can be reused.  Never
    kill a process merely because the old manifest contains its number: verify
    the command is one of the bridge launch forms first.
    """
    if not _pid_alive(pid):
        return
    if os.name != "nt":
        try:
            command = Path(f"/proc/{pid}/cmdline").read_bytes().replace(b"\0", b" ").decode()
        except OSError:
            return
        if "forge_agent_bridge.cli" not in command and "forge-bridge" not in command:
            return
    try:
        if os.name != "nt":
            os.killpg(pid, signal.SIGTERM)
        else:
            os.kill(pid, signal.SIGTERM)
    except (OSError, ProcessLookupError):
        return


def _child_death_signal() -> None:
    """Ask Linux to terminate the managed Bridge if this launcher dies."""
    if os.name == "nt":
        return
    try:
        import ctypes

        # Linux PR_SET_PDEATHSIG = 1.  Failure is harmless; normal teardown
        # and stale-manifest reconciliation remain the fallback mechanisms.
        ctypes.CDLL(None).prctl(1, signal.SIGTERM)
    except (AttributeError, OSError):
        pass
def _read_manifest(path: Path) -> dict[str, Any] | None:
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return doc if isinstance(doc, dict) else None


def _write_manifest(path: Path, doc: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(path)


def _bridge_command(port: int) -> list[str]:
    # Product Forge ships the Bridge package in the same wheel.  Resolving a
    # console script from PATH could silently run a different Bridge version
    # than the one whose contracts the portal was built against.
    return [sys.executable, "-m", "forge_agent_bridge.cli", "serve", "--port", str(port)]


def _free_loopback_port(preferred: int = 0) -> int:
    """Pick a loopback port without making 8471 a hidden global singleton."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(("127.0.0.1", preferred))
        return int(sock.getsockname()[1])


def _wait_bridge_ready(
    port: int,
    token_file: Path,
    timeout: float = 8.0,
    process: subprocess.Popen[bytes] | subprocess.Popen[str] | None = None,
) -> None:
    """Wait for managed Bridge storage, credentials and authenticated health.

    ``pair.token`` is created by the Bridge after its storage is initialized,
    so reading it before entering the retry loop creates a first-run race.  A
    missing token is therefore a readiness state, not an immediate failure.
    """
    import urllib.error
    import urllib.request

    deadline = time.monotonic() + timeout
    last_error = "not started"
    while time.monotonic() < deadline:
        if process is not None and process.poll() is not None:
            raise RuntimeError("forge-bridge exited during startup")
        try:
            if not token_file.is_file():
                last_error = "pair.token is not available yet"
                time.sleep(0.05)
                continue
            if os.name == "posix":
                # POSIX mode check only: on Windows chmod() is a no-op
                # (read-only bit only) and stat() reports 0o666 regardless,
                # so the check can never pass there. Token privacy on
                # Windows comes from the user-profile ACL instead.
                mode = token_file.stat().st_mode & 0o777
                if mode & 0o077:
                    raise PermissionError("pair.token permissions are too broad")
            token = token_file.read_text(encoding="utf-8").strip()
            if not token:
                last_error = "pair.token is empty"
                time.sleep(0.05)
                continue
            request = urllib.request.Request(
                f"http://127.0.0.1:{port}/status",
                headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
            )
            with urllib.request.urlopen(request, timeout=0.5) as response:  # noqa: S310 - loopback URL validated
                if response.status == 200:
                    return
            last_error = "unexpected health status"
        except (OSError, ValueError, urllib.error.URLError, PermissionError) as exc:
            last_error = str(exc)
        time.sleep(0.05)
    raise RuntimeError(f"forge-bridge did not become ready on port {port}: {last_error}")


def _lifecycle_log(home: Path) -> Path:
    return home / "portal" / "lifecycle.jsonl"


def _log_event(home: Path, event: str, **fields: Any) -> None:
    """Append one structured lifecycle record to the portal JSONL log.

    Bounded by a single rotation at 512 KiB.  Logging failures are swallowed:
    observability must never take the composition down.
    """
    path = _lifecycle_log(home)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.is_file() and path.stat().st_size > 512 * 1024:
            path.replace(path.with_name("lifecycle.1.jsonl"))
        record = {"ts": round(time.time(), 3), "event": event, **fields}
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    except OSError:
        pass


def _bridge_environment(env: dict[str, str]) -> dict[str, str]:
    """Make the embedded Bridge importable in a source checkout.

    The child is always launched with ``sys.executable -m`` so this path is
    only a development fallback; an unrelated ``forge-bridge`` on PATH is
    never allowed to shadow the bundled package.
    """
    sibling = Path(__file__).resolve().parents[4] / "forge-agent-bridge" / "src"
    if sibling.is_dir():
        existing = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = os.pathsep.join(filter(None, [str(sibling), existing]))
    return env


class _BridgeSupervisor:
    """Restart the managed Bridge on unexpected exit, then re-pair the gateway.

    Bounded: at most ``MAX_RESTARTS`` respawns per composition.  Beyond the cap
    the portal keeps serving with an honest ``degraded`` bridge state instead
    of crash-looping a child that cannot stay up.  Every transition lands in
    the structured lifecycle log and in the composition manifest.
    """

    MAX_RESTARTS = 3
    RETRY_DELAY_S = 2.0

    def __init__(self, *, port: int, home: Path, env: dict[str, str],
                 quiet: bool, token_file: Path) -> None:
        self._port = port
        self._home = home
        self._env = env
        self._quiet = quiet
        self._token_file = token_file
        self.proc: subprocess.Popen[Any] | None = None
        self.restarts = 0
        self.last_exit: int | None = None
        self.state = "stopped"
        self.gateway = "unpaired"
        self._not_before = 0.0

    def _spawn(self) -> subprocess.Popen[Any]:
        return subprocess.Popen(  # noqa: S603 - executable is fixed/discovered locally
            _bridge_command(self._port),
            cwd=str(self._home),
            env=self._env,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL if self._quiet else None,
            stderr=subprocess.DEVNULL if self._quiet else None,
            start_new_session=(os.name != "nt"),
            preexec_fn=_child_death_signal if os.name != "nt" else None,
        )

    def start(self) -> None:
        self.proc = self._spawn()
        self.state = "starting"
        if self.proc.poll() is not None:
            raise RuntimeError("forge-bridge exited before the portal could start")
        _wait_bridge_ready(self._port, self._token_file, process=self.proc)
        self.state = "running"
        _log_event(self._home, "bridge.started", pid=self.proc.pid, port=self._port)

    def check(self, *, adapter: ProductForgePortal | None = None) -> dict[str, Any]:
        """One supervision step; returns the manifest-friendly status."""
        if self.proc is None or self.proc.poll() is None:
            return self.status()
        self.last_exit = self.proc.returncode
        self.proc = None
        _log_event(self._home, "bridge.exited", exit_code=self.last_exit,
                   restarts=self.restarts)
        if self.restarts >= self.MAX_RESTARTS:
            self.state = "degraded"
            _log_event(self._home, "bridge.restart_cap", max=self.MAX_RESTARTS)
            return self.status()
        if time.monotonic() < self._not_before:
            self.state = "restarting"
            return self.status()
        self.restarts += 1
        self.state = "restarting"
        try:
            self.proc = self._spawn()
            _wait_bridge_ready(self._port, self._token_file, process=self.proc)
        except Exception as exc:  # noqa: BLE001 - retry on the next check
            self.proc = None
            self._not_before = time.monotonic() + self.RETRY_DELAY_S
            _log_event(self._home, "bridge.restart_failed", error=str(exc),
                       restarts=self.restarts)
            return self.status()
        self.state = "running"
        _log_event(self._home, "bridge.restarted", pid=self.proc.pid,
                   restarts=self.restarts)
        self._repair_gateway(adapter)
        return self.status()

    def _repair_gateway(self, adapter: ProductForgePortal | None) -> None:
        if adapter is None:
            return
        try:
            bootstrap = adapter._bridge_bootstrap(ctx=None)
            self.gateway = (
                "paired" if bootstrap.get("connected")
                else f"unpaired:{bootstrap.get('bridge', {}).get('reason', '?')}")
        except Exception as exc:  # noqa: BLE001 - pairing stays retryable
            self.gateway = f"unpaired:{type(exc).__name__}"
            _log_event(self._home, "bridge.repair_failed", error=str(exc))

    def status(self) -> dict[str, Any]:
        pid = self.proc.pid if self.proc is not None and self.proc.poll() is None else None
        return {
            "state": self.state,
            "pid": pid,
            "port": self._port,
            "url": f"http://127.0.0.1:{self._port}",
            "restarts": self.restarts,
            "last_exit": self.last_exit,
            "gateway": self.gateway,
        }

    def stop(self) -> None:
        if self.proc is not None and self.proc.poll() is None:
            if os.name == "nt":
                self.proc.terminate()
            else:
                try:
                    os.killpg(self.proc.pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass  # died between poll() and killpg — already gone
                except PermissionError:
                    # A supervisor may not own a detached process group (for
                    # example after a handoff or under a restricted runner).
                    # Fall back to terminating the child itself.
                    self.proc.terminate()
            try:
                self.proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.proc.kill()
        self.state = "stopped"


def run(*, port: int = 0, bridge_port: int = 8471, open_browser: bool = True,
        quiet: bool = True) -> None:
    """Start the Product Forge portal composition until interrupted."""
    assets = _assets_dir()
    home = home_dir()
    manifest_path = _manifest_path(home)
    previous = _read_manifest(manifest_path)
    if previous:
        portal_pid = int(previous.get("portal", {}).get("pid", 0))
        bridge_pid = int(previous.get("bridge", {}).get("pid", 0))
        if _pid_alive(portal_pid):
            raise RuntimeError(
                "Product Forge portal is already running at "
                f"{previous.get('portal', {}).get('url', 'unknown URL')}"
            )
        # A killed parent can leave the detached bridge alive. Reconcile the
        # manifest before binding the next port; this makes repeated launches
        # safe after terminal/window crashes.
        if _pid_alive(bridge_pid):
            _terminate_pid(bridge_pid)

    cfg = load_config(home)
    # 0 means automatic.  Keep 8471 accepted for compatibility, but if it is
    # already occupied choose a safe loopback port instead of attaching to an
    # unrelated process or leaving an orphaned bridge behind.
    if bridge_port == 0:
        bridge_port = _free_loopback_port()
    else:
        try:
            bridge_port = _free_loopback_port(bridge_port)
        except OSError:
            bridge_port = _free_loopback_port()
    from ..install.managed_runtime import ensure_postgres
    runtime_state = ensure_postgres(home, profile=str(cfg.get("install_profile", "recommended")))
    supervisor: _BridgeSupervisor | None = None
    server = None
    manifest = {
        "schema": "productforge/PortalComposition/1",
        "portal": {"pid": os.getpid(), "requested_port": port},
        "bridge": {"port": bridge_port, "command": _bridge_command(bridge_port)},
        "config_home": str(home),
        "provider_credentials": "deferred_until_first_use",
        "profile": cfg.get("install_profile", "recommended"),
        "database": runtime_state,
        "lifecycle_log": str(_lifecycle_log(home)),
        "state": "starting",
    }
    _write_manifest(manifest_path, manifest)
    _log_event(home, "portal.starting", pid=os.getpid(), requested_port=port)
    try:
        # Provision ~/.forge-bridge in-process through the vendored package —
        # idempotent (write-if-absent), so `productforge portal` stays a
        # single-command entry even when `productforge install` was skipped.
        try:
            from forge_agent_bridge.install import lifecycle as _bridge_lc
            manifest["bridge"]["provision"] = _bridge_lc.install(
                scope="user", profile="recommended", yes=True)
        except Exception as exc:  # noqa: BLE001 - serve creates the minimum anyway
            manifest["bridge"]["provision"] = {
                "state": "unverified", "error": str(exc)}

        # The adapter and the child bridge must agree on the dynamically
        # selected port.  This is what makes `productforge portal --port ...`
        # a self-contained composition instead of relying on port 8471.
        bridge_url = f"http://127.0.0.1:{bridge_port}"
        os.environ["FORGE_BRIDGE_URL"] = bridge_url
        bridge_env = _bridge_environment(os.environ.copy())
        bridge_env["FORGE_BRIDGE_URL"] = bridge_url
        token_file = Path(os.environ.get(
            "FORGE_BRIDGE_TOKEN_FILE", "~/.forge-bridge/pair.token")).expanduser()
        supervisor = _BridgeSupervisor(
            port=bridge_port, home=home, env=bridge_env, quiet=quiet,
            token_file=token_file)
        supervisor.start()
        adapter = ProductForgePortal()
        adapter.assets_dir = assets
        adapter.bridge_status = supervisor.status
        # Pre-pair the gateway session (pair.token → /pair/exchange) so the
        # first browser request hits a ready bridge — no bootstrap round-trip.
        try:
            bootstrap = adapter._bridge_bootstrap(ctx=None)
            supervisor.gateway = (
                "paired" if bootstrap.get("connected")
                else f"unpaired:{bootstrap.get('bridge', {}).get('reason', '?')}")
        except Exception as exc:  # noqa: BLE001 - bootstrap stays retryable client-side
            supervisor.gateway = f"unpaired:{type(exc).__name__}"
        server = PortalServer(adapter, port=port, quiet=quiet)
        thread = server.serve_in_thread()
        manifest["portal"].update({"port": server.port, "url": server.url})
        manifest["bridge"].update(supervisor.status())
        manifest["state"] = "running"
        _write_manifest(manifest_path, manifest)
        _log_event(home, "portal.running", url=server.url,
                   bridge_url=bridge_url, gateway=supervisor.gateway)
        print(f"Product Forge portal: {server.url}")
        print(f"Agent Bridge: {bridge_url} ({supervisor.gateway})")
        if open_browser:
            try:
                import webbrowser

                webbrowser.open(server.url)
            except Exception as exc:  # noqa: BLE001 - browser open is best effort
                print(f"could not open browser: {exc}")
        last_sig: tuple[Any, ...] | None = None
        while thread.is_alive():
            status = supervisor.check(adapter=adapter)
            sig = (status["state"], status["pid"], status["restarts"],
                   status["gateway"])
            if sig != last_sig:
                manifest["bridge"].update(status)
                _write_manifest(manifest_path, manifest)
                last_sig = sig
            thread.join(timeout=0.5)
    except KeyboardInterrupt:
        pass
    finally:
        if server is not None:
            server.shutdown()
            server.server_close()
        if supervisor is not None:
            supervisor.stop()
        manifest["state"] = "stopped"
        manifest["stopped_at"] = time.time()
        _write_manifest(manifest_path, manifest)
        _log_event(home, "portal.stopped", pid=os.getpid())
