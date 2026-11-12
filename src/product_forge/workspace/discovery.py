"""Deterministic, local-first discovery of workspace projects and context files.

Discovery deliberately returns metadata only.  Content is read through the
separate preview/import functions after the path has passed the same sandbox
and sensitive-file checks.  This keeps the Portal useful in an installed
repository without silently uploading or indexing the whole filesystem.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

SCHEMA = "productforge/WorkspaceDiscovery/v1"
MAX_REPOSITORIES = 64
MAX_DOCUMENTS = 500
MAX_DEPTH = 7
MAX_PREVIEW_BYTES = 512 * 1024
MAX_CLASSIFY_BYTES = 8192

IGNORED_DIRS = {
    ".git",
    ".hg",
    ".svn",
    ".idea",
    ".vscode",
    ".angular",
    ".next",
    ".pytest_cache",
    ".ruff_cache",
    ".mypy_cache",
    ".tox",
    ".venv",
    "venv",
    "env",
    "node_modules",
    "dist",
    "build",
    "target",
    "coverage",
    "__pycache__",
    ".cache",
    ".gradle",
    ".terraform",
    ".serverless",
    "vendor",
    "tmp",
    "temp",
}
SENSITIVE_NAMES = {
    ".env",
    ".env.local",
    ".env.development",
    ".env.production",
    ".env.test",
    "credentials",
    "credentials.json",
    "secrets.json",
    "secret.json",
    "id_rsa",
    "id_ed25519",
    "known_hosts",
    "config.json",
}
SENSITIVE_SUFFIXES = {
    ".pem",
    ".key",
    ".p12",
    ".pfx",
    ".crt",
    ".cer",
    ".der",
    ".jks",
}
DOC_SUFFIXES = {".md", ".mdx", ".txt", ".rst", ".adoc", ".yaml", ".yml", ".json", ".toml"}
MANIFESTS = {
    "pyproject.toml": "python",
    "setup.py": "python",
    "package.json": "node",
    "pnpm-workspace.yaml": "node",
    "go.mod": "go",
    "Cargo.toml": "rust",
    "pom.xml": "java",
    "build.gradle": "java",
    "composer.json": "php",
    "mix.exs": "elixir",
    "Gemfile": "ruby",
    "terraform.tf": "terraform",
    "main.tf": "terraform",
}
PROJECT_DOC_NAMES = {
    "readme",
    "readme.md",
    "agents.md",
    "claude.md",
    "contributing.md",
    "architecture.md",
    "adr",
    "decision",
    "decisions",
    "runbook",
    "roadmap",
}


class WorkspaceDiscoveryError(ValueError):
    """A requested workspace path is invalid or outside the local boundary."""


def _now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _resolved(path: Path) -> Path:
    return path.expanduser().resolve(strict=False)


def _inside(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _is_reparse(path: Path) -> bool:
    """Do not traverse symlinks/junction-like entries on any supported OS."""
    try:
        mode = path.lstat().st_mode
        if stat.S_ISLNK(mode):
            return True
        attrs = getattr(path.stat(), "st_file_attributes", 0)
        return bool(attrs & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400))
    except OSError:
        return True


def _sensitive(path: Path) -> bool:
    name = path.name.lower()
    if name in SENSITIVE_NAMES or name.startswith(".env"):
        return True
    if path.suffix.lower() in SENSITIVE_SUFFIXES:
        return True
    # Common credential-bearing names are excluded even when an extension is
    # used.  Do not rely on content scanning as the only protection.
    return any(token in name for token in ("secret", "credential", "token", "private-key"))


def _ignored_dir(name: str) -> bool:
    return name.lower() in {item.lower() for item in IGNORED_DIRS}


def _git_root(start: Path) -> Path | None:
    current = _resolved(start)
    if current.is_file():
        current = current.parent
    for candidate in (current, *current.parents):
        marker = candidate / ".git"
        if marker.is_dir() or marker.is_file():
            return candidate
    return None


def _looks_like_repo(path: Path) -> bool:
    if _is_reparse(path) or not path.is_dir():
        return False
    if (path / ".git").exists():
        return True
    return any((path / manifest).is_file() for manifest in MANIFESTS)


def _workspace_root(start: Path) -> tuple[Path, str]:
    explicit = os.environ.get("FORGE_WORKSPACE_ROOT", "").strip()
    if explicit:
        root = _resolved(Path(explicit))
        if not root.is_dir():
            raise WorkspaceDiscoveryError("FORGE_WORKSPACE_ROOT is not a directory")
        return root, "environment"

    current = _resolved(start)
    if current.is_file():
        current = current.parent
    current_repo = _git_root(current)
    # A workspace container is an ancestor with multiple independent project
    # directories.  This is what makes a portal launched from repo-a discover
    # repo-b beside it without asking the user for a path first.
    for candidate in (current, *current.parents[:4]):
        # Only widen from a repository to its immediate parent.  Walking
        # farther into e.g. a temp directory would accidentally treat an
        # unrelated collection of test folders as the user's workspace.
        if current_repo is not None and candidate != current_repo.parent:
            continue
        if current_repo is None and candidate != current:
            continue
        try:
            children = [
                p
                for p in candidate.iterdir()
                if p.is_dir() and not _ignored_dir(p.name) and _looks_like_repo(p)
            ]
        except OSError:
            continue
        if len(children) >= 2 and not (candidate / ".git").exists():
            return candidate, "workspace-container"
    return _git_root(current) or current, "repository"


def _project_name(root: Path) -> str:
    for manifest in ("pyproject.toml", "package.json", "Cargo.toml", "go.mod"):
        path = root / manifest
        if not path.is_file():
            continue
        try:
            if manifest == "package.json":
                value = json.loads(path.read_text(encoding="utf-8")).get("name")
                if value:
                    return str(value)
            elif manifest == "pyproject.toml":
                import tomllib

                value = tomllib.loads(path.read_text(encoding="utf-8")).get("project", {}).get("name")
                if value:
                    return str(value)
        except (OSError, ValueError, TypeError, UnicodeDecodeError):
            pass
    return root.name


def _repo_candidates(root: Path) -> list[Path]:
    found: list[Path] = []
    if _looks_like_repo(root):
        found.append(root)
    try:
        children = sorted(root.iterdir(), key=lambda p: p.name.lower())
    except OSError:
        children = []
    for child in children:
        if len(found) >= MAX_REPOSITORIES or _ignored_dir(child.name):
            continue
        if _looks_like_repo(child):
            found.append(child)
    if not found:
        found.append(root)
    return found[:MAX_REPOSITORIES]


def _classify(path: Path, repo: Path) -> str | None:
    if _sensitive(path) or path.suffix.lower() not in DOC_SUFFIXES:
        return None
    stem = path.stem.lower().replace("_", "-").replace(" ", "-")
    parts = {part.lower() for part in path.relative_to(repo).parts}
    if re.search(r"(^|[-.])(prd|product-requirements?|requirements)([-.]|$)", stem):
        return "prd"
    if re.search(r"(^|[-.])(brief|vision|problem|proposal)([-.]|$)", stem):
        return "brief"
    if "knowledge" in parts or "context" in parts or "docs" in parts or "documentation" in parts:
        return "knowledge"
    if stem in PROJECT_DOC_NAMES or stem.startswith("adr") or stem.startswith("decision"):
        return "knowledge"
    return None


def _title(path: Path) -> str:
    try:
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            for line in handle:
                line = line.strip().lstrip("#").strip()
                if line and len(line) <= 160:
                    return line
    except OSError:
        pass
    return path.stem.replace("-", " ").replace("_", " ").strip().title()


def _walk_documents(repo: Path, workspace: Path, limit: int) -> tuple[list[dict[str, Any]], list[str]]:
    documents: list[dict[str, Any]] = []
    skipped: list[str] = []
    try:
        walker = os.walk(repo, topdown=True, followlinks=False)
        for current_raw, dirs, files in walker:
            current = Path(current_raw)
            depth = len(current.relative_to(repo).parts)
            dirs[:] = [
                name
                for name in sorted(dirs, key=str.lower)
                if not _ignored_dir(name) and not _is_reparse(current / name) and depth < MAX_DEPTH
            ]
            if depth >= MAX_DEPTH:
                dirs[:] = []
            for name in sorted(files, key=str.lower):
                path = current / name
                if _is_reparse(path) or _sensitive(path):
                    skipped.append(path.relative_to(workspace).as_posix())
                    continue
                kind = _classify(path, repo)
                if kind is None:
                    continue
                try:
                    stat_result = path.stat()
                    size = int(stat_result.st_size)
                    modified_at = (
                        datetime.fromtimestamp(stat_result.st_mtime, UTC).isoformat().replace("+00:00", "Z")
                    )
                except OSError:
                    skipped.append(path.relative_to(workspace).as_posix())
                    continue
                relative = path.relative_to(workspace).as_posix()
                documents.append(
                    {
                        "id": hashlib.sha256(relative.encode("utf-8")).hexdigest()[:16],
                        "path": relative,
                        "relative_path": path.relative_to(repo).as_posix(),
                        "repository": repo.name,
                        "kind": kind,
                        "title": _title(path),
                        "extension": path.suffix.lower(),
                        "size": size,
                        "modified_at": modified_at,
                        "state": "discovered",
                        "readable": size <= MAX_PREVIEW_BYTES,
                    }
                )
                if len(documents) >= limit:
                    return documents, skipped
    except OSError:
        skipped.append(repo.relative_to(workspace).as_posix())
    return documents, skipped


def discover_workspace(
    start: Path | str | None = None, *, max_documents: int = MAX_DOCUMENTS
) -> dict[str, Any]:
    """Return bounded repository/project/document metadata for a local workspace."""
    root, source = _workspace_root(Path(start or Path.cwd()))
    repos = _repo_candidates(root)
    repository_items: list[dict[str, Any]] = []
    documents: list[dict[str, Any]] = []
    skipped: list[str] = []
    for repo in repos:
        manifests = [name for name in MANIFESTS if (repo / name).is_file()]
        repo_id = hashlib.sha256(repo.relative_to(root).as_posix().encode("utf-8")).hexdigest()[:16]
        repository_items.append(
            {
                "id": repo_id,
                "name": _project_name(repo),
                "path": repo.relative_to(root).as_posix() if repo != root else ".",
                "repository": repo.name,
                "is_git": (repo / ".git").exists(),
                "languages": sorted({MANIFESTS[name] for name in manifests}),
                "manifests": manifests,
                "state": "discovered",
            }
        )
        remaining = max(0, max_documents - len(documents))
        if remaining:
            found, repo_skipped = _walk_documents(repo, root, remaining)
            documents.extend(found)
            skipped.extend(repo_skipped)
    current_repo = _git_root(Path(start or Path.cwd()))
    current_relative = None
    if current_repo and _inside(current_repo, root):
        current_relative = current_repo.relative_to(root).as_posix() if current_repo != root else "."
    return {
        "schema": SCHEMA,
        "generated_at": _now(),
        "workspace": {
            "name": root.name,
            "path": str(root),
            "source": source,
            "current_repository": current_relative,
        },
        "repositories": repository_items,
        "projects": repository_items,
        "documents": documents,
        "skipped": skipped[:100],
        "limits": {"repositories": MAX_REPOSITORIES, "documents": max_documents, "depth": MAX_DEPTH},
        "state": "discovered",
    }


def _safe_document_path(workspace: Path, raw_path: str) -> Path:
    if not raw_path or "\x00" in raw_path:
        raise WorkspaceDiscoveryError("document path is required")
    candidate = _resolved(workspace / raw_path)
    root = _resolved(workspace)
    if not _inside(candidate, root) or _is_reparse(candidate) or _sensitive(candidate):
        raise WorkspaceDiscoveryError("document path is outside the workspace or is protected")
    if not candidate.is_file():
        raise WorkspaceDiscoveryError("document was not found")
    if _classify(candidate, _git_root(candidate) or root) is None:
        raise WorkspaceDiscoveryError("document is not an eligible product context file")
    return candidate


def preview_workspace_document(workspace: Path | str, raw_path: str) -> dict[str, Any]:
    root = _resolved(Path(workspace))
    path = _safe_document_path(root, raw_path)
    size = path.stat().st_size
    content = path.read_bytes()[:MAX_PREVIEW_BYTES].decode("utf-8", errors="replace")
    return {
        "path": path.relative_to(root).as_posix(),
        "kind": _classify(path, _git_root(path) or root) or "knowledge",
        "title": _title(path),
        "size": size,
        "preview": content,
        "truncated": size > MAX_PREVIEW_BYTES,
        "state": "previewed",
    }


def import_workspace_document(
    workspace: Path | str, raw_path: str, *, max_bytes: int = MAX_PREVIEW_BYTES
) -> dict[str, Any]:
    root = _resolved(Path(workspace))
    path = _safe_document_path(root, raw_path)
    size = path.stat().st_size
    if size > max_bytes:
        raise WorkspaceDiscoveryError("document is too large for a safe import")
    content = path.read_bytes().decode("utf-8", errors="replace")
    digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
    return {
        "path": path.relative_to(root).as_posix(),
        "kind": _classify(path, _git_root(path) or root) or "knowledge",
        "title": _title(path),
        "content": content,
        "content_hash": digest,
        "size": size,
        "state": "ready_for_import",
    }
