"""One-off: supersede the handoff mirror note with the updated local doc (update_note).

Follow-up to ingest_handoff_to_brain.py: the local handoff doc gained a
verification record (2026-09-26), so the brain mirror must be kept consistent.
"""
import json
import uuid
import urllib.request

BASE = "http://192.168.10.7:18083/mcp"
OLD_NOTE_ID = "1df8ab4f-02f2-444d-b5fc-29a3dc95797f"
with open(r"E:\Personal-Brain-V1-local\secrets\prod-trial-credential", "r", encoding="utf-8") as f:
    CRED = f.read().strip()
SESSION = {"id": None}
RID = {"n": 3000}


def call(method, params=None, req_id=None):
    RID["n"] += 1
    headers = {"Authorization": f"Bearer {CRED}", "Content-Type": "application/json",
               "MCP-Protocol-Version": "2025-11-25"}
    if SESSION["id"]:
        headers["MCP-Session-Id"] = SESSION["id"]
    body = {"jsonrpc": "2.0", "id": RID["n"], "method": method, "params": params or {}}
    req = urllib.request.Request(BASE, json.dumps(body).encode(), headers)
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            sid = resp.headers.get("MCP-Session-Id")
            if sid:
                SESSION["id"] = sid
            raw = resp.read().decode()
            return json.loads(raw) if raw.strip() else {"empty": True}
    except urllib.error.HTTPError as e:
        if SESSION["id"] is None and e.headers.get("MCP-Session-Id"):
            SESSION["id"] = e.headers["MCP-Session-Id"]
        try:
            return json.loads(e.read().decode())
        except Exception:
            return {"http_error": e.code}


def tool(name, arguments):
    r = call("tools/call", {"name": name, "arguments": arguments})
    result = r.get("result", {})
    sc = result.get("structuredContent", None)
    if sc is None and result.get("content"):
        sc = result["content"][0].get("text", "{}")
    if isinstance(sc, str):
        try:
            sc = json.loads(sc)
        except Exception:
            sc = {"raw": sc}
    sc = sc if isinstance(sc, dict) else {"raw": sc}
    if result.get("isError"):
        sc["_rpc_error"] = sc.get("code")
    return sc


with open(r"E:\新建文件夹\Personal-Brain-V1\docs\tasks\trae-cn-mcp-session-20260926.md", encoding="utf-8") as f:
    doc = f.read()

# Session gate: initialize first, or tools/call gets 400 MCP_SESSION_REQUIRED.
# (First run of this script omitted this block and reproduced the exact incident
# the handoff doc describes — the server was right, the client was wrong.)
call("initialize", {"protocolVersion": "2025-11-25", "capabilities": {},
                    "clientInfo": {"name": "handoff-update", "version": "1"}})
call("notifications/initialized", {}, None)

content = (
    "【交接·MCP_SESSION_REQUIRED】另一个 Trae CN 客户端 list tools 被挡的完整诊断与待执行方案（2026-09-26，"
    "详细版交接文档全文入库；2026-09-26 上午已接续执行并验证，本条为 update_note 更正版，取代旧镜像 1df8ab4f）。"
    "根因定案：非 OAuth 授权问题，是 MCP 2025-11-25 Streamable HTTP 会话生命周期问题——"
    "token 通过认证但客户端未携带 MCP-Session-Id 请求头，服务端按规范返回 400 MCP_SESSION_REQUIRED。\n\n"
    + doc
)

res = tool("update_note", {"old_note_id": OLD_NOTE_ID, "content": content,
                           "requested_scope": "knowledge",
                           "idempotency_key": str(uuid.uuid4())})
print("update_note:", json.dumps(res, ensure_ascii=False)[:600])

# Full raw response for diagnosis (idempotency: rerun gets same result key? no —
# new uuid each run; a true empty-success repeat would duplicate. Guarded below.)
if res == {"raw": None}:
    raw = call("tools/call", {"name": "update_note", "arguments": {
        "old_note_id": OLD_NOTE_ID, "content": content,
        "requested_scope": "knowledge", "idempotency_key": str(uuid.uuid4())}})
    print("RAW:", json.dumps(raw, ensure_ascii=False)[:1500])
