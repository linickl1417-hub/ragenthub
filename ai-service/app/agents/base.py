"""Agent 基类"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any


@dataclass
class AgentContext:
    question: str
    domain: str
    user_id: str
    domain_cfg: dict
    retrieved: list[dict] = field(default_factory=list)
    answer: str = ""
    guard_action: str = "pass"
    extra: dict[str, Any] = field(default_factory=dict)


class BaseAgent:
    name: str = "base"

    def run(self, ctx: AgentContext) -> AgentContext:
        raise NotImplementedError
