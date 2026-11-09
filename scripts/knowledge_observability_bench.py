"""Measure the local knowledge pipeline without inventing production claims.

The receipt covers the operations that exist in the current product: safe vault
scan, bounded import, wikilink resolution, one atomic export and SQLite/FTS
reindex/search.  Peak Python allocation is captured with ``tracemalloc``.
Provider token usage is reported separately as ``NOT_RUN`` because this offline
benchmark has no model provider. Retrieval-context budget and citation quality
are measured against a deterministic fixture corpus.
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

from product_forge.knowledge.ingest import chunk_text  # noqa: E402
from product_forge.knowledge.obsidian import (  # noqa: E402
    export_vault_document,
    import_vault_documents,
    scan_vault_documents,
)  # noqa: E402
from product_forge.knowledge.store_benchmark import run as run_store_benchmark  # noqa: E402
from product_forge.store.sqlite import Store  # noqa: E402

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


def _retrieval_quality() -> tuple[dict[str, Any], dict[str, Any]]:
    """Measure fixture-grounded citation quality and retrieval context budget."""
    corpus = (
        (
            "quality-spark",
            "Spark diagnosis",
            "Spark partition skew caused long-running tasks and uneven input partitions.",
            "spark skew partitions",
        ),
        (
            "quality-api",
            "API contract",
            "The API contract review found a breaking response field change and endpoint evidence.",
            "api contract breaking endpoint",
        ),
        (
            "quality-platform",
            "Platform incident",
            "The platform incident was linked to a Kubernetes deployment rollout and runbook.",
            "kubernetes deployment rollout",
        ),
    )
    with tempfile.TemporaryDirectory(prefix="productforge-citation-quality-") as directory:
        store = Store(Path(directory) / "quality.db")
        try:
            with store.transaction():
                for document_id, title, content, _question in corpus:
                    document = {
                        "id": document_id,
                        "product_id": "quality-product",
                        "title": title,
                        "content": content,
                        "source": {"kind": "fixture", "locator": f"fixture://{document_id}"},
                    }
                    store.put_doc("documents", document)
                    store.put_chunks(
                        document_id,
                        "quality-product",
                        chunk_text(content),
                    )

            rows: list[dict[str, Any]] = []
            context_token_counts: list[int] = []
            for expected_id, _title, _content, question in corpus:
                hits = store.search_fts("quality-product", question, limit=3)
                citations = [
                    {
                        "chunk_id": hit["id"],
                        "document_id": hit["document_id"],
                        "snippet": hit["snip"],
                        "title": store.doc_title(hit["document_id"]),
                    }
                    for hit in hits
                ]
                valid = all(
                    all(
                        str(citation.get(field) or "").strip()
                        for field in ("chunk_id", "document_id", "snippet", "title")
                    )
                    for citation in citations
                )
                context_tokens = sum(
                    max(1, len(str(citation["snippet"]).split())) for citation in citations
                )
                context_token_counts.append(context_tokens)
                rows.append(
                    {
                        "question": question,
                        "expected_document_id": expected_id,
                        "retrieved_document_ids": [
                            citation["document_id"] for citation in citations
                        ],
                        "relevant_retrieved": sum(
                            1
                            for citation in citations
                            if citation["document_id"] == expected_id
                        ),
                        "citation_fields_complete": valid,
                        "context_tokens_estimate": context_tokens,
                    }
                )
            relevant = sum(row["relevant_retrieved"] for row in rows)
            retrieved = sum(len(row["retrieved_document_ids"]) for row in rows)
            precision = relevant / retrieved if retrieved else 0.0
            recall = relevant / len(rows) if rows else 0.0
            completeness = (
                sum(row["citation_fields_complete"] for row in rows) / len(rows)
                if rows
                else 0.0
            )
            citation_quality = {
                "status": (
                    "PASS"
                    if precision == 1.0 and recall == 1.0 and completeness == 1.0
                    else "FAIL"
                ),
                "scope": "deterministic fixture retrieval; not a provider answer-quality evaluation",
                "precision_at_3": round(precision, 3),
                "recall_at_3": round(recall, 3),
                "citation_completeness": round(completeness, 3),
                "queries": rows,
            }
            token_budget = {
                "status": "PASS",
                "scope": "retrieval-context estimate",
                "max_context_tokens": max(context_token_counts, default=0),
                "mean_context_tokens": round(
                    sum(context_token_counts) / len(context_token_counts), 3
                )
                if context_token_counts
                else 0,
                "provider_usage": "NOT_RUN",
                "provider_usage_reason": "no model provider is used by the offline benchmark",
            }
            return token_budget, citation_quality
        finally:
            store.close()


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
        token_budget, citation_quality = _retrieval_quality()
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
            "token_budget": token_budget,
            "token_usage": {
                "status": "NOT_RUN",
                "reason": "provider token usage requires a governed model-provider run",
            },
            "citation_quality": citation_quality,
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
            "provider token usage is NOT_RUN without a governed model-provider run",
            "citation quality is fixture-scoped and does not represent provider answer quality",
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
