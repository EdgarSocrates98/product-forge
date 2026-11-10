"""forge.json version must match the package version (single source of truth)."""

import json
import os
import re
from pathlib import Path

import pytest

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


def test_agentic_manifest_version_matches_package() -> None:
    manifest = json.loads((REPO / "forge.agentic.json").read_text(encoding="utf-8"))
    version = _package_version()
    assert manifest["version"] == version, (
        f"forge.agentic.json version {manifest['version']} diverges from "
        f"package __version__ {version}"
    )


def test_agentic_manifest_publishes_implemented_knowledge_capabilities() -> None:
    manifest = json.loads((REPO / "forge.agentic.json").read_text(encoding="utf-8"))
    workflows = {item["id"]: item for item in manifest["workflows"]}
    expected = {
        "obsidian.preview",
        "obsidian.import",
        "obsidian.export",
        "obsidian.sync.plan",
        "obsidian.sync.apply",
        "knowledge.context.project",
        "knowledge.evidence.list",
    }
    assert expected <= workflows.keys()
    assert workflows["obsidian.preview"]["read_only"] is True
    assert workflows["obsidian.sync.apply"]["read_only"] is False
    assert workflows["knowledge.evidence.list"]["read_only"] is True


def test_packaged_manifests_match_root_manifests() -> None:
    for name in ("forge.json", "forge.agentic.json"):
        root = json.loads((REPO / name).read_text(encoding="utf-8"))
        packaged = json.loads(
            (REPO / "src" / "product_forge" / name).read_text(encoding="utf-8")
        )
        assert packaged == root, f"packaged {name} diverges from root manifest"


def test_portal_manifest_version_matches_package() -> None:
    manifest = json.loads(
        (REPO / "src" / "product_forge" / "portal_assets" / "angular" / "browser" / "manifest.json")
        .read_text(encoding="utf-8")
    )
    assert manifest["product_forge_version"] == _package_version()


def test_embedded_bridge_manifest_and_version_are_packaged_contracts() -> None:
    init = (REPO / "src" / "forge_agent_bridge" / "__init__.py").read_text(encoding="utf-8")
    match = re.search(r'__version__\s*=\s*"([^"]+)"', init)
    assert match, "embedded Bridge __version__ not found"
    version = match.group(1)
    manifest = json.loads(
        (REPO / "src" / "forge_agent_bridge" / "forge.json").read_text(encoding="utf-8")
    )
    agentic = json.loads(
        (REPO / "src" / "forge_agent_bridge" / "forge.agentic.json").read_text(encoding="utf-8")
    )
    assert manifest["forge_id"] == "forge-agent-bridge"
    assert manifest["version"] == version == agentic["version"] == "0.2.1"


def test_embedded_bridge_python_sources_match_standalone_checkout() -> None:
    standalone = REPO.parent / "forge-agent-bridge" / "src" / "forge_agent_bridge"
    embedded = REPO / "src" / "forge_agent_bridge"
    if not standalone.is_dir():
        if os.environ.get("FORGE_BRIDGE_PARITY_REQUIRED") == "1":
            pytest.fail("canonical Bridge checkout is required for this parity run")
        pytest.skip("standalone Bridge checkout is not present")
    tracked_suffixes = {".py", ".json"}
    canonical = {
        path.relative_to(standalone)
        for path in standalone.rglob("*")
        if path.is_file() and path.suffix in tracked_suffixes
    }
    bundled = {
        path.relative_to(embedded)
        for path in embedded.rglob("*")
        if path.is_file() and path.suffix in tracked_suffixes
    }
    assert bundled == canonical, (
        "embedded Bridge file inventory diverges: "
        f"missing={sorted(canonical - bundled)!s}, "
        f"extra={sorted(bundled - canonical)!s}"
    )
    for relative in sorted(canonical):
        source = standalone / relative
        copy = embedded / relative
        assert copy.read_bytes() == source.read_bytes(), f"embedded Bridge drift: {relative}"
