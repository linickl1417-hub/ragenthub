"""向量库抽象：Chroma（默认） / pgvector（可选）"""
from __future__ import annotations
from app.config import settings


def get_collection(domain: str):
    if settings.vector_backend == "pgvector":
        from app.core.vectorstore_pg import PgVectorStore
        return PgVectorStore(domain)
    return _ChromaAdapter(domain)


# ---------- Chroma 默认实现 ----------
class _ChromaAdapter:
    def __init__(self, domain: str):
        import chromadb
        from chromadb.config import Settings as ChromaSettings
        self._client = chromadb.PersistentClient(
            path=str(settings.chroma_dir),
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        self._col = self._client.get_or_create_collection(
            name=f"kb_{domain}", metadata={"hnsw:space": "cosine"},
        )

    def upsert(self, chunks: list[dict]) -> int:
        if not chunks:
            return 0
        self._col.upsert(
            ids=[c["id"] for c in chunks],
            documents=[c["content"] for c in chunks],
            metadatas=[{"source": c["source"]} for c in chunks],
        )
        return len(chunks)

    def query(self, question: str, top_k: int = 5) -> list[dict]:
        res = self._col.query(query_texts=[question], n_results=top_k)
        out = []
        docs = res.get("documents", [[]])[0]
        metas = res.get("metadatas", [[]])[0]
        dists = res.get("distances", [[]])[0]
        for d, m, dist in zip(docs, metas, dists):
            out.append({
                "content": d,
                "source": (m or {}).get("source", "unknown"),
                "score": round(1 - dist, 4),
            })
        return out

    def delete_by_source(self, source: str) -> int:
        """Delete all chunks belonging to one document (matched by source filename)."""
        existing = self._col.get(where={"source": source})
        ids = existing.get("ids", [])
        if not ids:
            return 0
        self._col.delete(ids=ids)
        return len(ids)

    def count(self) -> int:
        return self._col.count()


# ---------- 对外函数 ----------
def upsert_chunks(domain: str, chunks: list[dict]) -> int:
    return get_collection(domain).upsert(chunks)


def query(domain: str, question: str, top_k: int = 5) -> list[dict]:
    return get_collection(domain).query(question, top_k=top_k)


def delete_document_chunks(domain: str, source: str) -> int:
    """Remove every chunk of a document from the vector store."""
    return get_collection(domain).delete_by_source(source)


def count_chunks(domain: str) -> int:
    return get_collection(domain).count()
