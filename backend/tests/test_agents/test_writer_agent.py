"""
WriterAgent 单元测试

测试 WriterAgent 的核心功能：
1. 初始化
2. 内容生成
3. GEO 关键词覆盖率计算
4. 多候选生成和选择
"""

import pytest
from unittest.mock import AsyncMock, patch

from app.agents.content.writer_agent import WriterAgent
from app.agents.base import AgentConfig


class TestWriterAgentInitialization:
    """测试 WriterAgent 初始化"""

    def test_default_initialization(self):
        """测试默认初始化"""
        agent = WriterAgent()

        assert agent.config.name == "WriterAgent"
        assert agent.config.temperature == 0.7
        assert agent.config.model == "claude-3-5-sonnet-20240620"

    def test_custom_initialization(self):
        """测试自定义初始化"""
        config = AgentConfig(
            name="CustomWriterAgent",
            description="自定义内容生成器",
            model="claude-3-opus-20240229",
            temperature=0.8
        )

        agent = WriterAgent(config=config)

        assert agent.config.name == "CustomWriterAgent"
        assert agent.config.temperature == 0.8
        assert agent.config.model == "claude-3-opus-20240229"


class TestWriterAgentExecute:
    """测试 WriterAgent 执行"""

    @pytest.mark.asyncio
    async def test_execute_missing_topic(self):
        """测试缺少 topic 参数"""
        agent = WriterAgent()

        input_data = {
            "platform": "xiaohongshu"
        }

        response = await agent.execute(input_data)

        assert response.success is False
        assert "topic" in response.error.lower()

    @pytest.mark.asyncio
    async def test_execute_missing_references(self):
        """测试缺少 references 参数"""
        agent = WriterAgent()

        input_data = {
            "topic": "AI 写作工具",
            "platform": "xiaohongshu"
        }

        response = await agent.execute(input_data)

        assert response.success is False
        assert "references" in response.error.lower()

    @pytest.mark.asyncio
    async def test_execute_missing_strategy(self):
        """测试缺少 strategy 参数"""
        agent = WriterAgent()

        input_data = {
            "topic": "AI 写作工具",
            "platform": "xiaohongshu",
            "references": [
                {
                    "ref_id": "ref_1",
                    "text": "示例参考内容",
                    "structure": {
                        "hook": "H01",
                        "body": "B02",
                        "cta": "C01"
                    }
                }
            ]
        }

        response = await agent.execute(input_data)

        assert response.success is False
        assert "strategy" in response.error.lower()

    @pytest.mark.asyncio
    @patch('app.agents.content.writer_agent.ClaudeProvider.chat_completion')
    async def test_execute_success(self, mock_chat):
        """测试成功生成内容"""
        # Mock LLM 响应
        mock_chat.return_value = """
        {
            "hook": "你知道吗？AI 写作工具可以提升 10 倍效率",
            "body": "AI 写作工具通过智能算法，帮助你快速生成高质量内容。无论是文章、社交媒体帖子还是营销文案，AI 都能轻松搞定。",
            "cta": "关注我，了解更多 AI 工具推荐",
            "blueprint": {
                "scene": "办公室",
                "visual_elements": ["电脑", "笔记本"],
                "style": "简约现代"
            }
        }
        """

        agent = WriterAgent()

        input_data = {
            "topic": "AI 写作工具推荐",
            "platform": "xiaohongshu",
            "references": [
                {
                    "ref_id": "ref_1",
                    "text": "AI 工具可以提升效率",
                    "structure": {
                        "hook": "H01",
                        "body": "B02",
                        "cta": "C01"
                    }
                }
            ],
            "strategy": {
                "hook": "H01",
                "body": "B02",
                "cta": "C01"
            },
            "geo_constraints": {
                "keywords": ["AI", "写作", "工具", "效率"]
            }
        }

        response = await agent.execute(input_data)

        assert response.success is True
        assert "generated_contents" in response.data
        assert len(response.data["generated_contents"]) > 0

        # 验证生成的内容结构
        content = response.data["generated_contents"][0]
        assert "hook" in content
        assert "body" in content
        assert "cta" in content
        assert "blueprint" in content
        assert "geo_coverage" in content


class TestWriterAgentGEOCoverage:
    """测试 GEO 关键词覆盖率计算"""

    def test_calculate_geo_coverage_full(self):
        """测试完全覆盖"""
        agent = WriterAgent()

        geo_keywords = ["AI", "写作", "工具"]
        content = "这是一个关于 AI 写作工具的内容"

        coverage = agent._calculate_geo_coverage(geo_keywords, content)

        assert coverage == 1.0  # 所有关键词都覆盖

    def test_calculate_geo_coverage_partial(self):
        """测试部分覆盖"""
        agent = WriterAgent()

        geo_keywords = ["AI", "写作", "工具", "效率"]
        content = "这是一个关于 AI 写作的内容"  # 缺少"工具"和"效率"

        coverage = agent._calculate_geo_coverage(geo_keywords, content)

        assert coverage == 0.5  # 4 个关键词中覆盖 2 个

    def test_calculate_geo_coverage_none(self):
        """测试无覆盖"""
        agent = WriterAgent()

        geo_keywords = ["AI", "写作", "工具"]
        content = "这是一个完全不相关的内容"

        coverage = agent._calculate_geo_coverage(geo_keywords, content)

        assert coverage == 0.0  # 没有关键词被覆盖

    def test_calculate_geo_coverage_empty_keywords(self):
        """测试空关键词列表"""
        agent = WriterAgent()

        geo_keywords = []
        content = "这是一个测试内容"

        coverage = agent._calculate_geo_coverage(geo_keywords, content)

        assert coverage == 0.0  # 空关键词列表，覆盖率为 0


