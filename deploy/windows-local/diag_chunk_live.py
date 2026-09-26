"""Diagnose: 2 no-semantic cards + raw MCP response dump."""
import json
import urllib.request

from _ssh import open_client

cli = open_client()
cmd = r"""
docker exec personal-brain-v1-prod-db-1 psql -U brain -d brain -c "
SELECT e.target_id, e.target_type, left(e.searchable_text, 80) AS head
FROM search_index_entries e
JOIN raw_inputs r ON r.id = e.target_id
WHERE r.lifecycle_state = 'active' AND e.embedding IS NULL
  AND NOT EXISTS (SELECT 1 FROM search_index_chunks c WHERE c.entry_id = e.id);"
docker exec personal-brain-v1-prod-db-1 psql -U brain -d brain -c "
SELECT j.state, left(j.payload::text, 300) AS payload, left(coalesce(j.last_error,''),200) AS err
FROM jobs j WHERE j.job_type='rebuild_index' AND j.state NOT IN ('succeeded') LIMIT 5;"
"""
_, out, err = cli.exec_command(cmd, timeout=120)
print(out.read().decode("utf-8", "replace"))
e = err.read().decode("utf-8", "replace")
if e.strip():
    print("STDERR:", e[:500])
cli.close()

BASE = "http://192.168.10.7:18083/mcp"
CRED = open(r"E:\Personal-Brain-V1-local\secrets\prod-trial-credential", encoding="utf-8").read().strip()
SESSION = {"id": None}


def call(method, params=None, req_id=1):
    headers = {
        "Authorization": f"Bearer {CRED}",
        "Content-Type": "application/json",
        "MCP-Protocol-Version": "2025-11-25",
    }
    if SESSION["id"]:
        headers["MCP-Session-Id"] = SESSION["id"]
    body = {"jsonrpc": "2.0", "id": req_id, "method": method, "params": params or {}}
    req = urllib.request.Request(BASE, json.dumps(body).encode(), headers)
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            sid = resp.headers.get("MCP-Session-Id")
            if sid:
                SESSION["id"] = sid
            raw = resp.read().decode()
            return json.loads(raw) if raw.strip() else {"empty": True}
    except urllib.error.HTTPError as ex:
        sid = ex.headers.get("MCP-Session-Id")
        if sid:
            SESSION["id"] = sid
        try:
            return json.loads(ex.read().decode())
        except Exception:
            return {"error": f"HTTP {ex.code}"}


print("=== init ===")
print(json.dumps(call("initialize", {"protocolVersion": "2025-11-25", "capabilities": {},
                                     "clientInfo": {"name": "diag", "version": "0"}}, 1), ensure_ascii=False)[:400])
print("=== tools/call search_brain raw ===")
print(json.dumps(call("tools/call", {"name": "search_brain", "arguments": {
    "query": "MCP_SESSION_REQUIRED Trae", "limit": 5,
}}, 2), ensure_ascii=False)[:1500])
