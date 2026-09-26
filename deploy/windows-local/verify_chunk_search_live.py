"""Live long-doc retrieval acceptance: search_brain('MCP_SESSION_REQUIRED Trae')
must surface the handoff document (previously drowned out of the semantic list).
Endpoint: prod MCP http://192.168.10.7:18083/mcp, client prod-trial.
"""
import json
import urllib.request

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
    except urllib.error.HTTPError as e:
        sid = e.headers.get("MCP-Session-Id")
        if sid:
            SESSION["id"] = sid
        try:
            return json.loads(e.read().decode())
        except Exception:
            return {"error": f"HTTP {e.code}"}


call("initialize", {"protocolVersion": "2025-11-25", "capabilities": {},
                    "clientInfo": {"name": "chunk-accept", "version": "0"}}, 1)
call("notifications/initialized", {}, None)

for query in ["MCP_SESSION_REQUIRED Trae", "RRF 单列表淹没 交接文档"]:
    result = call("tools/call", {"name": "search_brain", "arguments": {
        "query": query, "limit": 5, "requested_scope": "knowledge",
    }}, 2)
    payload = result.get("result", {})
    content = payload.get("content", [])
    print(f"=== query: {query} (isError={payload.get('isError')}) ===")
    for item in content:
        print(item.get("text", "")[:1200])
    print()

# also fetch the handoff entry full text via the two-step flow
result = call("tools/call", {"name": "search_brain", "arguments": {
    "query": "MCP_SESSION_REQUIRED Trae", "limit": 1, "requested_scope": "knowledge",
}}, 3)
entry = json.loads(result["result"]["content"][0]["text"])
first = entry["hits"][0] if entry.get("hits") else None
if first:
    detail = call("tools/call", {"name": "get_entry_content", "arguments": {
        "entry_id": first["entry_id"],
    }}, 4)
    text = detail.get("result", {}).get("content", [{}])[0].get("text", "")
    print(f"=== get_entry_content({first['entry_id'][:8]}...) len={len(text)} ===")
    print(text[:600])
else:
    print("NO RESULT for handoff query")
