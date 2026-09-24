"""E2E: call a real tool through the HTTPS tunnel (prod, empty DB)."""
import json
import os
import urllib.request
import uuid

BASE = "https://www.h2d954063.nyat.app:43086/brain/mcp"
CRED = os.environ.get("BRAIN_MCP_CREDENTIAL", "")
if not CRED:
    print("BRAIN_MCP_CREDENTIAL env var required (prod credential)")
    raise SystemExit(2)
SESSION = {"id": None}


def call(method, params=None, req_id=1):
    headers = {"Authorization": f"Bearer {CRED}", "Content-Type": "application/json",
               "MCP-Protocol-Version": "2025-11-25"}
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
    except urllib.error.HTTPError as e:
        sid = e.headers.get("MCP-Session-Id")
        if sid:
            SESSION["id"] = sid
        try:
            return json.loads(e.read().decode())
        except Exception:
            return {"error": f"HTTP {e.code}"}


call("initialize", {"protocolVersion": "2025-11-25", "capabilities": {},
                    "clientInfo": {"name": "e2e-tunnel", "version": "1"}}, 1)
call("notifications/initialized", {}, None)
r = call("tools/call", {"name": "save_note", "arguments": {
    "content": "隧道部署验证：第一条通过 HTTPS 公网写入的笔记", "requested_scope": "knowledge",
    "idempotency_key": str(uuid.uuid4())}}, 2)
print(json.dumps(r, ensure_ascii=False)[:400])