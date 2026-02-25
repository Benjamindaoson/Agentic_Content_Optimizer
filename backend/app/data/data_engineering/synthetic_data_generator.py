"""
合成数据生成器

自动生成高质量的训练数据：
1. 主题生成 - 生成多样化的内容主题
2. 内容生成 - 生成不同质量等级的内容
3. 偏好对生成 - 生成用于 DPO 训练的偏好对
4. 评估数据生成 - 生成用于 Benchmark 的测试数据
"""

from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass
from datetime import datetime
import random
import logging
import json
import asyncio

from app.engine.llm.unified import UnifiedLLM

logger = logging.getLogger(__name__)


@dataclass
class SyntheticSample:
    """合成数据样本"""
    sample_id: str
    topic: str
    platform: str
    content: str
    quality_score: float
    metadata: Dict[str, Any]
    created_at: datetime


@dataclass
class PreferencePair:
    """偏好对（用于 DPO）"""
    pair_id: str
    topic: str
    platform: str
    chosen_content: str  # 更好的内容
    rejected_content: str  # 较差的内容
    chosen_score: float
    rejected_score: float
    metadata: Dict[str, Any]


class SyntheticDataGenerator:
    """
    合成数据生成器

    核心功能：
    1. 生成多样化的主题
    2. 生成不同质量的内容
    3. 生成偏好对
    4. 生成评估数据
    """

    def __init__(self, llm: Optional[UnifiedLLM] = None):
        """初始化合成数据生成器

        Args:
            llm: LLM 实例
        """
        self.llm = llm or UnifiedLLM()

        # 平台列表
        self.platforms = ["xiaohongshu", "weibo", "douyin"]

        # 主题类别
        self.topic_categories = [
            "AI 工具", "效率提升", "内容创作", "个人成长",
            "职场技能", "副业赚钱", "学习方法", "时间管理",
            "写作技巧", "视频制作", "社交媒体", "品牌营销"
        ]

        # 质量等级
        self.quality_levels = {
            "excellent": (8.5, 10.0),
            "good": (7.0, 8.5),
            "average": (5.0, 7.0),
            "poor": (3.0, 5.0)
        }

        logger.info("SyntheticDataGenerator initialized")

    async def generate_topics(
        self,
        num_topics: int = 100,
        categories: Optional[List[str]] = None
    ) -> List[str]:
        """生成多样化的主题

        Args:
            num_topics: 生成主题数量
            categories: 主题类别列表

        Returns:
            主题列表
        """
        logger.info(f"Generating {num_topics} topics...")

        categories = categories or self.topic_categories
        topics = []

        # 每个类别生成多个主题
        topics_per_category = num_topics // len(categories)

        for category in categories:
            prompt = f"""请生成 {topics_per_category} 个关于「{category}」的具体主题。

要求：
1. 主题要具体、有吸引力
2. 适合在社交媒体上讨论
3. 每个主题一行
4. 不要编号

示例：
如何用 ChatGPT 提升工作效率 10 倍
5 个让你脱颖而出的职场技能
从 0 到 1 打造个人 IP 的完整指南

请生成："""

            try:
                response = await self.llm.chat(
                    messages=[{"role": "user", "content": prompt}],
                    provider="claude",
                    model="haiku-4.5",
                    temperature=0.9,
                    max_tokens=1000
                )

                # 解析主题
                generated_topics = [
                    line.strip()
                    for line in response.strip().split('\n')
                    if line.strip() and not line.strip().startswith('#')
                ]

                topics.extend(generated_topics[:topics_per_category])

            except Exception as e:
                logger.error(f"Failed to generate topics for {category}: {e}")

        logger.info(f"Generated {len(topics)} topics")
        return topics[:num_topics]

    async def generate_content(
        self,
        topic: str,
        platform: str,
        quality_level: str = "good"
    ) -> SyntheticSample:
        """生成指定质量等级的内容

        Args:
            topic: 主题
            platform: 平台
            quality_level: 质量等级 (excellent/good/average/poor)

        Returns:
            合成数据样本
        """
        # 根据质量等级调整生成参数
        if quality_level == "excellent":
            temperature = 0.7
            instructions = "请生成一篇高质量、有深度、有价值的内容。"
        elif quality_level == "good":
            temperature = 0.8
            instructions = "请生成一篇质量良好、内容充实的内容。"
        elif quality_level == "average":
            temperature = 0.9
            instructions = "请生成一篇普通质量的内容。"
        else:  # poor
            temperature = 1.0
            instructions = "请生成一篇质量较差、内容空洞的内容。"

        # 平台特定要求
        platform_requirements = {
            "xiaohongshu": "小红书风格，使用 emoji，分段清晰",
            "weibo": "微博风格，简洁有力，140-280字",
            "douyin": "抖音风格，口语化，适合短视频"
        }

        prompt = f"""主题：{topic}
平台：{platform}

{instructions}

要求：
1. {platform_requirements.get(platform, '')}
2. 内容要吸引人
3. 结构清晰

请生成内容："""

        try:
            content = await self.llm.chat(
                messages=[{"role": "user", "content": prompt}],
                provider="claude",
                model="sonnet-4.5",
                temperature=temperature,
                max_tokens=2000
            )

            # 生成质量分数
            min_score, max_score = self.quality_levels[quality_level]
            quality_score = random.uniform(min_score, max_score)

            sample = SyntheticSample(
                sample_id=f"syn_{datetime.now().timestamp()}",
                topic=topic,
                platform=platform,
                content=content,
                quality_score=quality_score,
                metadata={
                    "quality_level": quality_level,
                    "temperature": temperature
                },
                created_at=datetime.now()
            )

            return sample

        except Exception as e:
            logger.error(f"Failed to generate content: {e}")
            raise

    async def generate_preference_pair(
        self,
        topic: str,
        platform: str
    ) -> PreferencePair:
        """生成偏好对（用于 DPO 训练）

        Args:
            topic: 主题
            platform: 平台

        Returns:
            偏好对
        """
        logger.debug(f"Generating preference pair for: {topic}")

        # 生成高质量内容（chosen）
        chosen_sample = await self.generate_content(
            topic=topic,
            platform=platform,
            quality_level="excellent"
        )

        # 生成低质量内容（rejected）
        rejected_sample = await self.generate_content(
            topic=topic,
            platform=platform,
            quality_level="average"
        )

        pair = PreferencePair(
            pair_id=f"pair_{datetime.now().timestamp()}",
            topic=topic,
            platform=platform,
            chosen_content=chosen_sample.content,
            rejected_content=rejected_sample.content,
            chosen_score=chosen_sample.quality_score,
            rejected_score=rejected_sample.quality_score,
            metadata={
                "chosen_quality": "excellent",
                "rejected_quality": "average"
            }
        )

        return pair

    async def generate_dataset(
        self,
        num_samples: int = 100,
        platforms: Optional[List[str]] = None,
        quality_distribution: Optional[Dict[str, float]] = None
    ) -> List[SyntheticSample]:
        """生成完整的数据集

        Args:
            num_samples: 样本数量
            platforms: 平台列表
            quality_distribution: 质量分布 {quality_level: ratio}

        Returns:
            合成数据样本列表
        """
        logger.info(f"Generating dataset with {num_samples} samples...")

        platforms = platforms or self.platforms

        # 默认质量分布
        if quality_distribution is None:
            quality_distribution = {
                "excellent": 0.2,
                "good": 0.4,
                "average": 0.3,
                "poor": 0.1
            }

        # 生成主题
        topics = await self.generate_topics(num_topics=num_samples)

        # 生成样本
        samples = []

        for i, topic in enumerate(topics):
            # 随机选择平台
            platform = random.choice(platforms)

            # 根据分布选择质量等级
            quality_level = random.choices(
                list(quality_distribution.keys()),
                weights=list(quality_distribution.values())
            )[0]

            try:
                sample = await self.generate_content(
                    topic=topic,
                    platform=platform,
                    quality_level=quality_level
                )

                samples.append(sample)

                if (i + 1) % 10 == 0:
                    logger.info(f"Generated {i + 1}/{num_samples} samples")

            except Exception as e:
                logger.error(f"Failed to generate sample {i}: {e}")

        logger.info(f"Dataset generation complete: {len(samples)} samples")
        return samples

    async def generate_preference_dataset(
        self,
        num_pairs: int = 50,
        platforms: Optional[List[str]] = None
    ) -> List[PreferencePair]:
        """生成偏好对数据集（用于 DPO）

        Args:
            num_pairs: 偏好对数量
            platforms: 平台列表

        Returns:
            偏好对列表
        """
        logger.info(f"Generating preference dataset with {num_pairs} pairs...")

        platforms = platforms or self.platforms

        # 生成主题
        topics = await self.generate_topics(num_topics=num_pairs)

        # 生成偏好对
        pairs = []

        for i, topic in enumerate(topics):
            platform = random.choice(platforms)

            try:
                pair = await self.generate_preference_pair(
                    topic=topic,
                    platform=platform
                )

                pairs.append(pair)

                if (i + 1) % 5 == 0:
                    logger.info(f"Generated {i + 1}/{num_pairs} pairs")

            except Exception as e:
                logger.error(f"Failed to generate pair {i}: {e}")

        logger.info(f"Preference dataset generation complete: {len(pairs)} pairs")
        return pairs

    def save_dataset(
        self,
        samples: List[SyntheticSample],
        output_file: str
    ):
        """保存数据集到文件

        Args:
            samples: 样本列表
            output_file: 输出文件路径
        """
        data = [
            {
                "sample_id": sample.sample_id,
                "topic": sample.topic,
                "platform": sample.platform,
                "content": sample.content,
                "quality_score": sample.quality_score,
                "metadata": sample.metadata,
                "created_at": sample.created_at.isoformat()
            }
            for sample in samples
        ]

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        logger.info(f"Dataset saved to {output_file}")

    def save_preference_dataset(
        self,
        pairs: List[PreferencePair],
        output_file: str
    ):
        """保存偏好对数据集到文件

        Args:
            pairs: 偏好对列表
            output_file: 输出文件路径
        """
        data = [
            {
                "pair_id": pair.pair_id,
                "topic": pair.topic,
                "platform": pair.platform,
                "chosen_content": pair.chosen_content,
                "rejected_content": pair.rejected_content,
                "chosen_score": pair.chosen_score,
                "rejected_score": pair.rejected_score,
                "metadata": pair.metadata
            }
            for pair in pairs
        ]

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        logger.info(f"Preference dataset saved to {output_file}")


# 全局实例（单例）
_synthetic_data_generator_instance: Optional[SyntheticDataGenerator] = None


def get_synthetic_data_generator() -> SyntheticDataGenerator:
    """获取合成数据生成器实例（单例）

    Returns:
        SyntheticDataGenerator 实例
    """
    global _synthetic_data_generator_instance

    if _synthetic_data_generator_instance is None:
        _synthetic_data_generator_instance = SyntheticDataGenerator()
        logger.info("Global SyntheticDataGenerator instance created")

    return _synthetic_data_generator_instance
