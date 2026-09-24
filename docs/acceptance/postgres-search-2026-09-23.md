# PostgreSQL retrieval evidence — 2026-09-23

Status: **PASS** for T179.

## Implemented retrieval path

- Chinese and mixed-language text is normalized by the locked `jieba==0.42.1` search tokenizer; unknown terms and source paths are preserved as lexemes.
- `search_index_entries` now owns a generated PostgreSQL `tsvector`, GIN index, pgvector value, vector model version and model-dimension metadata.
- Candidate SQL binds owner, exact authorized scope, sensitivity ceiling and validity before either FTS or vector ranking. Denied rows never enter either candidate list.
- Keyword and same-version semantic candidates use deterministic RRF (`k=60`). Exact expense totals and todo lists bypass probabilistic retrieval and use canonical structured queries.
- Results retain target identity, canonicality, freshness, model version, source links and visible stale/conflict/uncertainty warnings.
- Durable indexing jobs load the current canonical row under the job owner, persist the index, report fenced progress and recheck client status and target version before commit.

## Physical evidence

- A temporary isolated `pgvector/pgvector:pg16` container on `192.168.10.7` ran the complete 0001..0011 migration suite: **20 passed**.
- The physical test inserted Chinese/mixed text plus a three-dimensional versioned vector, retrieved it through both PostgreSQL FTS and pgvector, verified provenance/warnings, and reversed the complete schema.
- A real queued `extract_raw_input` job was claimed by `DurableJobPoller`, indexed canonical Chinese text, settled as `succeeded`, and became searchable.
- Full repository suite with the isolated DSN: **392 passed, 11 skipped, 0 failed**.
- The temporary container, database and SSH tunnel were removed after verification. Existing server containers and sites were untouched.
