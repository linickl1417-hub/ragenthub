"""RetrieverAgent: vector retrieval with reflection (rewrite query if relevance is low)"""
from __future__ import annotations

import hashlib
import re

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

# Pronoun / discourse markers that signal a follow-up that cannot be retrieved
# on its own — the previous user turn has to be folded into the query.
_FOLLOWUP_PREFIXES = (
    "它", "他", "她", "这", "那", "该", "其", "此", "上述", "前面", "上面",
    "it ", "this ", "that ", "these ", "those ", "they ", "and ", "what about ", "how about ",
)

_MAX_FOLLOWUP_CHARS = 12


def _digest(text: str) -> str:
    """Stable cache key across processes and restarts (hash() is salted)."""
    normalized = re.sub(r"\s+", " ", text.strip().lower())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]


class RetrieverAgent(BaseAgent):
    name = "retriever"

    def run(self, ctx: AgentContext) -> AgentContext:
        top_k = ctx.domain_cfg.get("top_k", 5)
        search_text = self._effective_query(ctx)
        cache = get_cache()
        cache_key = f"ret:{ctx.domain}:{top_k}:{_digest(search_text)}"

        cached = cache.get(cache_key)
        if cached:
            payload = cached if isinstance(cached, dict) else {"retrieved": cached}
            ctx.retrieved = payload.get("retrieved", [])
            ctx.extra["retrieved_count"] = len(ctx.retrieved)
            ctx.extra["cache_hit"] = True
            ctx.extra["reflection_rounds"] = payload.get("reflection_rounds", 0)
            ctx.extra["rewritten_query"] = payload.get("rewritten_query")
            ctx.extra["top_score"] = payload.get("top_score", 0)
            return ctx

        # First round retrieval
        results = query(ctx.domain, search_text, top_k=top_k)
        reflection_rounds = 0
        rewritten = None
        top_score = results[0]["score"] if results else 0

        # Reflection loop: if top-1 relevance is too low, rewrite query and retry
        if top_score < _RELEVANCE_THRESHOLD and results:
            reflection_rounds = 1
            candidate = self._rewrite_query(search_text)
            if candidate and candidate != search_text:
                rewritten = candidate
                ctx.extra["rewritten_query"] = rewritten
                retry_results = query(ctx.domain, rewritten, top_k=top_k)
                # Merge and keep best results (higher score first)
                merged = {r["content"]: r for r in results}
                for r in retry_results:
                    if r["content"] not in merged or r["score"] > merged[r["content"]]["score"]:
                        merged[r["content"]] = r
                results = sorted(merged.values(), key=lambda x: x["score"], reverse=True)[:top_k]

        final_top_score = results[0]["score"] if results else 0
        ctx.retrieved = results
        ctx.extra["retrieved_count"] = len(results)
        ctx.extra["cache_hit"] = False
        ctx.extra["reflection_rounds"] = reflection_rounds
        ctx.extra["top_score"] = final_top_score

        cache.set(
            cache_key,
            {
                "retrieved": results,
                "reflection_rounds": reflection_rounds,
                "rewritten_query": rewritten,
                "top_score": final_top_score,
            },
            ttl=300,
        )
        return ctx

    def _effective_query(self, ctx: AgentContext) -> str:
        """Fold the previous question into a short pronoun-based follow-up."""
        question = ctx.question.strip()
        history = ctx.extra.get("history") or []
        if not history or len(question) > _MAX_FOLLOWUP_CHARS:
            return ctx.question

        if not question.lower().startswith(_FOLLOWUP_PREFIXES):
            return ctx.question

        last_user = next(
            (m.get("content") for m in reversed(history) if m.get("role") == "user"),
            "",
        )
        last_user = (last_user or "").strip()
        if not last_user:
            return ctx.question

        combined = f"{last_user} {question}"
        ctx.extra["contextualized_query"] = combined
        return combined

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
        if q.startswith("什么是"):
            return f"{q} 定义 解释 概述"
        if q.startswith("如何") or q.startswith("怎么"):
            return f"{q} 步骤 方法 流程"
        if q.startswith("为什么") or q.startswith("为何"):
            return f"{q} 原因 原理 目的"
        if q.startswith("什么时候") or q.startswith("何时"):
            return f"{q} 时间 周期 截止"

        # Rule 3: extract key terms (last meaningful segment)
        segments = re.split(r"[，。？！、,.\?!]", q)
        segments = [s.strip() for s in segments if s.strip()]
        if len(segments) >= 2:
            key = segments[-1]
            return f"{q} {key} 相关"

        # Rule 4: fallback — just add "相关 资料"
        return f"{q} 相关 资料"
