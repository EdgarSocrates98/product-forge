# Knowledge storage scale baseline — 2026-11-08

Command:

```text
uv run python scripts/knowledge_store_bench.py --sizes 100,1000,10000
```

Result: `PASS`, including SQLite integrity check and FTS search at every size.

| documents | chunks | write median (ms) | search median (ms) | database bytes |
|---:|---:|---:|---:|---:|
| 100 | 100 | 162.951 | 0.401 | 143,360 |
| 1,000 | 1,000 | 1,395.714 | 0.410 | 843,776 |
| 10,000 | 10,000 | 14,347.139 | 0.923 | 7,925,760 |

All runs used one local SQLite database and one iteration per size. This is a
reproducible storage/extraction baseline, not a distributed production SLO;
network, concurrent writers and multi-process deployment remain outside this
measurement.
