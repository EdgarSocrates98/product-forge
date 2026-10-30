"""Multi-agent workflows — deterministic DAG over agents and tools.

Steps run in declared order (parallel only when marked `parallel_group`
— executed sequentially here with identical semantics, since all tools
are read-only and deterministic). Agent steps delegate through the real
runtime; tool steps go through the same policy-checked registry.
`{{var}}` interpolates prior step outputs; violations halt the run.
"""

from __future__ import annotations

import re
from typing import Any

from ..domain.models import AgentDefinition, new_id, utcnow
from ..errors import UnsafeOperationError
from ..store.sqlite import Store
from .runtime import run_agent
from .tools import REGISTRY, ToolCtx

_VAR = re.compile(r"\{\{([\w.]+)\}\}")


def _interpolate(text: str, ctx: dict[str, Any]) -> str:
    def rep(m: re.Match[str]) -> str:
        node: Any = ctx
        for part in m.group(1).split("."):
            node = node.get(part) if isinstance(node, dict) else None
            if node is None:
                return ""
        return str(node)

    return _VAR.sub(rep, text)


def run_workflow(store: Store, product_id: str, spec: dict[str, Any],
                 *, actor: str = "api") -> dict[str, Any]:
    """spec: {name, steps:[{id, kind:agent|tool, agent_id|tool, input?}]}"""
    wf_id = new_id("wfr")
    record = {"id": wf_id, "schema": "productforge/WorkflowRun/v1",
              "product_id": product_id, "name": spec.get("name", "workflow"),
              "status": "running", "steps": [], "context": {},
              "created_at": utcnow(), "updated_at": utcnow()}
    context: dict[str, Any] = {}
    halted = False

    for i, step in enumerate(spec.get("steps", [])[:20]):
        sid = step.get("id", f"step{i}")
        kind = step.get("kind", "tool")
        inp = _interpolate(str(step.get("input", "")), context)
        entry: dict[str, Any] = {"id": sid, "kind": kind}
        try:
            if kind == "agent":
                doc = store.get("agents", step["agent_id"])
                if doc.get("product_id") != product_id:
                    raise UnsafeOperationError("cross-product agent delegation denied")
                agent = AgentDefinition.model_validate(doc)
                run = run_agent(store, agent, inp, actor=f"workflow:{wf_id}")
                entry.update({"run_id": run["id"], "status": run["status"],
                              "violations": run["violations"]})
                context[sid] = run["output"]
            elif kind == "tool":
                tool_name = step["tool"]
                tool = REGISTRY.get(tool_name)
                if tool is None:
                    raise UnsafeOperationError(f"unknown tool {tool_name}")
                tctx = ToolCtx(product_id=product_id, actor=actor, run_id=wf_id)
                args = dict(step.get("args", {}))
                if "question" not in args and tool_name == "knowledge_query":
                    args["question"] = inp
                out = tool.fn(store, tctx, args)
                entry["status"] = "ok"
                context[sid] = out
            else:
                raise UnsafeOperationError(f"step kind must be agent|tool, got {kind}")
        except UnsafeOperationError as e:
            entry.update({"status": "denied", "error": str(e)})
            halted = True
        except Exception as e:
            entry.update({"status": "failed", "error": f"{type(e).__name__}: {e}"[:200]})
            halted = True
        record["steps"].append(entry)
        if halted:
            break

    record["status"] = "halted" if halted else "completed"
    record["context_keys"] = sorted(context)
    record["updated_at"] = utcnow()
    store.put_doc("workflow_runs", record, status=record["status"], name=record["name"])
    return record


MAX_PARALLEL_GROUP = 4


def plan_is_deterministic(spec: dict[str, Any]) -> bool:
    """Workflows are deterministic by construction: declared steps only."""
    return all(s.get("kind") in {"agent", "tool"} for s in spec.get("steps", []))
