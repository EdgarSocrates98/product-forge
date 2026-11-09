"""Measure the local knowledge pipeline without inventing production claims.

The receipt covers the operations that exist in the current product: safe vault
scan, bounded import, wikilink resolution, one atomic export and SQLite/FTS
reindex/search.  Peak Python allocation is captured with ``tracemalloc``. LLM
token usage and citation quality are reported as ``NOT_RUN`` because this
offline benchmark has no model provider and must not fabricate those signals.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import tempfile
import time
import tracemalloc
from collections.abc import Callable
from pathlib import Path
from typing import Any, TypeVar

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "src"))
sys.path.insert(0, str(_ROOT / "forge-obsidian" / "src"))

from product_forge.knowledge.obsidian import (  # noqa: E402
    export_vault_document,
    import_vault_documents,
    scan_vault_documents,
)  # noqa: E402
from product_forge.knowledge.store_benchmark import run as run_store_benchmark  # noqa: E402

T = TypeVar("T")
SCHEMA = "product-forge/knowledge-observability-benchmark/v1"
NOTE = """---
aliases: [Benchmark note {index}]
knowledge_state: draft
---
# Benchmark note {index}

See [[note-{next_index:04d}]]. The bounded diagnostic contains evidence and a
stable reference for the local knowledge pipeline.
"""


def _measure(fn: Callable[[], T]) -> tuple[T, float, int]:
    tracemalloc.start()
    started = time.perf_counter()
    try:
        value = fn()
        elapsed_ms = (time.perf_counter() - started) * 1000
        _current, peak_bytes = tracemalloc.get_traced_memory()
        return value, round(elapsed_ms, 3), peak_bytes
    finally:
        tracemalloc.stop()


def _vault(size: int) -> tuple[tempfile.TemporaryDirectory[str], Path, list[str]]:
    temporary = tempfile.TemporaryDirectory(prefix="productforge-observability-")
    root = Path(temporary.name) / "vault"
    notes = root / "notes"
    notes.mkdir(parents=True)
    (root / "exports").mkdir()
    paths: list[str] = []
    for index in range(size):
        name = f"note-{index:04d}.md"
        (notes / name).write_text(
            NOTE.format(index=index, next_index=(index + 1) % size),
            encoding="utf-8",
        )
        paths.append(f"notes/{name}")
    return temporary, root, paths


def _resolve_wikilinks(imported: list[dict[str, Any]]) -> dict[str, int]:
    targets = {Path(str(item["path"])).stem.casefold() for item in imported}
    links = 0
    resolved = 0
    for item in imported:
        for link in item.get("markdown", {}).get("wikilinks", []):
            links += 1
            if Path(str(link)).stem.casefold() in targets:
                resolved += 1
    return {"links": links, "resolved": resolved, "unresolved": links - resolved}


def _row(size: int) -> dict[str, Any]:
    temporary, vault, paths = _vault(size)
    try:
        scanned, scan_ms, scan_peak = _measure(
            lambda: scan_vault_documents(vault, prefix="notes", limit=size)
        )
        imported, import_ms, import_peak = _measure(lambda: import_vault_documents(vault, paths))
        resolved, resolve_ms, resolve_peak = _measure(lambda: _resolve_wikilinks(imported))
        _exported, export_ms, export_peak = _measure(
            lambda: export_vault_document(
                vault,
                f"exports/benchmark-{size}.md",
                "# Export benchmark\n\nReviewed candidate.\n",
            )
        )
        store_receipt, store_ms, store_peak = _measure(
            lambda: run_store_benchmark((size,), 1)["results"][0]
        )
        return {
            "documents": size,
            "scan": {
                "status": "PASS",
                "count": len(scanned["items"]),
                "elapsed_ms": scan_ms,
                "peak_python_bytes": scan_peak,
            },
            "import": {
                "status": "PASS",
                "count": len(imported),
                "elapsed_ms": import_ms,
                "peak_python_bytes": import_peak,
            },
            "wikilink_resolution": {
                "status": "PASS",
                **resolved,
                "elapsed_ms": resolve_ms,
                "peak_python_bytes": resolve_peak,
            },
            "export": {
                "status": "PASS",
                "scope": "one atomic document export",
                "elapsed_ms": export_ms,
                "peak_python_bytes": export_peak,
            },
            "reindex_search": {
                "status": "PASS",
                "scope": "SQLite FTS local benchmark",
                "elapsed_ms": store_ms,
                "peak_python_bytes": store_peak,
                **store_receipt,
            },
            "token_usage": {
                "status": "NOT_RUN",
                "reason": "no model provider is used by the offline benchmark",
            },
            "citation_quality": {
                "status": "NOT_RUN",
                "reason": "quality requires a governed retrieval/evaluation corpus",
            },
        }
    finally:
        temporary.cleanup()


def run(sizes: tuple[int, ...], iterations: int = 1) -> dict[str, Any]:
    if not sizes or any(size < 1 or size > 10_000 for size in sizes):
        raise ValueError("sizes must be between 1 and 10000")
    if iterations < 1:
        raise ValueError("iterations must be positive")
    rows: list[dict[str, Any]] = []
    for size in sizes:
        samples = [_row(size) for _ in range(iterations)]
        row = samples[0]
        if iterations > 1:
            for operation in ("scan", "import", "wikilink_resolution", "export", "reindex_search"):
                row[operation]["elapsed_ms_median"] = round(
                    statistics.median(sample[operation]["elapsed_ms"] for sample in samples), 3
                )
        rows.append(row)
    return {
        "schema": SCHEMA,
        "status": "PASS",
        "scope": "local-observability-only",
        "sizes": list(sizes),
        "iterations": iterations,
        "limitations": [
            "tracemalloc measures Python allocations, not resident process memory",
            "export measures one document per size, not a bulk export API",
            "token usage and citation quality are NOT_RUN without a model/evaluation corpus",
        ],
        "results": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sizes", default="100,1000,10000")
    parser.add_argument("--iterations", type=int, default=1)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    sizes = tuple(int(value.strip()) for value in args.sizes.split(",") if value.strip())
    receipt = run(sizes, args.iterations)
    output = json.dumps(receipt, ensure_ascii=False, indent=2) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(output, encoding="utf-8")
    print(output, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
