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
import threading
from hashlib import sha256
from typing import Any

MAX_OUTPUT_BYTES = 2 * 1024 * 1024
DEFAULT_TIMEOUT_S = 20.0
MAX_STDERR_BYTES = 256 * 1024


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


def _run_bounded(
    args: list[str],
    payload: bytes,
    *,
    timeout_s: float,
    max_stdout_bytes: int,
    max_stderr_bytes: int,
) -> tuple[int, bytes, bytes]:
    """Run without shell and stop retaining output past hard limits."""
    kwargs: dict[str, Any] = {
        "stdin": subprocess.PIPE,
        "stdout": subprocess.PIPE,
        "stderr": subprocess.PIPE,
        "shell": False,
    }
    if os.name == "nt":
        kwargs["creationflags"] = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    else:
        kwargs["start_new_session"] = True
    try:
        process = subprocess.Popen(args, **kwargs)  # noqa: S603 - shell is disabled and executable is resolved
    except OSError as exc:
        raise DefuddleError("DEFUDDLE-FAILED", "the optional extractor could not be started") from exc

    killed = threading.Event()
    exceeded: dict[str, bool] = {"stdout": False, "stderr": False}
    captured: dict[str, bytearray] = {"stdout": bytearray(), "stderr": bytearray()}

    def stop_process() -> None:
        if killed.is_set():
            return
        killed.set()
        try:
            process.kill()
        except OSError:
            pass

    def drain(name: str, stream: Any, limit: int) -> None:
        try:
            while True:
                chunk = stream.read(min(64 * 1024, limit + 1))
                if not chunk:
                    return
                remaining = limit - len(captured[name])
                if len(chunk) > remaining:
                    captured[name].extend(chunk[: max(0, remaining)])
                    exceeded[name] = True
                    stop_process()
                    return
                captured[name].extend(chunk)
        finally:
            stream.close()

    readers = [
        threading.Thread(target=drain, args=("stdout", process.stdout, max_stdout_bytes), daemon=True),
        threading.Thread(target=drain, args=("stderr", process.stderr, max_stderr_bytes), daemon=True),
    ]
    for reader in readers:
        reader.start()

    def send_input() -> None:
        try:
            process.stdin.write(payload)
            process.stdin.close()
        except (BrokenPipeError, OSError):
            pass

    writer = threading.Thread(target=send_input, daemon=True)
    writer.start()
    try:
        process.wait(timeout=max(0.1, float(timeout_s)))
    except subprocess.TimeoutExpired as exc:
        stop_process()
        process.wait(timeout=2)
        for reader in readers:
            reader.join(timeout=2)
        writer.join(timeout=2)
        raise DefuddleError("DEFUDDLE-TIMEOUT", "the optional extractor exceeded its time limit") from exc
    finally:
        if process.poll() is None:
            stop_process()
        for reader in readers:
            reader.join(timeout=2)
        writer.join(timeout=2)

    if exceeded["stdout"]:
        raise DefuddleError("DEFUDDLE-SIZE-LIMIT", "the extracted document exceeds the safe output limit")
    if exceeded["stderr"]:
        raise DefuddleError("DEFUDDLE-SIZE-LIMIT", "the optional extractor emitted excessive diagnostics")
    return int(process.returncode or 0), bytes(captured["stdout"]), bytes(captured["stderr"])


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
    returncode, stdout, _stderr = _run_bounded(
        [tool, "parse", "-", "--json", "--markdown"],
        raw.encode("utf-8"),
        timeout_s=timeout_s,
        max_stdout_bytes=max_output_bytes,
        max_stderr_bytes=MAX_STDERR_BYTES,
    )
    if returncode != 0:
        raise DefuddleError(
            "DEFUDDLE-FAILED",
            "the optional extractor rejected the document",
            details={"exit_code": returncode},
        )
    output = stdout.decode("utf-8", errors="replace")
    try:
        payload = json.loads(output)
    except (TypeError, ValueError) as exc:
        raise DefuddleError("DEFUDDLE-INVALID-JSON", "the optional extractor returned invalid JSON") from exc
    if not isinstance(payload, dict):
        raise DefuddleError("DEFUDDLE-INVALID-JSON", "the optional extractor returned a non-object")
    # Defuddle's JSON mode exposes Markdown as ``contentMarkdown``.  Keep the
    # older ``content`` spelling as a compatibility fallback for pinned CLI
    # releases, but never stringify a non-text payload into a false document.
    content_value = payload.get("contentMarkdown")
    if not isinstance(content_value, str) or not content_value.strip():
        content_value = payload.get("content")
    content = content_value.strip() if isinstance(content_value, str) else ""
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
