"""Reproducible scale benchmark for Product Forge knowledge extraction.

The benchmark exercises the production Markdown chunker, not a synthetic
reimplementation. It deliberately reports extraction-only evidence; SQLite
write/search latency is a separate future benchmark and is never implied by
this receipt.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import time
from pathlib import Path
from typing import Any

from product_forge.knowledge.ingest import chunk_markdown

DOCUMENT = """# Spark diagnosis {index}

The orders pipeline has a p95 latency metric and a bounded retry policy.
The diagnostic agent must preserve headings, source spans and evidence refs.

```python
df = spark.read.parquet("s3://bucket/orders")
```
"""


def _one(size: int) -> dict[str, Any]:
    documents = [DOCUMENT.format(index=index) for index in range(size)]
    started = time.perf_counter()
    chunks = [chunk for document in documents for chunk in chunk_markdown(document)]
    elapsed = time.perf_counter() - started
    digest = hashlib.sha256("".join(chunk.content_hash for chunk in chunks).encode("ascii")).hexdigest()
    return {
        "documents": size,
        "chunks": len(chunks),
        "elapsed_ms": round(elapsed * 1000, 3),
        "documents_per_second": round(size / elapsed, 2) if elapsed else None,
        "chunks_per_second": round(len(chunks) / elapsed, 2) if elapsed else None,
        "content_digest": digest,
    }


def run(sizes: tuple[int, ...], iterations: int) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for size in sizes:
        samples = [_one(size) for _ in range(iterations)]
        elapsed = [float(sample["elapsed_ms"]) for sample in samples]
        best = samples[elapsed.index(min(elapsed))]
        rows.append(
            {
                "documents": size,
                "iterations": iterations,
                "elapsed_ms_min": min(elapsed),
                "elapsed_ms_median": round(statistics.median(elapsed), 3),
                "elapsed_ms_max": max(elapsed),
                "documents_per_second_best": best["documents_per_second"],
                "chunks": best["chunks"],
                "content_digest": best["content_digest"],
            }
        )
    return {
        "schema": "product-forge/knowledge-scale-benchmark/v1",
        "status": "PASS",
        "scope": "markdown-chunking-only",
        "sizes": list(sizes),
        "iterations": iterations,
        "results": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sizes", default="100,1000,10000")
    parser.add_argument("--iterations", type=int, default=3)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    sizes = tuple(int(value.strip()) for value in args.sizes.split(",") if value.strip())
    if not sizes or any(value <= 0 for value in sizes):
        parser.error("--sizes must contain positive integers")
    if args.iterations < 1:
        parser.error("--iterations must be positive")
    receipt = run(sizes, args.iterations)
    text = json.dumps(receipt, ensure_ascii=False, indent=2) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8")
    print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
