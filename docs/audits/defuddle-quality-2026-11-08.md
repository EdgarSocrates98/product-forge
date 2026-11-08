# Defuddle quality gate — 2026-11-08

The optional extractor is verified with a deterministic HTML fixture sent over
stdin. The gate checks the real CLI output for title extraction, main-content
retention, list retention, navigation/footer removal and a numeric parse-time
metric. It accepts both the newer `contentMarkdown` field and the legacy
`content` field used by the currently resolved CLI.

## Run

```text
python scripts/defuddle_quality_bench.py
```

## Evidence

```json
{
  "schema": "productforge/DefuddleQuality/v1",
  "state": "passed",
  "score": "8/8",
  "extractor_output": "content",
  "parse_time_ms": 26
}
```

The benchmark is local-only and does not prove network fetching, Obsidian
semantics or production latency. Product Forge still keeps the URL security
boundary in its stdlib fetcher and passes validated HTML to Defuddle over
stdin.
