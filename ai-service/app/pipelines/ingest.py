"""文档切分与入库"""
from __future__ import annotations
import hashlib
from pathlib import Path
from langchain_text_splitters import RecursiveCharacterTextSplitter
from app.core.vectorstore import upsert_chunks
from app.core.db import DocumentMeta, SessionLocal


def _read_text(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in (".md", ".txt"):
        return path.read_text(encoding="utf-8", errors="ignore")
    if suffix == ".pdf":
        try:
            from pypdf import PdfReader
            reader = PdfReader(str(path))
            return "\n".join((p.extract_text() or "") for p in reader.pages)
        except Exception:
            return ""
    # 其它格式先按 utf-8 文本尝试
    return path.read_text(encoding="utf-8", errors="ignore")


def ingest_file(path: Path, domain: str, chunk_size: int = 500, overlap: int = 80) -> int:
    text = _read_text(path)
    if not text.strip():
        return 0

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=overlap,
        separators=["\n\n", "\n", "。", "！", "？", ".", " ", ""],
    )
    pieces = splitter.split_text(text)

    chunks = []
    for i, piece in enumerate(pieces):
        if not piece.strip():
            continue
        uid = hashlib.md5(f"{path.name}-{i}-{piece[:32]}".encode()).hexdigest()
        chunks.append({
            "id": uid,
            "content": piece.strip(),
            "source": path.name,
        })

    n = upsert_chunks(domain, chunks)

    # 写元数据
    db = SessionLocal()
    try:
        db.merge(DocumentMeta(
            filename=path.name, domain=domain, chunk_count=n,
        ))
        db.commit()
    finally:
        db.close()

    return n


def ingest_dir(dir_path: str | Path, domain: str) -> int:
    dir_path = Path(dir_path)
    if not dir_path.exists():
        return 0
    total = 0
    for p in dir_path.rglob("*"):
        if p.is_file() and p.suffix.lower() in (".md", ".txt", ".pdf"):
            total += ingest_file(p, domain)
    return total
