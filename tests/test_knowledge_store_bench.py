from product_forge.knowledge.store_benchmark import run


def test_store_benchmark_receipt_is_bounded_and_searchable():
    receipt = run((3,), 1)

    assert receipt["schema"] == "product-forge/knowledge-store-benchmark/v1"
    assert receipt["status"] == "PASS"
    row = receipt["results"][0]
    assert row["documents"] == 3
    assert row["chunks"] == 3
    assert row["search_hits"] == 3
    assert row["database_bytes"] > 0
