"""forge.json version must match the package version (single source of truth)."""

import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def _package_version() -> str:
    init = (REPO / "src" / "product_forge" / "__init__.py").read_text(encoding="utf-8")
    match = re.search(r'__version__\s*=\s*"([^"]+)"', init)
    assert match, "__version__ not found in src/product_forge/__init__.py"
    return match.group(1)


def test_forge_json_version_matches_package() -> None:
    manifest = json.loads((REPO / "forge.json").read_text(encoding="utf-8"))
    version = _package_version()
    assert manifest["version"] == version, (
        f"forge.json version {manifest['version']} diverges from "
        f"package __version__ {version}"
    )
