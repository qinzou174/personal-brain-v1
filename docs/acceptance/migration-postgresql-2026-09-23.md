# PostgreSQL migration evidence — 2026-09-23

Status: **PASS** for T184's isolated physical migration gate.

## Isolation and runtime

- Target: temporary Docker container on `192.168.10.7`, bound only to remote loopback and reached through an SSH local forward.
- Database: `personal_brain_20260923_test`; the enforced `_test` suffix gate rejected the first nonconforming database name before any migration ran.
- Image: `pgvector/pgvector@sha256:ccc6e83d6e35e931dc7c5def2022729d5a6c370318d099181995567ff1fb4d6b` (`pg16` tag at execution time).
- Client stack: SQLAlchemy 2.0.54, Alembic 1.20.0, psycopg 3.3.6.
- The temporary container and its ephemeral databases were removed after verification. Existing containers, sites and databases were not modified.

## Executed evidence

1. `tests/migration/test_full_chain_postgresql.py` physically upgraded revisions 0001 through 0011 in a randomly named `brain_migration_test_*` schema.
2. Every revision's preflight and post-validation SQL passed.
3. The resulting table inventory exactly matched the union of migration-owned tables; representative job, expense and self-model indexes were present.
4. The complete chain was downgraded from 0011 through 0001; the isolated schema contained zero tables afterward.
5. All migration tests passed: **20 passed**.
6. After adding physical FTS/pgvector and durable-index-worker coverage, the full repository suite using the same isolated PostgreSQL gate passed: **392 passed, 11 skipped**.
7. Without `BRAIN_TEST_POSTGRES_DSN`, the physical tests explicitly skip while static chain integrity remains active.

## Defects found and corrected by the physical run

- Migration 0002 declared `source_id` twice in multiple life-record tables.
- Migration 0002 declared `owner_id` twice in `todos`.
- Migration 0006 listed asset tables in an order that made reverse downgrade drop `asset_blobs` before the referencing `assets` table.
- The first pgvector revision installed the extension into the temporary application schema, preventing clean schema removal. It now installs the shared extension in `public` and keeps the application/test schema independently reversible.

These defects were invisible to the prior source-only checks and prevented a real full-chain migration or rollback. The corrected chain now exercises both directions on PostgreSQL.
