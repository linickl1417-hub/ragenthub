"""pgvector 后端：需要 pip install psycopg[binary] pgvector sentence-transformers
初始化 SQL 见 scripts/init_pgvector.sql
"""
from __future__ import annotations
import os
import numpy as np
import psycopg
from app.config import settings


class PgVectorStore:
    def __init__(self, domain: str):
        self.domain = domain
        self.dsn = settings.database_url.replace("postgresql+psycopg://", "postgresql://") \
            if settings.database_url else \
            "postgresql://ragenthub:ragenthub@localhost:5432/ragenthub"
        self._emb = None  # lazy load

    def _embedding(self):
        if self._emb is None:
            from sentence_transformers import SentenceTransformer
            self._emb = SentenceTransformer("all-MiniLM-L6-v2")
        return self._emb

    def upsert(self, chunks: list[dict]) -> int:
        if not chunks:
            return 0
        model = self._embedding()
        texts = [c["content"] for c in chunks]
        embs = model.encode(texts).tolist()
        with psycopg.connect(self.dsn) as conn, conn.cursor() as cur:
            for c, emb in zip(chunks, embs):
                cur.execute(
                    """
                    INSERT INTO kb_chunks(domain, chunk_id, content, source, embedding)
                    VALUES (%s,%s,%s,%s,%s)
                    ON CONFLICT (domain, chunk_id) DO UPDATE
                      SET content=EXCLUDED.content, source=EXCLUDED.source, embedding=EXCLUDED.embedding
                    """,
                    (self.domain, c["id"], c["content"], c["source"], np.array(emb).tolist()),
                )
            conn.commit()
        return len(chunks)

    def query(self, question: str, top_k: int = 5) -> list[dict]:
        model = self._embedding()
        q_emb = model.encode([question]).tolist()[0]
        with psycopg.connect(self.dsn) as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT content, source, 1 - (embedding <=> %s::vector) AS score
                FROM kb_chunks
                WHERE domain = %s
                ORDER BY embedding <=> %s::vector
                LIMIT %s
                """,
                (np.array(q_emb).tolist(), self.domain, np.array(q_emb).tolist(), top_k),
            )
            rows = cur.fetchall()
        return [
            {"content": r[0], "source": r[1], "score": round(float(r[2]), 4)}
            for r in rows
        ]
