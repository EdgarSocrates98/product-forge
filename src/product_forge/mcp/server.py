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
