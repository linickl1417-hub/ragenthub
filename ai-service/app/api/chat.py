"""Chat route: orchestrates 4-agent pipeline"""
from __future__ import annotations
import json
import time
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.config import load_domain_config, settings
from app.core.db import get_db, AuditLog, ChatHistory
from app.core.security import require_api_key
from app.models.schemas import ChatRequest, ChatResponse, RetrievedChunk
from app.agents.base import AgentContext
from app.agents.retriever import RetrieverAgent
from app.agents.guardian import GuardianAgent
from app.agents.generator import GeneratorAgent
from app.agents.auditor import AuditorAgent

router = APIRouter(prefix="/api/v1", tags=["chat"], dependencies=[Depends(require_api_key)])


@router.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest, db: Session = Depends(get_db)):
    t0 = time.time()
    cfg = load_domain_config(req.domain)

    # Multi-turn context: last N turns of this user in this domain.
    history = _load_context(db, req.user_id, req.domain)
    ctx = AgentContext(
        question=req.question, domain=req.domain,
        user_id=req.user_id, domain_cfg=cfg,
    )
    ctx.extra["history"] = history

    ctx = RetrieverAgent().run(ctx)
    ctx = GuardianAgent().run(ctx)
    ctx = await GeneratorAgent().run(ctx)

    latency = int((time.time() - t0) * 1000)
    ctx.extra["latency_ms"] = latency
    ctx = AuditorAgent(db).run(ctx)

    # Save chat history (user question + assistant answer)
    user_msg = ChatHistory(
        user_id=req.user_id, domain=req.domain,
        role="user", content=req.question,
    )
    assistant_msg = ChatHistory(
        user_id=req.user_id, domain=req.domain,
        role="assistant", content=ctx.answer,
        citations=json.dumps([{"source": c["source"], "score": c["score"]} for c in ctx.retrieved]),
        reflection_rounds=ctx.extra.get("reflection_rounds", 0),
    )
    db.add(user_msg)
    db.add(assistant_msg)
    db.commit()

    return ChatResponse(
        answer=ctx.answer,
        citations=[RetrievedChunk(**c) for c in ctx.retrieved],
        agent_trace={
            "guard_action": ctx.guard_action,
            "retrieved": ctx.extra.get("retrieved_count", 0),
            "llm_provider": ctx.extra.get("llm_provider", "n/a"),
            "reflection_rounds": ctx.extra.get("reflection_rounds", 0),
            "rewritten_query": ctx.extra.get("rewritten_query", None),
            "top_score": ctx.extra.get("top_score", 0),
            "context_turns": ctx.extra.get("context_turns", 0),
            "contextualized_query": ctx.extra.get("contextualized_query", None),
            "cache_hit": ctx.extra.get("cache_hit", False),
        },
        audit_id=ctx.extra.get("audit_id", 0),
        latency_ms=latency,
    )


def _load_context(db: Session, user_id: str, domain: str) -> list[dict]:
    """Load the trailing conversation turns for prompt context (oldest first)."""
    turns = settings.chat_context_turns
    if turns <= 0:
        return []

    rows = (
        db.query(ChatHistory)
        .filter(ChatHistory.user_id == user_id, ChatHistory.domain == domain)
        .order_by(ChatHistory.id.desc())
        .limit(turns * 2)
        .all()
    )
    if not rows:
        return []

    limit = settings.chat_context_max_chars
    messages = []
    for r in reversed(rows):
        content = (r.content or "").strip()
        if not content:
            continue
        if len(content) > limit:
            content = content[:limit] + "…"
        messages.append({"role": r.role, "content": content})
    return messages


@router.get("/audit/recent")
def recent_audits(db: Session = Depends(get_db), limit: int = 20, offset: int = 0):
    """Recent audit logs (Python-side view), newest first."""
    rows = (
        db.query(AuditLog)
        .order_by(AuditLog.created_at.desc())
        .offset(max(offset, 0))
        .limit(min(max(limit, 1), 100))
        .all()
    )
    return [
        {
            "id": r.id,
            "user_id": r.user_id,
            "domain": r.domain,
            "question": r.question,
            "guard_action": r.guard_action,
            "latency_ms": r.latency_ms,
            "created_at": r.created_at.isoformat(),
        }
        for r in rows
    ]
