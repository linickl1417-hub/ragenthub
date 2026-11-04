"""Chroma 向量库封装：按 domain 分 collection"""
from __future__ import annotations
import chromadb
from chromadb.config import Settings as ChromaSettings
from app.config import settings

_client = None


def get_client():
    global _client
    if _client is None:
        _client = chromadb.PersistentClient(
            path=str(settings.chroma_dir),
            settings=ChromaSettings(anonymized_telemetry=False),
        )
    return _client


def get_collection(domain: str):
    # 每个 domain 一个 collection，实现物理隔离
    return get_client().get_or_create_collection(
        name=f"kb_{domain}",
        metadata={"hnsw:space": "cosine"},
    )


def upsert_chunks(domain: str, chunks: list[dict]) -> int:
    """chunks: [{"id": str, "content": str, "source": str}]"""
    if not chunks:
        return 0
    col = get_collection(domain)
    col.upsert(
        ids=[c["id"] for c in chunks],
        documents=[c["content"] for c in chunks],
        metadatas=[{"source": c["source"]} for c in chunks],
    )
    return len(chunks)


def query(domain: str, question: str, top_k: int = 5) -> list[dict]:
    col = get_collection(domain)
    res = col.query(query_texts=[question], n_results=top_k)
    out = []
    docs = res.get("documents", [[]])[0]
    metas = res.get("metadatas", [[]])[0]
    dists = res.get("distances", [[]])[0]
    for d, m, dist in zip(docs, metas, dists):
        out.append({
            "content": d,
            "source": (m or {}).get("source", "unknown"),
            "score": round(1 - dist, 4),  # cosine 距离转相似度
        })
    return out
