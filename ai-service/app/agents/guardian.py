"""GuardianAgent：敏感词 / 越权 / 拒答 + 手机号身份证脱敏"""
from __future__ import annotations
import re
from app.agents.base import BaseAgent, AgentContext

# 简单脱敏正则
_PHONE = re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)")
_IDCARD = re.compile(r"(?<!\d)\d{17}[\dXx](?!\d)")
_BANKCARD = re.compile(r"(?<!\d)\d{16,19}(?!\d)")


def redact(text: str) -> str:
    text = _PHONE.sub("[手机号已脱敏]", text)
    text = _IDCARD.sub("[身份证已脱敏]", text)
    text = _BANKCARD.sub("[银行卡号已脱敏]", text)
    return text


class GuardianAgent(BaseAgent):
    name = "guardian"

    def run(self, ctx: AgentContext) -> AgentContext:
        # 1) 输入脱敏
        ctx.question = redact(ctx.question)

        # 2) 拒答主题命中
        deny = ctx.domain_cfg.get("deny_topics", []) or []
        for kw in deny:
            if kw and kw in ctx.question:
                ctx.guard_action = "denied"
                ctx.answer = f"抱歉，该问题涉及{kw}，按本业务规则无法回答。"
                return ctx

        ctx.guard_action = "pass"
        return ctx
