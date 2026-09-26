"""Deploy 2026-09-26 chunked semantic indexing (step 1: pull + build + migrate 0015)."""
import sys

from _ssh import open_client

EXPECTED = sys.argv[1] if len(sys.argv) > 1 else "fd28508"
cli = open_client()
cmd = r"""
cd /home/kms/deploy/personal-brain/prod
echo "=== git pull (with retry) ==="
EXPECTED=__EXPECTED__
for i in 1 2 3 4 5; do
  git pull --ff-only origin main >/tmp/pull.log 2>&1
  HEAD=$(git rev-parse --short HEAD)
  if [ "$HEAD" = "$EXPECTED" ]; then echo "pull ok: $HEAD (attempt $i)"; break; fi
  echo "attempt $i: HEAD=$HEAD != $EXPECTED, retrying..."; sleep 3
done
[ "$(git rev-parse --short HEAD)" = "$EXPECTED" ] || { echo "FATAL: HEAD mismatch"; cat /tmp/pull.log; exit 9; }
S=/home/kms/deploy/personal-brain/prod-data/secrets
export BRAIN_DB_PASSWORD_FILE=$S/db_password BRAIN_DB_DSN_FILE=$S/db_dsn \
       BRAIN_TOKEN_PEPPER_FILE=$S/token_pepper BRAIN_MODEL_API_KEY_FILE=$S/model_api_key
echo "=== build ==="
docker compose -f deploy/compose.prod.yaml build api worker 2>&1 | tail -4
echo "=== up -d (incl migrate) ==="
docker compose -f deploy/compose.prod.yaml up -d --build api worker migrate 2>&1 | tail -8
sleep 12
echo "=== ps ==="
docker ps --format '{{.Names}} {{.Status}}' | grep -i brain
echo "=== alembic version ==="
docker exec personal-brain-v1-prod-db-1 psql -U brain -d brain -c "SELECT version_num FROM alembic_version;"
echo "=== chunk table ==="
docker exec personal-brain-v1-prod-db-1 psql -U brain -d brain -c "\d search_index_chunks" | head -20
echo "=== api /doctor ==="
TOKEN=$(sudo cat /home/kms/deploy/personal-brain/prod/model-proxy/doctor_token 2>/dev/null || echo "")
if [ -n "$TOKEN" ]; then
  curl -s -H "Authorization: Bearer $TOKEN" http://127.0.0.1:18083/doctor | head -c 400
else
  echo "(no doctor token path; skip)"
fi
""".replace("__EXPECTED__", EXPECTED)
_, out, err = cli.exec_command(cmd, timeout=900)
print(out.read().decode("utf-8", "replace"))
e = err.read().decode("utf-8", "replace")
if e.strip():
    print("STDERR:", e[:800])
cli.close()
