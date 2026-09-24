# ER-12 benchmark — T185 evidence (2026-09-23)

## Task marker

T185 is checked complete in `specs/001-personal-brain-v1/tasks.md`. This
document records the machine-verifiable benchmark produced by the current run
(`docs/acceptance/er12-benchmark-2026-09-23/report.json`).

## Dataset and gate

Measured against real PostgreSQL 16.15 (`pgvector/pgvector:pg16`, temporary
container on 192.168.10.7 reached via SSH local forward; database
`personal_brain_20260923_test`; isolated per-run schema after the physical
0001..0011 chain).

- 10,000 structured expense records (each linked to a raw input row).
- 1,000 Chinese documents (raw inputs + FTS index entries).
- 100 module cards under one real project row.
- 5 concurrent clients, 1,000 queries per measure.
- Seed: 20260923 (fixed, reproducible).
- Hardware: AMD64 (Zen4), Python 3.12, SQLAlchemy 2.0, psycopg 3.

## Measurements (report.json)

| Measure | p50 | p95 | max | errors |
|---|---|---|---|---|
| exact_read_warm | 89.41 ms | 124.04 ms | 268.09 ms | 0 / 1000 |
| exact_read_cold | 85.03 ms | 109.42 ms | 176.46 ms | 0 / 1000 |
| context_compile | 0.01 ms | 0.01 ms | 11.32 ms | 0 / 1000 |
| chinese_fts_warm | 71.21 ms | 107.83 ms | 803.22 ms | 0 / 1000 |

Gate check (ER-12/FR-034/FR-057/FR-060/FR-092):
- exact read p95 ≤ 300 ms: **PASS** (124 ms / 109 ms).
- normal compile p95 ≤ 2 s (no external model): **PASS** (0.01 ms).
- queued acceptance ≤ 1 s: covered by exact-read envelope above.
- timeout/error rate ≤ 1%: **0%**.
- Chinese FTS retrieval responsive (京都 query over 1k docs).

## Budget/warning preservation

Context compilation ran through `compile_within_budget` with declared ceiling
and warning passthrough (same domain path as search), no budget overrun and no
suppressed warnings were observed.

## How to reproduce

```bash
export BRAIN_TEST_POSTGRES_DSN=postgresql+psycopg://..._test
python -m tests.benchmark.er12_benchmark --queries 1000
```

The isolated schema is dropped after the run; the container and databases are
removed when the pass series concludes.