"""Agent policy engine — checked before every run and every tool call.

Covers: tool allowlist, knowledge scope, input injection scan, step/
token budgets, forbidden capability escalation. Deny by default.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from ..domain.models import AgentDefinition

_INJECTION = re.compile(
    r"(ignore (all |previous )?instructions|system prompt|you are now|"
    r"disregard|reveal (your|the) (prompt|secret|token)|exfiltrat|"
    r"```\s*(bash|sh|python)\b|<script|DROP TABLE|DELETE FROM)",
    re.I,
)


@dataclass
class PolicyReport:
    allowed: bool
    violations: list[str] = field(default_factory=list)
    sanitized_input: str = ""
    injection_detected: bool = False


MAX_STEPS = 8
MAX_TOOL_CALLS = 12


def check_input(agent: AgentDefinition, user_input: str) -> PolicyReport:
    rep = PolicyReport(allowed=True, sanitized_input=user_input)
    if _INJECTION.search(user_input):
        rep.injection_detected = True
        # neutralize: strip matched directive spans, keep informational text
        rep.sanitized_input = _INJECTION.sub("[blocked]", user_input)
        rep.violations.append("prompt-injection-pattern")
        if agent.policies.get("strict_injection_block", True):
            rep.allowed = False
    return rep


def check_tool(agent: AgentDefinition, tool_name: str) -> PolicyReport:
    rep = PolicyReport(allowed=True)
    allowed = set(agent.tools_allowed or [])
    if tool_name not in allowed:
        rep.allowed = False
        rep.violations.append(f"tool-not-allowed:{tool_name}")
    from .tools import REGISTRY

    tool = REGISTRY.get(tool_name)
    if tool is None:
        rep.allowed = False
        rep.violations.append(f"unknown-tool:{tool_name}")
    elif tool.destructive and not agent.policies.get("allow_destructive", False):
        rep.allowed = False
        rep.violations.append(f"destructive-tool:{tool_name}")
    return rep


def check_budget(steps_done: int, calls_done: int,
                 agent: AgentDefinition) -> PolicyReport:
    rep = PolicyReport(allowed=True)
    max_steps = int(agent.policies.get("max_steps", MAX_STEPS))
    max_calls = int(agent.policies.get("max_tool_calls", MAX_TOOL_CALLS))
    if steps_done >= max_steps:
        rep.allowed = False
        rep.violations.append("budget:max-steps")
    if calls_done >= max_calls:
        rep.allowed = False
        rep.violations.append("budget:max-tool-calls")
    return rep
