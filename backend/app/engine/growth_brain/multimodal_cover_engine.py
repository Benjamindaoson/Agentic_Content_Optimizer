"""
多模态封面引擎 (Multimodal Cover Engine)

负责：
1. 封面自动生成（SD/MJ/DALL·E）
2. 点击率预测
3. A/B 测试
4. 风格优化
"""

import logging
from typing import List, Dict, Optional, Tuple
from datetime import datetime
from dataclasses import dataclass
from enum import Enum
import asyncio
from PIL import Image
import io

from sqlalchemy import Column, String, Integer, Float, DateTime, Boolean, JSON, Enum as SQLEnum, Text, LargeBinary
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_
from app.core.database import Base

logger = logging.getLogger(__name__)


class CoverGenerator(str, Enum):
    """封面生成器"""
    STABLE_DIFFUSION = 'stable_diffusion'
    MIDJOURNEY = 'midjourney'
    DALLE = 'dalle'
    MANUAL = 'manual'


class CoverStyle(str, Enum):
    """封面风格"""
    REALISTIC = 'realistic'  # 写实
    ILLUSTRATION = 'illustration'  # 插画
    MINIMALIST = 'minimalist'  # 极简
    VIBRANT = 'vibrant'  # 鲜艳
    ELEGANT = 'elegant'  # 优雅


# ==================== 数据库模型 ====================

class GeneratedCover(Base):
    """生成的封面表"""
    __tablename__ = 'generated_covers'

    cover_id = Column(String(64), primary_key=True, comment='封面ID')

    # 生成信息
    generator = Column(SQLEnum(CoverGenerator), nullable=False, comment='生成器')
    prompt = Column(Text, comment='生成提示词')
    negative_prompt = Column(Text, comment='负面提示词')
    style = Column(SQLEnum(CoverStyle), comment='风格')

    # 图片信息
    image_path = Column(String(1024), comment='图片路径')
    image_url = Column(String(1024), comment='图片URL')
    width = Column(Integer, comment='宽度')
    height = Column(Integer, comment='高度')
    aspect_ratio = Column(String(16), comment='宽高比')

    # 特征
    dominant_colors = Column(JSON, comment='主色调')
    color_distribution = Column(JSON, comment='色彩分布')
    has_face = Column(Boolean, default=False, comment='是否有人脸')
    face_position = Column(JSON, comment='人脸位置')
    text_overlay = Column(Boolean, default=False, comment='是否有文字叠加')
    text_content = Column(Text, comment='文字内容')

    # 预测
    predicted_ctr = Column(Float, comment='预测点击率')
    predicted_engagement = Column(Float, comment='预测互动率')

    # 实际表现
    actual_ctr = Column(Float, comment='实际点击率')
    actual_engagement = Column(Float, comment='实际互动率')
    impressions = Column(Integer, default=0, comment='曝光数')
    clicks = Column(Integer, default=0, comment='点击数')

    # 元数据
    created_at = Column(DateTime, default=datetime.now, comment='创建时间')
    meta_data = Column(JSON, comment='其他元数据')


class CoverABTest(Base):
    """封面 A/B 测试表"""
    __tablename__ = 'cover_ab_tests'

    test_id = Column(String(64), primary_key=True, comment='测试ID')

    # 测试信息
    generation_id = Column(String(64), comment='生成ID')
    cover_variants = Column(JSON, comment='封面变体列表')
    variant_count = Column(Integer, comment='变体数量')

    # 流量分配
    traffic_split = Column(JSON, comment='流量分配')
    test_duration_hours = Column(Integer, default=1, comment='测试时长（小时）')

    # 状态
    status = Column(String(32), default='running', comment='状态')
    started_at = Column(DateTime, comment='开始时间')
    ended_at = Column(DateTime, comment='结束时间')

    # 结果
    winner_cover_id = Column(String(64), comment='胜出封面ID')
    winner_ctr = Column(Float, comment='胜出点击率')
    confidence = Column(Float, comment='置信度')

    # 元数据
    created_at = Column(DateTime, default=datetime.now, comment='创建时间')
    meta_data = Column(JSON, comment='其他元数据')


