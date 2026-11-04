"""GeneratorAgent：拼装 prompt 调用 LLM；默认 Mock 保证无 key 也能跑"""
from __future__ import annotations
import httpx
from app.agents.base import BaseAgent, AgentContext
from app.config import settings


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


async def _openai_generate(ctx: AgentContext, prompt: str) -> str:
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(
            f"{settings.openai_base_url}/chat/completions",
            headers={"Authorization": f"Bearer {settings.openai_api_key}"},
            json={
                "model": settings.openai_model,
                "messages": [
                    {"role": "system", "content": ctx.domain_cfg["system_prompt"]},
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.2,
            },
        )
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]


class GeneratorAgent(BaseAgent):
    name = "generator"

    async def run(self, ctx: AgentContext) -> AgentContext:
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
                ctx.answer = await _openai_generate(ctx, prompt)
                ctx.extra["llm_provider"] = "openai"
            except Exception as e:  # noqa: BLE001
                ctx.answer = _mock_generate(ctx) + f"\n\n[LLM 调用失败已回退 Mock: {e}]"
        else:
            ctx.answer = _mock_generate(ctx)
            ctx.extra["llm_provider"] = "mock"

        # 输出再脱敏一次
        from app.agents.guardian import redact
        ctx.answer = redact(ctx.answer)
        return ctx
