"""Run a read-only SQL statement in the prod database (local-only; do not commit).

Usage: uv run python deploy/windows-local/server_sql.py "select 1"
The password is read from the prod secret file on the server host and passed to
psql via the environment, so nothing is embedded here.
"""

from __future__ import annotations

import shlex
import sys

import paramiko

from _ssh import open_client

PROD_SECRET = "/home/kms/deploy/personal-brain/prod-data/secrets/db_password"
DB_CONTAINER = "personal-brain-v1-prod-db-1"


def main() -> int:
    statement = sys.argv[1] if len(sys.argv) > 1 else "select 1"
    remote = (
        f'docker exec -e PGPASSWORD="$(cat {PROD_SECRET})" {DB_CONTAINER} '
        f"psql -U brain -d brain -At -c {shlex.quote(statement)}"
    )
    client = open_client()
    _, out, err = client.exec_command(remote, timeout=120)
    stdout = out.read().decode("utf-8", "replace")
    stderr = err.read().decode("utf-8", "replace")
    print(stdout, end="" if stdout.endswith("\n") else "\n")
    if stderr.strip():
        print("--- STDERR ---")
        print(stderr)
    client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())