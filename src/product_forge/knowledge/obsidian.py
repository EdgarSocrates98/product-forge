"""Optional Obsidian Markdown vault adapter.

Obsidian is a file format here, not a runtime dependency.  The adapter reads
and writes bounded Markdown under an explicitly configured vault root, refuses
symlinks/reparse points and traversal, and never shells out to the Obsidian
application or CLI.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import tempfile
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

import yaml

MAX_VAULT_BYTES = 1 * 1024 * 1024
MAX_INTEROP_BYTES = 1 * 1024 * 1024
_CANVAS_NODE_TYPES = {"text", "file", "link", "group"}
_CANVAS_SIDES = {"top", "right", "bottom", "left"}
_CANVAS_ENDS = {"none", "arrow"}
_CLASSIFICATIONS = {"public", "internal", "confidential", "restricted"}


class ObsidianVaultError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@runtime_checkable
class VaultLocator(Protocol):
    def locate(self) -> Path: ...


@runtime_checkable
class VaultReader(Protocol):
    def read(self, path: str) -> dict[str, Any]: ...


@runtime_checkable
class VaultWriter(Protocol):
    def write(self, path: str, content: str, *, baseline_hash: str | None = None) -> dict[str, Any]: ...


@runtime_checkable
class VaultScanner(Protocol):
    def scan(self, prefix: str = "") -> list[str]: ...


class MarkdownDocumentParser(Protocol):
    def parse(self, content: str) -> dict[str, Any]: ...


class FrontmatterAdapter(Protocol):
    def parse(self, content: str) -> tuple[dict[str, Any], str]: ...


class WikilinkResolver(Protocol):
    def resolve(self, link: str) -> str | None: ...


class AttachmentResolver(Protocol):
    def resolve(self, link: str) -> str | None: ...


class KnowledgeProjector(Protocol):
    def project(self, document: Mapping[str, Any]) -> Mapping[str, Any]: ...


class SyncPlanner(Protocol):
    def plan(self, path: str, content: str, *, baseline_hash: str | None = None) -> dict[str, Any]: ...


class ConflictDetector(Protocol):
    def detect(self, baseline_hash: str | None, current_hash: str | None, candidate_hash: str) -> str: ...


class ImportReceiptWriter(Protocol):
    def write_import_receipt(self, receipt: Mapping[str, Any]) -> None: ...


class ExportReceiptWriter(Protocol):
    def write_export_receipt(self, receipt: Mapping[str, Any]) -> None: ...


def _classification(value: str) -> str:
    if value not in _CLASSIFICATIONS:
        raise ObsidianVaultError("OBSIDIAN-CLASSIFICATION-INVALID", "unsupported document classification")
    return value


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
        for field in ("x", "y", "width", "height"):
            number = node.get(field)
            if isinstance(number, bool) or not isinstance(number, (int, float)):
                raise ObsidianVaultError(
                    "OBSIDIAN-CANVAS-INVALID",
                    f"canvas node field '{field}' must be numeric",
                )
        if node["width"] <= 0 or node["height"] <= 0:
            raise ObsidianVaultError(
                "OBSIDIAN-CANVAS-INVALID", "canvas node width and height must be positive"
            )
        required_content = {
            "text": "text",
            "file": "file",
            "link": "url",
        }.get(str(node_type))
        if required_content and not isinstance(node.get(required_content), str):
            raise ObsidianVaultError(
                "OBSIDIAN-CANVAS-INVALID",
                f"canvas {node_type} node requires string field '{required_content}'",
            )
        if node_type == "group" and "label" in node and not isinstance(node["label"], str):
            raise ObsidianVaultError(
                "OBSIDIAN-CANVAS-INVALID", "canvas group label must be a string"
            )
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
        for field in ("fromSide", "toSide"):
            if field in edge and edge[field] not in _CANVAS_SIDES:
                raise ObsidianVaultError(
                    "OBSIDIAN-CANVAS-INVALID", f"canvas edge field '{field}' is invalid"
                )
        for field in ("fromEnd", "toEnd"):
            if field in edge and edge[field] not in _CANVAS_ENDS:
                raise ObsidianVaultError(
                    "OBSIDIAN-CANVAS-INVALID", f"canvas edge field '{field}' is invalid"
                )
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
    resolved_root = _resolved(root)
    relative_parts = (
        candidate.relative_to(resolved_root).parts if _inside(candidate, resolved_root) else ()
    )
    blocked_dirs = {".git", ".obsidian", ".forge", ".cache", "__pycache__"}
    if any(part.lower() in blocked_dirs for part in relative_parts[:-1]):
        raise ObsidianVaultError(
            "OBSIDIAN-HIDDEN-REFUSED",
            "vault internal or cache directories are not import/export targets",
        )
    if not _inside(candidate, resolved_root) or candidate.suffix.lower() != ".md":
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
    if candidate.exists() and candidate.stat().st_nlink > 1:
        raise ObsidianVaultError("OBSIDIAN-HARDLINK-REFUSED", "vault document is a hardlink")
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


def parse_markdown_document(content: str) -> dict[str, Any]:
    """Extract Obsidian-native metadata without rewriting the source text.

    The raw Markdown remains the authority.  This bounded parser only projects
    stable references useful to graph and knowledge adapters; unknown syntax is
    deliberately retained in ``content`` and marked as preserved.
    """
    if not isinstance(content, str):
        raise ObsidianVaultError("OBSIDIAN-MARKDOWN-TYPE", "Markdown content must be text")
    frontmatter: dict[str, Any] = {}
    frontmatter_raw = ""
    body = content
    lines = content.splitlines()
    if lines and lines[0].strip() == "---":
        end = next((i for i in range(1, min(len(lines), 201)) if lines[i].strip() == "---"), None)
        if end is not None:
            frontmatter_raw = "\n".join(lines[1:end])
            body = "\n".join(lines[end + 1 :])
            for line in lines[1:end]:
                key, separator, value = line.partition(":")
                if not separator or not key.strip():
                    continue
                normalized = value.strip()
                if normalized.lower() in {"true", "false"}:
                    parsed: Any = normalized.lower() == "true"
                else:
                    parsed = normalized.strip("'\"")
                frontmatter[key.strip()] = parsed
            try:
                parsed_frontmatter = yaml.safe_load(frontmatter_raw)
            except yaml.YAMLError:
                parsed_frontmatter = None
            if isinstance(parsed_frontmatter, Mapping):
                frontmatter = dict(parsed_frontmatter)
    wikilinks = sorted(
        {
            match.group(1).strip()
            for match in re.finditer(r"(?<!!)\[\[([^\]|#]+)(?:#[^\]|]+)?(?:\|[^\]]+)?\]\]", body)
            if match.group(1).strip()
        }
    )
    embeds = sorted(
        {
            match.group(1).strip()
            for match in re.finditer(r"!\[\[([^\]|]+)(?:\|[^\]]+)?\]\]", body)
            if match.group(1).strip()
        }
    )
    tags = sorted(set(re.findall(r"(?<![\w#])#([A-Za-z][\w/-]*)", body)))
    callouts = sorted(set(re.findall(r"^>\s*\[!([^\]]+)\]", body, flags=re.MULTILINE)))
    code_blocks = [
        language.strip()
        for language in re.findall(r"^```([^\r\n]*)", body, flags=re.MULTILINE)
        if language.strip()
    ]
    def _string_list(value: Any) -> list[str]:
        values = value if isinstance(value, list) else [value]
        return sorted({str(item).strip() for item in values if str(item).strip()})

    aliases = _string_list(frontmatter.get("aliases", frontmatter.get("alias", [])))
    block_references = sorted(
        set(re.findall(r"(?<![\w])\^([A-Za-z0-9][A-Za-z0-9_-]{0,79})\b", body))
    )
    relative_links = sorted(
        {
            match.group(1).strip()
            for match in re.finditer(r"(?<!!)\[[^\]]*\]\(([^)\s]+)(?:\s+['\"][^)]*['\"])?\)", body)
            if match.group(1).strip()
            and not match.group(1).startswith(("#", "/", "//"))
            and not re.match(r"^[A-Za-z][A-Za-z0-9+.-]*:", match.group(1))
        }
    )
    attachment_extensions = {
        ".avif", ".bmp", ".gif", ".jpeg", ".jpg", ".m4a", ".mp3", ".mp4",
        ".ogg", ".pdf", ".png", ".svg", ".wav", ".webm", ".webp",
    }
    attachments = sorted(
        {
            reference.split("#", 1)[0].split("?", 1)[0]
            for reference in [*embeds, *relative_links]
            if Path(reference.split("#", 1)[0].split("?", 1)[0]).suffix.lower()
            in attachment_extensions
        }
    )
    return {
        "schema": "productforge/ObsidianMarkdown/v1",
        "frontmatter": frontmatter,
        "frontmatter_raw": frontmatter_raw,
        "wikilinks": wikilinks,
        "embeds": embeds,
        "tags": tags,
        "callouts": callouts,
        "code_blocks": code_blocks,
        "aliases": aliases,
        "block_references": block_references,
        "relative_links": relative_links,
        "attachments": attachments,
        "content": content,
        "unknown_syntax_preserved": True,
    }


def import_vault_document(vault: Path | str, raw_path: str) -> dict[str, Any]:
    root = _resolved(Path(vault))
    if not root.is_dir():
        raise ObsidianVaultError("OBSIDIAN-VAULT-MISSING", "configured Obsidian vault is not a directory")
    path = _safe(root, raw_path)
    size = path.stat().st_size
    if size > MAX_VAULT_BYTES:
        raise ObsidianVaultError("OBSIDIAN-SIZE-LIMIT", "vault document exceeds the safe size limit")
    try:
        content = path.read_bytes().decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ObsidianVaultError(
            "OBSIDIAN-UTF8-INVALID", "vault document is not valid UTF-8"
        ) from exc
    if "\x00" in content:
        raise ObsidianVaultError(
            "OBSIDIAN-BINARY-REFUSED", "binary content is not a Markdown document"
        )
    return {
        "schema": "productforge/ObsidianDocument/v1",
        "path": path.relative_to(root).as_posix(),
        "title": _title(path, content),
        "content": content,
        "content_hash": hashlib.sha256(content.encode("utf-8")).hexdigest(),
        "size": size,
        "state": "ready_for_import",
        "markdown": parse_markdown_document(content),
        "provenance": {
            "adapter": "stdlib-obsidian-markdown",
            "vault": root.name,
            "cli_required": False,
            "imported_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        },
    }


def export_vault_document(
    vault: Path | str,
    raw_path: str,
    content: str,
    *,
    baseline_hash: str | None = None,
    classification: str = "internal",
    source: str = "product-forge",
) -> dict[str, Any]:
    """Export without silently overwriting a manually changed note.

    A new note can be created directly. An existing note requires its current
    hash as ``baseline_hash``; the old bytes are snapshotted before an atomic
    replace and the post-write hash is verified.
    """
    root = _resolved(Path(vault))
    if not root.is_dir():
        raise ObsidianVaultError("OBSIDIAN-VAULT-MISSING", "configured Obsidian vault is not a directory")
    if len(content.encode("utf-8")) > MAX_VAULT_BYTES:
        raise ObsidianVaultError("OBSIDIAN-SIZE-LIMIT", "vault document exceeds the safe size limit")
    classification = _classification(classification)
    path = _safe(root, raw_path, for_write=True)
    candidate_bytes = content.encode("utf-8")
    candidate_hash = hashlib.sha256(candidate_bytes).hexdigest()
    previous_hash = None
    backup_path = None
    if path.exists():
        previous_bytes = path.read_bytes()
        previous_hash = hashlib.sha256(previous_bytes).hexdigest()
        if baseline_hash is None:
            raise ObsidianVaultError(
                "OBSIDIAN-CONFLICT",
                "destination exists; provide baseline_hash before replacing it",
            )
        if baseline_hash != previous_hash:
            raise ObsidianVaultError(
                "OBSIDIAN-CONFLICT",
                "destination changed after the sync baseline was captured",
            )
        backup_dir = root / ".forge" / "obsidian-backups"
        backup_dir.mkdir(parents=True, exist_ok=True)
        backup_path = backup_dir / f"{previous_hash}.md"
        if not backup_path.exists():
            _atomic_write(backup_path, previous_bytes)
    _atomic_write(path, candidate_bytes)
    if hashlib.sha256(path.read_bytes()).hexdigest() != candidate_hash:
        raise ObsidianVaultError("OBSIDIAN-INTEGRITY", "post-write hash verification failed")
    receipt = {
        # Keep the original document schema/state for existing API consumers;
        # the additive receipt fields expose the stronger sync contract.
        "schema": "productforge/ObsidianDocument/v1",
        "receipt_schema": "theforge/ObsidianSyncReceipt/v1",
        "version": "v1",
        "path": path.relative_to(root).as_posix(),
        "title": _title(path, content),
        "content_hash": candidate_hash,
        "previous_hash": previous_hash,
        "size": len(candidate_bytes),
        "state": "exported",
        "sync_state": "created" if previous_hash is None else "updated",
        "outcome": "exported",
        "classification": classification,
        "source": source,
        "backup_path": backup_path.relative_to(root).as_posix() if backup_path else None,
        "receipt_path": f".forge/obsidian-receipts/{candidate_hash}.json",
        "warnings": [],
        "unresolved": [],
        "exported_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "provenance": {"adapter": "stdlib-obsidian-markdown", "vault": root.name, "cli_required": False},
    }
    receipt_path = root / ".forge" / "obsidian-receipts" / f"{candidate_hash}.json"
    _atomic_write(
        receipt_path,
        json.dumps(receipt, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8"),
    )
    return receipt


def plan_vault_sync(
    vault: Path | str,
    raw_path: str,
    content: str,
    *,
    baseline_hash: str | None = None,
    classification: str = "internal",
    source: str = "product-forge",
) -> dict[str, Any]:
    """Create a dry-run sync plan; it never mutates the vault."""
    root = _resolved(Path(vault))
    if not root.is_dir():
        raise ObsidianVaultError("OBSIDIAN-VAULT-MISSING", "configured Obsidian vault is not a directory")
    if len(content.encode("utf-8")) > MAX_VAULT_BYTES:
        raise ObsidianVaultError("OBSIDIAN-SIZE-LIMIT", "vault document exceeds the safe size limit")
    classification = _classification(classification)
    path = _safe(root, raw_path, for_write=True)
    candidate_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
    current_hash = hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None
    if current_hash is None:
        state = "created"
    elif current_hash == candidate_hash:
        state = "unchanged"
    elif baseline_hash is None or baseline_hash != current_hash:
        state = "conflict"
    else:
        state = "updated"
    return {
        "schema": "theforge/ObsidianSyncPlan/v1",
        "version": "v1",
        "workspace": str(root.parent),
        "vault_id": root.name,
        "path": path.relative_to(root).as_posix(),
        "source": source,
        "classification": classification,
        "content_hash": candidate_hash,
        "previous_hash": current_hash,
        "baseline_hash": baseline_hash,
        "outcome": state,
        "warnings": ["confirmation required for mutation"] if state in {"created", "updated"} else [],
        "unresolved": ["manual conflict resolution required"] if state == "conflict" else [],
        "planned_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
    }


def list_obsidian_receipts(vault: Path | str, *, limit: int = 50) -> list[dict[str, Any]]:
    """Return bounded, body-free export history from the vault's Forge ledger."""
    if not 1 <= limit <= 100:
        raise ObsidianVaultError("OBSIDIAN-HISTORY-LIMIT", "history limit must be between 1 and 100")
    root = _resolved(Path(vault))
    if not root.is_dir():
        raise ObsidianVaultError("OBSIDIAN-VAULT-MISSING", "configured Obsidian vault is not a directory")
    receipt_dir = root / ".forge" / "obsidian-receipts"
    if not receipt_dir.is_dir():
        return []
    if _reparse(receipt_dir):
        raise ObsidianVaultError(
            "OBSIDIAN-SYMLINK-REFUSED",
            "vault receipt ledger is a symlink or reparse point",
        )
    entries: list[tuple[float, dict[str, Any]]] = []
    for path in receipt_dir.glob("*.json"):
        try:
            if not path.is_file() or _reparse(path) or path.stat().st_size > MAX_INTEROP_BYTES:
                continue
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            continue
        if not isinstance(value, dict) or value.get("receipt_schema") != "theforge/ObsidianSyncReceipt/v1":
            continue
        entries.append((path.stat().st_mtime, {k: v for k, v in value.items() if k != "content"}))
    entries.sort(key=lambda item: (-item[0], str(item[1].get("path", ""))))
    return [value for _, value in entries[:limit]]


def _atomic_write(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    original_mode = stat.S_IMODE(path.stat().st_mode) if path.exists() else None
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        if original_mode is not None:
            os.chmod(temporary, original_mode)
        with os.fdopen(fd, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.replace(temporary, path)
        except OSError as exc:
            raise ObsidianVaultError("OBSIDIAN-WRITE-FAILED", "atomic vault replace failed") from exc
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
