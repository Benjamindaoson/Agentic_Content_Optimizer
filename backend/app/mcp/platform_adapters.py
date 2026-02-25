"""
平台适配器 - MCP 多平台内容处理

核心功能：
1. 平台特定的内容格式化
2. 平台 API 集成
3. 内容发布管理
4. 指标收集
"""

from typing import Dict, Any, Optional, List
from abc import ABC, abstractmethod
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class Platform(str, Enum):
    """支持的平台"""
    XIAOHONGSHU = "xiaohongshu"
    DOUYIN = "douyin"
    WEIBO = "weibo"
    TIKTOK = "tiktok"
    INSTAGRAM = "instagram"
    TWITTER = "twitter"


class PlatformAdapter(ABC):
    """平台适配器基类"""

    def __init__(self, platform: Platform):
        self.platform = platform
        self.logger = logging.getLogger(f"{__name__}.{platform.value}")

    @abstractmethod
    async def format_content(
        self,
        content: Dict[str, Any]
    ) -> Dict[str, Any]:
        """格式化内容

        Args:
            content: 原始内容（包含 hook, body, cta）

        Returns:
            格式化后的内容
        """
        pass

    @abstractmethod
    async def publish(
        self,
        content: Dict[str, Any],
        account_id: str
    ) -> Dict[str, Any]:
        """发布内容

        Args:
            content: 内容
            account_id: 账号 ID

        Returns:
            发布结果
        """
        pass

    @abstractmethod
    async def get_metrics(
        self,
        post_id: str
    ) -> Dict[str, Any]:
        """获取内容指标

        Args:
            post_id: 帖子 ID

        Returns:
            指标数据
        """
        pass

    def _extract_keywords(self, text: str, limit: int = 5) -> List[str]:
        """从文本中提取关键词

        Args:
            text: 文本
            limit: 关键词数量限制

        Returns:
            关键词列表
        """
        # 简单实现：分词后取高频词
        # 生产环境应使用 jieba 或其他 NLP 工具
        words = text.split()
        return words[:limit]


class XiaohongshuAdapter(PlatformAdapter):
    """小红书适配器"""

    def __init__(self):
        super().__init__(Platform.XIAOHONGSHU)

    async def format_content(
        self,
        content: Dict[str, Any]
    ) -> Dict[str, Any]:
        """格式化为小红书风格

        特点：
        1. 使用 emoji
        2. 分段清晰
        3. 标签丰富
        4. 图片为主
        """
        hook = content.get("hook", "")
        body = content.get("body", "")
        cta = content.get("cta", "")

        # 格式化正文
        formatted_body = self._format_body_xiaohongshu(body)

        # 提取标签
        tags = self._extract_tags(content)

        # 组合完整内容
        full_text = f"{hook}\n\n{formatted_body}\n\n{cta}\n\n{' '.join(tags)}"

        formatted = {
            "title": hook,
            "body": full_text,
            "tags": tags,
            "images": content.get("images", []),
            "platform": "xiaohongshu",
            "original_content": content
        }

        self.logger.info(f"Formatted content for Xiaohongshu: {len(full_text)} chars, {len(tags)} tags")

        return formatted

    def _format_body_xiaohongshu(self, body: str) -> str:
        """格式化正文为小红书风格"""
        # 添加段落分隔
        paragraphs = body.split('\n')
        formatted_paragraphs = []

        for para in paragraphs:
            if para.strip():
                # 添加适当的 emoji（简化版）
                formatted_paragraphs.append(f"✨ {para.strip()}")

        return "\n\n".join(formatted_paragraphs)

    def _extract_tags(self, content: Dict[str, Any]) -> List[str]:
        """提取标签"""
        text = f"{content.get('hook', '')} {content.get('body', '')}"
        keywords = self._extract_keywords(text, limit=5)

        # 转换为标签格式
        tags = [f"#{keyword}" for keyword in keywords if len(keyword) > 1]

        return tags[:5]  # 最多 5 个标签

    async def publish(
        self,
        content: Dict[str, Any],
        account_id: str
    ) -> Dict[str, Any]:
        """发布到小红书

        注意：当前为模拟实现，生产环境需要集成真实 API
        """
        self.logger.info(f"Publishing to Xiaohongshu for account: {account_id}")

        # 模拟发布
        post_id = f"xhs_{account_id}_{hash(content['body']) % 100000}"

        return {
            "status": "success",
            "post_id": post_id,
            "url": f"https://xiaohongshu.com/explore/{post_id}",
            "platform": "xiaohongshu",
            "published_at": "2026-02-14T12:00:00Z"
        }

    async def get_metrics(
        self,
        post_id: str
    ) -> Dict[str, Any]:
        """获取小红书指标"""
        self.logger.info(f"Fetching metrics for post: {post_id}")

        # 模拟指标数据
        return {
            "post_id": post_id,
            "platform": "xiaohongshu",
            "likes": 0,
            "comments": 0,
            "shares": 0,
            "collects": 0,
            "views": 0,
            "engagement_rate": 0.0
        }


