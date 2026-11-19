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
        f"forge.json version {manifest['version']} diverges from package __version__ {version}"
    )


def test_agentic_manifest_version_matches_package() -> None:
    manifest = json.loads((REPO / "forge.agentic.json").read_text(encoding="utf-8"))
    version = _package_version()
    assert manifest["version"] == version, (
        f"forge.agentic.json version {manifest['version']} diverges from package __version__ {version}"
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
        packaged = json.loads((REPO / "src" / "product_forge" / name).read_text(encoding="utf-8"))
        assert packaged == root, f"packaged {name} diverges from root manifest"


def test_portal_manifest_version_matches_package() -> None:
    manifest = json.loads(
        (
            REPO / "src" / "product_forge" / "portal_assets" / "angular" / "browser" / "manifest.json"
        ).read_text(encoding="utf-8")
    )
    assert manifest["product_forge_version"] == _package_version()


def test_embedded_bridge_manifest_and_version_are_packaged_contracts() -> None:
    init = (REPO / "src" / "forge_agent_bridge" / "__init__.py").read_text(encoding="utf-8")
    match = re.search(r'__version__\s*=\s*"([^"]+)"', init)
    assert match, "embedded Bridge __version__ not found"
    version = match.group(1)
    manifest = json.loads((REPO / "src" / "forge_agent_bridge" / "forge.json").read_text(encoding="utf-8"))
    agentic = json.loads(
        (REPO / "src" / "forge_agent_bridge" / "forge.agentic.json").read_text(encoding="utf-8")
    )
    assert manifest["forge_id"] == "forge-agent-bridge"
    assert manifest["version"] == version == agentic["version"]


def _canonical_bridge_ref(repo: Path, git: str) -> str | None:
    """The ref the embedded Bridge is vendored against, or ``None``.

    Order: ``origin/main`` (published upstream state), ``main``, ``HEAD``.
    A sibling checkout sitting on an unmerged feature branch is not yet
    canonical — its commits must not fail this parity gate.
    """
    import subprocess

    for ref in ("origin/main", "main", "HEAD"):
        probe = subprocess.run(  # noqa: S603 - fixed git argv, ref probe
            [git, "-C", str(repo), "rev-parse", "--verify", "--quiet", ref],
            capture_output=True,
            timeout=30,
        )
        if probe.returncode == 0:
            return ref
    return None


def _committed_bridge_tree(repo: Path) -> dict[Path, bytes] | None:
    """The canonical Bridge package tree — ``{rel: bytes}``.

    Vendoring snapshots *committed upstream* state, so compare against the
    canonical ref (see :func:`_canonical_bridge_ref`), not the working
    tree: a concurrent wave's unmerged work in the sibling checkout is not
    drift. ``None`` when no ref resolves (gitless copy) — the caller then
    falls back to the working tree.
    """
    import shutil
    import subprocess

    git_dir = repo / ".git"
    if not git_dir.exists() or not git_dir.is_dir():
        return None
    git = shutil.which("git")
    if git is None:
        return None
    ref = _canonical_bridge_ref(repo, git)
    if ref is None:
        return None
    pkg_rel = "src/forge_agent_bridge"
    try:
        listing = subprocess.run(  # noqa: S603 - fixed git argv over a sibling checkout
            [git, "-C", str(repo), "ls-tree", "-r", "--name-only", ref, "--", pkg_rel],
            capture_output=True,
            check=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    tree: dict[Path, bytes] = {}
    for name in listing.stdout.splitlines():
        if not name.strip():
            continue
        try:
            blob = subprocess.run(  # noqa: S603 - fixed git argv, ref-pinned blob
                [git, "-C", str(repo), "show", f"{ref}:{name}"],
                capture_output=True,
                check=True,
                timeout=30,
            )
        except (OSError, subprocess.CalledProcessError):
            return None
        tree[Path(name).relative_to(pkg_rel)] = blob.stdout
    return tree


def test_embedded_bridge_python_sources_match_standalone_checkout() -> None:
    bridge_repo = REPO.parent / "forge-agent-bridge"
    standalone = bridge_repo / "src" / "forge_agent_bridge"
    embedded = REPO / "src" / "forge_agent_bridge"
    if not standalone.is_dir():
        if os.environ.get("FORGE_BRIDGE_PARITY_REQUIRED") == "1":
            pytest.fail("canonical Bridge checkout is required for this parity run")
        pytest.skip("standalone Bridge checkout is not present")
    tracked_suffixes = {".py", ".json"}
    # Prefer the committed tree: the working tree may carry another wave's
    # uncommitted edits, which are not vendored (and not drift) here.
    committed = _committed_bridge_tree(bridge_repo)
    if committed is not None:
        canonical_files = {rel for rel in committed if rel.suffix in tracked_suffixes}

        def canonical_bytes(rel: Path) -> bytes:
            return committed[rel]

    else:
        canonical_files = {
            path.relative_to(standalone)
            for path in standalone.rglob("*")
            if path.is_file() and path.suffix in tracked_suffixes
        }

        def canonical_bytes(rel: Path) -> bytes:
            return (standalone / rel).read_bytes()

    bundled = {
        path.relative_to(embedded)
        for path in embedded.rglob("*")
        if path.is_file() and path.suffix in tracked_suffixes
    }
    assert bundled == canonical_files, (
        "embedded Bridge file inventory diverges: "
        f"missing={sorted(canonical_files - bundled)!s}, "
        f"extra={sorted(bundled - canonical_files)!s}"
    )
    for relative in sorted(canonical_files):
        copy = embedded / relative
        assert copy.read_bytes() == canonical_bytes(relative), (
            f"embedded Bridge drift: {relative}"
        )
