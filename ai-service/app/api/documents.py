"""Document management routes: upload / list / delete"""
from __future__ import annotations
import logging
import tempfile
from pathlib import Path

from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends
from sqlalchemy.orm import Session

from app.core.events import get_event_bus
from app.core.db import get_db, DocumentMeta
from app.core.vectorstore import delete_document_chunks
from app.models.schemas import DocumentIngestResponse

router = APIRouter(prefix="/api/v1", tags=["documents"])
logger = logging.getLogger(__name__)

ALLOWED_SUFFIXES = {".md", ".txt", ".pdf"}
MAX_FILE_BYTES = 50 * 1024 * 1024  # 50 MB


@router.post("/documents", response_model=DocumentIngestResponse)
async def upload_document(
    file: UploadFile = File(...),
    domain: str = Form(...),
):
    """Upload a document and ingest it into the vector store."""
    filename = Path(file.filename or "").name
    if not filename:
        raise HTTPException(status_code=400, detail="Filename is required")

    suffix = Path(filename).suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{suffix}'. Allowed: md, txt, pdf",
        )

    payload = await file.read()
    if not payload:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")
    if len(payload) > MAX_FILE_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File exceeds {MAX_FILE_BYTES // (1024 * 1024)} MB limit",
        )

    tmp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(payload)
            tmp_path = Path(tmp.name)
        # ingest_file uses path.name as the chunk source, so keep the original name
        named_path = tmp_path.with_name(filename)
        tmp_path.replace(named_path)
        tmp_path = named_path

        result = get_event_bus().publish_document_uploaded(str(tmp_path), domain)
        chunks = result.get("chunks", 0)
        logger.info("Ingested document %s (domain=%s, chunks=%d)", filename, domain, chunks)
        return DocumentIngestResponse(file=filename, chunks=chunks, domain=domain)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Failed to ingest document %s", filename)
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {exc}") from exc
    finally:
        if tmp_path and tmp_path.exists():
            tmp_path.unlink(missing_ok=True)


@router.get("/documents")
def list_documents(db: Session = Depends(get_db), domain: str | None = None):
    """List ingested documents, optionally filtered by domain."""
    q = db.query(DocumentMeta)
    if domain:
        q = q.filter(DocumentMeta.domain == domain)
    rows = q.order_by(DocumentMeta.uploaded_at.desc()).all()
    return [
        {
            "id": r.id,
            "filename": r.filename,
            "domain": r.domain,
            "chunk_count": r.chunk_count,
            "uploaded_at": r.uploaded_at.isoformat(),
        }
        for r in rows
    ]


@router.delete("/documents/{filename}")
def delete_document(
    filename: str,
    domain: str,
    db: Session = Depends(get_db),
):
    """Delete a document from both the vector store and the metadata table."""
    meta = (
        db.query(DocumentMeta)
        .filter(DocumentMeta.filename == filename, DocumentMeta.domain == domain)
        .first()
    )
    if not meta:
        raise HTTPException(status_code=404, detail=f"Document '{filename}' not found in domain '{domain}'")

    removed = delete_document_chunks(domain, filename)
    db.delete(meta)
    db.commit()
    logger.info("Deleted document %s (domain=%s, chunks=%d)", filename, domain, removed)
    return {"filename": filename, "domain": domain, "chunks_deleted": removed}
