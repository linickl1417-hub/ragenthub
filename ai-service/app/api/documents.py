"""文档管理路由：上传 + 列表；上传后通过事件总线触发切分"""
from __future__ import annotations
import tempfile
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends
from sqlalchemy.orm import Session
from app.core.events import get_event_bus
from app.core.db import get_db, DocumentMeta
from app.models.schemas import DocumentIngestResponse

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

    bus = get_event_bus()
    result = bus.publish_document_uploaded(str(tmp_path), domain)
    return DocumentIngestResponse(
        file=file.filename or "unknown",
        chunks=result.get("chunks", 0),
        domain=domain,
    )


@router.get("/documents")
def list_documents(db: Session = Depends(get_db), domain: str | None = None):
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
