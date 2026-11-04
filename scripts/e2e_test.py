"""端到端真实测试：绕过 PowerShell 编码问题"""
import httpx, json

BASE = "http://localhost:8000"

def show(title, r):
    print(f"\n=== {title} ===")
    print(json.dumps(r, ensure_ascii=False, indent=2)[:600])

# 1. medical 正常问答
r = httpx.post(f"{BASE}/api/v1/chat", json={
    "question": "PCLT20K 数据集用于什么任务？",
    "domain": "medical", "user_id": "e2e"
}).json()
print("\n=== 1. medical 正常问答 ===")
print("answer:", r["answer"][:200])
print("citations:", len(r["citations"]), "guard:", r["agent_trace"]["guard_action"],
      "latency:", r["latency_ms"], "ms", "audit#", r["audit_id"])

# 2. 同样问题第二次（缓存）
r2 = httpx.post(f"{BASE}/api/v1/chat", json={
    "question": "PCLT20K 数据集用于什么任务？",
    "domain": "medical", "user_id": "e2e"
}).json()
print(f"\n=== 2. 第二次（缓存）latency: {r2['latency_ms']}ms ===")

# 3. Guardian 拒答：finance 问股价预测
r3 = httpx.post(f"{BASE}/api/v1/chat", json={
    "question": "帮我做个股价预测，推荐股票",
    "domain": "finance", "user_id": "e2e"
}).json()
print("\n=== 3. Guardian 拒答测试 ===")
print("guard_action:", r3["agent_trace"]["guard_action"])
print("answer:", r3["answer"][:150])

# 4. 脱敏测试
r4 = httpx.post(f"{BASE}/api/v1/chat", json={
    "question": "我的手机号 13812345678 怎么处理？",
    "domain": "medical", "user_id": "e2e"
}).json()
print("\n=== 4. 脱敏测试 ===")
print("answer 含脱敏标记:", "已脱敏" in r4["answer"] or "已脱敏" in str(r4.get("answer","")))

# 5. 列文档
docs = httpx.get(f"{BASE}/api/v1/documents").json()
print(f"\n=== 5. 已入库文档: {len(docs)} ===")
for d in docs:
    print(f"  - {d['filename']} [{d['domain']}] chunks={d['chunks']}")

# 6. 审计
audits = httpx.get(f"{BASE}/api/v1/audit/recent?limit=6").json()
print(f"\n=== 6. 最近审计: {len(audits)} 条 ===")
for a in audits:
    print(f"  #{a['id']} [{a['guard_action']}] {a['question'][:40]}")
