"""Rotate zafiro, deliver the new token to the owner's local secure file, verify (local-only; do not commit).

- rotate-client zafiro (old phone token dies immediately)
- copy the new credential into prod-data/secrets/zafiro-credential (10001:0600)
- fetch it to E:\\Personal-Brain-V1-local\\secrets\\zafiro-credential for the owner
- verify MCP initialize = 200 with the new token (status code only, no secret printed)
"""
from __future__ import annotations

import pathlib
import sys

from _ssh import open_client, password

PW = password()
LOCAL = pathlib.Path(r"E:\Personal-Brain-V1-local\secrets\zafiro-credential")
LOCAL.parent.mkdir(parents=True, exist_ok=True)
REMOTE_SECRET = "/home/kms/deploy/personal-brain/prod-data/secrets/zafiro-credential"

client = open_client()


def run(cmd: str, timeout: int = 60) -> str:
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", "replace")
    err = stderr.read().decode("utf-8", "replace")
    code = stdout.channel.recv_exit_status()
    return out, err, code


steps: list[tuple[str, str, int]] = []

# 1) rotate (clear the temp target first - rotate refuses to overwrite)
out, err, code = run(
    f"echo '{PW}' | sudo -S -v 2>/dev/null; "
    "cd /home/kms/deploy/personal-brain/prod && "
    "S=/home/kms/deploy/personal-brain/prod-data/secrets && "
    "export BRAIN_DB_PASSWORD_FILE=$S/db_password BRAIN_DB_DSN_FILE=$S/db_dsn "
    "BRAIN_TOKEN_PEPPER_FILE=$S/token_pepper BRAIN_MODEL_API_KEY_FILE=$S/model_api_key && "
    "docker compose -f deploy/compose.prod.yaml exec -T api sh -c 'rm -f /tmp/zafiro.new' </dev/null; "
    "docker compose -f deploy/compose.prod.yaml exec -T api python -m personal_brain_server rotate-client "
    "--client-id 102b8f90-5b0c-4657-80f2-c9b388c47a1b --credential-file /tmp/zafiro.new </dev/null 2>&1 | tail -1",
)
steps.append(("rotate", out.strip(), code))

# 2) copy into the server secrets dir (owner = container uid 10001)
out, err, code = run(
    f"echo '{PW}' | sudo -S docker cp personal-brain-v1-prod-api-1:/tmp/zafiro.new {REMOTE_SECRET} && "
    f"echo '{PW}' | sudo -S chown 10001:10001 {REMOTE_SECRET} && "
    f"echo '{PW}' | sudo -S chmod 600 {REMOTE_SECRET} && "
    f"echo '{PW}' | sudo -S docker exec personal-brain-v1-prod-api-1 sh -c 'rm -f /tmp/zafiro.new' </dev/null && "
    f"echo COPIED",
)
steps.append(("copy", out.strip(), code))

# 3) read the new token (server side) and store it locally - never printed
out, err, code = run(f"echo '{PW}' | sudo -S cat {REMOTE_SECRET} 2>/dev/null")
token = out.strip()
if len(token) != 64:
    print(f"FATAL: token length {len(token)}; aborting")
    for name, text, c in steps:
        print(f"-- {name} (rc={c}): {text[:200]}")
    client.close()
    sys.exit(1)
LOCAL.write_text(token + "\n", encoding="utf-8")

# 4) verify initialize with the new token (status code only)
out, err, code = run(
    f"echo '{PW}' | sudo -S sh -c \"curl -sS -o /dev/null -w '%{{http_code}}' -X POST "
    "http://192.168.10.7:18083/mcp -H 'Authorization: Bearer "
    + token
    + "' -H 'Content-Type: application/json' -d '{\\\"jsonrpc\\\":\\\"2.0\\\",\\\"id\\\":1,\\\"method\\\":\\\"initialize\\\",\\\"params\\\":{\\\"protocolVersion\\\":\\\"2025-11-25\\\",\\\"capabilities\\\":{{}},\\\"clientInfo\\\":{{\\\"name\\\":\\\"zafiro-phone\\\",\\\"version\\\":\\\"1\\\"}}}}'\" 2>/dev/null",
    timeout=30,
)
steps.append(("verify http", out.strip(), code))

for name, text, c in steps:
    print(f"-- {name} (rc={c}): {text[:160]}")
print(f"local credential file: {LOCAL}")
client.close()
