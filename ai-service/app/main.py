"""FastAPI 入口"""
from __future__ import annotations
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from app.core.db import init_db
from app.api import chat, documents

app = FastAPI(title="RAGentHub AI Service", version="0.1.0")


@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse(url="/docs")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)


@app.on_event("startup")
def _startup():
    init_db()


@app.get("/health")
def health():
    return {"status": "ok", "service": "ai-service"}


app.include_router(chat.router)
app.include_router(documents.router)
