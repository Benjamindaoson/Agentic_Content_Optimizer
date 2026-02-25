"""
Outcome 同步 + 自动采集定时任务

- sync_outcomes_to_rl_task: 每 6h 批量同步 Outcome → Thompson Sampling
- auto_scrape_outcomes_task: 每 6h 自动爬取已发布帖子的互动数据
"""

import asyncio
import logging
from datetime import datetime
from typing import Dict, Any

logger = logging.getLogger(__name__)


def _run_async(coro):
    """在 Celery worker 中安全运行异步函数。

    Python 3.11+ 优先使用 asyncio.Runner，避免手动管理事件循环。
    """
    try:
        with asyncio.Runner() as runner:
            return runner.run(coro)
    except AttributeError:
        # 兼容旧版本 Python
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()


async def _do_batch_sync() -> Dict[str, Any]:
    from app.core.database import async_session_factory
    from app.ml.rl.outcome_reward_bridge import batch_sync_pending_outcomes

    async with async_session_factory() as db:
        synced = await batch_sync_pending_outcomes(db, limit=500)
        await db.commit()
        return {"synced": synced, "timestamp": datetime.utcnow().isoformat()}


def sync_outcomes_to_rl_task() -> Dict[str, Any]:
    """
    批量同步 Outcome → Thompson Sampling（带重试机制）。
    调度建议：每 6 小时执行一次。
    """
    try:
        result = _run_async(_do_batch_sync())
        logger.info(f"[OUTCOME SYNC TASK] {result}")
        return {"success": True, **result}
    except Exception as e:
        logger.error(f"[OUTCOME SYNC TASK] Failed: {e}", exc_info=True)
        return {"success": False, "error": str(e)}


async def _do_auto_scrape() -> Dict[str, Any]:
    """自动爬取已发布帖子的互动数据"""
    from app.core.database import async_session_factory
    from sqlalchemy import text

    async with async_session_factory() as db:
        # 查询最近 7 天内已发布但尚未采集 Outcome 的帖子
        stmt = text("""
            SELECT DISTINCT g.trace_id, g.platform_post_url
            FROM generation_traces g
            WHERE g.platform_post_url IS NOT NULL
              AND g.platform_post_url != ''
              AND g.published_at IS NOT NULL
              AND g.published_at > NOW() - INTERVAL '7 days'
              AND NOT EXISTS (
                  SELECT 1 FROM outcomes o
                  WHERE o.trace_id = g.trace_id
                    AND o.time_bucket = '24h'
              )
            LIMIT 50
        """)

        try:
            result = await db.execute(stmt)
            rows = result.fetchall()
        except Exception as e:
            logger.warning(f"[AUTO SCRAPE] Query failed (table may not exist): {e}")
            return {"scraped": 0, "reason": "query_failed"}

        if not rows:
            return {"scraped": 0, "reason": "no_pending_posts"}

        records = [
            {"trace_id": row[0], "platform_post_url": row[1]}
            for row in rows
        ]

        from app.data.crawlers.outcome_scraper import scrape_and_sync_outcomes
        scraped = await scrape_and_sync_outcomes(db, records)
        await db.commit()

        return {
            "scraped": scraped,
            "total_pending": len(records),
            "timestamp": datetime.utcnow().isoformat(),
        }


def auto_scrape_outcomes_task() -> Dict[str, Any]:
    """
    自动爬取已发布帖子的互动数据。
    调度建议：每 6 小时执行一次，在 sync_outcomes_to_rl_task 之前运行。
    """
    try:
        result = _run_async(_do_auto_scrape())
        logger.info(f"[AUTO SCRAPE TASK] {result}")
        return {"success": True, **result}
    except Exception as e:
        logger.error(f"[AUTO SCRAPE TASK] Failed: {e}", exc_info=True)
        return {"success": False, "error": str(e)}
