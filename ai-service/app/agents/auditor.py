"""AuditorAgent：落审计日志"""
from __future__ import annotations
import json
from sqlalchemy.orm import Session
from app.agents.base import BaseAgent, AgentContext
from app.core.db import AuditLog


class AuditorAgent(BaseAgent):
    name = "auditor"

    def __init__(self, db: Session):
        self.db = db

    def run(self, ctx: AgentContext) -> AgentContext:
        rec = AuditLog(
            user_id=ctx.user_id,
            domain=ctx.domain,
            question=ctx.question,
            answer=ctx.answer,
            citations=json.dumps(
                [{"source": c["source"], "score": c["score"]} for c in ctx.retrieved],
                ensure_ascii=False,
            ),
            guard_action=ctx.guard_action,
            latency_ms=ctx.extra.get("latency_ms", 0),
        )
        self.db.add(rec)
        self.db.commit()
        self.db.refresh(rec)
        ctx.extra["audit_id"] = rec.id
        return ctx
