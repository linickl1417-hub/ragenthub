"""Domain management API: list / create / update / delete custom domains (DB-backed)"""
from __future__ import annotations
import json
import re
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from app.core.db import get_db, DomainConfig
from app.core.security import require_api_key

router = APIRouter(
    prefix="/api/v1/domains",
    tags=["domains"],
    dependencies=[Depends(require_api_key)],
)

_DOMAIN_ID_PATTERN = re.compile(r"^[a-z][a-z0-9_-]{1,63}$")


class DomainCreate(BaseModel):
    id: str = Field(..., min_length=2, max_length=64)
    name: str = Field(..., min_length=1, max_length=128)
    system_prompt: str = "You are a helpful assistant."
    deny_topics: list[str] = Field(default_factory=list)


class DomainUpdate(BaseModel):
    name: str | None = None
    system_prompt: str | None = None
    deny_topics: list[str] | None = None


def _load_builtin_domains() -> dict:
    import yaml
    from app.config import CONFIG_PATH

    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    return cfg.get("domains", {}) or {}


def _serialize(d: DomainConfig) -> dict:
    return {
        "id": d.domain_id,
        "name": d.name,
        "system_prompt": d.system_prompt,
        "deny_topics": json.loads(d.deny_topics or "[]"),
        "is_custom": True,
        "created_at": d.created_at.isoformat() if d.created_at else None,
        "updated_at": d.updated_at.isoformat() if d.updated_at else None,
    }


@router.get("")
def list_domains(db: Session = Depends(get_db)):
    """List all available domains (built-in from YAML + custom from DB)."""
    result = []
    for did, d in _load_builtin_domains().items():
        result.append({
            "id": did,
            "name": d.get("label", did),
            "is_custom": False,
        })

    for d in db.query(DomainConfig).order_by(DomainConfig.created_at.asc()).all():
        result.append({"id": d.domain_id, "name": d.name, "is_custom": True})

    return result


@router.post("", status_code=201)
def create_domain(body: DomainCreate, db: Session = Depends(get_db)):
    """Create a new custom domain."""
    did = body.id.strip().lower()
    if not _DOMAIN_ID_PATTERN.match(did):
        raise HTTPException(
            status_code=400,
            detail="Domain ID must start with a letter and contain only a-z, 0-9, _ or - (2-64 chars)",
        )

    if did in _load_builtin_domains():
        raise HTTPException(status_code=409, detail=f"'{did}' is a built-in domain and cannot be redefined")

    if db.query(DomainConfig).filter(DomainConfig.domain_id == did).first():
        raise HTTPException(status_code=409, detail=f"Domain '{did}' already exists")

    domain = DomainConfig(
        domain_id=did,
        name=body.name.strip(),
        system_prompt=body.system_prompt.strip(),
        deny_topics=json.dumps(body.deny_topics, ensure_ascii=False),
    )
    db.add(domain)
    db.commit()
    db.refresh(domain)
    return _serialize(domain)


@router.get("/{domain_id}")
def get_domain(domain_id: str, db: Session = Depends(get_db)):
    """Get full config of a custom domain."""
    d = db.query(DomainConfig).filter(DomainConfig.domain_id == domain_id).first()
    if not d:
        if domain_id in _load_builtin_domains():
            cfg = _load_builtin_domains()[domain_id]
            return {
                "id": domain_id,
                "name": cfg.get("label", domain_id),
                "system_prompt": cfg.get("system_prompt", ""),
                "deny_topics": cfg.get("deny_topics", []),
                "is_custom": False,
            }
        raise HTTPException(status_code=404, detail=f"Domain '{domain_id}' not found")
    return _serialize(d)


@router.put("/{domain_id}")
def update_domain(domain_id: str, body: DomainUpdate, db: Session = Depends(get_db)):
    """Update a custom domain (built-in domains are read-only)."""
    d = db.query(DomainConfig).filter(DomainConfig.domain_id == domain_id).first()
    if not d:
        raise HTTPException(status_code=404, detail=f"Custom domain '{domain_id}' not found")

    if body.name is not None:
        d.name = body.name.strip()
    if body.system_prompt is not None:
        d.system_prompt = body.system_prompt.strip()
    if body.deny_topics is not None:
        d.deny_topics = json.dumps(body.deny_topics, ensure_ascii=False)

    db.commit()
    db.refresh(d)
    return _serialize(d)


@router.delete("/{domain_id}")
def delete_domain(domain_id: str, db: Session = Depends(get_db)):
    """Delete a custom domain."""
    d = db.query(DomainConfig).filter(DomainConfig.domain_id == domain_id).first()
    if not d:
        raise HTTPException(status_code=404, detail=f"Custom domain '{domain_id}' not found")

    db.delete(d)
    db.commit()
    return {"id": domain_id, "status": "deleted"}
