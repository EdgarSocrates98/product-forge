"""Governed lifecycle for knowledge documents.

The state is deliberately separate from the indexing status on ``Document``:
``indexed`` only says that storage/search succeeded; it never makes content
authoritative.  Promotion to ``validated`` therefore requires explicit
evidence references and every transition is retained in document metadata.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal

KnowledgeState = Literal["captured", "draft", "reviewed", "validated", "deprecated", "rejected"]
KNOWLEDGE_STATES: tuple[str, ...] = (
    "captured",
    "draft",
    "reviewed",
    "validated",
    "deprecated",
    "rejected",
)

ALLOWED_TRANSITIONS: dict[str, frozenset[str]] = {
    "captured": frozenset({"draft", "reviewed", "rejected"}),
    "draft": frozenset({"reviewed", "rejected"}),
    "reviewed": frozenset({"draft", "validated", "rejected"}),
    "validated": frozenset({"reviewed", "deprecated"}),
    "deprecated": frozenset({"draft"}),
    "rejected": frozenset({"draft"}),
}


class KnowledgeLifecycleError(ValueError):
    """A requested knowledge-state transition is not governed."""


def current_state(metadata: dict[str, Any] | None) -> KnowledgeState:
    """Read a state, treating legacy documents as captured rather than trusted."""
    value = str((metadata or {}).get("knowledge_state") or "captured").strip().lower()
    if value not in KNOWLEDGE_STATES:
        raise KnowledgeLifecycleError(f"unsupported knowledge state {value!r}")
    return value  # type: ignore[return-value]


def transition(
    metadata: dict[str, Any] | None,
    target: str,
    *,
    evidence_refs: list[str] | tuple[str, ...] = (),
    reason: str = "",
    actor: str = "local",
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Apply one explicit transition and return metadata plus an audit receipt."""
    source = current_state(metadata)
    target = str(target or "").strip().lower()
    if target not in KNOWLEDGE_STATES:
        raise KnowledgeLifecycleError(f"unsupported knowledge state {target!r}")
    refs = sorted({str(ref).strip() for ref in evidence_refs if str(ref).strip()})
    reason = str(reason or "").strip()[:1000]
    if target == source:
        return dict(metadata or {}) | {"knowledge_state": source}, {
            "state": source,
            "previous_state": source,
            "changed": False,
            "evidence_refs": refs,
        }
    allowed = ALLOWED_TRANSITIONS[source]
    if target not in allowed:
        raise KnowledgeLifecycleError(f"transition {source!r} -> {target!r} is not allowed")
    if target == "validated" and not refs:
        raise KnowledgeLifecycleError("validated state requires at least one evidence reference")

    now = datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")
    result = dict(metadata or {})
    result.update(
        {
            "knowledge_state": target,
            "knowledge_state_changed_at": now,
            "knowledge_state_actor": str(actor or "local")[:200],
            "knowledge_state_reason": reason,
        }
    )
    if refs:
        result["knowledge_evidence_refs"] = refs
    history = list(result.get("knowledge_state_history") or [])
    history.append(
        {
            "from": source,
            "to": target,
            "at": now,
            "actor": str(actor or "local")[:200],
            "reason": reason,
            "evidence_refs": refs,
        }
    )
    result["knowledge_state_history"] = history[-50:]
    return result, {
        "state": target,
        "previous_state": source,
        "changed": True,
        "at": now,
        "actor": str(actor or "local")[:200],
        "reason": reason,
        "evidence_refs": refs,
    }
