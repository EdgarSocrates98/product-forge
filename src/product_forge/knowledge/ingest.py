"""Knowledge ingestion: deterministic chunking + hashing.

Chunking is paragraph-aware with a ~1200-char target and sentence
boundaries preferred. No ML deps — embeddings/LLM enrichment are
optional extras layered on top in later cycles.
"""

from __future__ import annotations

import hashlib
import re

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
