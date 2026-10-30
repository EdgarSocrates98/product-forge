"""Agent runtime — deterministic executor with full trace.

A run = ordered template steps, each a policy-checked tool call over
the real store. Output is composed ONLY from tool outputs + citations
(no synthesis without an LLM provider) — hallucination has no source.
Runs persist state for resume/cancel; step/budget caps bound agency.
"""

from __future__ import annotations

import time
from typing import Any

from ..domain.models import new_id, utcnow
from ..errors import ForgeError, NotFoundError, UnsafeOperationError
from ..store.sqlite import Store
from . import policy
from .tools import REGISTRY, TEMPLATES, ToolCtx

RUN_COLLECTION = "agent_runs"


def _run_doc(agent: Any, run_id: str, user_input: str) -> dict[str, Any]:
    return {"id": run_id, "schema": "productforge/AgentRun/v1",
            "product_id": agent.product_id, "agent_id": agent.id,
            "agent_version": agent.version, "input": user_input,
            "status": "running", "steps": [], "violations": [],
            "output": None, "created_at": utcnow(), "updated_at": utcnow()}


def run_agent(store: Store, agent: Any, user_input: str, *, actor: str = "api",
              cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    run_id = new_id("run")
    run = _run_doc(agent, run_id, user_input)

    inp = policy.check_input(agent, user_input)
    if inp.injection_detected:
        run["violations"].extend(inp.violations)
    if not inp.allowed:
        run["status"] = "blocked"
        run["output"] = {"refusal": "input blocked by policy", "violations": inp.violations}
        _persist(store, run)
        return run

    effective = inp.sanitized_input or user_input
    # Cycle 15: real LLM loop when a gateway provider is configured;
    # deterministic template path remains the honest fallback.
    if cfg is not None:
        from .llm_runtime import try_llm_run
        llm_run = try_llm_run(store, agent, effective, run, cfg)
        if llm_run is not None:
            llm_run["updated_at"] = utcnow()
            _persist(store, llm_run)
            return llm_run

    template = TEMPLATES.get(agent.template, TEMPLATES["custom"])
    steps = [s for s in agent.policies.get("steps", [])] or template["steps"]
    ctx = ToolCtx(product_id=agent.product_id, actor=actor, run_id=run_id)
    calls = 0
    citations: list[dict[str, Any]] = []
    findings: list[str] = []

    for i, step in enumerate(steps):
        budget = policy.check_budget(i, calls, agent)
        if not budget.allowed:
            run["violations"].extend(budget.violations)
            break
        tool_check = policy.check_tool(agent, step)
        if not tool_check.allowed:
            run["violations"].extend(tool_check.violations)
            run["steps"].append({"step": step, "status": "denied",
                                 "violations": tool_check.violations})
            continue
        tool = REGISTRY[step]
        args = {"question": effective} if step == "knowledge_query" else {}
        t0 = time.perf_counter()
        try:
            out = tool.fn(store, ctx, args)
            status = "ok"
        except ForgeError as e:
            out = {"error": e.body()}
            status = "error"
        calls += 1
        run["steps"].append({"step": step, "status": status, "duration_ms": round(
            (time.perf_counter() - t0) * 1000, 1)})
        if status == "ok":
            if step == "knowledge_query":
                citations.extend(out.get("citations", []))
                findings.append(f"{out['hit_count']} knowledge hit(s)")
            elif step == "knowledge_health":
                findings.append(f"knowledge health score {out.get('score')}")
            elif step == "data_sources":
                findings.append(f"{len(out.get('items', []))} data source(s) registered")
            else:
                n = len(out.get("items", out.get("nodes", [])))
                findings.append(f"{step}: {n} item(s)")

    run["status"] = "completed" if not run["violations"] or run["steps"] else "partial"
    run["output"] = {
        "summary": "; ".join(findings) if findings else "no findings — empty knowledge base",
        "citations": citations[:20],
        "grounded": bool(citations),
        "note": "deterministic template run; no LLM synthesis",
    }
    _persist(store, run)
    return run


def resume_run(store: Store, run_id: str) -> dict[str, Any]:
    run = store.get(RUN_COLLECTION, run_id)
    if run["status"] not in {"interrupted", "partial"}:
        raise UnsafeOperationError(f"run {run_id} is {run['status']}, not resumable")
    run["status"] = "resumed"
    run["updated_at"] = utcnow()
    store.audit({"id": new_id("aud"), "created_at": utcnow(), "action": "agent.run.resume",
                 "resource_type": "agent_runs", "resource_id": run_id,
                 "product_id": run["product_id"]})
    return run


def cancel_run(store: Store, run_id: str) -> dict[str, Any]:
    run = store.get(RUN_COLLECTION, run_id)
    if run["status"] in {"completed", "cancelled"}:
        raise UnsafeOperationError(f"run {run_id} already {run['status']}")
    run["status"] = "cancelled"
    run["updated_at"] = utcnow()
    _persist(store, run)
    return run


def get_run(store: Store, product_id: str, run_id: str) -> dict[str, Any]:
    run = store.get(RUN_COLLECTION, run_id)
    if run.get("product_id") != product_id:
        raise NotFoundError(f"run {run_id} not in product {product_id}")
    return run


def _persist(store: Store, run: dict[str, Any]) -> None:
    store.put_doc("agent_runs", run, status=run["status"], name=f"run:{run['agent_id']}")