class DouyinAdapter(PlatformAdapter):
    """抖音适配器"""

    def __init__(self):
        super().__init__(Platform.DOUYIN)

    async def format_content(
        self,
        content: Dict[str, Any]
    ) -> Dict[str, Any]:
        """格式化为抖音风格

        特点：
        1. 口语化
        2. 短视频脚本
        3. 音乐推荐
        4. 话题标签
        """
        # 创建视频脚本
        script = self._create_video_script(content)

        # 推荐音乐
        music = self._recommend_music(content)

        # 提取话题标签
        hashtags = self._extract_hashtags(content)

        formatted = {
            "script": script,
            "music": music,
            "hashtags": hashtags,
            "duration": self._estimate_duration(script),
            "platform": "douyin",
            "original_content": content
        }

        self.logger.info(f"Formatted content for Douyin: {len(script)} chars, {len(hashtags)} hashtags")

        return formatted

    def _create_video_script(self, content: Dict[str, Any]) -> str:
        """创建视频脚本"""
        hook = content.get("hook", "")
        body = content.get("body", "")
        cta = content.get("cta", "")

        # 分镜头
        script = f"""【开场】{hook}

【正文】
{body}

【结尾】{cta}
"""
        return script

    def _recommend_music(self, content: Dict[str, Any]) -> str:
        """推荐背景音乐"""
        # 简化版：根据内容情绪推荐
        return "热门音乐"

    def _extract_hashtags(self, content: Dict[str, Any]) -> List[str]:
        """提取话题标签"""
        text = f"{content.get('hook', '')} {content.get('body', '')}"
        keywords = self._extract_keywords(text, limit=3)

        hashtags = [f"#{keyword}" for keyword in keywords if len(keyword) > 1]

        return hashtags

    def _estimate_duration(self, script: str) -> int:
        """估算视频时长（秒）"""
        # 简单估算：每个字 0.5 秒
        return len(script) // 2

    async def publish(
        self,
        content: Dict[str, Any],
        account_id: str
    ) -> Dict[str, Any]:
        """发布到抖音"""
        self.logger.info(f"Publishing to Douyin for account: {account_id}")

        post_id = f"dy_{account_id}_{hash(content['script']) % 100000}"

        return {
            "status": "success",
            "post_id": post_id,
            "url": f"https://douyin.com/video/{post_id}",
            "platform": "douyin",
            "published_at": "2026-02-14T12:00:00Z"
        }

    async def get_metrics(
        self,
        post_id: str
    ) -> Dict[str, Any]:
        """获取抖音指标"""
        self.logger.info(f"Fetching metrics for post: {post_id}")

        return {
            "post_id": post_id,
            "platform": "douyin",
            "likes": 0,
            "comments": 0,
            "shares": 0,
            "views": 0,
            "engagement_rate": 0.0
        }


class WeiboAdapter(PlatformAdapter):
    """微博适配器"""

    def __init__(self):
        super().__init__(Platform.WEIBO)

    async def format_content(
        self,
        content: Dict[str, Any]
    ) -> Dict[str, Any]:
        """格式化为微博风格

        特点：
        1. 140 字限制（可长文）
        2. @提及和话题
        3. 图文结合
        """
        hook = content.get("hook", "")
        body = content.get("body", "")
        cta = content.get("cta", "")

        # 组合内容
        full_text = f"{hook} {body} {cta}"

        # 检查长度
        if len(full_text) > 140:
            # 使用长文模式
            is_long_text = True
        else:
            is_long_text = False

        # 提取话题
        topics = self._extract_topics(content)

        formatted = {
            "text": full_text,
            "is_long_text": is_long_text,
            "topics": topics,
            "images": content.get("images", []),
            "platform": "weibo",
            "original_content": content
        }

        self.logger.info(f"Formatted content for Weibo: {len(full_text)} chars, long_text={is_long_text}")

        return formatted

    def _extract_topics(self, content: Dict[str, Any]) -> List[str]:
        """提取话题"""
        text = f"{content.get('hook', '')} {content.get('body', '')}"
        keywords = self._extract_keywords(text, limit=3)

        topics = [f"#{keyword}#" for keyword in keywords if len(keyword) > 1]

        return topics

    async def publish(
        self,
        content: Dict[str, Any],
        account_id: str
    ) -> Dict[str, Any]:
        """发布到微博"""
        self.logger.info(f"Publishing to Weibo for account: {account_id}")

        post_id = f"wb_{account_id}_{hash(content['text']) % 100000}"

        return {
            "status": "success",
            "post_id": post_id,
            "url": f"https://weibo.com/{account_id}/{post_id}",
            "platform": "weibo",
            "published_at": "2026-02-14T12:00:00Z"
        }

    async def get_metrics(
        self,
        post_id: str
    ) -> Dict[str, Any]:
        """获取微博指标"""
        self.logger.info(f"Fetching metrics for post: {post_id}")

        return {
            "post_id": post_id,
            "platform": "weibo",
            "likes": 0,
            "comments": 0,
            "reposts": 0,
            "views": 0,
            "engagement_rate": 0.0
        }