class TestWriterAgentMultipleCandidates:
    """测试多候选生成"""

    @pytest.mark.asyncio
    @patch('app.agents.content.writer_agent.ClaudeProvider.chat_completion')
    async def test_generate_multiple_candidates(self, mock_chat):
        """测试生成多个候选内容"""
        # Mock LLM 响应（每次调用返回不同内容）
        mock_chat.side_effect = [
            '{"hook": "候选1", "body": "内容1", "cta": "CTA1", "blueprint": {}}',
            '{"hook": "候选2", "body": "内容2", "cta": "CTA2", "blueprint": {}}',
            '{"hook": "候选3", "body": "内容3", "cta": "CTA3", "blueprint": {}}'
        ]

        agent = WriterAgent()

        input_data = {
            "topic": "AI 写作工具",
            "platform": "xiaohongshu",
            "references": [
                {
                    "ref_id": "ref_1",
                    "text": "示例参考",
                    "structure": {"hook": "H01", "body": "B02", "cta": "C01"}
                }
            ],
            "strategy": {"hook": "H01", "body": "B02", "cta": "C01"},
            "geo_constraints": {"keywords": ["AI", "写作"]},
            "num_candidates": 3  # 生成 3 个候选
        }

        response = await agent.execute(input_data)

        assert response.success is True
        assert len(response.data["generated_contents"]) == 3

        # 验证每个候选都不同
        hooks = [c["hook"] for c in response.data["generated_contents"]]
        assert len(set(hooks)) == 3  # 3 个不同的 hook


class TestWriterAgentPlatformSpecific:
    """测试平台特定生成"""

    @pytest.mark.asyncio
    @patch('app.agents.content.writer_agent.ClaudeProvider.chat_completion')
    async def test_xiaohongshu_platform(self, mock_chat):
        """测试小红书平台特定生成"""
        mock_chat.return_value = '{"hook": "测试", "body": "内容", "cta": "CTA", "blueprint": {}}'

        agent = WriterAgent()

        input_data = {
            "topic": "AI 写作",
            "platform": "xiaohongshu",
            "references": [{"ref_id": "ref_1", "text": "参考", "structure": {"hook": "H01", "body": "B02", "cta": "C01"}}],
            "strategy": {"hook": "H01", "body": "B02", "cta": "C01"},
            "geo_constraints": {"keywords": ["AI"]}
        }

        response = await agent.execute(input_data)

        assert response.success is True

        # 验证调用 LLM 时包含平台信息
        call_args = mock_chat.call_args
        messages = call_args[1]["messages"]
        prompt = messages[0]["content"]

        assert "xiaohongshu" in prompt.lower() or "小红书" in prompt

    @pytest.mark.asyncio
    @patch('app.agents.content.writer_agent.ClaudeProvider.chat_completion')
    async def test_douyin_platform(self, mock_chat):
        """测试抖音平台特定生成"""
        mock_chat.return_value = '{"hook": "测试", "body": "内容", "cta": "CTA", "blueprint": {}}'

        agent = WriterAgent()

        input_data = {
            "topic": "AI 写作",
            "platform": "douyin",
            "references": [{"ref_id": "ref_1", "text": "参考", "structure": {"hook": "H01", "body": "B02", "cta": "C01"}}],
            "strategy": {"hook": "H01", "body": "B02", "cta": "C01"},
            "geo_constraints": {"keywords": ["AI"]}
        }

        response = await agent.execute(input_data)

        assert response.success is True

        # 验证调用 LLM 时包含平台信息
        call_args = mock_chat.call_args
        messages = call_args[1]["messages"]
        prompt = messages[0]["content"]

        assert "douyin" in prompt.lower() or "抖音" in prompt


class TestWriterAgentErrorHandling:
    """测试错误处理"""

    @pytest.mark.asyncio
    @patch('app.agents.content.writer_agent.ClaudeProvider.chat_completion')
    async def test_llm_error_handling(self, mock_chat):
        """测试 LLM 错误处理"""
        # Mock LLM 抛出异常
        mock_chat.side_effect = Exception("LLM API error")

        agent = WriterAgent()

        input_data = {
            "topic": "AI 写作",
            "platform": "xiaohongshu",
            "references": [{"ref_id": "ref_1", "text": "参考", "structure": {"hook": "H01", "body": "B02", "cta": "C01"}}],
            "strategy": {"hook": "H01", "body": "B02", "cta": "C01"},
            "geo_constraints": {"keywords": ["AI"]}
        }

        response = await agent.execute(input_data)

        assert response.success is False
        assert "error" in response.error.lower() or "llm" in response.error.lower()

    @pytest.mark.asyncio
    @patch('app.agents.content.writer_agent.ClaudeProvider.chat_completion')
    async def test_invalid_json_response(self, mock_chat):
        """测试无效 JSON 响应处理"""
        # Mock LLM 返回无效 JSON
        mock_chat.return_value = "这不是有效的 JSON"

        agent = WriterAgent()

        input_data = {
            "topic": "AI 写作",
            "platform": "xiaohongshu",
            "references": [{"ref_id": "ref_1", "text": "参考", "structure": {"hook": "H01", "body": "B02", "cta": "C01"}}],
            "strategy": {"hook": "H01", "body": "B02", "cta": "C01"},
            "geo_constraints": {"keywords": ["AI"]}
        }

        response = await agent.execute(input_data)

        # 应该处理 JSON 解析错误
        assert response.success is False or len(response.data.get("generated_contents", [])) == 0
