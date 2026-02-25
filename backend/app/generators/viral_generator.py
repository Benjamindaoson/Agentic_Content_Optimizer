"""
爆款内容生成器

基于模式库和强化学习的内容生成系统
"""

from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
import uuid
import numpy as np
from sqlalchemy.orm import Session

from app.viral import PatternLibrary
from app.ml.rl import (
    HybridRewardModelV2,
    DiversityScorer,
    ThompsonSamplingSelector
)
from app.db import Pattern, Generation


@dataclass
class GenerationCandidate:
    """生成候选"""
    candidate_id: str
    title: str
    text: str
    hook: str
    body: str
    cta: str

    # 模式信息
    pattern_id: str
    pattern_name: str

    # 评分
    quality_score: float
    predicted_score: float
    diversity_score: float
    hybrid_score: float

    # 元数据
    temperature: float
    generation_method: str
    metadata: Dict[str, Any]


@dataclass
class GenerationRequest:
    """生成请求"""
    category: str
    topic: str
    target_audience: Optional[str] = None
    style_preference: Optional[str] = None
    num_candidates: int = 5
    temperature: float = 0.8
    diversity_weight: float = 0.3


class ViralGenerator:
    """
    爆款内容生成器

    核心流程：
    1. 检索相关模式（PatternLibrary）
    2. 使用 Thompson Sampling 选择模式
    3. 基于模式生成多个候选
    4. 使用 RewardModel V2 评分
    5. 应用 Diversity Score 去重
    6. 返回 Top-K 候选
    """

    def __init__(
        self,
        pattern_library: PatternLibrary,
        reward_model: HybridRewardModelV2,
        diversity_scorer: DiversityScorer,
        thompson_selector: ThompsonSamplingSelector,
        llm_client: Optional[Any] = None
    ):
        self.pattern_library = pattern_library
        self.reward_model = reward_model
        self.diversity_scorer = diversity_scorer
        self.thompson_selector = thompson_selector
        self.llm_client = llm_client

    async def generate(
        self,
        request: GenerationRequest,
        db: Session
    ) -> List[GenerationCandidate]:
        """
        生成爆款内容候选

        Args:
            request: 生成请求
            db: 数据库会话

        Returns:
            候选列表（按 hybrid_score 排序）
        """
        # 1. 检索相关模式
        patterns = await self._retrieve_patterns(
            category=request.category,
            topic=request.topic,
            top_k=10
        )

        if not patterns:
            raise ValueError(f"未找到相关模式：{request.category} - {request.topic}")

        # 2. 使用 Thompson Sampling 选择模式
        selected_patterns = await self._select_patterns_with_thompson(
            patterns=patterns,
            num_select=min(5, len(patterns))
        )

        # 3. 基于模式生成候选
        candidates = []
        for pattern in selected_patterns:
            pattern_candidates = await self._generate_from_pattern(
                pattern=pattern,
                request=request,
                num_candidates=request.num_candidates // len(selected_patterns) + 1
            )
            candidates.extend(pattern_candidates)

        # 4. 使用 RewardModel V2 评分
        candidates = await self._score_candidates(candidates)

        # 5. 应用 Diversity Score
        candidates = await self._apply_diversity_scoring(
            candidates=candidates,
            diversity_weight=request.diversity_weight
        )

        # 6. 排序并返回 Top-K
        candidates.sort(key=lambda x: x.hybrid_score, reverse=True)
        top_candidates = candidates[:request.num_candidates]

        # 7. 保存生成记录
        await self._save_generations(top_candidates, request, db)

        return top_candidates

    async def _retrieve_patterns(
        self,
        category: str,
        topic: str,
        top_k: int = 10
    ) -> List[Pattern]:
        """检索相关模式"""
        # 使用 PatternLibrary 的向量检索
        patterns = await self.pattern_library.search_patterns(
            query=topic,
            category=category,
            top_k=top_k
        )
        return patterns

    async def _select_patterns_with_thompson(
        self,
        patterns: List[Pattern],
        num_select: int
    ) -> List[Pattern]:
        """使用 Thompson Sampling 选择模式"""
        # 构建 actions（每个模式是一个 action）
        actions = [
            {
                'action_id': p.pattern_id,
                'pattern': p,
                'success_rate': p.success_rate or 0.5,
                'sample_size': p.sample_size or 1
            }
            for p in patterns
        ]

        # Thompson Sampling 选择
        selected_actions = self.thompson_selector.select_actions(
            actions=actions,
            num_select=num_select
        )

        return [a['pattern'] for a in selected_actions]

    async def _generate_from_pattern(
        self,
        pattern: Pattern,
        request: GenerationRequest,
        num_candidates: int
    ) -> List[GenerationCandidate]:
        """基于模式生成候选"""
        candidates = []

        for i in range(num_candidates):
            # 使用不同的 temperature 生成多样性
            temperature = request.temperature + (i * 0.1 - 0.2)
            temperature = max(0.5, min(1.2, temperature))

            # 生成内容
            if self.llm_client:
                # 使用 LLM 生成
                content = await self._generate_with_llm(
                    pattern=pattern,
                    topic=request.topic,
                    temperature=temperature
                )
            else:
                # 使用模板生成（简化版）
                content = await self._generate_with_template(
                    pattern=pattern,
                    topic=request.topic
                )

            candidate = GenerationCandidate(
                candidate_id=str(uuid.uuid4()),
                title=content['title'],
                text=content['text'],
                hook=content['hook'],
                body=content['body'],
                cta=content['cta'],
                pattern_id=pattern.pattern_id,
                pattern_name=pattern.name,
                quality_score=0.0,  # 待评分
                predicted_score=0.0,  # 待评分
                diversity_score=0.0,  # 待评分
                hybrid_score=0.0,  # 待评分
                temperature=temperature,
                generation_method='llm' if self.llm_client else 'template',
                metadata={
                    'category': request.category,
                    'topic': request.topic,
                    'pattern_success_rate': pattern.success_rate
                }
            )

            candidates.append(candidate)

        return candidates

    async def _generate_with_llm(
        self,
        pattern: Pattern,
        topic: str,
        temperature: float
    ) -> Dict[str, str]:
        """使用 LLM 生成内容"""
        # 构建 prompt
        prompt = self._build_generation_prompt(pattern, topic)

        # 调用 LLM
        # TODO: 实际集成 OpenAI/Claude/Gemini
        response = await self.llm_client.generate(
            prompt=prompt,
            temperature=temperature,
            max_tokens=1000
        )

        # 解析响应
        content = self._parse_llm_response(response)
        return content

    async def _generate_with_template(
        self,
        pattern: Pattern,
        topic: str
    ) -> Dict[str, str]:
        """使用模板生成内容（简化版）"""
        # 替换模板中的占位符
        hook = pattern.hook_template.replace('{topic}', topic)
        cta = pattern.cta_template.replace('{topic}', topic)

        # 生成 body
        body_structure = pattern.body_structure or {}
        body_type = body_structure.get('type', 'list')

        if body_type == 'list':
            body = f"关于{topic}，这里有几个要点：\n1. 第一点\n2. 第二点\n3. 第三点"
        elif body_type == 'problem_solution':
            body = f"很多人在{topic}上遇到问题。解决方案是..."
        elif body_type == 'story':
            body = f"让我分享一个关于{topic}的故事..."
        else:
            body = f"关于{topic}的内容..."

        # 生成标题
        title = hook[:50] if len(hook) > 50 else hook

        # 组合完整文本
        text = f"{hook}\n\n{body}\n\n{cta}"

        return {
            'title': title,
            'text': text,
            'hook': hook,
            'body': body,
            'cta': cta
        }

    def _build_generation_prompt(
        self,
        pattern: Pattern,
        topic: str
    ) -> str:
        """构建生成 prompt"""
        prompt = f"""你是一个爆款内容创作专家。请基于以下模式生成一篇小红书笔记。

模式信息：
- 名称：{pattern.name}
- 描述：{pattern.description}
- Hook 模板：{pattern.hook_template}
- CTA 模板：{pattern.cta_template}
- 关键词：{', '.join(pattern.keywords or [])}

话题：{topic}

请生成：
1. 标题（吸引人的标题，不超过50字）
2. Hook（开头，引起兴趣）
3. Body（主体内容，3-5段）
4. CTA（行动号召，结尾）

输出格式（JSON）：
{{
    "title": "...",
    "hook": "...",
    "body": "...",
    "cta": "..."
}}
"""
        return prompt

    def _parse_llm_response(self, response: str) -> Dict[str, str]:
        """解析 LLM 响应"""
        import json
        try:
            content = json.loads(response)
            return {
                'title': content.get('title', ''),
                'hook': content.get('hook', ''),
                'body': content.get('body', ''),
                'cta': content.get('cta', ''),
                'text': f"{content.get('hook', '')}\n\n{content.get('body', '')}\n\n{content.get('cta', '')}"
            }
        except:
            # 解析失败，返回原始响应
            return {
                'title': response[:50],
                'hook': response[:200],
                'body': response,
                'cta': '',
                'text': response
            }

    async def _score_candidates(
        self,
        candidates: List[GenerationCandidate]
    ) -> List[GenerationCandidate]:
        """使用 RewardModel V2 评分"""
        for candidate in candidates:
            # 构建内容字典
            content = {
                'title': candidate.title,
                'text': candidate.text,
                'hook': candidate.hook,
                'body': candidate.body,
                'cta': candidate.cta
            }

            # 计算质量分数
            quality_score = await self.reward_model.calculate_quality_score(content)

            # 计算预测分数
            predicted_score = await self.reward_model.predict_viral_score(content)

            # 更新候选
            candidate.quality_score = quality_score
            candidate.predicted_score = predicted_score

        return candidates

    async def _apply_diversity_scoring(
        self,
        candidates: List[GenerationCandidate],
        diversity_weight: float
    ) -> List[GenerationCandidate]:
        """应用 Diversity Score"""
        # 计算每个候选的多样性分数
        for i, candidate in enumerate(candidates):
            # 与其他候选比较
            other_texts = [c.text for j, c in enumerate(candidates) if j != i]

            diversity_score = await self.diversity_scorer.calculate_diversity(
                text=candidate.text,
                reference_texts=other_texts
            )

            candidate.diversity_score = diversity_score

            # 计算混合分数
            candidate.hybrid_score = (
                (1 - diversity_weight) * candidate.predicted_score +
                diversity_weight * diversity_score
            )

        return candidates

    async def _save_generations(
        self,
        candidates: List[GenerationCandidate],
        request: GenerationRequest,
        db: Session
    ):
        """保存生成记录"""
        for rank, candidate in enumerate(candidates):
            generation = Generation(
                generation_id=candidate.candidate_id,
                pattern_id=candidate.pattern_id,
                platform='xiaohongshu',
                category=request.category,
                title=candidate.title,
                text=candidate.text,
                hook=candidate.hook,
                body=candidate.body,
                cta=candidate.cta,
                quality_score=candidate.quality_score,
                predicted_viral_score=candidate.predicted_score,
                diversity_score=candidate.diversity_score,
                hybrid_score=candidate.hybrid_score,
                generation_params={
                    'temperature': candidate.temperature,
                    'method': candidate.generation_method,
                    'topic': request.topic,
                    'target_audience': request.target_audience,
                    'style_preference': request.style_preference
                },
                rank=rank + 1,
                status='generated',
                generated_at=datetime.now()
            )

            db.add(generation)

        db.commit()
