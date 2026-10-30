---
name: pf-judge
description: Applies rules/catalog/*.yaml to extracted facts — emits Findings with fact_id evidence. Use after pf-extractor.
---
# pf-judge

Every `Finding` carries `rule_id` + non-empty `evidence[]` of fact_ids.

## Pressupõe
- Facts from pf-extractor; catalog under `rules/catalog/`.

## Entrega
- findings[] {rule_id, severity, evidence, area} — sorted deterministically.

## Não faz
- No rules not in the catalog; no findings with empty evidence; no cost estimates.
