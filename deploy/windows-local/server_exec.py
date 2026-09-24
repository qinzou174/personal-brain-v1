"""Run a command on the LAN server (local-only; do not commit)."""
import sys
import paramiko

from _ssh import open_client

cli = open_client()
_, out, err = cli.exec_command(sys.argv[1], timeout=600)
print(out.read().decode("utf-8", "replace"))
e = err.read().decode("utf-8", "replace")
if e.strip():
    print("--- STDERR ---")
    print(e)
cli.close()
