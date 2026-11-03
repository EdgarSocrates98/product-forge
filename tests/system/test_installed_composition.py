"""Installed Product Forge → Portal → Bridge journey.

The test is opt-in because it builds and installs a wheel. CI enables it in a
dedicated fake-provider lane; real-provider lanes must inject credentials and
set their provider matrix explicitly.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration


def _request(base: str, token: str, path: str, *, method: str = "GET", body: dict | None = None) -> dict:
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(  # noqa: S310 - loopback harness
        f"{base}{path}",
        data=data,
        method=method,
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
            "X-Forge-Session": token,
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:  # noqa: S310 - loopback harness
            return json.loads(response.read() or b"{}")
    except urllib.error.HTTPError as error:
        detail = error.read().decode(errors="replace")
        raise AssertionError(f"{method} {path} -> {error.code}: {detail}") from error


def test_installed_composition_fake_provider(tmp_path: Path) -> None:
    if os.environ.get("PRODUCT_FORGE_SYSTEM_HARNESS") != "1":
        pytest.skip("set PRODUCT_FORGE_SYSTEM_HARNESS=1 to run the installed-system lane")
    uv = shutil.which("uv")
    if not uv:
        pytest.skip("uv is required for the installed-system lane")

    repo = Path(__file__).resolve().parents[2]
    wheelhouse = tmp_path / "wheelhouse"
    subprocess.run([uv, "build", "--out-dir", str(wheelhouse)], cwd=repo, check=True)  # noqa: S603
    wheel = next(wheelhouse.glob("product_forge-*.whl"))
    venv = tmp_path / "venv"
    subprocess.run([uv, "venv", str(venv)], cwd=repo, check=True)  # noqa: S603
    python = venv / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    subprocess.run([uv, "pip", "install", "--python", str(python), str(wheel)], check=True)  # noqa: S603
    product_home = tmp_path / "product-home"
    process_env = {
        **os.environ,
        "HOME": str(tmp_path / "home"),
        "PRODUCT_FORGE_HOME": str(product_home),
    }
    command = [str(venv / ("Scripts/productforge.exe" if os.name == "nt" else "bin/productforge")),
               "portal", "--no-open", "--port", "0"]
    # Keep the installed server log visible when the opt-in lane fails. A
    # generic 500 envelope is intentionally safe for clients, but without
    # the child log the system harness cannot diagnose a broken bundle.
    process = subprocess.Popen(command, env=process_env, stdout=None, stderr=None)  # noqa: S603
    try:
        composition_path = product_home / "portal" / "composition.json"
        composition: dict = {}
        for _ in range(100):
            if composition_path.is_file():
                composition = json.loads(composition_path.read_text(encoding="utf-8"))
                if composition.get("state") == "running":
                    break
            if process.poll() is not None:
                    raise AssertionError("portal exited during startup")
            time.sleep(0.2)
        assert composition.get("state") == "running", composition

        portal_url = str(composition["portal"]["url"])
        parsed = urllib.parse.urlsplit(portal_url)
        base = f"{parsed.scheme}://{parsed.netloc}"
        token = urllib.parse.parse_qs(parsed.query)["forge_session"][0]
        assert _request(base, token, "/api/v1/health")["data"]["status"] in {"healthy", "degraded"}

        _request(base, token, "/api/v1/bridge/bootstrap", method="POST",
                 body={"confirm": "bootstrap"})
        workspace = _request(base, token, "/api/v1/workspaces", method="POST",
                             body={"name": "Installed system", "confirm": "create"})["data"]
        product = _request(base, token, "/api/v1/products", method="POST",
                           body={"workspace_id": workspace["id"], "name": "System journey",
                                 "confirm": "create"})["data"]
        task = _request(base, token, f"/api/v1/products/{product['id']}/tasks", method="POST",
                        body={"title": "Verify installed journey", "confirm": "create"})["data"]
        assert task["product_id"] == product["id"]

        session = _request(base, token, "/api/v1/chat/sessions", method="POST",
                           body={"provider": "fake", "title": "Installed fake chat",
                                 "confirm": "create"})["data"]
        _request(base, token, f"/api/v1/chat/sessions/{session['id']}/prompt", method="POST",
                 body={"text": "Create a follow-up task", "confirm": "send"})
        events: list[dict] = []
        for _ in range(30):
            events = _request(base, token, f"/api/v1/chat/sessions/{session['id']}/events",
                              method="POST", body={"after_seq": 0}).get("data", {}).get("items", [])
            if events:
                break
            time.sleep(0.3)
        assert events, "fake provider produced no persisted events"
        assert _request(base, token, f"/api/v1/products/{product['id']}/tasks")["data"]["items"]
        assert _request(base, token, "/api/v1/audit")["data"]["items"]
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
