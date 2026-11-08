"""SQLAlchemy 引擎：根据 DB_BACKEND 切换 sqlite / mysql / postgres"""
from __future__ import annotations
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Text, DateTime, create_engine, UniqueConstraint
from sqlalchemy.orm import declarative_base, sessionmaker
from app.config import settings


def utcnow() -> datetime:
    """Timezone-aware UTC now, stored naive for cross-database compatibility."""
    return datetime.now(timezone.utc).replace(tzinfo=None)

if settings.db_backend == "sqlite":
    url = f"sqlite:///{settings.sqlite_path}"
    engine = create_engine(url, connect_args={"check_same_thread": False}, future=True)
elif settings.db_backend == "mysql":
    url = settings.database_url or "mysql+pymysql://ragenthub:ragenthub@localhost:3306/ragenthub?charset=utf8mb4"
    engine = create_engine(url, pool_pre_ping=True, future=True)
elif settings.db_backend == "postgres":
    url = settings.database_url or "postgresql+psycopg://ragenthub:ragenthub@localhost:5432/ragenthub"
    engine = create_engine(url, pool_pre_ping=True, future=True)
else:
    raise ValueError(f"未知 DB_BACKEND: {settings.db_backend}")

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
Base = declarative_base()


class DocumentMeta(Base):
    __tablename__ = "document_meta"
    __table_args__ = (UniqueConstraint("filename", "domain", name="uq_filename_domain"),)
    id = Column(Integer, primary_key=True, autoincrement=True)
    filename = Column(String(256), index=True)
    domain = Column(String(64), index=True)
    chunk_count = Column(Integer, default=0)
    uploaded_at = Column(DateTime, default=utcnow)


class AuditLog(Base):
    __tablename__ = "audit_log"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(64), index=True)
    domain = Column(String(64))
    question = Column(Text)
    answer = Column(Text)
    citations = Column(Text)
    guard_action = Column(String(32))
    latency_ms = Column(Integer)
    created_at = Column(DateTime, default=utcnow, index=True)


class DomainConfig(Base):
    """Custom domain configuration (user-created domains)"""
    __tablename__ = "domain_config"
    __table_args__ = (UniqueConstraint("domain_id", name="uq_domain_id"),)
    id = Column(Integer, primary_key=True, autoincrement=True)
    domain_id = Column(String(64), index=True)
    name = Column(String(128))
    system_prompt = Column(Text, default="")
    deny_topics = Column(Text, default="[]")  # JSON array
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)


class ChatHistory(Base):
    """Chat history per user per domain"""
    __tablename__ = "chat_history"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(64), index=True)
    domain = Column(String(64), index=True)
    role = Column(String(16))  # user / assistant
    content = Column(Text)
    citations = Column(Text, default="[]")  # JSON array
    reflection_rounds = Column(Integer, default=0)
    created_at = Column(DateTime, default=utcnow, index=True)


def init_db():
    Base.metadata.create_all(engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
