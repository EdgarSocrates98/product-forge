"""Verify the packaged Agent Bridge copy against an explicit canonical checkout."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

TRACKED_SUFFIXES = {".py", ".json"}


def _revision(root: Path) -> str:
    try:
        return subprocess.check_output(  # noqa: S603 - fixed git argv below
            ["git", "-C", str(root), "rev-parse", "HEAD"],  # noqa: S607
            text=True,
            stderr=subprocess.STDOUT,
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return "unversioned"


def _inventory(root: Path) -> set[Path]:
    return {
        path.relative_to(root)
        for path in root.rglob("*")
        if path.is_file() and path.suffix in TRACKED_SUFFIXES
    }


def check(canonical: Path, embedded: Path) -> dict[str, object]:
    canonical = canonical.resolve()
    embedded = embedded.resolve()
    if not canonical.is_dir():
        raise RuntimeError(f"canonical bridge source does not exist: {canonical}")
    if not embedded.is_dir():
        raise RuntimeError(f"embedded bridge source does not exist: {embedded}")
    expected = _inventory(canonical)
    actual = _inventory(embedded)
    missing = sorted(str(path) for path in expected - actual)
    extra = sorted(str(path) for path in actual - expected)
    drift = [
        str(path)
        for path in sorted(expected & actual)
        if (canonical / path).read_bytes() != (embedded / path).read_bytes()
    ]
    result = {
        "canonical_root": str(canonical),
        "canonical_revision": _revision(canonical),
        "embedded_root": str(embedded),
        "embedded_revision": _revision(embedded),
        "missing": missing,
        "extra": extra,
        "drift": drift,
        "status": "VERIFIED" if not missing and not extra and not drift else "FAILED",
    }
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--standalone-root", type=Path, required=True)
    parser.add_argument(
        "--embedded-root",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "src" / "forge_agent_bridge",
    )
    args = parser.parse_args()
    try:
        result = check(args.standalone_root / "src" / "forge_agent_bridge", args.embedded_root)
    except RuntimeError as exc:
        print(json.dumps({"status": "FAILED", "error": str(exc)}, sort_keys=True))
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0 if result["status"] == "VERIFIED" else 1


if __name__ == "__main__":
    sys.exit(main())
