from product_forge.knowledge.obsidian import validate_base_document, validate_canvas_document
from product_forge.knowledge.obsidian_templates import (
    TEMPLATE_IDS,
    build_base_document,
    build_canvas_document,
    render_obsidian_template,
)


def test_all_required_templates_render_as_explicit_drafts():
    assert len(TEMPLATE_IDS) == 14
    for template_id in TEMPLATE_IDS:
        note = render_obsidian_template(
            template_id,
            title="Investigation",
            source="spark-forge-aws",
            summary="Evidence-backed summary.",
            sections={"Findings": "- unresolved"},
            relations=("runbook://spark",),
        )
        assert f"forge_template: {template_id}" in note
        assert "knowledge_state: draft" in note
        assert "runbook://spark" in note


def test_canvas_projection_is_deterministic_and_structurally_valid():
    first = build_canvas_document(
        title="Spark investigation",
        central_note="Partitions are uneven.",
        evidence=["evidence://job-1"],
        hypotheses=["skew in input distribution"],
        decisions=["review partition strategy"],
        next_steps=["run the bounded diagnostic"],
    )
    second = build_canvas_document(
        title="Spark investigation",
        central_note="Partitions are uneven.",
        evidence=["evidence://job-1"],
        hypotheses=["skew in input distribution"],
        decisions=["review partition strategy"],
        next_steps=["run the bounded diagnostic"],
    )
    assert first == second
    assert validate_canvas_document(first)["state"] == "validated"


def test_base_projection_is_bounded_and_does_not_evaluate_formulas():
    document = build_base_document(
        dashboard_id="open-investigations",
        title="Open investigations",
        filter_expression="knowledge_state = 'draft'",
    )
    result = validate_base_document(document)
    assert result["state"] == "validated"
    assert "full Bases semantics are not implemented" in result["warnings"][0]
    assert document["metadata"]["formula_engine"] == "not_implemented"