class CoverFeatures(Base):
    """封面特征表"""
    __tablename__ = 'cover_features'

    feature_id = Column(String(64), primary_key=True, comment='特征ID')
    cover_id = Column(String(64), nullable=False, comment='封面ID')

    # 色彩特征
    avg_brightness = Column(Float, comment='平均亮度')
    avg_saturation = Column(Float, comment='平均饱和度')
    color_variance = Column(Float, comment='色彩方差')
    dominant_hue = Column(Float, comment='主色调')

    # 构图特征
    composition_score = Column(Float, comment='构图分数')
    rule_of_thirds = Column(Float, comment='三分法得分')
    symmetry_score = Column(Float, comment='对称性得分')

    # 内容特征
    face_count = Column(Integer, default=0, comment='人脸数量')
    face_area_ratio = Column(Float, comment='人脸面积占比')
    text_area_ratio = Column(Float, comment='文字面积占比')
    object_count = Column(Integer, comment='物体数量')

    # 复杂度
    edge_density = Column(Float, comment='边缘密度')
    texture_complexity = Column(Float, comment='纹理复杂度')

    # 元数据
    extracted_at = Column(DateTime, default=datetime.now, comment='提取时间')


@dataclass
class CoverCandidate:
    """封面候选"""
    cover_id: str
    image_path: str
    generator: CoverGenerator
    style: CoverStyle
    predicted_ctr: float
    features: Dict


@dataclass
class ABTestResult:
    """A/B 测试结果"""
    winner_cover_id: str
    winner_ctr: float
    variants: List[Dict]
    confidence: float
    is_significant: bool


