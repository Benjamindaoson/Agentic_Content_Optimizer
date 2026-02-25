"""Prompt 模板仓储。"""

from __future__ import annotations

import logging
from typing import Any, Optional

from sqlalchemy import and_, desc, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import async_session_factory
from app.prompting.models import PromptTemplate

logger = logging.getLogger(__name__)


class PromptRepository:
    """Prompt 模板版本管理。"""

    async def get_active_template(
        self,
        name: str,
        channel: str = "default",
        db: Optional[AsyncSession] = None,
    ) -> Optional[PromptTemplate]:
        owns_session = db is None
        if owns_session:
            db = async_session_factory()
        try:
            assert db is not None
            stmt = (
                select(PromptTemplate)
                .where(
                    and_(
                        PromptTemplate.name == name,
                        PromptTemplate.channel == channel,
                        PromptTemplate.is_active.is_(True),
                    )
                )
                .order_by(desc(PromptTemplate.version))
                .limit(1)
            )
            res = await db.execute(stmt)
            return res.scalar_one_or_none()
        finally:
            if owns_session and db is not None:
                await db.close()

    async def render_prompt(
        self,
        name: str,
        variables: dict[str, Any],
        channel: str = "default",
    ) -> Optional[str]:
        tpl = await self.get_active_template(name=name, channel=channel)
        if not tpl:
            return None
        try:
            return tpl.template.format(**variables)
        except Exception as e:
            logger.warning(f"Prompt render failed for {name} v{tpl.version}: {e}")
            return None

    async def upsert_template(
        self,
        name: str,
        template: str,
        version: int,
        channel: str = "default",
        is_active: bool = True,
        description: str | None = None,
        created_by: str = "system",
    ) -> PromptTemplate:
        async with async_session_factory() as db:
            if is_active:
                await db.execute(
                    update(PromptTemplate)
                    .where(
                        and_(
                            PromptTemplate.name == name,
                            PromptTemplate.channel == channel,
                            PromptTemplate.is_active.is_(True),
                        )
                    )
                    .values(is_active=False)
                )
            entity = PromptTemplate(
                name=name,
                template=template,
                version=version,
                channel=channel,
                is_active=is_active,
                description=description,
                created_by=created_by,
            )
            db.add(entity)
            await db.commit()
            await db.refresh(entity)
            return entity


prompt_repository = PromptRepository()

