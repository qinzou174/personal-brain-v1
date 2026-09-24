"""Full-journey smoke test over all 30 MCP tools against the local runtime.

Writes a JSONL report of every call: tool, ok/fail, error, result summary.
"""
import base64
import json
import uuid

from mcp_probe import call, SESSION

RESULTS = []
_id = [100]


def next_id():
    _id[0] += 1
    return _id[0]


def rec(tool, resp, note=""):
    ok = isinstance(resp, dict) and "result" in resp and not resp["result"].get("isError")
    sc = {}
    if isinstance(resp, dict) and "result" in resp:
        sc = resp["result"].get("structuredContent") or {}
        if not sc:
            try:
                sc = json.loads(resp["result"]["content"][0]["text"])
            except Exception:
                sc = {}
    elif isinstance(resp, dict) and "error" in resp:
        sc = resp["error"]
    content = json.dumps(sc, ensure_ascii=False)
    RESULTS.append({"tool": tool, "ok": ok, "note": note, "result": content[:600]})
    print(f"[{'OK ' if ok else 'FAIL'}] {tool} {('— ' + note) if note else ''} {content[:220] if not ok else ''}")
    return content


def result_of(raw):
    if isinstance(raw, dict):
        return raw
    try:
        return json.loads(raw)
    except Exception:
        return {}


def u():
    return str(uuid.uuid4())


def tc(name, args, note=""):
    return rec(name, call("tools/call", {"name": name, "arguments": args}, next_id()), note)


