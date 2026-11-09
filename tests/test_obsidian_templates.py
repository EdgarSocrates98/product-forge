from product_forge.knowledge.obsidian import validate_base_document, validate_canvas_document
from product_forge.knowledge.obsidian_templates import (
    BASE_DASHBOARD_SPECS,
    TEMPLATE_IDS,
    build_base_dashboard_catalog,
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


def test_canvas_projection_covers_all_cross_forge_story_groups():
    document = build_canvas_document(
        title="Cross-Forge investigation",
        central_note="Evidence-backed decision.",
        causes=["uneven input"],
        resources=["runbook://spark"],
        contracts=["contract://orders"],
    )

    text = "\n".join(node["text"] for node in document["nodes"])
    assert all(heading in text for heading in ("Causes", "Resources", "Contracts"))
    assert validate_canvas_document(document)["state"] == "validated"


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


def test_base_dashboard_catalog_covers_the_governed_knowledge_views():
    catalog = build_base_dashboard_catalog()

    assert len(catalog) == 8
    assert {item["name"] for item in catalog} == {item[0] for item in BASE_DASHBOARD_SPECS}
    assert {item["views"][0]["name"] for item in catalog} == {
        "Open Investigations",
        "Verified Knowledge",
        "Stale Knowledge",
        "Unresolved Findings",
        "API Contract Changes",
        "Spark Incidents",
        "Platform Incidents",
        "Cross-Forge Decisions",
    }
    assert all(validate_base_document(item)["state"] == "validated" for item in catalog)
