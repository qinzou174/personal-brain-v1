"""Verify 2026-09-26 chunked indexing backfill + live long-doc retrieval."""
from _ssh import open_client

cli = open_client()
cmd = r"""
echo '=== job queue state (all types, last 30 min) ==='
docker exec personal-brain-v1-prod-db-1 psql -U brain -d brain -c "
SELECT job_type, state, count(*) FROM jobs WHERE created_at > now() - interval '30 minutes' GROUP BY job_type, state ORDER BY 3 DESC LIMIT 10;"
echo '=== dead letters ==='
docker exec personal-brain-v1-prod-db-1 psql -U brain -d brain -c "
SELECT count(*) FROM jobs WHERE state='dead';"
echo '=== chunk stats ==='
docker exec personal-brain-v1-prod-db-1 psql -U brain -d brain -c "
SELECT count(*) AS total_chunks,
       count(DISTINCT entry_id) AS chunked_cards
FROM search_index_chunks;"
echo '=== chunked parent cards must have embedding IS NULL ==='
docker exec personal-brain-v1-prod-db-1 psql -U brain -d brain -c "
SELECT count(*) AS chunked_parents_with_vector
FROM search_index_entries e
WHERE e.embedding IS NOT NULL
  AND EXISTS (SELECT 1 FROM search_index_chunks c WHERE c.entry_id = e.id);"
echo '=== live cards missing vector AND missing chunks (should be 0 or secret-skipped only) ==='
docker exec personal-brain-v1-prod-db-1 psql -U brain -d brain -c "
SELECT count(*) AS live_cards_no_semantic
FROM search_index_entries e
JOIN raw_inputs r ON r.id = e.target_id
WHERE r.lifecycle_state = 'active'
  AND e.embedding IS NULL
  AND NOT EXISTS (SELECT 1 FROM search_index_chunks c WHERE c.entry_id = e.id);"
echo '=== biggest chunked docs ==='
docker exec personal-brain-v1-prod-db-1 psql -U brain -d brain -c "
SELECT e.target_type, left(r.content, 40) AS head, count(*) AS chunks
FROM search_index_chunks c
JOIN search_index_entries e ON e.id = c.entry_id
JOIN raw_inputs r ON r.id = e.target_id
GROUP BY e.target_type, r.id ORDER BY chunks DESC LIMIT 5;"
"""
_, out, err = cli.exec_command(cmd, timeout=300)
print(out.read().decode("utf-8", "replace"))
e = err.read().decode("utf-8", "replace")
if e.strip():
    print("STDERR:", e[:800])
cli.close()
