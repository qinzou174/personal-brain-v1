"""MCP smoke over the HTTPS + nyat.app tunnel -> nginx -> 18083 (prod stack).

Validates the full external path: real client -> tunnel -> nginx /brain/mcp
-> Personal Brain prod api. Uses the prod-trial credential.
"""
import json
import os
import sys
import urllib.request

BASE = "https://www.h2d954063.nyat.app:43086/brain/mcp"
CRED = os.environ.get("BRAIN_MCP_CREDENTIAL", "")
if not CRED:
    print("BRAIN_MCP_CREDENTIAL env var required (prod credential)")
    sys.exit(2)
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
        with urllib.request.urlopen(req, timeout=30) as resp:
            sid = resp.headers.get("MCP-Session-Id")
            if sid:
                SESSION["id"] = sid
            raw = resp.read().decode()
            print(f"[{method}] HTTP {resp.status} session={sid}")
            return json.loads(raw) if raw.strip() else {"empty": True}
    except urllib.error.HTTPError as e:
        sid = e.headers.get("MCP-Session-Id")
        if sid:
            SESSION["id"] = sid
        print(f"[{method}] HTTP {e.code} session={sid}")
        try:
            return json.loads(e.read().decode())
        except Exception:
            return {"error": f"HTTP {e.code}"}


def main():
    r = call("initialize", {"protocolVersion": "2025-11-25", "capabilities": {},
                            "clientInfo": {"name": "tunnel-smoke", "version": "1"}}, 1)
    print("init:", json.dumps(r, ensure_ascii=False)[:220])
    call("notifications/initialized", {}, None)
    r = call("tools/list", {}, 2)
    tools = r.get("result", {}).get("tools", [])
    print(f"tools/list -> {len(tools)} tools")
    names = sorted(t["name"] for t in tools)
    print("first8:", names[:8])
    print("count: 30" if len(tools) == 30 else f"count: {len(tools)}")


if __name__ == "__main__":
    main()