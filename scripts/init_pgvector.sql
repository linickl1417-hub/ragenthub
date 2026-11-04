-- 初始化 pgvector 表结构
-- 在 postgres 容器内执行：psql -U ragenthub -d ragenthub -f init_pgvector.sql

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS kb_chunks (
    id          BIGSERIAL PRIMARY KEY,
    domain      TEXT NOT NULL,
    chunk_id    TEXT NOT NULL,
    content     TEXT NOT NULL,
    source      TEXT,
    embedding   vector(384),              -- all-MiniLM-L6-v2 维度
    created_at  TIMESTAMP DEFAULT NOW(),
    UNIQUE (domain, chunk_id)
);

CREATE INDEX IF NOT EXISTS kb_chunks_domain_idx ON kb_chunks(domain);
CREATE INDEX IF NOT EXISTS kb_chunks_emb_idx ON kb_chunks USING hnsw (embedding vector_cosine_ops);
