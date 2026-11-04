"""RetrieverAgent：向量检索 top-k"""
from __future__ import annotations
from app.agents.base import BaseAgent, AgentContext
from app.core.vectorstore import query


class RetrieverAgent(BaseAgent):
    name = "retriever"

    def run(self, ctx: AgentContext) -> AgentContext:
        top_k = ctx.domain_cfg.get("top_k", 5)
        ctx.retrieved = query(ctx.domain, ctx.question, top_k=top_k)
        ctx.extra["retrieved_count"] = len(ctx.retrieved)
        return ctx
