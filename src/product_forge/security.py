"""Security primitives: secret redaction, path confinement, token store.

Everything the core persists passes through ``redact`` — same invariant
as the-forge core. API tokens are local-only, 0600, rotatable/revocable.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import secrets
from pathlib import Path
from typing import Any, TypeVar

_T = TypeVar("_T")

SECRET_KEYS = (
    "token",
    "secret",
    "password",
    "cookie",
    "authorization",
    "api_key",
    "apikey",
    "credential",
    "client_secret",
    "private_key",
    "connection_string",
)

REDACT_EXEMPT = frozenset({"plan_token", "token_id", "token_preview",
                           "tokens_in", "tokens_out"})


def _secretish(key: str) -> bool:
    k = key.lower()
    return any(s in k for s in SECRET_KEYS) and k not in REDACT_EXEMPT


def redact(obj: _T) -> _T:
    """Deep-scrub secret-shaped values before persistence or transport."""
    if isinstance(obj, dict):
        out: dict[str, Any] = {}
        for k, v in obj.items():
            if _secretish(str(k)):
                out[k] = "[redacted]" if v else v
            else:
                out[k] = redact(v)
        return out  # type: ignore[return-value]
    if isinstance(obj, (list, tuple)):
        return [redact(v) for v in obj]  # type: ignore[return-value]
    return obj


def safe_path(raw: str | Path, roots: list[Path]) -> Path:
    """Resolve ``raw`` and require it to live inside one of ``roots``."""
    p = Path(raw).expanduser().resolve()
    for root in roots:
        try:
            p.relative_to(Path(root).expanduser().resolve())
            return p
        except ValueError:
            continue
    from .errors import PermissionDeniedError

    raise PermissionDeniedError(f"path outside allowed roots: {raw}")


class TokenStore:
    """Local API bearer token — generated on first use, file 0600."""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._token: str | None = None

    def _load(self) -> str | None:
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
            tok = data.get("token")
            return tok if isinstance(tok, str) and tok else None
        except (OSError, json.JSONDecodeError):
            return None

    def _persist(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"token": self._token, "preview": self.preview}
        self._path.write_text(json.dumps(payload), encoding="utf-8")
        try:
            self._path.chmod(0o600)
        except OSError:
            pass

    @property
    def token(self) -> str:
        if self._token is None:
            self._token = self._load() or secrets.token_urlsafe(32)
            self._persist()
        return self._token

    @property
    def preview(self) -> str:
        return hashlib.sha256(self.token.encode()).hexdigest()[:12]

    def check(self, presented: str | None) -> bool:
        if not presented:
            return False
        return hmac.compare_digest(presented, self.token)

    def rotate(self) -> str:
        self._token = secrets.token_urlsafe(32)
        self._persist()
        return self._token

    def revoke(self) -> None:
        self._token = secrets.token_urlsafe(32)
        self._persist()
