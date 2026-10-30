"""Data contracts + impact analysis over the entity/relation graph."""

from __future__ import annotations

from collections import deque
from typing import Any

from ..store.sqlite import Store

TYPE_MAP = {"string": str, "integer": int, "number": (int, float),
            "boolean": bool, "object": dict, "array": list, "null": type(None)}


def validate_payload(contract: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    """contract: {fields:[{name,type,required}], quality:[{field,rule}]}"""
    violations = []
    fields = {f["name"]: f for f in contract.get("fields", [])}
    for name, f in fields.items():
        present = name in payload
        if f.get("required") and not present:
            violations.append({"rule": "required", "field": name})
            continue
        if present:
            t = TYPE_MAP.get(f.get("type", "string"), str)
            if not isinstance(payload[name], t) and payload[name] is not None:
                violations.append({"rule": "type", "field": name,
                                   "expected": f["type"],
                                   "got": type(payload[name]).__name__})
    for q in contract.get("quality", []):
        field, rule = q.get("field"), q.get("rule")
        val = payload.get(field)
        if rule == "not-null" and val is None:
            violations.append({"rule": "not-null", "field": field})
        elif rule == "non-empty" and not val:
            violations.append({"rule": "non-empty", "field": field})
        elif isinstance(rule, str) and rule.startswith("in:"):
            allowed = rule[3:].split("|")
            if str(val) not in allowed:
                violations.append({"rule": "enum", "field": field, "allowed": allowed})
    return {"schema": "productforge/ContractValidation/v1",
            "contract_id": contract.get("id"), "valid": not violations,
            "violations": violations}


def impact_analysis(store: Store, product_id: str, entity_id: str,
                    max_depth: int = 3) -> dict[str, Any]:
    """BFS over relations: what breaks if `entity_id` changes?"""
    relations = store.list("relations", product_id=product_id, limit=5000)
    adj: dict[str, list[dict[str, Any]]] = {}
    for r in relations:
        adj.setdefault(r["from_entity"], []).append(r)
    impacted, seen, q = [], {entity_id}, deque([(entity_id, 0)])
    while q:
        node, depth = q.popleft()
        if depth >= max_depth:
            continue
        for rel in adj.get(node, []):
            tgt = rel["to_entity"]
            if tgt not in seen:
                seen.add(tgt)
                try:
                    ent = store.get("entities", tgt)
                except Exception:  # noqa: S112 — to_entity may be a chunk/doc id
                    continue
                impacted.append({"entity_id": tgt, "name": ent.get("name"),
                                 "kind": ent.get("kind"), "depth": depth + 1,
                                 "via": rel["kind"]})
                q.append((tgt, depth + 1))
    return {"schema": "productforge/ImpactAnalysis/v1", "product_id": product_id,
            "origin": entity_id, "max_depth": max_depth,
            "impacted": impacted, "count": len(impacted)}
