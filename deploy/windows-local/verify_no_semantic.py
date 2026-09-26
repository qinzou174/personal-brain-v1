"""Final: no-semantic count post-drain (must be 0 or secret-skipped)."""
from _ssh import open_client

cli = open_client()
cmd = r"""
docker exec personal-brain-v1-prod-db-1 psql -U brain -d brain -c "
SELECT count(*) AS live_no_semantic
FROM search_index_entries e
JOIN raw_inputs r ON r.id = e.target_id
WHERE r.lifecycle_state = 'active' AND e.embedding IS NULL
  AND NOT EXISTS (SELECT 1 FROM search_index_chunks c WHERE c.entry_id = e.id);"
docker exec personal-brain-v1-prod-db-1 psql -U brain -d brain -c "
SELECT count(*) AS total_chunks, count(DISTINCT entry_id) AS chunked_cards FROM search_index_chunks;"
"""
_, out, err = cli.exec_command(cmd, timeout=120)
print(out.read().decode("utf-8", "replace"))
e = err.read().decode("utf-8", "replace")
if e.strip():
    print("STDERR:", e[:500])
cli.close()
