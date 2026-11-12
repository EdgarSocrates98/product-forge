"""Run a deterministic quality gate against the optional Defuddle CLI.

The benchmark deliberately uses a local HTML fixture over stdin.  It never
fetches a URL, executes returned HTML, or changes Product Forge state.  A
missing optional CLI is reported as ``unavailable`` rather than as a passing
quality result.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from typing import Any

FIXTURE = """<!doctype html>
<html><head><title>Forge Runbook</title></head>
<body>
<nav>Ignore navigation</nav>
<main><article>
<h1>Safe Spark Runbook</h1>
<p>Diagnose skew before changing capacity.</p>
<h2>Checks</h2>
<ul><li>Inspect stage duration.</li><li>Confirm partition balance.</li></ul>
</article></main>
<footer>Ignore footer</footer>
</body></html>
"""


def _command() -> list[str] | None:
    configured = os.environ.get("FORGE_DEFUDDLE_BIN", "").strip()
    if configured:
        resolved = configured if os.path.isfile(configured) else shutil.which(configured)
        return [resolved, "parse", "-", "--json", "--markdown"] if resolved else None
    npx = shutil.which("npx") or shutil.which("npx.cmd")
    return [npx, "--yes", "defuddle", "parse", "-", "--json", "--markdown"] if npx else None


def main() -> int:
    command = _command()
    if not command:
        print(json.dumps({"schema": "productforge/DefuddleQuality/v1", "state": "unavailable"}))
        return 2
    try:
        completed = subprocess.run(  # noqa: S603 - command is resolved from PATH or explicit executable
            command,
            input=FIXTURE,
            text=True,
            capture_output=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        print(
            json.dumps(
                {
                    "schema": "productforge/DefuddleQuality/v1",
                    "state": "failed",
                    "error": type(exc).__name__,
                }
            )
        )
        return 1
    try:
        payload: Any = json.loads(completed.stdout)
    except json.JSONDecodeError:
        payload = None

    content = ""
    if isinstance(payload, dict):
        raw_content = payload.get("contentMarkdown", payload.get("content", ""))
        content = raw_content.strip() if isinstance(raw_content, str) else ""
    checks = {
        "command_succeeded": completed.returncode == 0,
        "object_payload": isinstance(payload, dict),
        "title": isinstance(payload, dict) and payload.get("title") == "Forge Runbook",
        "main_content": "Diagnose skew before changing capacity." in content,
        "list_content": "Inspect stage duration." in content and "Confirm partition balance." in content,
        "navigation_removed": "Ignore navigation" not in content,
        "footer_removed": "Ignore footer" not in content,
        "parse_time_metric": isinstance(payload, dict) and isinstance(payload.get("parseTime"), (int, float)),
    }
    passed = sum(checks.values())
    result = {
        "schema": "productforge/DefuddleQuality/v1",
        "state": "passed" if all(checks.values()) else "failed",
        "checks": checks,
        "score": f"{passed}/{len(checks)}",
        "extractor_output": (
            "contentMarkdown" if isinstance(payload, dict) and "contentMarkdown" in payload else "content"
        ),
        "parse_time_ms": payload.get("parseTime") if isinstance(payload, dict) else None,
    }
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if all(checks.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
