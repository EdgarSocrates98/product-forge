"""Gateway synthesis — provider-boundary contract (Forge Protocol: subprocess+JSON).

Profiles (economy|balanced|deep) live in agents/routing.GATEWAY_PROFILES and
select model hints + daily token budgets. A provider is an *external* command
declared in config (`gateway.provider_cmd`) — Product Forge never imports an
LLM SDK and never fabricates text: absent provider → `unavailable:*` states.

Wire format (stdin → stdout, one JSON doc each way):

  request : productforge/SynthesisRequest/v1
    {question, citations[], profile, model_hint, max_tokens}
  response: productforge/SynthesisResult/v1
    {text, tokens_in, tokens_out}  (provider must be honest about usage)

Provider stdout is truncated at the profile's max_tokens. Credentials never
enter env or logs: the provider command carries no secret material and the
result passes through security.redact before any persistence.
"""

from __future__ import annotations

import json
import subprocess
from typing import Any

from ..agents.routing import GATEWAY_PROFILES, record_usage

REQ_SCHEMA = "productforge/SynthesisRequest/v1"
RES_SCHEMA = "productforge/SynthesisResult/v1"


def _provider_cmd(cfg: dict[str, Any]) -> list[str] | None:
    cmd = (cfg.get("gateway") or {}).get("provider_cmd")
    return list(cmd) if cmd else None


def synthesize(store: Any, product_id: str, question: str,
               citations: list[dict[str, Any]], cfg: dict[str, Any]) -> dict[str, Any]:
    """Attempt a grounded synthesis through the configured gateway provider.

    Returns a result doc — never raises for missing capability:
      status "ok"          → {text, provider, tokens_in, tokens_out}
      status "unavailable" → {reason}  (no provider configured / spawn banned)
      status "error"       → {error}   (provider ran but failed/misbehaved)
    """
    profile = str(cfg.get("gateway_profile", "balanced"))
    prof = GATEWAY_PROFILES.get(profile, GATEWAY_PROFILES["balanced"])
    cmd = _provider_cmd(cfg)
    if not cmd:
        return {"status": "unavailable", "reason": "no-provider-adapter",
                "detail": "set gateway.provider_cmd to enable synthesis",
                "profile": profile}
    request = {"schema": REQ_SCHEMA, "question": question,
               "citations": citations[:20], "profile": profile,
               "model_hint": prof["task_models"].get("synthesis", "standard"),
               "max_tokens": min(prof["max_tokens_day"], 4096)}
    try:
        proc = subprocess.run(  # noqa: S603 — provider cmd is operator config, not user input
            cmd, input=json.dumps(request), capture_output=True, text=True,
            timeout=int((cfg.get("gateway") or {}).get("timeout_s", 30)),
            env={"PATH": "/usr/bin:/bin:/usr/local/bin"}, check=False)
    except (OSError, subprocess.TimeoutExpired) as e:
        return {"status": "unavailable", "reason": "provider-unreachable",
                "error": str(e)[:200], "profile": profile}
    if proc.returncode != 0:
        return {"status": "error", "error": (proc.stderr or "provider failed")[:200],
                "profile": profile}
    try:
        result = json.loads(proc.stdout.strip().splitlines()[-1])
    except (json.JSONDecodeError, IndexError):
        return {"status": "error", "error": "provider returned non-JSON output",
                "profile": profile}
    text = str(result.get("text", ""))
    if not text:
        return {"status": "error", "error": "provider returned empty text",
                "profile": profile}
    tokens_in = int(result.get("tokens_in", 0))
    tokens_out = int(result.get("tokens_out", 0))
    record_usage(store, product_id,
                 {"tokens_in": tokens_in, "tokens_out": tokens_out, "tool_calls": 0})
    return {"status": "ok", "text": text,
            "provider": {"cmd": cmd[0], "model_hint": request["model_hint"]},
            "tokens_in": tokens_in, "tokens_out": tokens_out,
            "profile": profile, "schema": RES_SCHEMA}