class MultimodalCoverEngine:
    """
    多模态封面引擎

    功能：
    1. 封面自动生成
    2. 点击率预测
    3. A/B 测试
    4. 风格优化
    """

    def __init__(
        self,
        db: Session,
        candidate_count: int = 5,
        test_duration_hours: int = 1
    ):
        self.db = db
        self.candidate_count = candidate_count
        self.test_duration_hours = test_duration_hours

    # ==================== 封面生成 ====================

    async def generate_cover_candidates(
        self,
        title: str,
        text: str,
        style: CoverStyle = None,
        generators: List[CoverGenerator] = None
    ) -> List[CoverCandidate]:
        """
        生成封面候选

        Args:
            title: 标题
            text: 正文
            style: 风格
            generators: 生成器列表

        Returns:
            封面候选列表
        """
        if generators is None:
            generators = [
                CoverGenerator.STABLE_DIFFUSION,
                CoverGenerator.DALLE
            ]

        candidates = []

        # 1. 生成提示词
        prompt = self._create_prompt(title, text, style)

        # 2. 使用不同生成器生成
        for generator in generators:
            if generator == CoverGenerator.STABLE_DIFFUSION:
                covers = await self._generate_with_sd(prompt, style)
                candidates.extend(covers)
            elif generator == CoverGenerator.DALLE:
                covers = await self._generate_with_dalle(prompt, style)
                candidates.extend(covers)
            elif generator == CoverGenerator.MIDJOURNEY:
                covers = await self._generate_with_mj(prompt, style)
                candidates.extend(covers)

        # 3. 提取特征
        for candidate in candidates:
            features = await self._extract_features(candidate.image_path)
            candidate.features = features

        # 4. 预测点击率
        for candidate in candidates:
            ctr = await self._predict_ctr(candidate)
            candidate.predicted_ctr = ctr

        # 5. 排序并选择 Top N
        candidates.sort(key=lambda x: x.predicted_ctr, reverse=True)
        selected = candidates[:self.candidate_count]

        logger.info(f"✅ 生成 {len(selected)} 个封面候选")

        return selected

    def _create_prompt(self, title: str, text: str, style: CoverStyle = None) -> str:
        """创建生成提示词"""
        # 简化版：基于标题和正文生成提示词
        prompt = f"Create a cover image for: {title}"

        if style:
            style_prompts = {
                CoverStyle.REALISTIC: "photorealistic, high quality, detailed",
                CoverStyle.ILLUSTRATION: "illustration, artistic, colorful",
                CoverStyle.MINIMALIST: "minimalist, clean, simple",
                CoverStyle.VIBRANT: "vibrant colors, energetic, bold",
                CoverStyle.ELEGANT: "elegant, sophisticated, refined"
            }
            prompt += f", {style_prompts.get(style, '')}"

        return prompt

    async def _generate_with_sd(
        self,
        prompt: str,
        style: CoverStyle = None
    ) -> List[CoverCandidate]:
        """使用 Stable Diffusion 生成"""
        import uuid

        # TODO: 实际实现需要调用 SD API
        # 这里是模拟数据

        candidates = []

        for i in range(2):
            cover_id = f"cover_{uuid.uuid4().hex[:16]}"
            image_path = f"/tmp/covers/{cover_id}.png"

            # 模拟生成
            # actual_image = await sd_api.generate(prompt)
            # actual_image.save(image_path)

            candidate = CoverCandidate(
                cover_id=cover_id,
                image_path=image_path,
                generator=CoverGenerator.STABLE_DIFFUSION,
                style=style or CoverStyle.REALISTIC,
                predicted_ctr=0.0,  # 稍后预测
                features={}
            )

            candidates.append(candidate)

        return candidates

    async def _generate_with_dalle(
        self,
        prompt: str,
        style: CoverStyle = None
    ) -> List[CoverCandidate]:
        """
        使用 DALL-E 3 生成封面。
        自动下载图片到本地 /tmp/covers/ 并返回路径。
        """
        import uuid
        import httpx
        import pathlib
        from app.core.config import get_settings
        settings = get_settings()

        if not settings.OPENAI_API_KEY:
            logger.warning("OPENAI_API_KEY not set, DALL-E generation skipped")
            return []

        style_suffix = {
            CoverStyle.REALISTIC: "photorealistic, high quality photography",
            CoverStyle.ILLUSTRATION: "cute illustration, flat vector design, clean lines",
            CoverStyle.MINIMALIST: "minimalist design, clean white background, simple composition",
            CoverStyle.VIBRANT: "vibrant bold colors, eye-catching, high contrast",
            CoverStyle.ELEGANT: "elegant luxury aesthetic, muted tones, refined",
        }
        suffix = style_suffix.get(style, "modern and visually appealing")

        full_prompt = (
            f"{prompt}\n\n"
            f"Style: {suffix}. "
            f"Aspect: portrait 3:4. No text or watermarks. "
            f"Suitable for Xiaohongshu (Little Red Book) cover."
        )

        candidates = []
        try:
            async with httpx.AsyncClient(timeout=60) as client:
                resp = await client.post(
                    "https://api.openai.com/v1/images/generations",
                    headers={
                        "Authorization": f"Bearer {settings.OPENAI_API_KEY}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": "dall-e-3",
                        "prompt": full_prompt[:4000],
                        "n": 1,
                        "size": "1024x1792",
                        "quality": "standard",
                    },
                )
                resp.raise_for_status()
                data = resp.json()

            covers_dir = pathlib.Path("/tmp/covers")
            covers_dir.mkdir(parents=True, exist_ok=True)

            for img in data.get("data", []):
                cover_id = f"cover_{uuid.uuid4().hex[:16]}"
                image_url = img.get("url", "")
                image_path = str(covers_dir / f"{cover_id}.png")

                if image_url:
                    async with httpx.AsyncClient(timeout=30) as dl_client:
                        img_resp = await dl_client.get(image_url)
                        img_resp.raise_for_status()
                        pathlib.Path(image_path).write_bytes(img_resp.content)

                candidates.append(CoverCandidate(
                    cover_id=cover_id,
                    image_path=image_path,
                    generator=CoverGenerator.DALLE,
                    style=style or CoverStyle.ILLUSTRATION,
                    predicted_ctr=0.0,
                    features={"dalle_prompt": full_prompt[:200]},
                ))

            logger.info(f"DALL-E generated {len(candidates)} covers")

        except Exception as e:
            logger.error(f"DALL-E generation failed: {e}", exc_info=True)

        return candidates

    async def _generate_with_mj(
        self,
        prompt: str,
        style: CoverStyle = None
    ) -> List[CoverCandidate]:
        """使用 MidJourney 生成"""
        # TODO: 实际实现需要调用 MJ API
        return []

    # ==================== 特征提取 ====================

    async def _extract_features(self, image_path: str) -> Dict:
        """提取封面特征"""
        # TODO: 实际实现需要使用 CV 库
        # 这里是模拟数据

        features = {
            'avg_brightness': 0.65,
            'avg_saturation': 0.55,
            'color_variance': 0.3,
            'dominant_hue': 180.0,
            'composition_score': 0.75,
            'face_count': 1,
            'face_area_ratio': 0.25,
            'text_area_ratio': 0.1,
            'edge_density': 0.4,
            'texture_complexity': 0.6
        }

        return features

    # ==================== 点击率预测 ====================

    async def _predict_ctr(self, candidate: CoverCandidate) -> float:
        """Predict CTR using trained model with heuristic fallback."""
        features = candidate.features

        # Try using trained LightGBM / metric predictor
        try:
            from app.ml.rl.real_metric_predictors import RealMetricPredictorEnsemble
            predictor = RealMetricPredictorEnsemble()
            content = {
                'hook': features.get('title_text', ''),
                'body': str(features),
                'cta': '',
            }
            result = predictor.predict_all(content)
            return float(result.get('ctr', 0.5))
        except Exception:
            pass

        # Heuristic fallback
        ctr = 0.5
        if 0.4 < features.get('avg_brightness', 0) < 0.7:
            ctr += 0.1
        if 0.4 < features.get('avg_saturation', 0) < 0.7:
            ctr += 0.1
        if features.get('face_count', 0) > 0:
            ctr += 0.15
        if features.get('composition_score', 0) > 0.7:
            ctr += 0.1
        return min(ctr, 1.0)

    # ==================== A/B 测试 ====================

    async def run_ab_test(
        self,
        generation_id: str,
        candidates: List[CoverCandidate],
        traffic_split: Dict[str, float] = None
    ) -> str:
        """
        运行 A/B 测试

        Args:
            generation_id: 生成ID
            candidates: 封面候选列表
            traffic_split: 流量分配

        Returns:
            测试ID
        """
        import uuid

        if traffic_split is None:
            # 均分流量
            split_ratio = 1.0 / len(candidates)
            traffic_split = {
                c.cover_id: split_ratio
                for c in candidates
            }

        # 创建测试
        test = CoverABTest(
            test_id=f"test_{uuid.uuid4().hex[:16]}",
            generation_id=generation_id,
            cover_variants=[
                {
                    'cover_id': c.cover_id,
                    'generator': c.generator.value,
                    'predicted_ctr': c.predicted_ctr
                }
                for c in candidates
            ],
            variant_count=len(candidates),
            traffic_split=traffic_split,
            test_duration_hours=self.test_duration_hours,
            status='running',
            started_at=datetime.now()
        )

        self.db.add(test)
        self.db.commit()

        logger.info(f"✅ 启动 A/B 测试: {test.test_id}, {len(candidates)} 个变体")

        return test.test_id

    async def analyze_ab_test(self, test_id: str) -> ABTestResult:
        """
        分析 A/B 测试结果

        Args:
            test_id: 测试ID

        Returns:
            测试结果
        """
        # 获取测试
        test = self.db.query(CoverABTest).filter(
            CoverABTest.test_id == test_id
        ).first()

        if not test:
            raise ValueError(f"测试不存在: {test_id}")

        # 获取各变体的实际数据
        variants = []

        for variant in test.cover_variants:
            cover_id = variant['cover_id']

            # 获取封面数据
            cover = self.db.query(GeneratedCover).filter(
                GeneratedCover.cover_id == cover_id
            ).first()

            if cover and cover.impressions > 0:
                actual_ctr = cover.clicks / cover.impressions
            else:
                actual_ctr = 0.0

            variants.append({
                'cover_id': cover_id,
                'impressions': cover.impressions if cover else 0,
                'clicks': cover.clicks if cover else 0,
                'ctr': actual_ctr
            })

        # 找出胜者
        winner = max(variants, key=lambda x: x['ctr'])

        # 计算置信度（简化版）
        confidence = 0.95 if winner['impressions'] > 100 else 0.7

        # 判断显著性
        is_significant = winner['ctr'] > 0.05 and confidence > 0.9

        result = ABTestResult(
            winner_cover_id=winner['cover_id'],
            winner_ctr=winner['ctr'],
            variants=variants,
            confidence=confidence,
            is_significant=is_significant
        )

        # 更新测试结果
        test.status = 'completed'
        test.ended_at = datetime.now()
        test.winner_cover_id = winner['cover_id']
        test.winner_ctr = winner['ctr']
        test.confidence = confidence

        self.db.commit()

        logger.info(f"✅ A/B 测试完成: 胜者 {winner['cover_id']}, CTR={winner['ctr']:.3f}")

        return result

    # ==================== 风格优化 ====================

    async def optimize_style(
        self,
        account_id: str,
        historical_days: int = 30
    ) -> CoverStyle:
        """
        优化封面风格

        Args:
            account_id: 账号ID
            historical_days: 历史天数

        Returns:
            推荐风格
        """
        cutoff_time = datetime.now() - timedelta(days=historical_days)

        # 统计各风格的平均 CTR
        style_performance = {}

        for style in CoverStyle:
            covers = self.db.query(GeneratedCover).filter(
                and_(
                    GeneratedCover.style == style,
                    GeneratedCover.created_at >= cutoff_time,
                    GeneratedCover.actual_ctr.isnot(None)
                )
            ).all()

            if covers:
                avg_ctr = sum(c.actual_ctr for c in covers) / len(covers)
                style_performance[style] = avg_ctr

        if not style_performance:
            return CoverStyle.REALISTIC

        # 返回表现最好的风格
        best_style = max(style_performance.items(), key=lambda x: x[1])[0]

        logger.info(f"✅ 推荐风格: {best_style.value}")

        return best_style


# ==================== 使用示例 ====================

async def example_usage():
    """使用示例"""
    from app.db import get_db

    db = next(get_db())

    # 1. 创建引擎
    engine = MultimodalCoverEngine(
        db=db,
        candidate_count=5,
        test_duration_hours=1
    )

    # 2. 生成封面候选
    candidates = await engine.generate_cover_candidates(
        title="冬季护肤攻略",
        text="分享我的冬季护肤心得...",
        style=CoverStyle.REALISTIC
    )

    print(f"生成 {len(candidates)} 个封面候选")

    # 3. 运行 A/B 测试
    test_id = await engine.run_ab_test(
        generation_id='gen_123',
        candidates=candidates[:3]  # 测试前 3 个
    )

    print(f"启动 A/B 测试: {test_id}")

    # 4. 分析结果（1小时后）
    # result = await engine.analyze_ab_test(test_id)
    # print(f"胜者: {result.winner_cover_id}, CTR={result.winner_ctr:.3f}")

    # 5. 优化风格
    best_style = await engine.optimize_style('account_001')
    print(f"推荐风格: {best_style.value}")
