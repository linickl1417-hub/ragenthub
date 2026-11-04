"""文档管理路由：上传 + 列表"""
from __future__ import annotations
import tempfile
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends
from sqlalchemy.orm import Session
from app.pipelines.ingest import ingest_file
from app.models.schemas import DocumentIngestResponse
from app.core.db import get_db, DocumentMeta

router = APIRouter(prefix="/api/v1", tags=["documents"])


@router.post("/documents", response_model=DocumentIngestResponse)
async def upload_document(
    file: UploadFile = File(...),
    domain: str = Form(...),
):
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in (".md", ".txt", ".pdf"):
        raise HTTPException(400, f"暂不支持 {suffix}，仅支持 md/txt/pdf")

    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(await file.read())
        tmp_path = Path(tmp.name)

    n = ingest_file(tmp_path, domain)
    return DocumentIngestResponse(file=file.filename or "unknown", chunks=n, domain=domain)


@router.get("/documents")
def list_documents(db: Session = Depends(get_db), domain: str | None = None):
    """列出已入库的文档元数据"""
    q = db.query(DocumentMeta)
    if domain:
        q = q.filter(DocumentMeta.domain == domain)
    rows = q.order_by(DocumentMeta.uploaded_at.desc()).all()
    return [
        {
            "filename": r.filename,
            "domain": r.domain,
            "chunks": r.chunk_count,
            "uploaded_at": r.uploaded_at.isoformat(),
        }
        for r in rows
    ]
