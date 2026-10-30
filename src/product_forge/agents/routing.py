"""Model routing + cost ledger — gateway profiles and honest budgets.

No provider calls happen without an installed LLM extra; routing picks
the candidate provider/model per task class and records budget usage.
"""

from __future__ import annotations

from typing import Any

GATEWAY_PROFILES: dict[str, dict[str, Any]] = {
    "economy": {"max_tokens_day": 50_000, "prefer_local": True,
                "task_models": {"retrieval": "local-fts", "synthesis": "small",
                                "extraction": "local-heuristic"}},
    "balanced": {"max_tokens_day": 200_000, "prefer_local": False,
                 "task_models": {"retrieval": "local-fts", "synthesis": "standard",
                                 "extraction": "standard"}},
    "deep": {"max_tokens_day": 1_000_000, "prefer_local": False,
             "task_models": {"retrieval": "hybrid", "synthesis": "large",
                             "extraction": "large"}},
}


def route(task_class: str, profile: str = "balanced",
          providers: list[str] | None = None) -> dict[str, Any]:
    cfg = GATEWAY_PROFILES.get(profile, GATEWAY_PROFILES["balanced"])
    available = providers or ["local"]
    use_llm = "local" not in available and not cfg["prefer_local"]
    return {"task_class": task_class, "profile": profile,
            "model": cfg["task_models"].get(task_class, "standard"),
            "llm_used": use_llm,
            "fallback": not use_llm,
            "reason": ("deterministic local path — no LLM provider configured"
                       if not use_llm else f"routed via {available[0]}")}


def record_usage(store: Any, product_id: str, usage: dict[str, Any]) -> dict[str, Any]:
    """Append to the product's daily budget ledger (audit-safe)."""
    from ..domain.models import utcnow

    day = utcnow()[:10]
    key = f"budget:{product_id}:{day}"
    try:
        doc = store.get("budget_ledger", key)
    except Exception:
        doc = {"id": key, "schema": "productforge/BudgetLedger/v1",
               "product_id": product_id, "day": day,
               "tokens_in": 0, "tokens_out": 0, "tool_calls": 0, "runs": 0}
    doc["tokens_in"] += int(usage.get("tokens_in", 0))
    doc["tokens_out"] += int(usage.get("tokens_out", 0))
    doc["tool_calls"] += int(usage.get("tool_calls", 0))
    doc["runs"] += 1
    store.put_doc("budget_ledger", doc, name=key)
    return doc
