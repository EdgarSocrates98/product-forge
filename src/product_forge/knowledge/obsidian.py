"""Optional Obsidian Markdown vault adapter.

Obsidian is a file format here, not a runtime dependency.  The adapter reads
and writes bounded Markdown under an explicitly configured vault root, refuses
symlinks/reparse points and traversal, and never shells out to the Obsidian
application or CLI.
"""

from __future__ import annotations

import hashlib
import stat
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

MAX_VAULT_BYTES = 1 * 1024 * 1024
MAX_INTEROP_BYTES = 1 * 1024 * 1024
_CANVAS_NODE_TYPES = {"text", "file", "link", "group"}


class ObsidianVaultError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def _bounded_document(document: str | bytes | Mapping[str, Any], *, kind: str) -> Any:
    """Decode one bounded Obsidian interchange document without executing content."""
    if isinstance(document, bytes):
        if len(document) > MAX_INTEROP_BYTES:
            raise ObsidianVaultError("OBSIDIAN-SIZE-LIMIT", f"{kind} document exceeds the safe size limit")
        try:
            text = document.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ObsidianVaultError("OBSIDIAN-UTF8-INVALID", f"{kind} document is not valid UTF-8") from exc
    elif isinstance(document, str):
        if len(document.encode("utf-8")) > MAX_INTEROP_BYTES:
            raise ObsidianVaultError("OBSIDIAN-SIZE-LIMIT", f"{kind} document exceeds the safe size limit")
        text = document
    elif isinstance(document, Mapping):
        return dict(document)
    else:
        raise ObsidianVaultError(
            f"OBSIDIAN-{kind.upper()}-INVALID", f"{kind} document must be text or an object"
        )

    try:
        value = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise ObsidianVaultError(f"OBSIDIAN-{kind.upper()}-INVALID", f"{kind} document is malformed") from exc
    if not isinstance(value, Mapping):
        raise ObsidianVaultError(
            f"OBSIDIAN-{kind.upper()}-INVALID", f"{kind} document must contain an object"
        )
    return dict(value)


def validate_canvas_document(document: str | bytes | Mapping[str, Any]) -> dict[str, Any]:
    """Validate the safe, structural subset of JSON Canvas used for interoperability.

    This deliberately validates rather than renders or executes a canvas.  Unknown
    optional fields are preserved by the caller and do not make a document invalid.
    """
    value = _bounded_document(document, kind="canvas")
    nodes = value.get("nodes")
    edges = value.get("edges")
    if not isinstance(nodes, list) or not isinstance(edges, list):
        raise ObsidianVaultError(
            "OBSIDIAN-CANVAS-INVALID", "canvas document requires nodes and edges arrays"
        )

    node_ids: set[str] = set()
    for node in nodes:
        if not isinstance(node, Mapping):
            raise ObsidianVaultError("OBSIDIAN-CANVAS-INVALID", "every canvas node must be an object")
        node_id = node.get("id")
        node_type = node.get("type")
        if not isinstance(node_id, str) or not node_id.strip() or node_id in node_ids:
            raise ObsidianVaultError(
                "OBSIDIAN-CANVAS-INVALID", "canvas node ids must be unique and non-empty"
            )
        if node_type not in _CANVAS_NODE_TYPES:
            raise ObsidianVaultError("OBSIDIAN-CANVAS-INVALID", "canvas node type is unsupported")
        node_ids.add(node_id)

    edge_ids: set[str] = set()
    for edge in edges:
        if not isinstance(edge, Mapping):
            raise ObsidianVaultError("OBSIDIAN-CANVAS-INVALID", "every canvas edge must be an object")
        edge_id = edge.get("id")
        from_node = edge.get("fromNode")
        to_node = edge.get("toNode")
        if not isinstance(edge_id, str) or not edge_id.strip() or edge_id in edge_ids:
            raise ObsidianVaultError(
                "OBSIDIAN-CANVAS-INVALID", "canvas edge ids must be unique and non-empty"
            )
        if from_node not in node_ids or to_node not in node_ids:
            raise ObsidianVaultError("OBSIDIAN-CANVAS-INVALID", "canvas edge endpoint does not exist")
        edge_ids.add(edge_id)

    return {
        "schema": "productforge/ObsidianCanvasValidation/v1",
        "kind": "canvas",
        "state": "validated",
        "nodes": len(nodes),
        "edges": len(edges),
        "warnings": [],
    }


def validate_base_document(document: str | bytes | Mapping[str, Any]) -> dict[str, Any]:
    """Validate the bounded Obsidian Bases interchange shape.

    Bases evolves independently of Product Forge.  We therefore validate the
    container and known section types, preserve unknown fields, and avoid
    claiming full Bases query/view semantics.
    """
    value = _bounded_document(document, kind="base")
    expected_types = {
        "properties": Mapping,
        "formulas": Mapping,
        "views": list,
        "filters": (str, list, Mapping),
    }
    for key, expected in expected_types.items():
        if key in value and not isinstance(value[key], expected):
            raise ObsidianVaultError("OBSIDIAN-BASE-INVALID", f"base field '{key}' has an invalid shape")
    if "views" in value:
        for view in value["views"]:
            if not isinstance(view, Mapping):
                raise ObsidianVaultError("OBSIDIAN-BASE-INVALID", "every base view must be an object")

    warnings = [
        "validation covers the interchange container and known section shapes; "
        "full Bases semantics are not implemented"
    ]
    return {
        "schema": "productforge/ObsidianBaseValidation/v1",
        "kind": "base",
        "state": "validated",
        "sections": sorted(value),
        "views": len(value.get("views", [])) if isinstance(value.get("views"), list) else 0,
        "warnings": warnings,
    }


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
