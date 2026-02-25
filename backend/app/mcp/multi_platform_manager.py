"""
多平台内容管理器

核心功能：
1. 多平台同步发布
2. 平台特定优化
3. 发布监控
4. 性能追踪
"""

from typing import Dict, Any, List, Optional
import logging
import asyncio

from app.mcp.platform_adapters import (
    PlatformAdapter,
    XiaohongshuAdapter,
    DouyinAdapter,
    WeiboAdapter,
    Platform
)

logger = logging.getLogger(__name__)


class MultiPlatformManager:
    """多平台内容管理器

    管理多个平台的内容发布和监控
    """

    def __init__(self):
        """初始化多平台管理器"""
        self.adapters: Dict[Platform, PlatformAdapter] = {
            Platform.XIAOHONGSHU: XiaohongshuAdapter(),
            Platform.DOUYIN: DouyinAdapter(),
            Platform.WEIBO: WeiboAdapter(),
        }

        logger.info(f"MultiPlatformManager initialized with {len(self.adapters)} platforms")

    def add_adapter(self, platform: Platform, adapter: PlatformAdapter):
        """添加平台适配器

        Args:
            platform: 平台
            adapter: 适配器
        """
        self.adapters[platform] = adapter
        logger.info(f"Added adapter for platform: {platform}")

    async def format_for_platform(
        self,
        content: Dict[str, Any],
        platform: Platform
    ) -> Optional[Dict[str, Any]]:
        """为特定平台格式化内容

        Args:
            content: 原始内容
            platform: 目标平台

        Returns:
            格式化后的内容
        """
        adapter = self.adapters.get(platform)
        if not adapter:
            logger.warning(f"No adapter for platform: {platform}")
            return None

        try:
            formatted = await adapter.format_content(content)
            return formatted
        except Exception as e:
            logger.error(f"Error formatting content for {platform}: {e}", exc_info=True)
            return None

    async def publish_to_platform(
        self,
        content: Dict[str, Any],
        platform: Platform,
        account_id: str
    ) -> Optional[Dict[str, Any]]:
        """发布到单个平台

        Args:
            content: 内容
            platform: 平台
            account_id: 账号 ID

        Returns:
            发布结果
        """
        adapter = self.adapters.get(platform)
        if not adapter:
            logger.warning(f"No adapter for platform: {platform}")
            return None

        try:
            # 格式化内容
            formatted_content = await adapter.format_content(content)

            # 发布
            result = await adapter.publish(formatted_content, account_id)

            logger.info(f"Published to {platform}: {result.get('post_id')}")

            return result
        except Exception as e:
            logger.error(f"Error publishing to {platform}: {e}", exc_info=True)
            return {
                "status": "failed",
                "platform": platform.value,
                "error": str(e)
            }

    async def publish_to_multiple_platforms(
        self,
        content: Dict[str, Any],
        platforms: List[Platform],
        account_ids: Dict[Platform, str]
    ) -> Dict[Platform, Dict[str, Any]]:
        """发布到多个平台

        Args:
            content: 原始内容
            platforms: 目标平台列表
            account_ids: 各平台的账号 ID

        Returns:
            各平台的发布结果
        """
        logger.info(f"Publishing to {len(platforms)} platforms")

        # 并发发布到所有平台
        tasks = []
        for platform in platforms:
            account_id = account_ids.get(platform)
            if not account_id:
                logger.warning(f"No account ID for platform: {platform}")
                continue

            task = self.publish_to_platform(content, platform, account_id)
            tasks.append((platform, task))

        # 等待所有发布完成
        results = {}
        for platform, task in tasks:
            try:
                result = await task
                results[platform] = result
            except Exception as e:
                logger.error(f"Error publishing to {platform}: {e}", exc_info=True)
                results[platform] = {
                    "status": "failed",
                    "platform": platform.value,
                    "error": str(e)
                }

        # 统计结果
        success_count = sum(1 for r in results.values() if r and r.get("status") == "success")
        logger.info(f"Published to {success_count}/{len(platforms)} platforms successfully")

        return results

    async def get_platform_metrics(
        self,
        platform: Platform,
        post_id: str
    ) -> Optional[Dict[str, Any]]:
        """获取单个平台的指标

        Args:
            platform: 平台
            post_id: 帖子 ID

        Returns:
            指标数据
        """
        adapter = self.adapters.get(platform)
        if not adapter:
            logger.warning(f"No adapter for platform: {platform}")
            return None

        try:
            metrics = await adapter.get_metrics(post_id)
            return metrics
        except Exception as e:
            logger.error(f"Error getting metrics from {platform}: {e}", exc_info=True)
            return None

    async def monitor_performance(
        self,
        post_ids: Dict[Platform, str]
    ) -> Dict[Platform, Dict[str, Any]]:
        """监控多平台表现

        Args:
            post_ids: 各平台的帖子 ID

        Returns:
            各平台的指标数据
        """
        logger.info(f"Monitoring performance for {len(post_ids)} platforms")

        # 并发获取所有平台的指标
        tasks = []
        for platform, post_id in post_ids.items():
            task = self.get_platform_metrics(platform, post_id)
            tasks.append((platform, task))

        # 等待所有指标获取完成
        metrics = {}
        for platform, task in tasks:
            try:
                result = await task
                metrics[platform] = result
            except Exception as e:
                logger.error(f"Error getting metrics from {platform}: {e}", exc_info=True)
                metrics[platform] = None

        return metrics

    async def compare_platform_performance(
        self,
        post_ids: Dict[Platform, str]
    ) -> Dict[str, Any]:
        """比较各平台表现

        Args:
            post_ids: 各平台的帖子 ID

        Returns:
            比较结果
        """
        # 获取所有平台的指标
        all_metrics = await self.monitor_performance(post_ids)

        # 计算总体指标
        total_likes = 0
        total_comments = 0
        total_shares = 0
        total_views = 0

        platform_rankings = []

        for platform, metrics in all_metrics.items():
            if not metrics:
                continue

            likes = metrics.get("likes", 0)
            comments = metrics.get("comments", 0)
            shares = metrics.get("shares", 0)
            views = metrics.get("views", 0)

            total_likes += likes
            total_comments += comments
            total_shares += shares
            total_views += views

            # 计算平台得分（简单加权）
            score = likes * 1 + comments * 2 + shares * 3 + views * 0.01

            platform_rankings.append({
                "platform": platform.value,
                "score": score,
                "metrics": metrics
            })

        # 排序
        platform_rankings.sort(key=lambda x: x["score"], reverse=True)

        return {
            "total_metrics": {
                "likes": total_likes,
                "comments": total_comments,
                "shares": total_shares,
                "views": total_views
            },
            "platform_rankings": platform_rankings,
            "best_platform": platform_rankings[0]["platform"] if platform_rankings else None
        }

    def get_supported_platforms(self) -> List[str]:
        """获取支持的平台列表

        Returns:
            平台列表
        """
        return [platform.value for platform in self.adapters.keys()]

    def get_stats(self) -> Dict[str, Any]:
        """获取管理器统计信息

        Returns:
            统计信息
        """
        return {
            "total_platforms": len(self.adapters),
            "supported_platforms": self.get_supported_platforms()
        }
