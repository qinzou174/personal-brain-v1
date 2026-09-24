"""Rebuild the runtime image and restart services on the LAN server (local-only)."""
import sys
import paramiko

from _ssh import open_client

cli = open_client()
cmd = "cd /home/kms/personal-brain-v1 && docker compose build api 2>&1 | tail -5 && docker compose up -d 2>&1 | tail -8"
_, out, err = cli.exec_command(cmd, timeout=600)
print(out.read().decode("utf-8", "replace"))
e = err.read().decode("utf-8", "replace")
if e.strip():
    print("--- STDERR ---")
    print(e)
cli.close()
