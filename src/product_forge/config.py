"""Configuration: layered env > file > defaults. Scope-aware state dir.

State lives under ``$PRODUCT_FORGE_HOME`` or, by default,
``~/.productforge`` (user scope) or ``./.productforge`` (project scope).
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Literal

Scope = Literal["user", "project", "workspace"]

DEFAULTS: dict[str, Any] = {
    "scope": "user",
    "db_path": "state/productforge.db",
    "object_store": "state/objects",
    "log_level": "INFO",
    "read_only_default": True,
    "api": {"bind": "127.0.0.1", "port": 0, "token_file": "state/api_token"},
    "llm": {"provider": "none", "model": None, "budget_tokens_day": 200_000},
    "gateway_profile": "balanced",  # economy | balanced | deep
    # LLM provider boundary (§15.5): provider_cmd is an external subprocess
    # speaking productforge/SynthesisRequest|Result — never an SDK import,
    # never credentials in this file. None = synthesis honestly unavailable.
    "gateway": {"provider_cmd": None, "timeout_s": 30},
    "install_profile": "recommended",  # minimal | recommended | full
}

ENV_PREFIX = "PRODUCT_FORGE_"


def home_dir(scope: Scope | None = None, root: Path | None = None) -> Path:
    env = os.environ.get(f"{ENV_PREFIX}HOME")
    if env:
        return Path(env).expanduser().resolve()
    scope = scope or DEFAULTS["scope"]
    base = root or Path.cwd()
    if scope in ("project", "workspace"):
        return (base / ".productforge").resolve()
    return (Path.home() / ".productforge").resolve()


def config_path(home: Path) -> Path:
    return home / "config.json"


def load_config(home: Path | None = None) -> dict[str, Any]:
    home = home or home_dir()
    cfg = json.loads(json.dumps(DEFAULTS))
    path = config_path(home)
    if path.exists():
        try:
            file_cfg = json.loads(path.read_text(encoding="utf-8"))
            _deep_merge(cfg, file_cfg)
        except (json.JSONDecodeError, OSError):
            pass
    _apply_env(cfg)
    return cfg


def save_config(cfg: dict[str, Any], home: Path | None = None) -> Path:
    home = home or home_dir()
    path = config_path(home)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cfg, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    try:
        path.chmod(0o600)
    except OSError:
        pass
    return path


def _deep_merge(dst: dict[str, Any], src: dict[str, Any]) -> None:
    for k, v in src.items():
        if isinstance(v, dict) and isinstance(dst.get(k), dict):
            _deep_merge(dst[k], v)
        else:
            dst[k] = v


def _apply_env(cfg: dict[str, Any]) -> None:
    if v := os.environ.get(f"{ENV_PREFIX}LOG_LEVEL"):
        cfg["log_level"] = v
    if v := os.environ.get(f"{ENV_PREFIX}DB_PATH"):
        cfg["db_path"] = v
    if v := os.environ.get(f"{ENV_PREFIX}GATEWAY_PROFILE"):
        cfg["gateway_profile"] = v
    if v := os.environ.get(f"{ENV_PREFIX}LLM_PROVIDER"):
        cfg.setdefault("llm", {})["provider"] = v


def db_path(home: Path, cfg: dict[str, Any] | None = None) -> Path:
    cfg = cfg or load_config(home)
    p = Path(str(cfg["db_path"]))
    return p if p.is_absolute() else home / p
