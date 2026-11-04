"""Pydantic schemas"""
from __future__ import annotations
from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)
    domain: str = "medical"
    user_id: str = "anonymous"
    top_k: int | None = None


class RetrievedChunk(BaseModel):
    content: str
    source: str
    score: float


class ChatResponse(BaseModel):
    answer: str
    citations: list[RetrievedChunk]
    agent_trace: dict
    audit_id: int
    latency_ms: int


class DocumentIngestResponse(BaseModel):
    file: str
    chunks: int
    domain: str
