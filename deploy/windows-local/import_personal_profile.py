"""Import the real personal profile (个人信息.txt, GPT chat-derived archive) into
the local instance (127.0.0.1:18082).

Principles honored:
  - Raw-first: the archive text is saved verbatim (no summarization, no deletion).
  - Grouping only for indexability: consecutive sections are stored as one note
    under a theme title; every section's original text is kept.
  - Claims: only stable/explicit parts become self claims; B = candidate,
    C = pending_confirmation (never disguised as confirmed fact).
"""
import json
import re
import sys
import uuid

sys.path.insert(0, __file__.rsplit("\\", 1)[0])
from mcp_probe import call, SESSION

ARCHIVE = r"e:\新建文件夹\Personal-Brain-V1\个人信息.txt"
PREFIX = "真实档案-"

# (note_title, [block_indexes]) — block 0 = opening, then 一、..一百五十四、 then closing
GROUPS = [
    ("档案开篇与基础背景", [0, 1]),
    ("性格核心：秩序感/追根究底/元认知", [2, 3, 4, 5]),
    ("完美主义/停不下来/方向感", [6, 7, 8]),
    ("意义感/恋旧/连续性/生活感", [9, 10, 11, 12, 13, 14]),
    ("深夜/日记/独处/亲密矛盾", [15, 16, 17, 18, 19, 20]),
    ("恋爱史/记忆地图/失去观", [21, 22, 23, 24, 25]),
    ("人生理想/现实拉扯/事业/圈层", [26, 27, 28, 29]),
    ("比较/身份/小众/筛选/认知变化", [30, 31, 32, 33, 34, 35, 36, 37]),
    ("自由/关系秩序/对称性/透明/安全感", [38, 39, 40, 41, 42, 43, 44, 45, 46, 47, 48, 49]),
    ("成长/依靠/孤独/游戏生活感", [50, 51, 52, 53, 54, 55, 56, 57]),
    ("AI陪伴项目/主体性/记忆观", [58, 59, 60, 61, 62, 63, 64]),
    ("工程方法论/Personal Brain/数据哲学", [65, 66, 67, 68, 69, 70, 71, 72, 73]),
    ("Agent/Telegram/Roblox AI/能落地", [74, 75, 76, 77, 78, 79, 80]),
    ("英语/图像审美/角色卡/壁纸", [81, 82, 83, 84, 85, 86, 87, 88, 89, 90, 91, 92]),
    ("交流哲学/活人感/忙空/商业社会观", [93, 94, 95, 96, 97, 98, 99, 100, 101, 102, 103]),
    ("猫/医保/网络/隐私/技术自主", [104, 105, 106, 107, 108, 109, 110, 111, 112]),
    ("AI模型/额度/消费/收藏/时间流逝", [113, 114, 115, 116, 117, 118]),
    ("自我发现/交流偏好/开放关系/人格/连续性", [119, 120, 121, 122, 123, 124, 125, 126, 127, 128, 129, 130, 131, 132, 133, 134, 135, 136, 137, 138, 139, 140, 141, 142, 143, 144, 145, 146, 147, 148, 149, 150, 151, 152]),
    ("矛盾清单/待验证/结语", [153, 154]),
]

# (category, claim_text, policy_class) — B=candidate, C=pending_confirmation
CLAIMS = [
    ("preference", "喜欢深夜凌晨两三点，城市退潮后的安静时光，听纯音乐、看窗外、回忆", "B"),
    ("aesthetic", "喜欢真实摄影感、电影感、生活感；讨厌模板味、网红感、过度磨皮、塑料感", "B"),
    ("aesthetic", "人物图追求身份级还原，讨厌脸漂移、五官改动、身材被美化", "B"),
    ("preference", "不喜欢太大众，追求个性+体面+辨识度，但不想为了奇怪而奇怪", "B"),
    ("interest", "喜欢 Roblox 聊天交友型服务器，看重多人世界里有人在做自己事的生活感", "B"),
    ("habit", "状态不好时需要独处，不希望被安慰式陪伴打扰；忙而有序会降低焦虑", "B"),
    ("communication_style", "讨厌咨询腔和安慰式口吻，喜欢像认识很久的老朋友一样自然、直接、可吐槽", "B"),
    ("working_style", "高层原则明确、底层让 AI 自主判断；大型工程修改前先报告、不执行", "B"),
    ("value", "连续性：东西应当长期存在，不轻易丢失、不漂移、不被替代；过去是现在的一部分", "C"),
    ("philosophy", "爱一个人不等于拥有一个人，不能因为自己难受就剥夺对方的自由", "C"),
    ("value", "我珍惜了，也会失去；失去不等于没有珍惜过", "C"),
    ("philosophy", "自由要和同意、不伤害、契约、责任一起看", "C"),
    ("goal", "建立自己的事业，挣良心钱，拥有自主权，不替别人打一辈子工", "C"),
    ("value", "关系可以增加、发展，但自己的核心位置不能被重新排位", "C"),
]


def split_blocks(text: str) -> list[str]:
    parts = re.split(r"\n---\n", text)
    return [p.strip() for p in parts if p.strip()]


def main():
    with open(ARCHIVE, encoding="utf-8") as f:
        blocks = split_blocks(f.read())
    print(f"archive blocks: {len(blocks)}")

    call("initialize", {"protocolVersion": "2025-11-25", "capabilities": {},
                        "clientInfo": {"name": "import-profile", "version": "0"}}, 1)
    call("notifications/initialized", {}, None)

    saved = 0
    for title, indexes in GROUPS:
        body = "\n\n---\n\n".join(blocks[i] for i in indexes if i < len(blocks))
        content = f"{PREFIX}{title}\n\n{body}"
        r = call("tools/call", {"name": "save_note", "arguments": {
            "content": content, "requested_scope": "knowledge",
            "idempotency_key": str(uuid.uuid4()),
        }}, 900)
        inner = r.get("result", {}).get("structuredContent", {})
        if inner.get("status") == "accepted":
            saved += 1
            print(f"  [note {saved}] {title} (blocks {len(indexes)}, {len(body)} chars)")
        else:
            print(f"  [FAIL] {title}: {json.dumps(r.get('error', inner), ensure_ascii=False)[:120]}")

    claimed = 0
    for category, claim_text, policy_class in CLAIMS:
        r = call("tools/call", {"name": "propose_self_claim", "arguments": {
            "category": category, "claim_text": claim_text, "policy_class": policy_class,
            "requested_scope": "self", "idempotency_key": str(uuid.uuid4()),
        }}, 900)
        inner = r.get("result", {}).get("structuredContent", {})
        status = inner.get("status") or inner.get("lifecycle_state")
        claimed += 1
        print(f"  [claim {claimed}] {policy_class}/{category} -> {status} | {claim_text[:30]}...")

    print(f"\ndone: notes={saved} claims={claimed}")


if __name__ == "__main__":
    main()
