"""Tests for access control, rate limiting, multi-turn context and pagination."""
import sys
import uuid
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from app.config import settings  # noqa: E402
from app.core.security import check_rate_limit  # noqa: E402
from app.agents.base import AgentContext  # noqa: E402
from app.agents.retriever import RetrieverAgent, _digest  # noqa: E402
from app.agents.generator import _build_messages  # noqa: E402
from app.api.chat import _load_context  # noqa: E402
from app.core.db import SessionLocal, ChatHistory  # noqa: E402


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c


# ---------- API key ----------

def test_api_key_required_when_configured(client, monkeypatch):
    monkeypatch.setattr(settings, "api_key", "test-secret")

    assert client.get("/api/v1/domains").status_code == 401
    assert client.get("/api/v1/domains", headers={"X-API-Key": "wrong"}).status_code == 401

    ok = client.get("/api/v1/domains", headers={"X-API-Key": "test-secret"})
    assert ok.status_code == 200

    bearer = client.get(
        "/api/v1/domains", headers={"Authorization": "Bearer test-secret"}
    )
    assert bearer.status_code == 200


def test_health_stays_open_with_auth_enabled(client, monkeypatch):
    monkeypatch.setattr(settings, "api_key", "test-secret")
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["auth"] == "enabled"


# ---------- Rate limiting ----------

def test_rate_limit_blocks_after_budget(monkeypatch):
    monkeypatch.setattr(settings, "rate_limit_per_minute", 2)
    identity = "test-key-rate-limit"

    assert check_rate_limit(identity)[0] is True
    assert check_rate_limit(identity)[0] is True
    allowed, retry_after = check_rate_limit(identity)
    assert allowed is False
    assert retry_after >= 1


def test_rate_limit_disabled_when_zero(monkeypatch):
    monkeypatch.setattr(settings, "rate_limit_per_minute", 0)
    for _ in range(5):
        assert check_rate_limit("test-key-disabled")[0] is True


def test_open_path_matching():
    from app.core.security import is_open_path

    assert is_open_path("/") is True
    assert is_open_path("/health") is True
    assert is_open_path("/docs") is True
    assert is_open_path("/web/index.html") is True
    # Regression: "/" used to prefix-match everything, silently disabling the limiter.
    assert is_open_path("/api/v1/domains") is False
    assert is_open_path("/api/v1/chat") is False


def test_rate_limit_middleware_enforced(client, monkeypatch):
    monkeypatch.setattr(settings, "rate_limit_per_minute", 2)
    # Unique identity so the assertion does not depend on budget consumed by
    # other tests running inside the same one-minute window.
    headers = {"X-API-Key": f"rl-test-{uuid.uuid4().hex[:8]}"}
    codes = [client.get("/api/v1/domains", headers=headers).status_code for _ in range(4)]

    assert codes[0] == 200
    assert codes[-1] == 429


# ---------- Multi-turn context ----------

def _seed_history(user_id: str, domain: str) -> None:
    db = SessionLocal()
    try:
        db.query(ChatHistory).filter(
            ChatHistory.user_id == user_id, ChatHistory.domain == domain
        ).delete()
        db.add_all([
            ChatHistory(user_id=user_id, domain=domain, role="user",
                        content="What is the PCLT20K dataset used for?"),
            ChatHistory(user_id=user_id, domain=domain, role="assistant",
                        content="It is used for liver pathology image segmentation."),
        ])
        db.commit()
    finally:
        db.close()


def test_load_context_returns_previous_turns(client):
    _seed_history("ctx-user", "medical")
    db = SessionLocal()
    try:
        messages = _load_context(db, "ctx-user", "medical")
    finally:
        db.close()

    assert [m["role"] for m in messages] == ["user", "assistant"]
    assert "PCLT20K" in messages[0]["content"]


def test_generator_messages_include_history():
    ctx = AgentContext(
        question="它用在哪里？",
        domain="medical",
        user_id="ctx-user",
        domain_cfg={"system_prompt": "You are a medical assistant."},
    )
    ctx.extra["history"] = [
        {"role": "user", "content": "PCLT20K 是什么？"},
        {"role": "assistant", "content": "一个数据集。"},
    ]

    messages = _build_messages(ctx, "【参考资料】…\n\n【用户问题】\n它用在哪里？")

    assert messages[0]["role"] == "system"
    assert "medical assistant" in messages[0]["content"]
    assert messages[1]["content"] == "PCLT20K 是什么？"
    assert messages[-1]["content"].startswith("【参考资料】")


# ---------- Contextualised retrieval ----------

def test_effective_query_folds_followup():
    ctx = AgentContext(
        question="它是什么",
        domain="medical",
        user_id="u",
        domain_cfg={},
    )
    ctx.extra["history"] = [{"role": "user", "content": "PCLT20K 数据集"}]
    effective = RetrieverAgent()._effective_query(ctx)
    assert "PCLT20K" in effective
    assert ctx.extra["contextualized_query"] == effective


def test_effective_query_keeps_standalone_question():
    ctx = AgentContext(
        question="What is the refund policy?",
        domain="finance",
        user_id="u",
        domain_cfg={},
    )
    ctx.extra["history"] = [{"role": "user", "content": "hello"}]
    assert RetrieverAgent()._effective_query(ctx) == ctx.question


# ---------- Cache key stability ----------

def test_cache_key_is_stable_across_case_and_spacing():
    assert _digest("  What  Is RAG? ") == _digest("what is rag?")


# ---------- Pagination ----------

def test_documents_pagination_header(client):
    r = client.get("/api/v1/documents", params={"limit": 10, "offset": 0})
    assert r.status_code == 200
    assert "X-Total-Count" in r.headers
    assert int(r.headers["X-Total-Count"]) >= len(r.json())


def test_audit_supports_offset(client):
    r = client.get("/api/v1/audit/recent", params={"limit": 5, "offset": 0})
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_history_pagination_before_id(client):
    _seed_history("page-user", "medical")
    first = client.get(
        "/api/v1/chat/history",
        params={"user_id": "page-user", "domain": "medical", "limit": 2},
    )
    assert first.status_code == 200
    rows = first.json()
    assert len(rows) == 2
    older = client.get(
        "/api/v1/chat/history",
        params={
            "user_id": "page-user",
            "domain": "medical",
            "limit": 2,
            "before_id": rows[0]["id"],
        },
    )
    assert older.status_code == 200
    assert all(r["id"] < rows[0]["id"] for r in older.json())
