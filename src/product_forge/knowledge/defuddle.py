"""Optional Defuddle CLI adapter for already-fetched HTML.

The network boundary remains :mod:`product_forge.knowledge.url`: it validates
DNS, redirects, ports, size and content type before this adapter is called.
Defuddle receives HTML over stdin only, so it never gets a URL to fetch and is
never a required dependency for the stdlib extractor.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from hashlib import sha256
from typing import Any

MAX_OUTPUT_BYTES = 2 * 1024 * 1024
DEFAULT_TIMEOUT_S = 20.0


class DefuddleError(ValueError):
    """Stable, safe-to-display optional-extractor failure."""

    def __init__(self, code: str, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.details = details or {}


def executable(command: str | None = None) -> str | None:
    """Resolve an explicit command or the optional ``defuddle`` executable."""
    candidate = (command or os.environ.get("FORGE_DEFUDDLE_BIN") or "defuddle").strip()
    if not candidate:
        return None
    return candidate if os.path.isabs(candidate) and os.path.isfile(candidate) else shutil.which(candidate)


def parse_defuddle(
    html: str,
    source_url: str,
    *,
    command: str | None = None,
    timeout_s: float = DEFAULT_TIMEOUT_S,
    max_output_bytes: int = MAX_OUTPUT_BYTES,
) -> dict[str, Any]:
    """Parse bounded, already-fetched HTML through Defuddle's JSON CLI."""
    raw = str(html or "")
    if not raw:
        raise DefuddleError("DEFUDDLE-EMPTY", "the HTML document is empty")
    tool = executable(command)
    if not tool:
        raise DefuddleError(
            "DEFUDDLE-UNAVAILABLE",
            "Defuddle is not installed; use the stdlib extractor or install the optional CLI",
        )
    try:
        completed = subprocess.run(  # noqa: S603 - executable is resolved without a shell
            [tool, "parse", "-", "--json", "--markdown"],
            input=raw,
            text=True,
            capture_output=True,
            timeout=max(0.1, float(timeout_s)),
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise DefuddleError("DEFUDDLE-TIMEOUT", "the optional extractor exceeded its time limit") from exc
    except OSError as exc:
        raise DefuddleError("DEFUDDLE-FAILED", "the optional extractor could not be started") from exc
    output = completed.stdout or ""
    if len(output.encode("utf-8", errors="replace")) > max_output_bytes:
        raise DefuddleError("DEFUDDLE-SIZE-LIMIT", "the extracted document exceeds the safe output limit")
    if completed.returncode != 0:
        raise DefuddleError(
            "DEFUDDLE-FAILED",
            "the optional extractor rejected the document",
            details={"exit_code": completed.returncode},
        )
    try:
        payload = json.loads(output)
    except (TypeError, ValueError) as exc:
        raise DefuddleError("DEFUDDLE-INVALID-JSON", "the optional extractor returned invalid JSON") from exc
    if not isinstance(payload, dict):
        raise DefuddleError("DEFUDDLE-INVALID-JSON", "the optional extractor returned a non-object")
    content = str(payload.get("content") or "").strip()
    if not content:
        raise DefuddleError("DEFUDDLE-NO-CONTENT", "the optional extractor found no main content")
    title = str(payload.get("title") or payload.get("description") or "").strip()[:160]
    return {
        "schema": "productforge/DefuddleDocument/v1",
        "url": source_url,
        "title": title or source_url,
        "content": content,
        "content_hash": sha256(content.encode("utf-8")).hexdigest(),
        "content_type": "text/markdown",
        "extractor": "defuddle-cli",
        "state": "ready_for_import",
        "warnings": ["Defuddle received validated local HTML over stdin; remote scripts were not executed"],
        "metrics": {
            "bytes_in": len(raw.encode("utf-8")),
            "characters": len(content),
            "parse_time_ms": payload.get("parseTime"),
            "max_output_bytes": max_output_bytes,
        },
        "provenance": {"requested_url": source_url, "adapter": "defuddle-cli", "network_fetch": "stdlib-url"},
    }
