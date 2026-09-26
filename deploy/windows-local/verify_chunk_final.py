"""Final checks: why 2 live cards lack semantics; proper chunked-doc listing."""
from _ssh import open_client

cli = open_client()
cmd = r"""
echo '=== the 2 no-semantic cards ==='
docker exec personal-brain-v1-prod-db-1 psql -U brain -d brain -c "
SELECT e.target_type, e.target_id, left(e.searchable_text, 60) AS head, e.warnings
FROM search_index_entries e
JOIN raw_inputs r ON r.id = e.target_id
WHERE r.lifecycle_state = 'active' AND e.embedding IS NULL
  AND NOT EXISTS (SELECT 1 FROM search_index_chunks c WHERE c.entry_id = e.id);"
echo '=== top chunked docs (fixed grouping) ==='
docker exec personal-brain-v1-prod-db-1 psql -U brain -d brain -c "
SELECT e.target_type, r.id, min(left(e.searchable_text, 36)) AS head, count(*) AS chunks
FROM search_index_chunks c
JOIN search_index_entries e ON e.id = c.entry_id
JOIN raw_inputs r ON r.id = e.target_id
GROUP BY e.target_type, r.id ORDER BY chunks DESC LIMIT 8;"
echo '=== doctor ==='
docker logs personal-brain-v1-prod-api-1 --since 90s 2>&1 | tail -4
"""
_, out, err = cli.exec_command(cmd, timeout=300)
print(out.read().decode("utf-8", "replace"))
e = err.read().decode("utf-8", "replace")
if e.strip():
    print("STDERR:", e[:800])
cli.close()
