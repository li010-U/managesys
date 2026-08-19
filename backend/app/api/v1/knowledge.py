"""??? API"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db, get_current_user, require_permission
from app.db.compat_sql import exec_sql
from app.models import User

router = APIRouter(prefix="/kb", tags=["Knowledge Base"])


class KnowledgeCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=256)
    category: Optional[str] = Field(None, max_length=64)
    content: str = Field(..., min_length=1)
    source_order_id: Optional[int] = None


def _row_to_dict(r):
    d = dict(r._mapping)
    return d


@router.get("", summary="List knowledge articles")
async def list_articles(
    keyword: Optional[str] = None,
    category: Optional[str] = None,
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(require_permission("work:view")),
):
    conditions = []
    params = []
    if keyword:
        conditions.append("(LOWER(title) LIKE ? OR LOWER(content) LIKE ?)")
        params.extend(["%{}%".format(keyword.lower()), "%{}%".format(keyword.lower())])
    if category:
        conditions.append("category = ?")
        params.append(category)
    where = " AND ".join(conditions) if conditions else "1=1"
    sql = """
        SELECT k.*, u.username as creator_name
        FROM kb_articles k LEFT JOIN users u ON k.created_by = u.id
        WHERE {}
        ORDER BY k.created_at DESC
        LIMIT ?
    """.format(where)
    rows = (await exec_sql(db, sql, tuple(params) + (limit,))).fetchall()
    return {"data": [_row_to_dict(r) for r in rows]}


@router.post("", summary="Create knowledge article")
async def create_article(
    data: KnowledgeCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _ = Depends(require_permission("work:create")),
):
    await exec_sql(db, """
        INSERT INTO kb_articles (title, category, content, source_order_id, created_by, created_at)
        VALUES (?, ?, ?, ?, ?, datetime('now','localtime'))
    """, (data.title, data.category, data.content, data.source_order_id, current_user.id))
    row = (await exec_sql(db, """
        SELECT k.*, u.username as creator_name
        FROM kb_articles k LEFT JOIN users u ON k.created_by = u.id
        ORDER BY k.id DESC LIMIT 1
    """)).fetchone()
    from app.services.audit_service import AuditService
    AuditService.log_request(db, request, current_user=current_user, action="create", target_type="knowledge", target_id=str(row.id), detail=f"创建知识文章: {data.title}")
    return {"data": _row_to_dict(row)}


@router.get("/recommend", summary="Recommend articles by keyword")
async def recommend_articles(
    keyword: str = Query(..., min_length=1, max_length=256),
    limit: int = Query(5, ge=1, le=20),
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(require_permission("work:view")),
):
    sql = """
        SELECT k.*, u.username as creator_name
        FROM kb_articles k LEFT JOIN users u ON k.created_by = u.id
        WHERE (LOWER(k.title) LIKE ? OR LOWER(k.content) LIKE ?)
        ORDER BY k.created_at DESC
        LIMIT {}
    """.format(limit)
    rows = (await exec_sql(db, sql, ("%{}%".format(keyword.lower()), "%{}%".format(keyword.lower())))).fetchall()
    return {"data": [_row_to_dict(r) for r in rows]}
