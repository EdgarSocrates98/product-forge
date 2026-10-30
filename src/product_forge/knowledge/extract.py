"""Deterministic entity extraction — no LLM required.

Heuristics over chunk text produce provisional entities with evidence
(chunk ids) and confidence scores. An LLM enricher can refine later;
everything stays auditable and provisional until curated.
"""

from __future__ import annotations

import re

from ..domain.models import EntityKind, KnowledgeEntity, Relation, RelKind, new_id

_PATTERNS: list[tuple[EntityKind, re.Pattern[str]]] = [
    (EntityKind.API, re.compile(r"\b(?:GET|POST|PUT|PATCH|DELETE)\s+(/[\w/{}/._-]+)|(/api/v\d+/[\w/._-]+)")),
    (EntityKind.TABLE, re.compile(r"\b(?:table|tabela)\s+[`'\"]?([a-z_][\w.]+)[`'\"]?|FROM\s+([a-z_][\w.]+)", re.I)),  # noqa: E501
    (EntityKind.METRIC, re.compile(r"\b(?:metric|métrica|kpi|sla|sl[oai]|conversion rate|churn|mrr|arr|dau|mau|error rate|latency|p95|p99)\b[:\s]*([a-z_][\w ]{0,30})?", re.I)),  # noqa: E501
    (EntityKind.FEATURE, re.compile(r"^#{1,3}\s+([A-Z][\w .-]{2,60})\s*$", re.M)),
    (EntityKind.EVENT, re.compile(r"\bevent[o]?\b[:\s]+[`'\"]?([a-z_][\w.]+)[`'\"]?", re.I)),
]

_STAKEHOLDER = re.compile(r"\b(?:owner|responsável|stakeholder|team|time)\s*[:\-]\s*([A-Z][\w .-]{1,40})", re.M)  # noqa: E501
_TERM = re.compile(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})\b")

_CONF = {EntityKind.API: 0.9, EntityKind.TABLE: 0.85, EntityKind.METRIC: 0.8,
         EntityKind.FEATURE: 0.75, EntityKind.EVENT: 0.7, EntityKind.OTHER: 0.4}


def extract_entities(product_id: str, chunks: list[dict]) -> list[KnowledgeEntity]:
    """chunks: [{id, text}] → dedup'd provisional entities with evidence."""
    found: dict[tuple[str, str], KnowledgeEntity] = {}

    def add(kind: EntityKind, name: str, chunk_id: str, conf: float) -> None:
        name = name.strip().rstrip(".,:;")
        if not (2 <= len(name) <= 80):
            return
        key = (kind.value, name.lower())
        ent = found.get(key)
        if ent is None:
            ent = KnowledgeEntity(id=new_id("ent"), product_id=product_id, kind=kind,
                                  name=name, confidence=conf, evidence=[], provisional=True)
            found[key] = ent
        if chunk_id not in ent.evidence:
            ent.evidence.append(chunk_id)
        ent.confidence = min(0.99, ent.confidence + 0.03 * len(ent.evidence))

    for ch in chunks:
        cid, text = ch["id"], ch["text"]
        for kind, pat in _PATTERNS:
            for m in pat.finditer(text):
                name = next((g for g in m.groups() if g), m.group(0))[:80]
                add(kind, name, cid, _CONF.get(kind, 0.5))
        for m in _STAKEHOLDER.finditer(text):
            add(EntityKind.STAKEHOLDER, m.group(1), cid, 0.7)
        for m in _TERM.finditer(text):
            term = m.group(1)
            if sum(c.isupper() for c in term.split()[0][0]) and len(term.split()) >= 2:
                add(EntityKind.OTHER, term, cid, _CONF[EntityKind.OTHER])
    return list(found.values())


def build_relations(product_id: str, entities: list[KnowledgeEntity],
                    chunks: list[dict]) -> list[Relation]:
    """documented_in(entity→doc chunk) + co-occurrence related_to."""
    rels: list[Relation] = []
    by_chunk: dict[str, list[KnowledgeEntity]] = {}
    for ent in entities:
        for cid in ent.evidence:
            by_chunk.setdefault(cid, []).append(ent)
    seen: set[tuple[str, str, str]] = set()
    for cid, ents in by_chunk.items():
        for ent in ents:
            rels.append(Relation(id=new_id("rel"), product_id=product_id,
                                 from_entity=ent.id, to_entity=cid,
                                 kind=RelKind.DOCUMENTED_IN, confidence=ent.confidence,
                                 evidence=[cid]))
        for i, a in enumerate(ents):
            for b in ents[i + 1:]:
                key = tuple(sorted([a.id, b.id])) + (RelKind.RELATED_TO.value,)  # type: ignore[misc]
                if key in seen or a.id == b.id:
                    continue
                seen.add(key)  # type: ignore[arg-type]
                rels.append(Relation(id=new_id("rel"), product_id=product_id,
                                     from_entity=a.id, to_entity=b.id,
                                     kind=RelKind.RELATED_TO,
                                     confidence=min(a.confidence, b.confidence) * 0.6,
                                     evidence=[cid]))
    return rels
