"""Deterministic Obsidian templates and bounded Level-B projections.

The module generates new documents only. It never evaluates Bases formulas,
executes Canvas content, or rewrites an existing note; the vault adapter owns
the reviewed write path and conflict policy.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Iterable, Mapping
from typing import Any

import yaml

from product_forge.knowledge.obsidian import serialize_base_document

TEMPLATE_IDS = (
    "investigation-note",
    "spark-diagnostic",
    "glue-lake-formation-incident",
    "azure-runtime-investigation",
    "api-contract-review",
    "api-breaking-change",
    "platform-incident",
    "runbook",
    "adr",
    "postmortem",
    "decision-record",
    "knowledge-source",
    "validation-report",
    "cross-forge-investigation",
)

BASE_DASHBOARD_SPECS = (
    ("open-investigations", "Open Investigations", 'knowledge_state == "draft"'),
    ("verified-knowledge", "Verified Knowledge", 'knowledge_state == "validated"'),
    ("stale-knowledge", "Stale Knowledge", 'freshness == "stale"'),
    ("unresolved-findings", "Unresolved Findings", "unresolved_count > 0"),
    ("api-contract-changes", "API Contract Changes", 'forge_domain == "api"'),
    ("spark-incidents", "Spark Incidents", 'forge_domain == "spark"'),
    ("platform-incidents", "Platform Incidents", 'forge_domain == "platform"'),
    ("cross-forge-decisions", "Cross-Forge Decisions", 'forge_domain == "cross-forge"'),
)


def _slug(value: str) -> str:
    result = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return result or "item"


def _frontmatter(template_id: str, title: str, source: str, classification: str) -> str:
    metadata = {
        "forge_template": template_id,
        "title": title.strip() or "Investigation",
        "source": source.strip() or "product-forge",
        "classification": classification,
        "knowledge_state": "draft",
    }
    return yaml.safe_dump(metadata, sort_keys=False, allow_unicode=True).rstrip()


def render_obsidian_template(
    template_id: str,
    *,
    title: str,
    source: str,
    classification: str = "internal",
    summary: str = "",
    sections: Mapping[str, str] | None = None,
    relations: Iterable[str] = (),
) -> str:
    """Render a reviewable Markdown note with explicit draft provenance."""
    if template_id not in TEMPLATE_IDS:
        raise ValueError(f"unknown Obsidian template: {template_id}")
    if classification not in {"public", "internal", "confidential", "restricted"}:
        raise ValueError(f"unsupported classification: {classification}")
    lines = [
        "---",
        _frontmatter(template_id, title, source, classification),
        "---",
        "",
        f"# {title.strip() or 'Investigation'}",
        "",
    ]
    if summary.strip():
        lines.extend([summary.strip(), ""])
    for heading, body in (sections or {}).items():
        if not str(heading).strip():
            continue
        lines.extend([f"## {heading.strip()}", body.strip() or "- None reported", ""])
    relation_items = [item.strip() for item in relations if str(item).strip()]
    if relation_items:
        lines.extend(["## Related references", *[f"- {item}" for item in relation_items], ""])
    return "\n".join(lines).rstrip() + "\n"


def build_canvas_document(
    *,
    title: str,
    central_note: str,
    evidence: Iterable[str] = (),
    hypotheses: Iterable[str] = (),
    causes: Iterable[str] = (),
    resources: Iterable[str] = (),
    contracts: Iterable[str] = (),
    decisions: Iterable[str] = (),
    next_steps: Iterable[str] = (),
) -> dict[str, Any]:
    """Build a deterministic, structural JSON Canvas subset.

    Node IDs are content-derived so repeating a projection does not create
    artificial graph churn. The output is a document, not an executable plan.
    """
    groups = (
        ("evidence", "Evidence", evidence),
        ("hypotheses", "Hypotheses", hypotheses),
        ("causes", "Causes", causes),
        ("resources", "Resources", resources),
        ("contracts", "Contracts", contracts),
        ("decisions", "Decisions", decisions),
        ("next-steps", "Next steps", next_steps),
    )
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    center_id = "node-" + hashlib.sha256(("center:" + title).encode("utf-8")).hexdigest()[:12]
    nodes.append({
        "id": center_id,
        "type": "text",
        "text": f"# {title}\n\n{central_note}".strip(),
        "x": 0,
        "y": 0,
        "width": 420,
        "height": 220,
    })
    index = 0
    for group_id, heading, values in groups:
        for value in values:
            text = str(value).strip()
            if not text:
                continue
            node_id = "node-" + hashlib.sha256(f"{group_id}:{index}:{text}".encode()).hexdigest()[:12]
            node = {
                "id": node_id,
                "type": "text",
                "text": f"## {heading}\n\n{text}",
                "x": 520 + (index % 2) * 460,
                "y": 260 + (index // 2) * 180,
                "width": 380,
                "height": 140,
            }
            nodes.append(node)
            edges.append({
                "id": "edge-" + hashlib.sha256(f"{center_id}:{node_id}".encode()).hexdigest()[:12],
                "fromNode": center_id,
                "toNode": node_id,
                "fromSide": "right",
                "toSide": "left",
                "toEnd": "arrow",
            })
            index += 1
    return {"nodes": nodes, "edges": edges}


def build_base_document(*, dashboard_id: str, title: str, filter_expression: str) -> dict[str, Any]:
    """Build a valid official Bases document understood by Obsidian.

    The dashboard id selects the caller's destination filename; it is not
    emitted as an undocumented top-level Bases field. Filters are emitted as
    source syntax only; Product Forge never evaluates formulas.
    """
    if not dashboard_id.strip() or not title.strip() or not filter_expression.strip():
        raise ValueError("dashboard_id, title and filter_expression are required")
    return {
        "filters": filter_expression.strip(),
        "views": [{"type": "table", "name": title.strip()}],
    }


def render_base_document(*, dashboard_id: str, title: str, filter_expression: str) -> str:
    """Render one official ``.base`` file as deterministic YAML."""
    return serialize_base_document(
        build_base_document(
            dashboard_id=dashboard_id,
            title=title,
            filter_expression=filter_expression,
        )
    )


def build_base_dashboard_catalog() -> list[dict[str, Any]]:
    """Build the bounded dashboard set used by the knowledge workspace.

    Filters are emitted as source syntax only. The caller still owns review,
    vault authorization and the reviewed sync path; this function never
    evaluates a Bases expression or reads vault state.
    """
    return [
        build_base_document(
            dashboard_id=dashboard_id,
            title=title,
            filter_expression=filter_expression,
        )
        for dashboard_id, title, filter_expression in BASE_DASHBOARD_SPECS
    ]


def build_base_dashboard_artifacts() -> dict[str, str]:
    """Return the governed dashboard ids mapped to ready-to-write ``.base`` YAML."""
    return {
        dashboard_id: render_base_document(
            dashboard_id=dashboard_id,
            title=title,
            filter_expression=filter_expression,
        )
        for dashboard_id, title, filter_expression in BASE_DASHBOARD_SPECS
    }


__all__ = [
    "TEMPLATE_IDS",
    "BASE_DASHBOARD_SPECS",
    "build_base_document",
    "build_base_dashboard_catalog",
    "build_base_dashboard_artifacts",
    "build_canvas_document",
    "render_base_document",
    "render_obsidian_template",
]
