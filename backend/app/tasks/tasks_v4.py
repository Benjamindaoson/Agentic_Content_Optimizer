"""
v4.0 Growth Brain Celery 定时任务

包含：
1. 自动化账号运营定时任务
2. 封面 A/B 测试监控
3. 多平台效果对比
4. 因果关系发现
"""

from typing import Dict, Any, List
from datetime import datetime, date, timedelta
import asyncio

from app.tasks.celery_config import task, celery_app
from celery.schedules import crontab
from app.db import get_db
from app.growth_brain.auto_account_manager import (
    AutoAccountManager,
    TopicSource
)
from app.growth_brain.multimodal_cover_engine import (
    MultimodalCoverEngine,
    CoverABTest
)
from app.growth_brain.multi_platform_engine import (
    MultiPlatformEngine,
    UnifiedContentRecord
)
from app.growth_brain.causal_inference_engine import (
    CausalInferenceEngine
)


# ==================== 自动化账号运营任务 ====================

@task(name='app.tasks.v4.discover_trending_topics')
def discover_trending_topics_task() -> Dict[str, Any]:
    """
    发现热点话题（每日任务）

    每天早上 6:00 自动扫描各平台热点话题
    """
    with get_db() as db:
        manager = AutoAccountManager(db)

        # 从所有平台发现话题
        sources = [
            TopicSource.XHS_TRENDING,
            TopicSource.WEIBO_TRENDING,
            TopicSource.DOUYIN_TRENDING
        ]

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            topics = loop.run_until_complete(
                manager.discover_trending_topics(sources, limit=50)
            )

            return {
                "success": True,
                "count": len(topics),
                "topics": [t.topic_id for t in topics],
                "timestamp": datetime.now().isoformat()
            }

        finally:
            loop.close()


@task(name='app.tasks.v4.create_daily_plans')
def create_daily_plans_task(account_ids: List[str] = None) -> Dict[str, Any]:
    """
    创建每日计划（每日任务）

    为所有活跃账号创建每日内容计划
    """
    with get_db() as db:
        manager = AutoAccountManager(db)

        # 如果没有指定账号，获取所有活跃账号
        if not account_ids:
            # TODO: 从账号池获取活跃账号
            account_ids = ["account_001", "account_002"]  # 示例

        plans = []
        today = date.today()

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            for account_id in account_ids:
                try:
                    plan = loop.run_until_complete(
                        manager.create_daily_plan(account_id, today)
                    )
                    plans.append(plan.plan_id)
                except Exception as e:
                    print(f"创建计划失败 {account_id}: {e}")

            return {
                "success": True,
                "count": len(plans),
                "plans": plans,
                "timestamp": datetime.now().isoformat()
            }

        finally:
            loop.close()


@task(name='app.tasks.v4.monitor_recent_posts')
def monitor_recent_posts_task(time_window_minutes: int = 60) -> Dict[str, Any]:
    """
    监控最近发布的内容（每小时任务）

    监控最近 N 分钟内发布的内容表现
    """
    from app.growth_brain.auto_account_manager import ContentSchedule

    with get_db() as db:
        manager = AutoAccountManager(db)

        # 获取最近发布的内容
        cutoff_time = datetime.now() - timedelta(minutes=time_window_minutes)

        schedules = db.query(ContentSchedule).filter(
            ContentSchedule.published_at >= cutoff_time,
            ContentSchedule.status == 'published'
        ).all()

        results = []

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            for schedule in schedules:
                try:
                    performance = loop.run_until_complete(
                        manager.monitor_performance(
                            schedule.schedule_id,
                            time_window_minutes
                        )
                    )
                    results.append({
                        "schedule_id": schedule.schedule_id,
                        "performance": performance
                    })
                except Exception as e:
                    print(f"监控失败 {schedule.schedule_id}: {e}")

            return {
                "success": True,
                "count": len(results),
                "results": results,
                "timestamp": datetime.now().isoformat()
            }

        finally:
            loop.close()


# ==================== 封面 A/B 测试任务 ====================

@task(name='app.tasks.v4.analyze_ab_tests')
def analyze_ab_tests_task() -> Dict[str, Any]:
    """
    分析 A/B 测试结果（每小时任务）

    分析所有运行中的 A/B 测试，选出胜者
    """
    with get_db() as db:
        engine = MultimodalCoverEngine(db)

        # 获取所有运行中的测试
        running_tests = db.query(CoverABTest).filter(
            CoverABTest.status == 'running'
        ).all()

        results = []

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            for test in running_tests:
                # 检查测试是否已运行足够时间
                if test.started_at:
                    elapsed_hours = (datetime.now() - test.started_at).total_seconds() / 3600

                    if elapsed_hours >= test.test_duration_hours:
                        try:
                            result = loop.run_until_complete(
                                engine.analyze_ab_test(test.test_id)
                            )
                            results.append({
                                "test_id": test.test_id,
                                "winner": result.winner_cover_id,
                                "winner_ctr": result.winner_ctr
                            })
                        except Exception as e:
                            print(f"分析测试失败 {test.test_id}: {e}")

            return {
                "success": True,
                "count": len(results),
                "results": results,
                "timestamp": datetime.now().isoformat()
            }

        finally:
            loop.close()


