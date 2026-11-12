from product_forge.domain.models import Document, DocumentStatus, new_id
from product_forge.knowledge.versions import explorer_versions, prepare_version
from product_forge.store.sqlite import Store


def test_source_backed_documents_keep_persisted_lineage(tmp_path):
    store = Store(tmp_path / "state.db")
    first_metadata, previous = prepare_version(
        store, "prd_1", {"source": "url", "source_url": "https://example.com/runbook"}
    )
    assert previous is None
    first = Document(
        id=new_id("doc"),
        product_id="prd_1",
        title="Runbook",
        content_hash="a",
        status=DocumentStatus.INDEXED,
        metadata=first_metadata,
    )
    store.put("documents", first)

    second_metadata, previous = prepare_version(
        store, "prd_1", {"source": "url", "source_url": "https://example.com/runbook"}
    )
    second = Document(
        id=new_id("doc"),
        product_id="prd_1",
        title="Runbook",
        content_hash="b",
        status=DocumentStatus.INDEXED,
        metadata=second_metadata,
    )
    store.put("documents", second)

    first_saved = store.get("documents", first.id)
    assert previous == first.id
    assert first_saved["metadata"]["is_current"] is False
    assert second.metadata_["version"] == 2
    assert second.metadata_["previous_document_id"] == first.id

    versions = explorer_versions(store, "prd_1", store.get("documents", second.id))
    assert versions["state"] == "historical"
    assert [item["metadata"]["version"] for item in versions["items"]] == [1, 2]
    assert versions["current_document_id"] == second.id
    store.close()
