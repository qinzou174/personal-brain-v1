"""Tail the production api/worker docker logs into local files (local-only; do not commit).

Usage: uv run python deploy/windows-local/tail_prod_logs.py <duration-seconds>
Polls `docker logs --since` in 15s increments and appends new lines to
docs/acceptance/audit-2026-09-25/live-api.log and live-worker.log so the
MCP write-test traffic can be correlated with server-side behavior.
"""

from __future__ import annotations

import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import paramiko

from _ssh import open_client

OUT_DIR = Path(__file__).resolve().parents[2] / "docs" / "acceptance" / "audit-2026-09-25"
POLL_SECONDS = 15


def main() -> int:
    duration = int(sys.argv[1]) if len(sys.argv) > 1 else 600
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    files = {name: (OUT_DIR / f"live-{name}.log").open("a", encoding="utf-8")
             for name in ("api", "worker")}
    client = open_client()
    since = datetime.now(timezone.utc) - timedelta(seconds=5)
    deadline = time.monotonic() + duration
    print(f"tailing for {duration}s -> {OUT_DIR}", flush=True)
    try:
        while time.monotonic() < deadline:
            stamp = since.strftime("%H:%M:%S")
            for name in ("api", "worker"):
                cmd = (
                    "docker logs personal-brain-v1-prod-"
                    f"{name}-1 --since {POLL_SECONDS}s 2>&1 | grep -v '^$' | head -100"
                )
                _, out, err = client.exec_command(cmd, timeout=20)
                text = out.read().decode("utf-8", "replace")
                err.read()
                if text.strip():
                    files[name].write(f"--- poll@{stamp} ---\n{text}\n")
                    files[name].flush()
                    print(f"[{name}] +{text.count(chr(10))} lines", flush=True)
            since = datetime.now(timezone.utc) - timedelta(seconds=3)
            time.sleep(POLL_SECONDS)
    finally:
        for handle in files.values():
            handle.close()
        client.close()
        print("tail finished", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
