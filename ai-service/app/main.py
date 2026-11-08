"""FastAPI entry point"""
from __future__ import annotations
import logging
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from app.config import settings
from app.core.db import init_db, engine
from app.core.security import caller_identity, check_rate_limit, is_open_path
from app.api import chat, documents, domains, history

# ---------- Logging ----------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger("ragenthub")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    logger.info(
        "ai-service started | db=%s vector=%s cache=%s llm=%s",
        settings.db_backend, settings.vector_backend,
        settings.cache_backend, settings.llm_provider,
    )
    yield
    logger.info("ai-service shutting down")


app = FastAPI(
    title="RAGentHub AI Service",
    version="0.1.0",
    description="Enterprise multi-agent RAG platform — retrieval, guardrails, generation, audit.",
    lifespan=lifespan,
)


# ---------- Middleware ----------
# Registration order matters: the last added middleware is the outermost one.
# CORS is registered last so that rate-limited (429) responses still carry the
# CORS headers a browser client needs.
@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    if not is_open_path(request.url.path):
        allowed, retry_after = check_rate_limit(caller_identity(request))
        if not allowed:
            logger.warning(
                "Rate limit exceeded for %s on %s", caller_identity(request), request.url.path
            )
            return JSONResponse(
                status_code=429,
                content={
                    "error": "rate_limit_exceeded",
                    "detail": f"Too many requests, retry in {retry_after}s",
                    "path": request.url.path,
                },
                headers={"Retry-After": str(retry_after)},
            )
    return await call_next(request)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Retry-After"],
)


# ---------- Unified error responses ----------
@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={
            "error": "validation_error",
            "detail": exc.errors(),
            "path": request.url.path,
        },
    )


@app.exception_handler(Exception)
async def unhandled_error_handler(request: Request, exc: Exception):
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={
            "error": "internal_error",
            "detail": "Internal server error",
            "path": request.url.path,
        },
    )


# ---------- Static UI ----------
_web_dir = Path("/app/web")
if not _web_dir.exists():
    _web_dir = Path(__file__).resolve().parents[2] / "web"
if _web_dir.exists():
    app.mount("/web", StaticFiles(directory=str(_web_dir), html=True), name="web")


@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse(url="/docs")


@app.get("/health")
def health():
    """Liveness + readiness probe: verifies DB connectivity."""
    db_ok = True
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception:  # noqa: BLE001
        db_ok = False
        logger.warning("Health check: database unreachable")

    status = "ok" if db_ok else "degraded"
    return {
        "status": status,
        "service": "ai-service",
        "database": "up" if db_ok else "down",
        "auth": "enabled" if settings.api_key else "disabled",
        "llm_provider": settings.llm_provider,
    }


# ---------- Routers ----------
app.include_router(chat.router)
app.include_router(documents.router)
app.include_router(domains.router)
app.include_router(history.router)
