"""smoke test：不依赖真实向量库 / LLM，直接测核心逻辑"""
import sys
from pathlib import Path

# 让 tests 能 import app
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.agents.guardian import GuardianAgent, redact
from app.agents.base import AgentContext


def _ctx(question: str, domain_cfg: dict) -> AgentContext:
    return AgentContext(
        question=question,
        domain="finance",
        user_id="tester",
        domain_cfg=domain_cfg,
    )


def test_redact_phone_id_bankcard():
    text = "联系我 13812345678，身份证 110101199001011234，卡号 6222020200112233445"
    out = redact(text)
    assert "13812345678" not in out
    assert "110101199001011234" not in out
    assert "6222020200112233445" not in out
    assert "已脱敏" in out


def test_guardian_deny_topic():
    cfg = {"deny_topics": ["股价预测", "内幕消息"], "top_k": 3}
    ctx = GuardianAgent().run(_ctx("帮我做个股价预测", cfg))
    assert ctx.guard_action == "denied"
    assert "无法回答" in ctx.answer


def test_guardian_pass_normal_question():
    cfg = {"deny_topics": ["股价预测"], "top_k": 3}
    ctx = GuardianAgent().run(_ctx("定期存款起存金额是多少", cfg))
    assert ctx.guard_action == "pass"


def test_health_endpoint():
    from fastapi.testclient import TestClient
    from app.main import app
    client = TestClient(app)
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
