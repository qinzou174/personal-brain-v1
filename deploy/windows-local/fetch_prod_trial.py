"""Fetch the current prod-trial credential to a local secure file (local-only; do not commit)."""
from __future__ import annotations

import pathlib
import sys

from _ssh import open_client, password

LOCAL = pathlib.Path(r"E:\Personal-Brain-V1-local\secrets\prod-trial-credential")
LOCAL.parent.mkdir(parents=True, exist_ok=True)

client = open_client()
stdin, stdout, stderr = client.exec_command(
    f"echo '{password()}' | sudo -S cat /home/kms/deploy/personal-brain/prod-data/secrets/prod-trial-credential 2>/dev/null",
    timeout=30,
)
token = stdout.read().decode().strip()
stderr.read()
if len(token) != 64:
    print(f"FATAL: unexpected token length {len(token)}")
    sys.exit(1)
LOCAL.write_text(token + "\n", encoding="utf-8")
LOCAL.chmod(0o600)
print(f"saved {len(token)}-char credential -> {LOCAL}")
client.close()
