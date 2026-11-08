"""API contract tests: domains CRUD, documents listing, chat history, reflection rewrite."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from app.core.db import SessionLocal, DomainConfig, ChatHistory  # noqa: E402
from app.agents.retriever import RetrieverAgent  # noqa: E402


@pytest.fixture()
def client():
    # Using the client as a context manager triggers the lifespan startup,
    # which creates the schema before the first request is served.
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def cleanup_custom_domain():
    """Ensure the test domain row does not leak into the local database."""
    created = []

    def _register(domain_id: str):
        created.append(domain_id)

    yield _register

    db = SessionLocal()
    try:
        for did in created:
            db.query(DomainConfig).filter(DomainConfig.domain_id == did).delete()
        db.commit()
    finally:
        db.close()


def test_list_domains_includes_builtin(client):
    r = client.get("/api/v1/domains")
    assert r.status_code == 200
    ids = {d["id"] for d in r.json()}
    assert {"medical", "finance", "gov"} <= ids


def test_create_domain_rejects_invalid_id(client):
    r = client.post("/api/v1/domains", json={"id": "1bad id!", "name": "Bad"})
    assert r.status_code == 400
    assert "must start with a letter" in r.json()["detail"]


def test_create_domain_rejects_builtin_id(client):
    r = client.post("/api/v1/domains", json={"id": "medical", "name": "Duplicate"})
    assert r.status_code == 409


def test_domain_lifecycle(client, cleanup_custom_domain):
    payload = {
        "id": "test-legal",
        "name": "Test Legal",
        "system_prompt": "You are a legal assistant.",
        "deny_topics": ["contract"],
    }

    created = client.post("/api/v1/domains", json=payload)
    assert created.status_code == 201
    cleanup_custom_domain("test-legal")

    detail = client.get("/api/v1/domains/test-legal")
    assert detail.status_code == 200
    assert detail.json()["deny_topics"] == ["contract"]

    dup = client.post("/api/v1/domains", json=payload)
    assert dup.status_code == 409

    updated = client.put("/api/v1/domains/test-legal", json={"name": "Legal v2"})
    assert updated.status_code == 200
    assert updated.json()["name"] == "Legal v2"

    removed = client.delete("/api/v1/domains/test-legal")
    assert removed.status_code == 200
    assert removed.json()["status"] == "deleted"


def test_documents_list_shape(client):
    r = client.get("/api/v1/documents")
    assert r.status_code == 200
    rows = r.json()
    assert isinstance(rows, list)
    for row in rows:
        assert {"id", "filename", "domain", "chunk_count", "uploaded_at"} <= set(row)


def test_chat_history_empty_for_new_user(client):
    r = client.get(
        "/api/v1/chat/history",
        params={"user_id": "pytest-no-such-user", "domain": "medical"},
    )
    assert r.status_code == 200
    assert r.json() == []


def test_chat_history_clear(client):
    db = SessionLocal()
    try:
        db.add(ChatHistory(user_id="pytest-clear", domain="medical", role="user", content="hi"))
        db.commit()
    finally:
        db.close()

    r = client.delete(
        "/api/v1/chat/history",
        params={"user_id": "pytest-clear", "domain": "medical"},
    )
    assert r.status_code == 200
    assert r.json()["deleted"] >= 1


def test_reflection_rewrite_english():
    query = RetrieverAgent()._rewrite_query("What is the PCLT20K dataset?")
    assert query != "What is the PCLT20K dataset?"
    assert "define" in query or "explain" in query


def test_reflection_rewrite_chinese():
    query = RetrieverAgent()._rewrite_query("今天吃什么外卖？")
    assert "相关" in query or "资料" in query
