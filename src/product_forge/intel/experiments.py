"""Experiment Studio + Meeting Intelligence (Cycle 17).

Honesty rules:
- Conclusions are deterministic comparisons of operator-recorded results
  against declared baselines/guardrails — never a causal claim.
- Meeting extraction produces *drafts*; nothing publishes without an
  explicit human `reviewed` flag.
"""

from __future__ import annotations

import re
from typing import Any

_ACTION_MARKERS = re.compile(
    r"^\s*[-*]?\s*(todo|action|ação|task|next step)[:\-]?\s+(.+)", re.IGNORECASE)
_DECISION_MARKERS = re.compile(
    r"^\s*[-*]?\s*(decision|decisão|decidimos|agreed|acordado)[:\-]?\s+(.+)", re.IGNORECASE)


def conclude_experiment(exp: dict[str, Any], results: dict[str, float],
                        verdict: str = "") -> dict[str, Any]:
    """Compare recorded results to baseline/guardrails — deterministic verdict."""
    guardrail_breaches = {
        g: {"limit": limit, "observed": results.get(g)}
        for g, limit in (exp.get("guardrails") or {}).items()
        if g in results and results[g] > limit
    }
    if guardrail_breaches:
        outcome = "stopped_by_guardrail"
    elif verdict:
        outcome = verdict
    else:
        improved = [m for m in exp.get("success_metrics") or []
                    if m in results and m in (exp.get("baseline") or {})
                    and results[m] > exp["baseline"][m]]
        outcome = ("supporting_hypothesis" if improved
                   else "inconclusive:not-enough-improvement")
    return {"outcome": outcome, "results": results,
            "guardrail_breaches": guardrail_breaches,
            "status": "stopped" if guardrail_breaches else "concluded",
            "note": "deterministic comparison; no causal inference implied"}


def extract_drafts(transcript: str) -> list[dict[str, Any]]:
    """Deterministic line-scan → draft decision/action items with line refs."""
    items: list[dict[str, Any]] = []
    for i, line in enumerate(transcript.splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        if m := _DECISION_MARKERS.match(line):
            items.append({"kind": "decision", "text": m.group(2).strip(), "line": i})
        elif m := _ACTION_MARKERS.match(line):
            items.append({"kind": "action", "text": m.group(2).strip(), "line": i})
    return items


def decision_completeness(decision: dict[str, Any]) -> dict[str, Any]:
    """Decision journal checklist — what's present, what's missing."""
    checks = {
        "title": bool(decision.get("title")),
        "context": bool(decision.get("context")),
        "decision": bool(decision.get("decision")),
        "alternatives": bool(decision.get("alternatives")),
        "evidence": bool(decision.get("evidence")),
        "assumptions": bool(decision.get("assumptions")),
        "risks": bool(decision.get("risks")),
    }
    missing = [k for k, ok in checks.items() if not ok]
    return {"schema": "productforge/DecisionCompleteness/v1",
            "completeness": round(sum(checks.values()) / len(checks), 2),
            "missing": missing,
            "note": "completeness ≠ correctness — fields present, quality human-judged"}
