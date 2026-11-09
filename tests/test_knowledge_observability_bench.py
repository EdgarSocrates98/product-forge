import importlib.util
from pathlib import Path

_SPEC = importlib.util.spec_from_file_location(
    "knowledge_observability_bench",
    Path(__file__).parents[1] / "scripts" / "knowledge_observability_bench.py",
)
assert _SPEC and _SPEC.loader
_MODULE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MODULE)
run = _MODULE.run


def test_observability_receipt_measures_local_budget_and_fixture_citations_without_faking_provider_usage():
    receipt = run((3,), 1)
    assert receipt["schema"] == "product-forge/knowledge-observability-benchmark/v1"
    row = receipt["results"][0]
    assert row["scan"]["count"] == 3
    assert row["import"]["count"] == 3
    assert row["wikilink_resolution"]["resolved"] == 3
    assert row["reindex_search"]["search_hits"] == 3
    assert row["token_budget"]["status"] == "PASS"
    assert row["token_budget"]["provider_usage"] == "NOT_RUN"
    assert row["citation_quality"]["status"] == "PASS"
    assert row["citation_quality"]["precision_at_3"] == 1.0
    assert row["citation_quality"]["citation_completeness"] == 1.0
