"""Knowledge ingestion: deterministic chunking + hashing.

Chunking is paragraph-aware with a ~1200-char target and sentence
boundaries preferred. No ML deps — embeddings/LLM enrichment are
optional extras layered on top in later cycles.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

TARGET = 1200
MAX_CHUNK = 2000


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def chunk_text(text: str, target: int = TARGET, max_len: int = MAX_CHUNK) -> list[str]:
    text = text.replace("\r\n", "\n").strip()
    if not text:
        return []
    paras = re.split(r"\n\s*\n", text)
    chunks: list[str] = []
    buf = ""
    for para in paras:
        para = para.strip()
        if not para:
            continue
        if len(buf) + len(para) + 2 <= target:
            buf = f"{buf}\n\n{para}" if buf else para
            continue
        if buf:
            chunks.append(buf)
            buf = ""
        while len(para) > max_len:
            cut = para.rfind(". ", 0, max_len)
            cut = cut + 1 if cut > 0 else max_len
            chunks.append(para[:cut].strip())
            para = para[cut:].strip()
        buf = para
    if buf:
        chunks.append(buf)
    return [c for c in chunks if c]


@dataclass(frozen=True)
class MarkdownChunk:
    """A Markdown-aware chunk with stable provenance within one artifact."""

    text: str
    heading_path: tuple[str, ...]
    start_offset: int
    end_offset: int
    sequence: int
    token_estimate: int
    content_hash: str


_HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$")


def chunk_markdown(text: str, target: int = TARGET, max_len: int = MAX_CHUNK) -> list[MarkdownChunk]:
    """Split Markdown without losing headings, fences, tables or source spans.

    The existing :func:`chunk_text` remains the compatibility path for the
    SQLite store.  This richer representation is intentionally storage-neutral
    so adapters can persist document/chunk contracts without changing the
    current product database schema.
    """
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    if not normalized.strip():
        return []
    lines = normalized.splitlines(keepends=True)
    heading_stack: list[tuple[int, str]] = []
    blocks: list[tuple[str, tuple[str, ...], int, int]] = []
    block_lines: list[str] = []
    block_start = 0
    offset = 0
    in_fence = False

    def flush(end: int) -> None:
        nonlocal block_lines, block_start
        value = "".join(block_lines).strip()
        if value:
            blocks.append((value, tuple(title for _, title in heading_stack), block_start, end))
        block_lines = []
        block_start = end

    for raw in lines:
        line = raw.rstrip("\r\n")
        heading = None if in_fence else _HEADING.match(line)
        if heading:
            flush(offset)
            level, title = len(heading.group(1)), heading.group(2).strip()
            heading_stack[:] = [(n, value) for n, value in heading_stack if n < level]
            heading_stack.append((level, title))
            block_start = offset
        elif not in_fence and not line.strip():
            flush(offset + len(raw))
        else:
            if not block_lines:
                block_start = offset
            block_lines.append(raw)
            if line.lstrip().startswith("```") or line.lstrip().startswith("~~~"):
                in_fence = not in_fence
        offset += len(raw)
    flush(len(normalized))

    result: list[MarkdownChunk] = []
    sequence = 0
    for value, headings, start, end in blocks:
        # Keep fenced code and table blocks atomic: splitting either changes
        # their meaning and makes later citations impossible to reconstruct.
        structured = value.lstrip().startswith(("```", "~~~", "|"))
        pieces = [value] if structured else chunk_text(value, target=target, max_len=max_len)
        cursor = start
        for piece in pieces:
            relative = normalized.find(piece, cursor, end)
            if relative < 0:
                relative = cursor
            piece_end = relative + len(piece)
            result.append(
                MarkdownChunk(
                    text=piece,
                    heading_path=headings,
                    start_offset=relative,
                    end_offset=piece_end,
                    sequence=sequence,
                    token_estimate=max(1, len(piece.split())),
                    content_hash=sha256_text(piece),
                )
            )
            sequence += 1
            cursor = piece_end
    return result
