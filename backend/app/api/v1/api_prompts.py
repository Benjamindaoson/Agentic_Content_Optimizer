"""Prompt 模板管理 API。"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import and_, desc, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_admin_user
from app.core.database import get_db
from app.models.user import User
from app.prompting.models import PromptTemplate

router = APIRouter(prefix="/api/v1/prompts", tags=["prompts"])


class PromptTemplateCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    channel: str = Field(default="default", max_length=32)
    template: str = Field(..., min_length=20)
    description: Optional[str] = None
    is_active: bool = True
    created_by: str = "api"


@router.get("/")
async def list_prompt_templates(
    name: Optional[str] = None,
    channel: Optional[str] = None,
    limit: int = 100,
    _: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    stmt = select(PromptTemplate).order_by(desc(PromptTemplate.created_at)).limit(max(1, min(limit, 500)))
    if name:
        stmt = stmt.where(PromptTemplate.name == name)
    if channel:
        stmt = stmt.where(PromptTemplate.channel == channel)
    rows = (await db.execute(stmt)).scalars().all()
    return {
        "items": [
            {
                "id": r.id,
                "name": r.name,
                "channel": r.channel,
                "version": r.version,
                "is_active": r.is_active,
                "description": r.description,
                "created_by": r.created_by,
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "updated_at": r.updated_at.isoformat() if r.updated_at else None,
            }
            for r in rows
        ]
    }


@router.post("/")
async def create_prompt_template(
    req: PromptTemplateCreate,
    _: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    # 自动递增版本号
    latest_stmt = (
        select(PromptTemplate)
        .where(and_(PromptTemplate.name == req.name, PromptTemplate.channel == req.channel))
        .order_by(desc(PromptTemplate.version))
        .limit(1)
    )
    latest = (await db.execute(latest_stmt)).scalar_one_or_none()
    next_version = (latest.version + 1) if latest else 1

    if req.is_active:
        await db.execute(
            update(PromptTemplate)
            .where(and_(PromptTemplate.name == req.name, PromptTemplate.channel == req.channel))
            .values(is_active=False)
        )

    entity = PromptTemplate(
        name=req.name,
        channel=req.channel,
        version=next_version,
        template=req.template,
        description=req.description,
        is_active=req.is_active,
        created_by=req.created_by,
    )
    db.add(entity)
    await db.flush()
    await db.refresh(entity)
    return {
        "id": entity.id,
        "name": entity.name,
        "channel": entity.channel,
        "version": entity.version,
        "is_active": entity.is_active,
    }


@router.post("/{template_id}/activate")
async def activate_prompt_template(
    template_id: int,
    _: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    target = await db.get(PromptTemplate, template_id)
    if not target:
        raise HTTPException(status_code=404, detail="template not found")

    await db.execute(
        update(PromptTemplate)
        .where(and_(PromptTemplate.name == target.name, PromptTemplate.channel == target.channel))
        .values(is_active=False)
    )
    target.is_active = True
    await db.flush()
    return {"success": True, "id": template_id, "name": target.name, "version": target.version}

