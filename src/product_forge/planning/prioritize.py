"""Prioritization — RICE and WSJF scoring, deterministic and explainable."""

from __future__ import annotations

from typing import Any


def score_rice(reach: float, impact: float, confidence: float, effort: float) -> float:
    if effort <= 0:
        return 0.0
    return round(reach * impact * (confidence / 100.0) / effort, 2)


def score_wsjf(user_value: float, time_criticality: float, risk_reduction: float,
               job_size: float) -> float:
    if job_size <= 0:
        return 0.0
    return round((user_value + time_criticality + risk_reduction) / job_size, 2)


def score_initiative(initiative: dict[str, Any], factors: dict[str, Any]) -> dict[str, Any]:
    """factors may carry rice{reach,impact,confidence,effort} and/or
    wsjf{user_value,time_criticality,risk_reduction,job_size}."""
    out: dict[str, Any] = {"initiative_id": initiative["id"], "methods": {}}
    scores = []
    if rice := factors.get("rice"):
        s = score_rice(float(rice.get("reach", 0)), float(rice.get("impact", 0)),
                       float(rice.get("confidence", 50)), float(rice.get("effort", 1)))
        out["methods"]["rice"] = {"score": s, "inputs": rice}
        scores.append(s)
    if wsjf := factors.get("wsjf"):
        s = score_wsjf(float(wsjf.get("user_value", 0)), float(wsjf.get("time_criticality", 0)),
                       float(wsjf.get("risk_reduction", 0)), float(wsjf.get("job_size", 1)))
        out["methods"]["wsjf"] = {"score": s, "inputs": wsjf}
        scores.append(s)
    if not scores:
        out["methods"]["default"] = {"score": float(initiative.get("priority_score", 0))}
        scores.append(float(initiative.get("priority_score", 0)))
    out["score"] = round(sum(scores) / len(scores), 2)
    out["evidence_count"] = len(initiative.get("evidence", []))
    return out
