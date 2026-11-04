"""Chat route: orchestrates 4-agent pipeline"""
from __future__ import annotations
import time
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.config import load_domain_config
from app.core.db import get_db, AuditLog
from app.models.schemas import ChatRequest, ChatResponse, RetrievedChunk
from app.agents.base import AgentContext
from app.agents.retriever import RetrieverAgent
from app.agents.guardian import GuardianAgent
from app.agents.generator import GeneratorAgent
from app.agents.auditor import AuditorAgent

router = APIRouter(prefix="/api/v1", tags=["chat"])


@router.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest, db: Session = Depends(get_db)):
    t0 = time.time()
    cfg = load_domain_config(req.domain)
    ctx = AgentContext(
        question=req.question, domain=req.domain,
        user_id=req.user_id, domain_cfg=cfg,
    )

    ctx = RetrieverAgent().run(ctx)
    ctx = GuardianAgent().run(ctx)
    ctx = await GeneratorAgent().run(ctx)

    latency = int((time.time() - t0) * 1000)
    ctx.extra["latency_ms"] = latency
    ctx = AuditorAgent(db).run(ctx)

    return ChatResponse(
        answer=ctx.answer,
        citations=[RetrievedChunk(**c) for c in ctx.retrieved],
        agent_trace={
            "guard_action": ctx.guard_action,
            "retrieved": ctx.extra.get("retrieved_count", 0),
            "llm_provider": ctx.extra.get("llm_provider", "n/a"),
            "reflection_rounds": ctx.extra.get("reflection_rounds", 0),
            "rewritten_query": ctx.extra.get("rewritten_query", None),
        },
        audit_id=ctx.extra.get("audit_id", 0),
        latency_ms=latency,
    )


@router.get("/audit/recent")
def recent_audits(db: Session = Depends(get_db), limit: int = 20):
    """Recent audit logs (Python-side view)"""
    rows = (
        db.query(AuditLog)
        .order_by(AuditLog.created_at.desc())
        .limit(min(limit, 100))
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
