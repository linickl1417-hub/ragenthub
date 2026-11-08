"""Chat history API: get and manage chat history"""
from __future__ import annotations
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.core.db import get_db, ChatHistory

router = APIRouter(prefix="/api/v1/chat", tags=["history"])


@router.get("/history")
def get_chat_history(
    user_id: str = Query(...),
    domain: str = Query(...),
    limit: int = Query(50, le=200),
    db: Session = Depends(get_db),
):
    """Get chat history for a user in a specific domain"""
    rows = (
        db.query(ChatHistory)
        .filter(ChatHistory.user_id == user_id, ChatHistory.domain == domain)
        .order_by(ChatHistory.created_at.asc())
        .limit(limit)
        .all()
    )
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
