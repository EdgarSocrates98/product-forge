#!/usr/bin/env python3
# vendor.py — propagate the neutral forge_obsidian package to sibling forges.
#
# What it does, why, when:
#   - copies `src/forge_obsidian/{__init__.py,obsidian.py}` →
#     `<repo>/<pkg>/_forge_obsidian/` (byte-parity vendored subpackage,
#     same convention as `_forge_portal.py`/`_installkit.py`)
#   - the vendored import path is `from <pkg>._forge_obsidian import …`;
#     the canonical import `from forge_obsidian import …` stays the source
#     of truth in product-forge
#   - `--check` verifies byte-parity without writing (drift gate)
#
# Usage:  python forge-obsidian/scripts/vendor.py [--repo NAME] [--check]
#
# Each receiving forge still needs `pyyaml` as a runtime dependency — the
# vendored engine imports `yaml`. Forges whose contract forbids runtime
# deps (the-forge core is stdlib-only) are intentionally not vendored;
# they exchange `theforge/Obsidian*` contracts instead.

from __future__ import annotations

import argparse
import hashlib
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WORKSPACE = ROOT.parent.parent
SRC = ROOT / "src" / "forge_obsidian"
FILES = ("__init__.py", "obsidian.py", "notes.py", "cli.py")

# sibling repo → package dir that receives _forge_obsidian/
FORGES: dict[str, str] = {
    "api-forge": "src/apiforge",
    "api-sentinel-forge": "src/api_sentinel",
    "code-atlas-forge": "src/code_atlas",
    "data-sentinel-forge": "src/data_sentinel",
    "forge-agent-bridge": "src/forge_agent_bridge",
    "forge-doctor-api": "src/forge_doctor_api",
    "forge-doctor-data": "src/forge_doctor_data",
    "forge-lens": "src/forge_lens",
    "platform-forge": "platformforge",
    "spark-forge-aws": "sparkforge_aws",
    "spark-forge-azure": "sparkforge_azure",
    # product-forge embeds the canonical package itself — never vendored.
    # the-forge core is stdlib-only by invariant — contracts only.
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def vendor_one(name: str, pkg_dir: str, *, check: bool) -> list[str]:
    repo = WORKSPACE / name
    notes: list[str] = []
    if not repo.is_dir():
        return [f"SKIP {name}: checkout not found at {repo}"]
    dst_dir = repo / pkg_dir / "_forge_obsidian"
    stale: list[Path] = []
    for fname in FILES:
        src = SRC / fname
        dst = dst_dir / fname
        if dst.is_file() and sha256(dst) == sha256(src):
            notes.append(f"  {fname}: parity ok")
        else:
            stale.append(dst)
    extra = [p for p in dst_dir.glob("*.py") if p.name not in FILES] if dst_dir.is_dir() else []
    if extra:
        stale.extend(extra)
        notes.append(f"  extra files to remove: {', '.join(p.name for p in extra)}")
    if check:
        if stale:
            notes.append(f"DRIFT {name}: {len(stale)} target(s) out of parity")
        return notes
    dst_dir.mkdir(parents=True, exist_ok=True)
    for fname in FILES:
        shutil.copyfile(SRC / fname, dst_dir / fname)
        notes.append(f"  wrote {(dst_dir / fname).relative_to(repo)}")
    for p in extra:
        p.unlink()
    return notes


def main() -> int:
    ap = argparse.ArgumentParser(description="Vendor forge_obsidian to sibling forges")
    ap.add_argument("--repo", choices=sorted(FORGES), help="vendor a single forge")
    ap.add_argument("--check", action="store_true", help="verify parity without writing")
    args = ap.parse_args()

    for fname in FILES:
        if not (SRC / fname).is_file():
            print(f"error: {SRC / fname} not found", file=sys.stderr)
            return 2

    targets = {args.repo: FORGES[args.repo]} if args.repo else FORGES
    drift = False
    for name, pkg in targets.items():
        print(f"{name}:")
        for line in vendor_one(name, pkg, check=args.check):
            print(line)
            if line.startswith("DRIFT"):
                drift = True
    return 1 if (args.check and drift) else 0


if __name__ == "__main__":
    raise SystemExit(main())
