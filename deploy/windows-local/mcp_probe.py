"""Probe the local MCP endpoint: initialize, list tools, dump schemas."""
import json
import sys
import urllib.request

BASE = "http://127.0.0.1:18082/mcp"
CRED = open(r"E:\Personal-Brain-V1-local\secrets\windows-trial-credential", encoding="utf-8").read().strip()
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
                return json.loads(raw) if raw.strip() else {"empty": True}
    except urllib.error.HTTPError as e:
        sid = e.headers.get("MCP-Session-Id")
        if sid:
            SESSION["id"] = sid
        try:
            return json.loads(e.read().decode())
        except Exception:
            return {"error": f"HTTP {e.code}"}


if __name__ == "__main__":
    call("initialize", {"protocolVersion": "2025-11-25", "capabilities": {},
                        "clientInfo": {"name": "probe", "version": "0"}}, 1)
    call("notifications/initialized", {}, None)
    result = call("tools/list", {}, 2)
    tools = result.get("result", {}).get("tools", [])
    out = sys.argv[1] if len(sys.argv) > 1 else "-"
    if out == "-":
        print(json.dumps(tools, ensure_ascii=False, indent=2))
    else:
        with open(out, "w", encoding="utf-8") as f:
            json.dump(tools, f, ensure_ascii=False, indent=2)
        print(f"{len(tools)} tools dumped to {out}")
        for t in tools:
            print(t["name"])
