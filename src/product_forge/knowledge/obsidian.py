"""Optional Obsidian Markdown vault adapter.

Obsidian is a file format here, not a runtime dependency.  The adapter reads
and writes bounded Markdown under an explicitly configured vault root, refuses
symlinks/reparse points and traversal, and never shells out to the Obsidian
application or CLI.
"""

from __future__ import annotations

import hashlib
import stat
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

MAX_VAULT_BYTES = 1 * 1024 * 1024


class ObsidianVaultError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def _resolved(path: Path) -> Path:
    return path.expanduser().resolve(strict=False)


def _inside(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _reparse(path: Path) -> bool:
    try:
        mode = path.lstat().st_mode
        if stat.S_ISLNK(mode):
            return True
        attrs = getattr(path.stat(), "st_file_attributes", 0)
        return bool(attrs & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400))
    except OSError:
        return True


def _safe(root: Path, raw_path: str, *, for_write: bool = False) -> Path:
    if not raw_path or "\x00" in raw_path:
        raise ObsidianVaultError("OBSIDIAN-PATH-REQUIRED", "vault path is required")
    candidate = _resolved(root / raw_path)
    if not _inside(candidate, _resolved(root)) or candidate.suffix.lower() != ".md":
        raise ObsidianVaultError("OBSIDIAN-PATH-REFUSED", "path must be Markdown inside the vault")
    current = _resolved(root)
    for part in candidate.relative_to(current).parts[:-1]:
        current = current / part
        if _reparse(current):
            raise ObsidianVaultError(
                "OBSIDIAN-SYMLINK-REFUSED", "vault path contains a symlink or reparse point"
            )
    if candidate.exists() and _reparse(candidate):
        raise ObsidianVaultError("OBSIDIAN-SYMLINK-REFUSED", "vault path is a symlink or reparse point")
    if not for_write and not candidate.is_file():
        raise ObsidianVaultError("OBSIDIAN-NOT-FOUND", "vault document was not found")
    if for_write and not candidate.parent.is_dir():
        raise ObsidianVaultError("OBSIDIAN-PARENT-MISSING", "vault destination directory was not found")
    return candidate


def _title(path: Path, content: str) -> str:
    for line in content.splitlines():
        value = line.strip()
        if value.startswith("# ") and value[2:].strip():
            return value[2:].strip()[:160]
    return path.stem.replace("-", " ").replace("_", " ").strip().title()


def import_vault_document(vault: Path | str, raw_path: str) -> dict[str, Any]:
    root = _resolved(Path(vault))
    if not root.is_dir():
        raise ObsidianVaultError("OBSIDIAN-VAULT-MISSING", "configured Obsidian vault is not a directory")
    path = _safe(root, raw_path)
    size = path.stat().st_size
    if size > MAX_VAULT_BYTES:
        raise ObsidianVaultError("OBSIDIAN-SIZE-LIMIT", "vault document exceeds the safe size limit")
    content = path.read_bytes().decode("utf-8", errors="replace")
    return {
        "schema": "productforge/ObsidianDocument/v1",
        "path": path.relative_to(root).as_posix(),
        "title": _title(path, content),
        "content": content,
        "content_hash": hashlib.sha256(content.encode("utf-8")).hexdigest(),
        "size": size,
        "state": "ready_for_import",
        "provenance": {
            "adapter": "stdlib-obsidian-markdown",
            "vault": root.name,
            "cli_required": False,
            "imported_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        },
    }


def export_vault_document(vault: Path | str, raw_path: str, content: str) -> dict[str, Any]:
    root = _resolved(Path(vault))
    if not root.is_dir():
        raise ObsidianVaultError("OBSIDIAN-VAULT-MISSING", "configured Obsidian vault is not a directory")
    if len(content.encode("utf-8")) > MAX_VAULT_BYTES:
        raise ObsidianVaultError("OBSIDIAN-SIZE-LIMIT", "vault document exceeds the safe size limit")
    path = _safe(root, raw_path, for_write=True)
    path.write_text(content, encoding="utf-8", newline="\n")
    return {
        "schema": "productforge/ObsidianDocument/v1",
        "path": path.relative_to(root).as_posix(),
        "title": _title(path, content),
        "content_hash": hashlib.sha256(content.encode("utf-8")).hexdigest(),
        "size": len(content.encode("utf-8")),
        "state": "exported",
        "provenance": {"adapter": "stdlib-obsidian-markdown", "vault": root.name, "cli_required": False},
    }
