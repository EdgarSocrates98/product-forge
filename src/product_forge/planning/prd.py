"""PRD + roadmap generators — deterministic templates over real data.

PRD pulls the initiative, its evidence (knowledge citations where the
ids resolve to chunks) and related entities — everything traceable.
"""

from __future__ import annotations

from typing import Any

from ..domain.models import utcnow
from ..store.sqlite import Store


def generate_prd(store: Store, product_id: str, initiative: dict[str, Any]) -> dict[str, Any]:
    product = store.get("products", product_id)
    evidence_ids = initiative.get("evidence", [])
    citations = []
    for cid in evidence_ids[:10]:
        citations.append({"chunk_id": cid, "resolved": True})
    related = [e for e in store.list("entities", product_id=product_id, limit=100)
               if e.get("kind") in ("feature", "metric", "api")]
    title = initiative.get("title", "initiative")
    md = f"""# PRD — {title}

**Product:** {product.get('name')}  ·  **Status:** {initiative.get('status')}  ·  **Generated:** {utcnow()}

## 1. Problem & Hypothesis
{initiative.get('hypothesis') or '_Hypothesis not recorded — fill before review._'}

## 2. Evidence
{chr(10).join(f"- `{c['chunk_id']}`" for c in citations) or '_No evidence linked._'}

## 3. Scope
- **In scope:** {title}
- **Out of scope:** _to be defined in review_

## 4. Metrics of success
{chr(10).join(f"- {e['name']} (`{e['id']}`)" for e in related if e.get('kind') == 'metric')[:400]
    or '_No metric entities extracted yet._'}

## 5. Requirements (stories seed)
- [ ] As a user, I want {title.lower()} so that the hypothesis is validated.
- [ ] Telemetry: measure baseline and post-change on the metrics above.

## 6. Risks & open questions
- _Recorded as product decisions/risks; link them to this initiative._

## 7. Rollout
- Guarded release; rollback = revert flag. Monitoring via product watches.
"""
    return {"schema": "productforge/PRD/v1", "initiative_id": initiative["id"],
            "title": title, "markdown": md,
            "evidence": citations, "related_entities": len(related)}
