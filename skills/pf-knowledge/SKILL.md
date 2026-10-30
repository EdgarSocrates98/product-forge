---
name: pf-knowledge
description: Knowledge management — import docs, FTS search with citations, entity graph, health. Use for 'import document', 'search knowledge', 'knowledge graph', 'context'.
metadata:
  version: "1.0.0"
  forge: product-forge
  manifest: forge/Skill/v1
---
# Knowledge

## Objetivo
Grow trustworthy product knowledge: chunked docs + citations + entity graph + health score.

## Pré-condições
- Product exists

## Instruções
1. Import: `productforge knowledge import <pid> <file>` or `POST /documents/import` {title,text}.
2. Query: `productforge knowledge query <pid> '<q>'` → cited chunks (FTS5, punctuation-safe).
3. Extract: `POST /knowledge/extract` → entities + edges into the product graph.
4. Health: `GET /knowledge-health` → coverage/citation metrics.

## Ferramentas
- `productforge knowledge import|query|extract`
- `GET /graph`
- `GET /knowledge-health`

## Exemplos
- Import runbook.md → query 'rollback procedure' → top chunk + document citation.

## Limitações
- No LLM summarization w/o gateway — returns chunks, not prose answers.
- Heuristic entity extraction — verify high-impact edges manually.

## Evals
- Imported doc retrievable by FTS with citation; health endpoint counts it.

## Referências
- API envelope: `forge/PortalApi/1` — `{correlation_id, data, error}`
- Docs: `docs/audit/IMPLEMENTATION_GAP_MATRIX.md`, `docs/adr/ADR-001-architecture-and-persistence.md`
- Source: `src/product_forge/`
