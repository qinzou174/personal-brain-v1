"""Wait for rebuild_index queue to drain, then final chunk verification."""
import time

from _ssh import open_client

cli = open_client()
cmd = r"""
for i in $(seq 1 60); do
  ROW=$(docker exec personal-brain-v1-prod-db-1 psql -U brain -d brain -t -A -c "
    SELECT coalesce(sum(count),0) FROM jobs
    WHERE job_type='rebuild_index' AND state IN ('queued','leased');")
  echo "poll $i: pending=$ROW"
  [ "$ROW" = "0" ] && break
  sleep 10
done
echo '=== final job states ==='
docker exec personal-brain-v1-prod-db-1 psql -U brain -d brain -c "
SELECT state, count(*) FROM jobs WHERE job_type='rebuild_index' GROUP BY state;"
echo '=== failed payloads sample (if any) ==='
docker exec personal-brain-v1-prod-db-1 psql -U brain -d brain -c "
SELECT count(*) FROM jobs WHERE job_type='rebuild_index' AND state='failed';"
echo '=== chunk stats ==='
docker exec personal-brain-v1-prod-db-1 psql -U brain -d brain -c "
SELECT count(*) AS total_chunks, count(DISTINCT entry_id) AS chunked_cards FROM search_index_chunks;"
echo '=== live cards missing vector AND chunks ==='
docker exec personal-brain-v1-prod-db-1 psql -U brain -d brain -c "
SELECT e.target_type, count(*) FROM search_index_entries e
JOIN raw_inputs r ON r.id = e.target_id
WHERE r.lifecycle_state = 'active' AND e.embedding IS NULL
  AND NOT EXISTS (SELECT 1 FROM search_index_chunks c WHERE c.entry_id = e.id)
GROUP BY 1;"
echo '=== top chunked docs ==='
docker exec personal-brain-v1-prod-db-1 psql -U brain -d brain -c "
SELECT e.target_type, left(r.searchable_text, 36) AS head, count(*) AS chunks
FROM search_index_chunks c
JOIN search_index_entries e ON e.id = c.entry_id
JOIN raw_inputs r ON r.id = e.target_id
GROUP BY e.target_type, r.id ORDER BY chunks DESC LIMIT 5;"
"""
_, out, err = cli.exec_command(cmd, timeout=900)
print(out.read().decode("utf-8", "replace"))
e = err.read().decode("utf-8", "replace")
if e.strip():
    print("STDERR:", e[:800])
cli.close()