@task(name='app.tasks.v4.optimize_cover_styles')
def optimize_cover_styles_task(account_ids: List[str] = None) -> Dict[str, Any]:
    """
    优化封面风格（每周任务）

    为所有账号优化封面风格
    """
    with get_db() as db:
        engine = MultimodalCoverEngine(db)

        # 如果没有指定账号，获取所有活跃账号
        if not account_ids:
            account_ids = ["account_001", "account_002"]  # 示例

        results = []

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            for account_id in account_ids:
                try:
                    best_style = loop.run_until_complete(
                        engine.optimize_style(account_id, historical_days=30)
                    )
                    results.append({
                        "account_id": account_id,
                        "recommended_style": best_style.value
                    })
                except Exception as e:
                    print(f"优化风格失败 {account_id}: {e}")

            return {
                "success": True,
                "count": len(results),
                "results": results,
                "timestamp": datetime.now().isoformat()
            }

        finally:
            loop.close()


# ==================== 多平台效果对比任务 ====================

@task(name='app.tasks.v4.compare_platform_performance')
def compare_platform_performance_task(days: int = 7) -> Dict[str, Any]:
    """
    跨平台效果对比（每日任务）

    对比最近 N 天内所有内容的跨平台表现
    """
    with get_db() as db:
        engine = MultiPlatformEngine(db)

        # 获取最近的内容
        cutoff_time = datetime.now() - timedelta(days=days)

        contents = db.query(UnifiedContentRecord).filter(
            UnifiedContentRecord.created_at >= cutoff_time
        ).all()

        results = []

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            for content in contents:
                try:
                    comparison = loop.run_until_complete(
                        engine.compare_cross_platform_performance(content.content_id)
                    )
                    results.append({
                        "content_id": content.content_id,
                        "best_platform": comparison.best_platform.value if comparison.best_platform else None,
                        "insights": comparison.insights
                    })
                except Exception as e:
                    print(f"对比失败 {content.content_id}: {e}")

            return {
                "success": True,
                "count": len(results),
                "results": results,
                "timestamp": datetime.now().isoformat()
            }

        finally:
            loop.close()


# ==================== 因果关系发现任务 ====================

@task(name='app.tasks.v4.discover_causal_relationships')
def discover_causal_relationships_task() -> Dict[str, Any]:
    """
    发现因果关系（每周任务）

    从历史数据中自动发现因果关系
    """
    with get_db() as db:
        engine = CausalInferenceEngine(db)

        # 定义要分析的变量
        variables = [
            'hook_type',
            'cover_color',
            'publish_time',
            'content_length',
            'topic_heat',
            'engagement_rate',
            'viral_score'
        ]

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            relationships = loop.run_until_complete(
                engine.discover_causal_relationships(
                    variables=variables,
                    time_window_days=30
                )
            )

            return {
                "success": True,
                "count": len(relationships),
                "relationships": [
                    {
                        "from": r.from_node,
                        "to": r.to_node,
                        "strength": r.strength
                    }
                    for r in relationships
                ],
                "timestamp": datetime.now().isoformat()
            }

        finally:
            loop.close()


# ==================== 定时任务配置 ====================

# 添加到 Celery Beat 调度
celery_app.conf.beat_schedule.update({
    # 每天早上 6:00 发现热点话题
    'discover-trending-topics': {
        'task': 'app.tasks.v4.discover_trending_topics',
        'schedule': crontab(hour=6, minute=0),
    },

    # 每天早上 7:00 创建每日计划
    'create-daily-plans': {
        'task': 'app.tasks.v4.create_daily_plans',
        'schedule': crontab(hour=7, minute=0),
    },

    # 每小时监控最近发布的内容
    'monitor-recent-posts': {
        'task': 'app.tasks.v4.monitor_recent_posts',
        'schedule': 3600.0,  # 每小时
    },

    # 每小时分析 A/B 测试结果
    'analyze-ab-tests': {
        'task': 'app.tasks.v4.analyze_ab_tests',
        'schedule': 3600.0,  # 每小时
    },

    # 每周日凌晨 2:00 优化封面风格
    'optimize-cover-styles': {
        'task': 'app.tasks.v4.optimize_cover_styles',
        'schedule': crontab(hour=2, minute=0, day_of_week=0),
    },

    # 每天凌晨 3:00 对比平台表现
    'compare-platform-performance': {
        'task': 'app.tasks.v4.compare_platform_performance',
        'schedule': crontab(hour=3, minute=0),
    },

    # 每周一凌晨 4:00 发现因果关系
    'discover-causal-relationships': {
        'task': 'app.tasks.v4.discover_causal_relationships',
        'schedule': crontab(hour=4, minute=0, day_of_week=1),
    },
})
