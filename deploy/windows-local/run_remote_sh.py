"""Pipe a local script file to the remote bash via stdin (local-only; do not commit).

Usage: uv run python deploy/windows-local/run_remote_sh.py <script.sh>
Avoids all PowerShell quoting pitfalls: the script is read locally and piped
to `bash -s` on the server untouched.
"""

from __future__ import annotations

import sys
from pathlib import Path

import paramiko

from _ssh import open_client


def main() -> int:
    script = Path(sys.argv[1]).read_text(encoding="utf-8")
    client = open_client()
    stdin, stdout, stderr = client.exec_command("bash -s", timeout=600)
    stdin.write(script)
    stdin.flush()
    stdin.channel.shutdown_write()
    print(stdout.read().decode("utf-8", "replace"))
    code = stdout.channel.recv_exit_status()
    err = stderr.read().decode("utf-8", "replace")
    if err.strip():
        print("--- STDERR (tail) ---")
        print("\n".join(err.strip().splitlines()[-10:]))
    client.close()
    return code


if __name__ == "__main__":
    sys.exit(main())
