"""LLM agent runtime — real agentic loop over the gateway provider (Cycle 15).

Provider contract (subprocess+JSON, Forge Protocol):
  stdin : productforge/AgentRequest/v1
    {mode:"agent", system, input, tools[], history[], profile, model_hint}
  stdout: productforge/AgentResponse/v1
    {tool_calls?: [{tool, arguments}], text?: str,
     tokens_in?: int, tokens_out?: int}

Loop: history grows with tool results until the provider emits `text`
(final grounded answer) or max_turns hits. Every tool call passes the same
policy gate as the deterministic path; every provider turn records tokens in
the product budget ledger. No provider → caller keeps deterministic mode;
the run is never fabricated.
"""

from __future__ import annotations

import json
import subprocess
import time
from typing import Any

from ..errors import ForgeError
from ..store.sqlite import Store
from . import policy
from .tools import REGISTRY, ToolCtx

MAX_TURNS = 8


def _provider_cmd(cfg: dict[str, Any]) -> list[str] | None:
    cmd = (cfg.get("gateway") or {}).get("provider_cmd")
    return list(cmd) if cmd else None


def _call(cmd: list[str], req: dict[str, Any], timeout_s: int) -> dict[str, Any]:
    proc = subprocess.run(  # noqa: S603 — operator-configured provider
        cmd, input=json.dumps(req), capture_output=True, text=True,
        timeout=timeout_s, env={"PATH": "/usr/bin:/bin:/usr/local/bin"}, check=False)
    if proc.returncode != 0:
        raise ForgeError("PF-PROVIDER", (proc.stderr or "provider failed")[:200],
                         retryable=True)
    return json.loads(proc.stdout.strip().splitlines()[-1])


def try_llm_run(store: Store, agent: Any, user_input: str, run: dict[str, Any],
                cfg: dict[str, Any]) -> dict[str, Any] | None:
    """Attempt an LLM-loop run. Returns the populated run doc, or None when no
    provider is configured (caller falls back to deterministic path)."""
    cmd = _provider_cmd(cfg)
    if not cmd:
        return None
    from ..agents.routing import GATEWAY_PROFILES, record_usage

    profile = str(cfg.get("gateway_profile", "balanced"))
    prof = GATEWAY_PROFILES.get(profile, GATEWAY_PROFILES["balanced"])
    timeout_s = int((cfg.get("gateway") or {}).get("timeout_s", 30))
    allowed_tools = [t for t in agent.tools_allowed if t in REGISTRY]
    tools = [{"name": t, "description": REGISTRY[t].description} for t in allowed_tools]
    ctx = ToolCtx(product_id=agent.product_id, actor="agent-llm", run_id=run["id"])
    system = (f"You are {agent.name}, a specialist product agent. "
              f"Mission: {agent.mission}. Ground every claim in tool evidence; "
              f"cite sources. Never invent data.")
    history: list[dict[str, Any]] = [{"role": "user", "content": user_input}]
    citations: list[dict[str, Any]] = []
    tokens_in = tokens_out = 0

    for turn in range(MAX_TURNS):
        req = {"schema": "productforge/AgentRequest/v1", "mode": "agent",
               "system": system, "input": user_input, "tools": tools,
               "history": history, "profile": profile,
               "model_hint": prof["task_models"].get("synthesis", "standard")}
        t0 = time.perf_counter()
        try:
            resp = _call(cmd, req, timeout_s)
        except ForgeError as e:
            run["violations"].append({"step": f"llm-turn-{turn}", "error": e.body()})
            run["status"] = "error"
            return run
        except (json.JSONDecodeError, IndexError):
            run["status"] = "error"
            run["output"] = {"refusal": "provider returned non-JSON"}
            return run
        dur = round((time.perf_counter() - t0) * 1000, 1)
        tokens_in += int(resp.get("tokens_in", 0))
        tokens_out += int(resp.get("tokens_out", 0))
        record_usage(store, agent.product_id,
                     {"tokens_in": int(resp.get("tokens_in", 0)),
                      "tokens_out": int(resp.get("tokens_out", 0)),
                      "tool_calls": 0})
        run["steps"].append({"step": f"llm-turn-{turn}", "status": "ok",
                             "duration_ms": dur,
                             "tokens_in": resp.get("tokens_in", 0),
                             "tokens_out": resp.get("tokens_out", 0)})

        for tc in resp.get("tool_calls") or []:
            name = str(tc.get("tool", ""))
            check = policy.check_tool(agent, name)
            if not check.allowed or name not in REGISTRY:
                run["violations"].extend(check.violations)
                history.append({"role": "tool", "tool": name,
                                "content": json.dumps({"error": "denied-by-policy"})})
                run["steps"].append({"step": name, "status": "denied",
                                     "violations": check.violations})
                continue
            args = tc.get("arguments") or {}
            if not isinstance(args, dict):
                args = {}
            t0 = time.perf_counter()
            try:
                out = REGISTRY[name].fn(store, ctx, args)
                tool_status = "ok"
            except ForgeError as e:
                out = {"error": e.body()}
                tool_status = "error"
            run["steps"].append({"step": name, "status": tool_status,
                                 "duration_ms": round((time.perf_counter() - t0) * 1000, 1)})
            if tool_status == "ok" and name == "knowledge_query":
                citations.extend(out.get("citations", []))
            history.append({"role": "tool", "tool": name,
                            "content": json.dumps(out)[:8000]})

        text = resp.get("text")
        if text:
            run["status"] = "completed"
            run["output"] = {"answer": text, "citations": citations[:20],
                             "grounded": bool(citations),
                             "tokens_in": tokens_in, "tokens_out": tokens_out,
                             "llm": True, "profile": profile}
            return run
        if not resp.get("tool_calls"):
            # provider produced neither text nor tool calls → honest stop
            run["status"] = "partial"
            run["output"] = {"refusal": "provider produced no output",
                             "citations": citations[:20]}
            return run

    run["status"] = "partial"
    run["output"] = {"refusal": f"max turns ({MAX_TURNS}) reached",
                     "citations": citations[:20]}
    return run
