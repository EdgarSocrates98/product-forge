"""Foreground Product Forge portal composition.

The portal command is the explicit user action that starts the local UI and
the Agent Bridge. Install remains side-effect limited: it prepares assets and
configuration but never starts provider processes or requests credentials.
"""

from __future__ import annotations

import json
import os
import re
import shutil
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
    if pid <= 0:
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
    executable = shutil.which("forge-bridge")
    if executable:
        return [executable, "serve", "--port", str(port)]
    return [sys.executable, "-m", "forge_agent_bridge.cli", "serve", "--port", str(port)]


def _free_loopback_port(preferred: int = 0) -> int:
    """Pick a loopback port without making 8471 a hidden global singleton."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(("127.0.0.1", preferred))
        return int(sock.getsockname()[1])


def _wait_bridge_ready(port: int, token_file: Path, timeout: float = 8.0) -> None:
    """Wait for the managed bridge health endpoint, not just its PID."""
    import urllib.request

    token = token_file.read_text(encoding="utf-8").strip()
    deadline = time.monotonic() + timeout
    last_error = "not started"
    while time.monotonic() < deadline:
        try:
            request = urllib.request.Request(
                f"http://127.0.0.1:{port}/status",
                headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
            )
            with urllib.request.urlopen(request, timeout=0.5) as response:  # noqa: S310 - loopback URL validated
                if response.status == 200:
                    return
            last_error = "unexpected health status"
        except Exception as exc:  # noqa: BLE001 - startup retry boundary
            last_error = str(exc)
        time.sleep(0.1)
    raise RuntimeError(f"forge-bridge did not become ready on port {port}: {last_error}")


def _bridge_environment(env: dict[str, str]) -> dict[str, str]:
    """Add the sibling checkout only for development worktrees.

    Installed users use the ``forge-bridge`` console script or an installed
    Python package.  In a three-repository checkout this fallback makes the
    documented single-command portal smoke test work without a second manual
    server command, while never downloading code or mutating the environment.
    """
    if shutil.which("forge-bridge"):
        return env
    sibling = Path(__file__).resolve().parents[4] / "forge-agent-bridge" / "src"
    if sibling.is_dir():
        existing = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = os.pathsep.join(filter(None, [str(sibling), existing]))
    return env


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
    bridge = None
    server = None
    manifest = {
        "schema": "productforge/PortalComposition/1",
        "portal": {"pid": os.getpid(), "requested_port": port},
        "bridge": {"port": bridge_port, "command": _bridge_command(bridge_port)},
        "config_home": str(home),
        "provider_credentials": "deferred_until_first_use",
        "profile": cfg.get("install_profile", "recommended"),
        "database": runtime_state,
        "state": "starting",
    }
    _write_manifest(manifest_path, manifest)
    try:
        # The adapter and the child bridge must agree on the dynamically
        # selected port.  This is what makes `productforge portal --port ...`
        # a self-contained composition instead of relying on port 8471.
        bridge_url = f"http://127.0.0.1:{bridge_port}"
        os.environ["FORGE_BRIDGE_URL"] = bridge_url
        bridge_env = _bridge_environment(os.environ.copy())
        bridge_env["FORGE_BRIDGE_URL"] = bridge_url
        bridge = subprocess.Popen(  # noqa: S603 - executable is fixed/discovered locally
            _bridge_command(bridge_port),
            cwd=str(home),
            env=bridge_env,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL if quiet else None,
            stderr=subprocess.DEVNULL if quiet else None,
            start_new_session=(os.name != "nt"),
            preexec_fn=_child_death_signal if os.name != "nt" else None,
        )
        if bridge.poll() is not None:
            raise RuntimeError("forge-bridge exited before the portal could start")
        _wait_bridge_ready(bridge_port, Path(os.environ.get(
            "FORGE_BRIDGE_TOKEN_FILE", "~/.forge-bridge/pair.token")).expanduser())
        adapter = ProductForgePortal()
        adapter.assets_dir = assets
        server = PortalServer(adapter, port=port, quiet=quiet)
        thread = server.serve_in_thread()
        manifest["portal"].update({"port": server.port, "url": server.url})
        manifest["bridge"].update({"pid": bridge.pid, "url": bridge_url})
        manifest["state"] = "running"
        _write_manifest(manifest_path, manifest)
        print(f"Product Forge portal: {server.url}")
        if open_browser:
            try:
                import webbrowser

                webbrowser.open(server.url)
            except Exception as exc:  # noqa: BLE001 - browser open is best effort
                print(f"could not open browser: {exc}")
        while thread.is_alive():
            thread.join(timeout=0.5)
    except KeyboardInterrupt:
        pass
    finally:
        if server is not None:
            server.shutdown()
            server.server_close()
        if bridge is not None and bridge.poll() is None:
            if os.name == "nt":
                bridge.terminate()
            else:
                os.killpg(bridge.pid, signal.SIGTERM)
            try:
                bridge.wait(timeout=5)
            except subprocess.TimeoutExpired:
                bridge.kill()
        manifest["state"] = "stopped"
        manifest["stopped_at"] = time.time()
        _write_manifest(manifest_path, manifest)
