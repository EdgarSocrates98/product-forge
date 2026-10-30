"""MCP server (stdio) — exposes productforge tools to agent hosts.

Tools are read-only by default: context recovery, knowledge query,
product/agent listing. Mutations go through the CLI/API where policy,
audit and approvals live.
"""

from __future__ import annotations

import json
from typing import Any

from ..config import db_path, home_dir, load_config
from ..store.sqlite import Store


def _store() -> Store:
    home = home_dir()
    return Store(db_path(home, load_config(home)))


def tool_specs() -> list[dict[str, Any]]:
    return [
        {"name": "productforge_status", "description": "Product Forge version, home and capability flags",
         "inputSchema": {"type": "object", "properties": {}}},  # noqa: E501
        {"name": "product_list", "description": "List products (optionally by workspace_id)",
         "inputSchema": {"type": "object", "properties": {"workspace_id": {"type": "string"}}}},  # noqa: E501
        {"name": "product_context", "description": "Product Context Package for a product",
         "inputSchema": {"type": "object", "properties": {"product_id": {"type": "string"}}, "required": ["product_id"]}},  # noqa: E501
        {"name": "knowledge_query", "description": "FTS retrieval over product knowledge, with citations",
         "inputSchema": {"type": "object", "properties": {"product_id": {"type": "string"}, "question": {"type": "string"}},  # noqa: E501
                         "required": ["product_id", "question"]}},
        {"name": "agent_list", "description": "List agent definitions for a product",
         "inputSchema": {"type": "object", "properties": {"product_id": {"type": "string"}}, "required": ["product_id"]}},  # noqa: E501
        {"name": "product_graph", "description": "Entity/relation graph projection for a product",
         "inputSchema": {"type": "object", "properties": {"product_id": {"type": "string"}}, "required": ["product_id"]}},  # noqa: E501
        {"name": "knowledge_health", "description": "Knowledge coverage/citation health for a product",
         "inputSchema": {"type": "object", "properties": {"product_id": {"type": "string"}}, "required": ["product_id"]}},  # noqa: E501
        {"name": "query_validate", "description": "Validate a read-only SQL statement (sqlglot)",
         "inputSchema": {"type": "object", "properties": {"statement": {"type": "string"}}, "required": ["statement"]}},  # noqa: E501
        {"name": "dashboard_list", "description": "List dashboards for a product",
         "inputSchema": {"type": "object", "properties": {"product_id": {"type": "string"}}, "required": ["product_id"]}},  # noqa: E501
        {"name": "roadmap", "description": "Now/next/later roadmap lanes for a product",
         "inputSchema": {"type": "object", "properties": {"product_id": {"type": "string"}}, "required": ["product_id"]}},  # noqa: E501
        {"name": "alerts_list", "description": "List open/acked alerts for a product",
         "inputSchema": {"type": "object", "properties": {"product_id": {"type": "string"}}, "required": ["product_id"]}},  # noqa: E501
        {"name": "audit_list", "description": "Audit events (optionally filtered by product_id)",
         "inputSchema": {"type": "object", "properties": {"product_id": {"type": "string"}}}},  # noqa: E501
        {"name": "agent_run", "description": "Run a product agent (policy-checked, audited)",
         "inputSchema": {"type": "object", "properties": {"agent_id": {"type": "string"}, "input": {"type": "string"}},  # noqa: E501
                         "required": ["agent_id", "input"]}},
        {"name": "agent_eval", "description": "Run the default eval suite for an agent and persist the score",
         "inputSchema": {"type": "object", "properties": {"agent_id": {"type": "string"}}, "required": ["agent_id"]}},  # noqa: E501
    ]


def call_tool(name: str, args: dict[str, Any]) -> dict[str, Any]:
    from .. import FORGE_ID, __version__

    st = _store()
    try:
        if name == "productforge_status":
            return {"forge_id": FORGE_ID, "version": __version__}
        if name == "product_list":
            return {"items": st.list("products", workspace_id=args.get("workspace_id"))}
        if name == "product_context":
            pid = args["product_id"]
            return {"schema": "productforge/ProductContextPackage/v1",
                    "product": st.get("products", pid),
                    "entities": st.list("entities", product_id=pid, limit=200),
                    "agents": st.list("agents", product_id=pid, limit=100)}
        if name == "knowledge_query":
            hits = st.search_fts(args["product_id"], args["question"], limit=int(args.get("limit", 5)))
            return {"hits": hits, "citations": [
                {"chunk_id": h["id"], "document_id": h["document_id"], "snippet": h["snip"]} for h in hits]}
        if name == "agent_list":
            return {"items": st.list("agents", product_id=args["product_id"])}
        if name == "product_graph":
            from ..knowledge.graph import product_graph
            return product_graph(st, args["product_id"])
        if name == "knowledge_health":
            from ..knowledge.graph import knowledge_health
            return knowledge_health(st, args["product_id"])
        if name == "query_validate":
            from dataclasses import asdict

            from ..analytics.sqlvalidate import validate
            return asdict(validate(args["statement"]))
        if name == "dashboard_list":
            return {"items": st.list("dashboards", product_id=args["product_id"])}
        if name == "roadmap":
            from ..planning.roadmap import build_roadmap
            return build_roadmap(st, args["product_id"])
        if name == "alerts_list":
            return {"items": st.list("alerts", product_id=args["product_id"])}
        if name == "audit_list":
            pid = args.get("product_id")
            items = st.list("audit_events", limit=100)
            if pid:
                items = [a for a in items if a.get("product_id") == pid]
            return {"items": items}
        if name == "agent_run":
            from ..agents.runtime import run_agent
            from ..domain.models import AgentDefinition
            agent = AgentDefinition.model_validate(st.get("agents", args["agent_id"]))
            return run_agent(st, agent, args["input"], actor="mcp")
        if name == "agent_eval":
            from ..agents.evals import run_evals
            from ..domain.models import AgentDefinition
            agent = AgentDefinition.model_validate(st.get("agents", args["agent_id"]))
            return run_evals(st, agent)
        return {"error": f"unknown tool: {name}"}
    finally:
        st.close()


def serve() -> None:
    """Minimal JSON-RPC stdio loop (MCP handshake + tools/list + tools/call)."""
    import sys

    def _send(obj: dict[str, Any]) -> None:
        sys.stdout.write(json.dumps(obj) + "\n")
        sys.stdout.flush()

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except json.JSONDecodeError:
            continue
        rid = req.get("id")
        method = req.get("method", "")
        if method == "initialize":
            _send({"jsonrpc": "2.0", "id": rid, "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "product-forge", "version": "0.1.0"}}})
        elif method == "notifications/initialized":
            continue
        elif method == "tools/list":
            _send({"jsonrpc": "2.0", "id": rid, "result": {"tools": tool_specs()}})
        elif method == "tools/call":
            params = req.get("params", {})
            result = call_tool(params.get("name", ""), params.get("arguments", {}))
            _send({"jsonrpc": "2.0", "id": rid, "result": {
                "content": [{"type": "text", "text": json.dumps(result, default=str)}]}})
        elif method == "ping":
            _send({"jsonrpc": "2.0", "id": rid, "result": {}})
        elif rid is not None:
            _send({"jsonrpc": "2.0", "id": rid,
                   "error": {"code": -32601, "message": f"method not found: {method}"}})
