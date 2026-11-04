"""SQLite 业务库：文档元数据 + 审计日志"""
from __future__ import annotations
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from app.config import settings

engine = create_engine(
    f"sqlite:///{settings.sqlite_path}",
    connect_args={"check_same_thread": False},
    future=True,
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
Base = declarative_base()


class DocumentMeta(Base):
    __tablename__ = "document_meta"
    id = Column(Integer, primary_key=True, autoincrement=True)
    filename = Column(String(256), index=True)
    domain = Column(String(64), index=True)
    chunk_count = Column(Integer, default=0)
    uploaded_at = Column(DateTime, default=datetime.utcnow)


class AuditLog(Base):
    __tablename__ = "audit_log"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(64), index=True)
    domain = Column(String(64))
    question = Column(Text)
    answer = Column(Text)
    citations = Column(Text)          # JSON 字符串
    guard_action = Column(String(32))  # pass | denied | redacted
    latency_ms = Column(Integer)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)


def init_db():
    Base.metadata.create_all(engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
