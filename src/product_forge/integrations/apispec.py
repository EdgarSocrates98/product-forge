"""OpenAPI/AsyncAPI parsing + breaking-change detection — real diffs."""

from __future__ import annotations

from typing import Any

import yaml

from ..errors import ValidationError


def load_spec(raw: str | dict[str, Any]) -> dict[str, Any]:
    doc = yaml.safe_load(raw) if isinstance(raw, str) else raw
    if not isinstance(doc, dict):
        raise ValidationError("spec is not a JSON/YAML document")
    return doc


def parse_openapi(spec: dict[str, Any]) -> dict[str, Any]:
    """Extract the API surface: operations, params, schemas."""
    if "openapi" not in spec and "swagger" not in spec:
        raise ValidationError("not an OpenAPI document (missing openapi/swagger)")
    ops = []
    for path, item in (spec.get("paths") or {}).items():
        if not isinstance(item, dict):
            continue
        for method, op in item.items():
            if method not in {"get", "post", "put", "patch", "delete", "head", "options"}:
                continue
            params = [{"name": p.get("name"), "in": p.get("in"),
                       "required": bool(p.get("required")),
                       "type": ((p.get("schema") or {}).get("type"))}
                      for p in (op.get("parameters") or []) + (item.get("parameters") or [])
                      if isinstance(p, dict)]
            ops.append({"path": path, "method": method.upper(),
                        "operation_id": op.get("operationId"),
                        "summary": op.get("summary", ""),
                        "params": params,
                        "request_body_required": bool(
                            (op.get("requestBody") or {}).get("required")),
                        "responses": sorted((op.get("responses") or {}).keys())})
    schemas = {k: {"type": (v or {}).get("type"),
                   "properties": sorted((v.get("properties") or {}).keys()),
                   "required": sorted(v.get("required") or [])}
               for k, v in (spec.get("components", {}).get("schemas") or {}).items()}
    return {"kind": "openapi", "version": spec.get("openapi") or spec.get("swagger"),
            "title": (spec.get("info") or {}).get("title", ""),
            "operations": ops, "schemas": schemas}


def parse_asyncapi(spec: dict[str, Any]) -> dict[str, Any]:
    if "asyncapi" not in spec:
        raise ValidationError("not an AsyncAPI document")
    channels = []
    for name, ch in (spec.get("channels") or {}).items():
        ops = [op for op in ("publish", "subscribe") if isinstance(ch.get(op), dict)]
        channels.append({"channel": name, "operations": ops,
                         "messages": sorted({m for op in ops
                                             for m in ((ch[op].get("message") or {})
                                                       .get("name", []),)
                                             if isinstance(m, str)})})
    return {"kind": "asyncapi", "version": spec.get("asyncapi"),
            "title": (spec.get("info") or {}).get("title", ""), "channels": channels}


def diff_openapi(old: dict[str, Any], new: dict[str, Any]) -> dict[str, Any]:
    """Breaking-change detection between two parsed OpenAPI surfaces."""
    a, b = parse_openapi(load_spec(old)), parse_openapi(load_spec(new))
    aops = {(o["method"], o["path"]): o for o in a["operations"]}
    bops = {(o["method"], o["path"]): o for o in b["operations"]}
    breaking: list[dict[str, Any]] = []
    additions: list[str] = []
    for key, op in aops.items():
        if key not in bops:
            breaking.append({"type": "operation-removed",
                             "operation": f"{key[0]} {key[1]}"})
            continue
        nop = bops[key]
        aparams = {p["name"]: p for p in op["params"] if p["name"]}
        nparams = {p["name"]: p for p in nop["params"] if p["name"]}
        for name, p in aparams.items():
            if name not in nparams:
                breaking.append({"type": "param-removed",
                                 "operation": f"{key[0]} {key[1]}", "param": name})
            elif p["type"] and nparams[name]["type"] and p["type"] != nparams[name]["type"]:
                breaking.append({"type": "param-type-changed",
                                 "operation": f"{key[0]} {key[1]}", "param": name,
                                 "from": p["type"], "to": nparams[name]["type"]})
        for name, p in nparams.items():
            if name not in aparams and p["required"]:
                breaking.append({"type": "required-param-added",
                                 "operation": f"{key[0]} {key[1]}", "param": name})
        removed_codes = set(op["responses"]) - set(nop["responses"])
        for code in removed_codes:
            if code.startswith("2"):
                breaking.append({"type": "success-response-removed",
                                 "operation": f"{key[0]} {key[1]}", "code": code})
    for key in bops:
        if key not in aops:
            additions.append(f"{key[0]} {key[1]}")
    for sname, s in a["schemas"].items():
        ns = b["schemas"].get(sname)
        if ns is None:
            breaking.append({"type": "schema-removed", "schema": sname})
            continue
        for prop in set(s["properties"]) - set(ns["properties"]):
            breaking.append({"type": "schema-property-removed",
                             "schema": sname, "property": prop})
        for req in set(ns["required"]) - set(s["required"]):
            breaking.append({"type": "schema-required-added",
                             "schema": sname, "property": req})
    return {"schema": "productforge/ApiBreakingChangeReport/v1",
            "from_version": a["version"], "to_version": b["version"],
            "breaking": breaking, "additions": additions,
            "is_breaking": bool(breaking)}
