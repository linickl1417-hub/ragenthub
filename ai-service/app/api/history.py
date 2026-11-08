"""Chat history API: get and manage chat history"""
from __future__ import annotations
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.core.db import get_db, ChatHistory
from app.core.security import require_api_key

router = APIRouter(
    prefix="/api/v1/chat",
    tags=["history"],
    dependencies=[Depends(require_api_key)],
)


@router.get("/history")
def get_chat_history(
    user_id: str = Query(...),
    domain: str = Query(...),
    limit: int = Query(50, ge=1, le=200),
    before_id: int | None = Query(None, description="Return messages older than this id"),
    db: Session = Depends(get_db),
):
    """Most recent messages for a user in a domain, returned in chronological order.

    Pass ``before_id`` with the oldest id of the previous page to load older
    messages (backwards pagination).
    """
    q = db.query(ChatHistory).filter(
        ChatHistory.user_id == user_id,
        ChatHistory.domain == domain,
    )
    if before_id is not None:
        q = q.filter(ChatHistory.id < before_id)

    rows = q.order_by(ChatHistory.id.desc()).limit(limit).all()
    rows.reverse()  # oldest first for display

    return [
        {
            "id": r.id,
            "role": r.role,
            "content": r.content,
            "citations": r.citations,
            "reflection_rounds": r.reflection_rounds,
            "created_at": r.created_at.isoformat(),
        }
        for r in rows
    ]


@router.delete("/history")
def clear_chat_history(
    user_id: str = Query(...),
    domain: str = Query(...),
    db: Session = Depends(get_db),
):
    """Clear chat history for a user in a specific domain"""
    deleted = (
        db.query(ChatHistory)
        .filter(ChatHistory.user_id == user_id, ChatHistory.domain == domain)
        .delete()
    )
    db.commit()
    return {"deleted": deleted}
