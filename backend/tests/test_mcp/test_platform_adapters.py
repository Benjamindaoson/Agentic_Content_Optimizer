"""
MCP 平台适配器单元测试

测试多平台内容适配功能：
1. 内容格式化
2. 平台发布
3. 指标获取
"""

import pytest
from unittest.mock import AsyncMock, patch

from app.mcp.platform_adapters import (
    XiaohongshuAdapter,
    DouyinAdapter,
    WeiboAdapter,
    Platform
)


class TestXiaohongshuAdapter:
    """测试小红书适配器"""

    @pytest.mark.asyncio
    async def test_format_content(self):
        """测试内容格式化"""
        adapter = XiaohongshuAdapter()

        content = {
            "hook": "AI 写作工具推荐",
            "body": "这是一个很棒的 AI 写作工具\n可以大幅提升效率",
            "cta": "关注我了解更多",
            "images": ["image1.jpg", "image2.jpg"]
        }

        formatted = await adapter.format_content(content)

        assert formatted["platform"] == "xiaohongshu"
        assert "title" in formatted
        assert "body" in formatted
        assert "tags" in formatted
        assert len(formatted["tags"]) > 0
        assert formatted["images"] == ["image1.jpg", "image2.jpg"]

    @pytest.mark.asyncio
    async def test_publish(self):
        """测试发布"""
        adapter = XiaohongshuAdapter()

        content = {
            "title": "测试标题",
            "body": "测试内容",
            "tags": ["#AI", "#写作"],
            "images": []
        }

        result = await adapter.publish(content, "test_account")

        assert result["status"] == "success"
        assert "post_id" in result
        assert "url" in result
        assert result["platform"] == "xiaohongshu"

    @pytest.mark.asyncio
    async def test_get_metrics(self):
        """测试获取指标"""
        adapter = XiaohongshuAdapter()

        metrics = await adapter.get_metrics("xhs_123")

        assert metrics["platform"] == "xiaohongshu"
        assert "likes" in metrics
        assert "comments" in metrics
        assert "shares" in metrics
        assert "collects" in metrics


class TestDouyinAdapter:
    """测试抖音适配器"""

    @pytest.mark.asyncio
    async def test_format_content(self):
        """测试内容格式化"""
        adapter = DouyinAdapter()

        content = {
            "hook": "AI 写作技巧分享",
            "body": "今天教大家如何使用 AI 提升写作效率",
            "cta": "点赞关注不迷路"
        }

        formatted = await adapter.format_content(content)

        assert formatted["platform"] == "douyin"
        assert "script" in formatted
        assert "music" in formatted
        assert "hashtags" in formatted
        assert "duration" in formatted
        assert formatted["duration"] > 0

    @pytest.mark.asyncio
    async def test_create_video_script(self):
        """测试视频脚本创建"""
        adapter = DouyinAdapter()

        content = {
            "hook": "开场白",
            "body": "正文内容",
            "cta": "结尾"
        }

        script = adapter._create_video_script(content)

        assert "【开场】" in script
        assert "【正文】" in script
        assert "【结尾】" in script
        assert "开场白" in script
        assert "正文内容" in script
        assert "结尾" in script

    @pytest.mark.asyncio
    async def test_publish(self):
        """测试发布"""
        adapter = DouyinAdapter()

        content = {
            "script": "测试脚本",
            "music": "测试音乐",
            "hashtags": ["#AI", "#写作"]
        }

        result = await adapter.publish(content, "test_account")

        assert result["status"] == "success"
        assert "post_id" in result
        assert result["platform"] == "douyin"


class TestWeiboAdapter:
    """测试微博适配器"""

    @pytest.mark.asyncio
    async def test_format_content_short(self):
        """测试短文本格式化"""
        adapter = WeiboAdapter()

        content = {
            "hook": "AI 写作",
            "body": "简短内容",
            "cta": "关注"
        }

        formatted = await adapter.format_content(content)

        assert formatted["platform"] == "weibo"
        assert formatted["is_long_text"] is False
        assert "text" in formatted
        assert "topics" in formatted

    @pytest.mark.asyncio
    async def test_format_content_long(self):
        """测试长文本格式化"""
        adapter = WeiboAdapter()

        # 创建超过 140 字的内容
        long_body = "这是一段很长的内容。" * 30

        content = {
            "hook": "AI 写作工具推荐",
            "body": long_body,
            "cta": "关注我了解更多"
        }

        formatted = await adapter.format_content(content)

        assert formatted["platform"] == "weibo"
        assert formatted["is_long_text"] is True

    @pytest.mark.asyncio
    async def test_extract_topics(self):
        """测试话题提取"""
        adapter = WeiboAdapter()

        content = {
            "hook": "AI 写作工具",
            "body": "人工智能 自然语言处理"
        }

        topics = adapter._extract_topics(content)

        assert len(topics) > 0
        assert all(topic.startswith("#") and topic.endswith("#") for topic in topics)

    @pytest.mark.asyncio
    async def test_publish(self):
        """测试发布"""
        adapter = WeiboAdapter()

        content = {
            "text": "测试微博内容",
            "is_long_text": False,
            "topics": ["#AI#", "#写作#"],
            "images": []
        }

        result = await adapter.publish(content, "test_account")

        assert result["status"] == "success"
        assert "post_id" in result
        assert result["platform"] == "weibo"


class TestPlatformAdapterBase:
    """测试平台适配器基类功能"""

    def test_extract_keywords(self):
        """测试关键词提取"""
        adapter = XiaohongshuAdapter()

        text = "AI 写作 工具 推荐 效率 提升"
        keywords = adapter._extract_keywords(text, limit=3)

        assert len(keywords) <= 3
        assert all(isinstance(kw, str) for kw in keywords)
