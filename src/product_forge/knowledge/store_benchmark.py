"""Reproducible SQLite + FTS benchmark for Product Forge knowledge storage."""

from __future__ import annotations

import argparse
import json
import statistics
import tempfile
import time
from pathlib import Path
from typing import Any

from ..store.sqlite import Store
from .ingest import chunk_text


def _document(index: int) -> dict[str, Any]:
    content = (
        f"# Spark diagnosis {index}\n\n"
        "The orders pipeline has a p95 latency metric and a bounded retry policy.\n"
    )
    return {
        "id": f"bench-document-{index}",
        "product_id": "bench-product",
        "title": f"Spark diagnosis {index}",
        "content": content,
        "source": {"kind": "benchmark", "locator": f"bench://document/{index}"},
    }


def _one(size: int) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="productforge-store-bench-") as directory:
        database = Path(directory) / "state.db"
        store = Store(database)
        try:
            write_started = time.perf_counter()
            with store.transaction():
                for index in range(size):
                    document = _document(index)
                    store.put_doc("documents", document)
                    store.put_chunks(document["id"], document["product_id"], chunk_text(document["content"]))
            write_elapsed = time.perf_counter() - write_started

            search_started = time.perf_counter()
            hits = store.search_fts("bench-product", "latency retry", limit=20)
            search_elapsed = time.perf_counter() - search_started
            assert store.integrity_check()
            return {
                "documents": size,
                "chunks": len(store.list_chunks("bench-product", limit=size + 1)),
                "write_ms": round(write_elapsed * 1000, 3),
                "search_ms": round(search_elapsed * 1000, 3),
                "search_hits": len(hits),
                "documents_per_second": round(size / write_elapsed, 2) if write_elapsed else None,
                "database_bytes": database.stat().st_size,
            }
        finally:
            store.close()


def run(sizes: tuple[int, ...], iterations: int) -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    for size in sizes:
        samples = [_one(size) for _ in range(iterations)]
        results.append(
            {
                "documents": size,
                "iterations": iterations,
                "write_ms_median": round(statistics.median(sample["write_ms"] for sample in samples), 3),
                "search_ms_median": round(statistics.median(sample["search_ms"] for sample in samples), 3),
                "write_ms_max": max(sample["write_ms"] for sample in samples),
                "search_ms_max": max(sample["search_ms"] for sample in samples),
                "chunks": samples[0]["chunks"],
                "search_hits": samples[0]["search_hits"],
                "database_bytes": samples[0]["database_bytes"],
            }
        )
    return {
        "schema": "product-forge/knowledge-store-benchmark/v1",
        "status": "PASS",
        "scope": "sqlite-store-and-fts-local-baseline",
        "sizes": list(sizes),
        "iterations": iterations,
        "results": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sizes", default="100,1000,10000")
    parser.add_argument("--iterations", type=int, default=1)
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