def run():
    rec("initialize", call("initialize", {"protocolVersion": "2025-11-25", "capabilities": {},
                                          "clientInfo": {"name": "smoke", "version": "0"}}, 1))
    call("notifications/initialized", {}, None)
    rec("tools/list", call("tools/list", {}, next_id()), note="30 个工具")

    # --- knowledge ---
    note_raw = tc("save_note", {"content": "冒烟测试笔记：Windows 本地部署验证。", "requested_scope": "knowledge", "idempotency_key": u()})
    note = result_of(note_raw)
    source_id = note.get("source_id") or note.get("record_id")
    tc("search_brain", {"query": "冒烟测试笔记", "requested_scope": "knowledge", "limit": 5}, note="无嵌入环境可能 fail-closed")
    tc("answer_brain", {"query": "冒烟测试笔记写了什么", "requested_scope": "knowledge"}, note="无嵌入环境可能 fail-closed")
    tc("get_brain_context", {"intent": "回顾最近记录", "requested_scope": "knowledge", "detail": "summary"})

    # --- todos ---
    tc("add_todo", {"content": "冒烟测试待办", "requested_scope": "todo", "idempotency_key": u(), "priority": 2})
    todos_raw = tc("list_todos", {"requested_scope": "todo"})
    items = (result_of(todos_raw).get("todos") or result_of(todos_raw).get("items") or [])
    todo_id, todo_ver = (None, 1)
    if items:
        first = items[-1]
        todo_id = first.get("todo_id") or first.get("id")
        todo_ver = first.get("version") or 1
    tc("complete_todo", {"todo_id": todo_id, "expected_version": todo_ver, "idempotency_key": u(), "requested_scope": "todo"} if todo_id else {},
       note="" if todo_id else "SKIP: 无 todo_id")

    # --- finance ---
    tc("add_expense", {"amount": "12.50", "currency": "CNY", "category": "测试", "description": "冒烟测试支出",
                       "occurred_timezone": "Asia/Shanghai", "requested_scope": "finance", "idempotency_key": u()})
    tc("get_expense_summary", {"currency": "CNY", "requested_scope": "finance"})
    tc("list_expense_records", {"requested_scope": "finance"})

    # --- self model ---
    tc("propose_self_claim", {"category": "value", "claim_text": "重视证据驱动决策（冒烟测试）", "policy_class": "A",
                              "requested_scope": "self", "idempotency_key": u()})
    tc("get_self_context", {"requested_scope": "self"})
    tc("create_review_item", {"item_type": "profile_confirmation", "subject_refs": [], "proposal": {"note": "smoke"},
                              "requested_scope": "review", "idempotency_key": u()})

    # --- project lifecycle ---
    proj = result_of(tc("create_project", {"name": f"冒烟项目-{u()[:8]}", "purpose": "MCP 全量冒烟", "requested_scope": "projects", "idempotency_key": u()}))
    pid = proj.get("project_id") or proj.get("record_id") or proj.get("id")
    if pid:
        # Mirror LAN provisioning: grant the dynamic project scope to the client.
        import provision_project_scope
        provision_project_scope.provision(pid)
        tc("get_project_context", {"project_id": pid})
        tc("check_freshness", {"project_id": pid})
        tc("record_decision", {"project_id": pid, "statement": "采用结构化冒烟", "rationale": "验证记录链路",
                               "affected_modules": ["smoke"], "idempotency_key": u()})
        tc("record_constraint", {"project_id": pid, "statement": "不使用真实个人数据", "rationale": "测试约束",
                                 "affected_modules": ["smoke"], "idempotency_key": u()})
        task = result_of(tc("start_task", {"project_id": pid, "goal": "完成冒烟任务", "revision": "r1",
                                           "dirty_state": False, "constraints": ["不导入真实数据"], "idempotency_key": u()}))
        tid = task.get("task_id") or task.get("record_id") or task.get("id")
        tc("get_active_task", {"project_id": pid})
        tc("get_recent_changes", {"project_id": pid})
        tc("get_module_context", {"project_id": pid, "module_name": "smoke"})
        tc("search_project", {"project_id": pid, "query": "冒烟", "limit": 5})
        tc("sync_workspace", {"project_id": pid, "approved_root_identity": "smoke-root", "root_proof": "smoke-proof",
                              "revision": "r1", "branch_ref": None, "dirty_state": False,
                              "changed_paths": ["smoke/README.md"], "file_hashes": {"smoke/README.md": "deadbeef"},
                              "modules": [{"name": "smoke", "files": ["smoke/README.md"]}],
                              "bridge_client_id": "91914bb7-461b-481d-8993-8970251e0cc7", "idempotency_key": u()})
        if tid:
            tc("checkpoint_task", {"task_id": tid, "completed_work": "完成脚本", "next_step": "finalize",
                                   "problems": "", "revision": "r2", "requested_scope": "projects",
                                   "idempotency_key": u(), "dirty_files": [], "changed_files": ["smoke/README.md"],
                                   "decisions": ["结构化冒烟"], "verification_evidence": "smoke run"})
            tc("finalize_task", {"task_id": tid, "outcome": "全部工具验证", "verification": "smoke 脚本通过",
                                 "remaining_work": "", "end_revision": "r2", "end_dirty_state": False,
                                 "changed_files": ["smoke/README.md"], "requested_scope": "projects", "idempotency_key": u()})
        else:
            tc("checkpoint_task", {}, note="SKIP: 无 task_id")
            tc("finalize_task", {}, note="SKIP: 无 task_id")
    else:
        for t in ["get_project_context", "check_freshness", "record_decision", "record_constraint",
                  "start_task", "get_active_task", "get_recent_changes", "get_module_context",
                  "search_project", "sync_workspace", "checkpoint_task", "finalize_task"]:
            tc(t, {}, note="SKIP: 无 project_id")

    # --- deletion plan ---
    plan = result_of(tc("create_deletion_plan", {"targets": [["note", source_id or u()]], "dependents": {},
                                                 "requested_scope": "review", "idempotency_key": u()}))
    plan_id = plan.get("plan_id") or plan.get("record_id") or plan.get("id")
    tc("get_deletion_plan", {"plan_id": plan_id} if plan_id else {}, note="" if plan_id else "SKIP: 无 plan_id")

    # --- asset / ops ---
    tc("upload_asset", {"content_base64": base64.b64encode("smoke".encode()).decode(),
                        "original_name": "smoke.txt", "media_type": "text/plain",
                        "source_id": source_id or u(), "idempotency_key": u()})
    op_id = note.get("operation_id")
    tc("get_operation_status", {"operation_id": op_id} if op_id else {}, note="" if op_id else "SKIP: 无 operation_id")

    # --- protocol negatives ---
    rec("tools/call:unknown_tool", call("tools/call", {"name": "no_such_tool", "arguments": {}}, next_id()),
        note="应 VALIDATION_FAILED(-32000)")
    rec("ping", call("ping", {}, next_id()), note="Bug2 已修复：应返回空 result")
    rec("tools/call:propose_self_claim category=设备",
        call("tools/call", {"name": "propose_self_claim", "arguments": {
            "category": "设备", "claim_text": "拥有 MacBook Air M1。", "policy_class": "A",
            "requested_scope": "self", "idempotency_key": u()}}, next_id()),
        note="Bug1 已修复：应 VALIDATION_FAILED 而非 500")
    rec("tools/call:save_note 缺参",
        call("tools/call", {"name": "save_note", "arguments": {}}, next_id()),
        note="Bug3 已修复：应 VALIDATION_FAILED 而非 parse error")


if __name__ == "__main__":
    run()
    out = r"C:\Users\槐至\AppData\Local\Temp\brain_smoke_report.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(RESULTS, f, ensure_ascii=False, indent=2)
    expected_deny = ("TOOL_DENIED", "SCOPE_DENIED", "VALIDATION_FAILED", "NOT_FOUND",
                     "CONFIRMATION_REQUIRED", "WORKSPACE_BOUNDARY_VIOLATION")
    hard = [x for x in RESULTS if not x["ok"] and "SKIP" not in x["note"]
            and not any(k in x["result"] for k in expected_deny)]
    print(f"\nTOTAL={len(RESULTS)} OK={len(RESULTS)-len(hard)} HARD_FAIL={len(hard)}")
    for x in hard:
        print("HARD:", x["tool"], x["result"][:200])
    print(f"report: {out}  session={SESSION['id']}")
