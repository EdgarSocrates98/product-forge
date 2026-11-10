import pytest

from product_forge.knowledge.lifecycle import KnowledgeLifecycleError, transition


def test_agent_knowledge_requires_review_and_evidence_before_validation():
    metadata, receipt = transition({"knowledge_state": "draft"}, "reviewed", reason="human review")
    assert metadata["knowledge_state"] == "reviewed"
    assert receipt["changed"] is True
    with pytest.raises(KnowledgeLifecycleError, match="evidence"):
        transition(metadata, "validated")
    validated, receipt = transition(
        metadata, "validated", evidence_refs=["spark-job-42", "run-abc"], reason="checked against receipt"
    )
    assert validated["knowledge_state"] == "validated"
    assert validated["knowledge_evidence_refs"] == ["run-abc", "spark-job-42"]
    assert receipt["evidence_refs"] == ["run-abc", "spark-job-42"]


@pytest.mark.parametrize(
    ("source", "target"),
    [
        ("captured", "validated"),
        ("draft", "deprecated"),
        ("validated", "rejected"),
        ("deprecated", "validated"),
    ],
)
def test_unsafe_knowledge_transitions_are_refused(source, target):
    with pytest.raises(KnowledgeLifecycleError):
        transition({"knowledge_state": source}, target, evidence_refs=["evidence-1"])


def test_legacy_documents_are_safe_and_same_state_is_idempotent():
    metadata, receipt = transition({}, "captured")
    assert metadata["knowledge_state"] == "captured"
    assert receipt["changed"] is False
