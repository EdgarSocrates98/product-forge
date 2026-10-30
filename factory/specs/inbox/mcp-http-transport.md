---
id: mcp-http-transport
title: MCP streamable-HTTP transport alongside stdio
agent: codex
risk: low
grill: pending
verification: python -m pytest tests/ -k mcp && curl -N localhost:PORT/mcp
---

# MCP streamable-HTTP transport alongside stdio

## Context
MCP server is stdio-only. §15.2 hosts expect streamable-HTTP for remote/cloud hosts.

## Acceptance Criteria
- [ ] `productforge mcp serve --transport http --port N` serves the same tool surface
- [ ] tools/list + tools/call identical to stdio for the 14 tools
- [ ] Bearer auth reuses the local token
- [ ] Stdio remains default (no behavior change for hosts)

## Constraints
- Auth required on HTTP; no anonymous tool calls
- Same JSON-RPC message shape

## Grill Gate
<!-- complete before dispatch: decision owner? out of scope? riskiest assumption?
     smallest acceptable version? — do NOT invent answers autonomously -->

## Review Notes
Remote host support.
