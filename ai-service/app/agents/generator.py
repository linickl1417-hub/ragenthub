"""GeneratorAgent：拼装 prompt 调用 LLM；默认 Mock 保证无 key 也能跑"""
from __future__ import annotations
import httpx
from app.agents.base import BaseAgent, AgentContext
from app.config import settings

SYSTEM_SUFFIX = (
    "\n\n回答规则：\n"
    "1. 只依据【参考资料】作答，资料不足时明确说明「资料中未提及」，不要编造。\n"
    "2. 结合【对话历史】理解省略与指代（例如「它」「这个」指的是上一轮的对象）。\n"
    "3. 答案简洁，中文提问用中文作答，英文提问用英文作答。"
)


def _mock_generate(ctx: AgentContext) -> str:
    """无 LLM key 时的兜底：直接基于检索片段组装答案，便于本地演示"""
    if not ctx.retrieved:
        return "根据现有资料无法确定答案，请联系人工客服或补充更多资料。"
    refs = "\n".join(
        f"[{i+1}] (来源: {c['source']})\n{c['content']}"
        for i, c in enumerate(ctx.retrieved)
    )
    return (
        f"【基于 {len(ctx.retrieved)} 条检索结果的回答（Mock 模式）】\n"
        f"问题：{ctx.question}\n\n"
        f"参考资料：\n{refs}\n\n"
        f"（配置 OPENAI_API_KEY 后将切换为真实 LLM 生成）"
    )


def _build_messages(ctx: AgentContext, prompt: str) -> list[dict]:
    """system + conversation history + current grounded question."""
    messages = [
        {"role": "system", "content": (ctx.domain_cfg.get("system_prompt") or "") + SYSTEM_SUFFIX}
    ]
    for m in ctx.extra.get("history") or []:
        if m.get("role") in ("user", "assistant") and m.get("content"):
            messages.append({"role": m["role"], "content": m["content"]})
    messages.append({"role": "user", "content": prompt})
    return messages


async def _openai_generate(messages: list[dict]) -> str:
    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(
            f"{settings.openai_base_url}/chat/completions",
            headers={"Authorization": f"Bearer {settings.openai_api_key}"},
            json={
                "model": settings.openai_model,
                "messages": messages,
                "temperature": 0.2,
            },
        )
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]


class GeneratorAgent(BaseAgent):
    name = "generator"

    async def run(self, ctx: AgentContext) -> AgentContext:
        history = ctx.extra.get("history") or []
        ctx.extra["context_turns"] = sum(1 for m in history if m.get("role") == "user")

        if ctx.guard_action == "denied":
            return ctx  # 已被拒答，不进生成

        if not ctx.retrieved:
            ctx.answer = "未检索到相关资料，建议补充文档后再问。"
            return ctx

        context = "\n\n".join(
            f"[片段{i+1}|来源:{c['source']}]\n{c['content']}"
            for i, c in enumerate(ctx.retrieved)
        )
        prompt = f"【参考资料】\n{context}\n\n【用户问题】\n{ctx.question}"

        if settings.llm_provider == "openai" and settings.openai_api_key:
            try:
                ctx.answer = await _openai_generate(_build_messages(ctx, prompt))
                ctx.extra["llm_provider"] = "openai"
            except Exception as e:  # noqa: BLE001
                ctx.answer = _mock_generate(ctx) + f"\n\n[LLM 调用失败已回退 Mock: {e}]"
                ctx.extra["llm_provider"] = "mock(fallback)"
        else:
            ctx.answer = _mock_generate(ctx)
            ctx.extra["llm_provider"] = "mock"

        # 输出再脱敏一次
        from app.agents.guardian import redact
        ctx.answer = redact(ctx.answer)
        return ctx
