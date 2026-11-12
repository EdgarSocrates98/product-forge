"""Managed local services for the recommended Product Forge profile."""

from __future__ import annotations

import hashlib
import os
import secrets
import shutil
import socket
import subprocess
import time
from pathlib import Path
from urllib.parse import quote

from ..config import load_config, save_config


def _free_port(preferred: int = 54329) -> int:
    for port in range(preferred, preferred + 50):
        with socket.socket() as sock:
            try:
                sock.bind(("127.0.0.1", port))
            except OSError:
                continue
            return port
    raise RuntimeError("no free local PostgreSQL port found in 54329-54378")


def docker_compose_available() -> bool:
    docker = shutil.which("docker")
    if not docker:
        return False
    result = subprocess.run(  # noqa: S603 - executable is the discovered Docker binary
        [docker, "compose", "version"], capture_output=True, text=True, check=False, timeout=10
    )
    return result.returncode == 0


def _compose(home: Path) -> Path:
    return home / "runtime" / "docker-compose.postgres.yml"


def _env_file(home: Path) -> Path:
    return home / "runtime" / "postgres.env"


def _project_name(home: Path) -> str:
    digest = hashlib.sha256(str(home.resolve()).encode()).hexdigest()[:10]
    return f"productforge_{digest}"


def _compose_args(home: Path, docker: str) -> list[str]:
    return [
        docker,
        "compose",
        "-p",
        _project_name(home),
        "--env-file",
        str(_env_file(home)),
        "-f",
        str(_compose(home)),
    ]


def _write_runtime_files(home: Path, *, password: str, port: int) -> None:
    runtime = home / "runtime"
    runtime.mkdir(parents=True, exist_ok=True)
    compose = _compose(home)
    compose_text = """services:
  postgres:
    image: postgres:16-alpine
    restart: unless-stopped
    environment:
      POSTGRES_DB: productforge
      POSTGRES_USER: productforge
      POSTGRES_PASSWORD: ${PRODUCTFORGE_POSTGRES_PASSWORD}
    ports:
      - "127.0.0.1:${PRODUCTFORGE_POSTGRES_PORT}:5432"
    volumes:
      - productforge-postgres:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U productforge -d productforge"]
      interval: 3s
      timeout: 3s
      retries: 20
volumes:
  productforge-postgres:
"""
    compose.write_text(
        compose_text,
        encoding="utf-8",
    )
    env = _env_file(home)
    env.write_text(
        f"PRODUCTFORGE_POSTGRES_PASSWORD={password}\nPRODUCTFORGE_POSTGRES_PORT={port}\n",
        encoding="utf-8",
    )
    try:
        compose.chmod(0o600)
        env.chmod(0o600)
    except OSError:
        pass


def ensure_postgres(home: Path, *, profile: str = "recommended") -> dict[str, object]:
    """Start/reconcile managed PostgreSQL and persist its DSN.

    ``minimal`` and explicit offline mode remain SQLite-only. Recommended and
    full profiles fail with an actionable error when Docker is unavailable,
    instead of silently changing the persistence backend.
    """
    cfg = load_config(home)
    if profile in {"minimal", "offline"} or os.environ.get("PRODUCT_FORGE_OFFLINE") == "1":
        cfg.setdefault("store", {})["backend"] = "sqlite"
        cfg.setdefault("store", {})["managed_by_docker"] = False
        save_config(cfg, home)
        return {"backend": "sqlite", "managed": False, "reason": "profile/offline"}

    explicit_dsn = os.environ.get("PRODUCT_FORGE_DATABASE_URL") or cfg.get("store", {}).get("database_url")
    if explicit_dsn and not cfg.get("store", {}).get("managed_by_docker"):
        cfg.setdefault("store", {})["backend"] = "postgres"
        save_config(cfg, home)
        return {"backend": "postgres", "managed": False, "dsn": "configured"}

    # Local installs without a DSN stay zero-configuration SQLite. Docker is
    # still supported as a first-class runtime, but must be requested
    # explicitly so a transient local container cannot break the CLI or tests.
    if os.environ.get("PRODUCT_FORGE_MANAGED_POSTGRES") != "1":
        cfg.setdefault("store", {})["backend"] = "sqlite"
        cfg.setdefault("store", {})["managed_by_docker"] = False
        save_config(cfg, home)
        return {"backend": "sqlite", "managed": False, "reason": "no DSN"}

    if os.environ.get("PRODUCT_FORGE_DISABLE_DOCKER") == "1":
        if os.environ.get("PRODUCT_FORGE_ALLOW_SQLITE_FALLBACK") == "1":
            cfg.setdefault("store", {})["backend"] = "sqlite"
            save_config(cfg, home)
            return {"backend": "sqlite", "managed": False, "reason": "explicit fallback"}
        raise RuntimeError(
            "Docker is disabled; use --profile minimal or set PRODUCT_FORGE_ALLOW_SQLITE_FALLBACK=1"
        )
    if not docker_compose_available():
        raise RuntimeError(
            "Docker Compose is required for the recommended profile. "
            "Install/start Docker Desktop, or rerun with --profile minimal for SQLite."
        )

    runtime = home / "runtime"
    env_path = _env_file(home)
    password = ""
    port = int(cfg.get("store", {}).get("managed_port", 54329) or 54329)
    if env_path.exists():
        values = dict(line.split("=", 1) for line in env_path.read_text().splitlines() if "=" in line)
        password = values.get("PRODUCTFORGE_POSTGRES_PASSWORD", "")
        port = int(values.get("PRODUCTFORGE_POSTGRES_PORT", port))
    if not password:
        password = secrets.token_urlsafe(32)
        port = _free_port(port)
        _write_runtime_files(home, password=password, port=port)
    elif not _compose(home).exists():
        _write_runtime_files(home, password=password, port=port)

    docker = shutil.which("docker")
    assert docker
    command = [*_compose_args(home, docker), "up", "-d"]
    result = subprocess.run(  # noqa: S603 - command is built from fixed Docker args
        command, cwd=runtime, capture_output=True, text=True, check=False, timeout=120
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()[-500:]
        raise RuntimeError(f"PostgreSQL Docker service could not start: {detail}")
    deadline = time.monotonic() + 45
    while time.monotonic() < deadline:
        check = subprocess.run(  # noqa: S603 - command is built from fixed Docker args
            [
                *_compose_args(home, docker),
                "exec",
                "-T",
                "postgres",
                "pg_isready",
                "-U",
                "productforge",
                "-d",
                "productforge",
            ],
            cwd=runtime,
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
        if check.returncode == 0:
            dsn = f"postgresql://productforge:{quote(password, safe='')}@127.0.0.1:{port}/productforge"
            cfg.setdefault("store", {}).update(
                {
                    "backend": "postgres",
                    "database_url": dsn,
                    "managed_by_docker": True,
                    "managed_port": port,
                }
            )
            save_config(cfg, home)
            return {"backend": "postgres", "managed": True, "port": port, "health": "healthy"}
        time.sleep(1)
    raise RuntimeError("PostgreSQL container started but did not become healthy within 45 seconds")


def postgres_status(home: Path) -> dict[str, object]:
    cfg = load_config(home)
    store = cfg.get("store", {})
    return {
        "backend": store.get("backend", "auto"),
        "managed": bool(store.get("managed_by_docker")),
        "port": store.get("managed_port"),
        "dsn_configured": bool(store.get("database_url")),
        "compose": str(_compose(home)) if _compose(home).exists() else None,
    }
