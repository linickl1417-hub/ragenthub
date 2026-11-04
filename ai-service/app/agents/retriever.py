"""RetrieverAgent: vector retrieval with reflection (rewrite query if relevance is low)"""
from __future__ import annotations
from app.agents.base import BaseAgent, AgentContext
from app.core.vectorstore import query
from app.core.cache import get_cache


# Similarity threshold: if top-1 score is below this, trigger reflection loop
_RELEVANCE_THRESHOLD = 0.35

# Simple query rewrite rules for reflection loop
_QUERY_REWRITE_RULES = {
    "what": ["define", "explain", "overview"],
    "how": ["steps", "process", "method"],
    "why": ["reason", "cause", "purpose"],
    "when": ["time", "period", "deadline"],
    "where": ["location", "place", "address"],
}


class RetrieverAgent(BaseAgent):
    name = "retriever"

    def run(self, ctx: AgentContext) -> AgentContext:
        top_k = ctx.domain_cfg.get("top_k", 5)
        cache = get_cache()
        cache_key = f"ret:{ctx.domain}:{top_k}:{hash(ctx.question)}"

        cached = cache.get(cache_key)
        if cached:
            ctx.retrieved = cached
            ctx.extra["retrieved_count"] = len(cached)
            ctx.extra["cache_hit"] = True
            ctx.extra["reflection_rounds"] = 0
            return ctx

        # First round retrieval
        results = query(ctx.domain, ctx.question, top_k=top_k)
        reflection_rounds = 0
        top_score = results[0]["score"] if results else 0

        # Reflection loop: if top-1 relevance is too low, rewrite query and retry
        if top_score < _RELEVANCE_THRESHOLD and results:
            reflection_rounds = 1
            rewritten = self._rewrite_query(ctx.question)
            if rewritten and rewritten != ctx.question:
                ctx.extra["rewritten_query"] = rewritten
                retry_results = query(ctx.domain, rewritten, top_k=top_k)
                # Merge and keep best results (higher score first)
                merged = {r["content"]: r for r in results}
                for r in retry_results:
                    if r["content"] not in merged or r["score"] > merged[r["content"]]["score"]:
                        merged[r["content"]] = r
                results = sorted(merged.values(), key=lambda x: x["score"], reverse=True)[:top_k]

        ctx.retrieved = results
        ctx.extra["retrieved_count"] = len(results)
        ctx.extra["cache_hit"] = False
        ctx.extra["reflection_rounds"] = reflection_rounds
        ctx.extra["top_score"] = results[0]["score"] if results else 0

        cache.set(cache_key, ctx.retrieved, ttl=300)
        return ctx

    def _rewrite_query(self, question: str) -> str:
        """Simple query rewrite: expand with synonyms / related terms."""
        q = question.strip()
        q_lower = q.lower()

        # Rule 1: English wh-word prefix
        for wh_word, expansions in _QUERY_REWRITE_RULES.items():
            if q_lower.startswith(wh_word):
                extra = " ".join(expansions[:2])
                return f"{q} {extra}"

        # Rule 2: Chinese question patterns
        if q.startswith("什么是") or q.startswith("什么是"):
            return f"{q} 定义 解释 概述"
        if q.startswith("如何") or q.startswith("怎么"):
            return f"{q} 步骤 方法 流程"
        if q.startswith("为什么") or q.startswith("为何"):
            return f"{q} 原因 原理 目的"
        if q.startswith("什么时候") or q.startswith("何时"):
            return f"{q} 时间 周期 截止"

        # Rule 3: extract key terms (last meaningful segment)
        # Split by common punctuation, take last 2 segments
        import re
        segments = re.split(r"[，。？！、,.\?!]", q)
        segments = [s.strip() for s in segments if s.strip()]
        if len(segments) >= 2:
            key = segments[-1]
            return f"{q} {key} 相关"

        # Rule 4: fallback — just add "相关 资料"
        return f"{q} 相关 资料"
