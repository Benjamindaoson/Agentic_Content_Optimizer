from pydantic import BaseModel, Field, validator
from typing import List, Optional, Dict, Any
from enum import Enum


class EvaluationDimension(str, Enum):
    """评估维度"""
    CREATIVITY = "creativity"  # 创意性
    EXECUTABILITY = "executability"  # 可执行性
    GEO_OPTIMIZATION = "geo_optimization"  # GEO优化
    PLATFORM_FIT = "platform_fit"  # 平台适配
    ENGAGEMENT_POTENTIAL = "engagement_potential"  # 互动潜力


class ApprovalStatus(str, Enum):
    """审批状态"""
    APPROVED = "approved"  # 通过
    REJECTED = "rejected"  # 拒绝
    NEEDS_REVISION = "needs_revision"  # 需要修改


class DimensionScore(BaseModel):
    """单个维度评分"""
    dimension: EvaluationDimension
    score: float = Field(..., ge=0.0, le=1.0, description="评分（0-1）")
    reasoning: str = Field(..., min_length=10, description="评分理由")
    suggestions: Optional[List[str]] = Field(default_factory=list, description="改进建议")


class CriticEvaluation(BaseModel):
    """Critic 评估结果"""

    # 多维度评分
    dimension_scores: List[DimensionScore] = Field(..., min_items=5, max_items=5)

    # 综合评分
    overall_score: float = Field(..., ge=0.0, le=1.0, description="综合评分（0-1）")

    # 审批决策
    approval_status: ApprovalStatus

    # 评估摘要
    summary: str = Field(..., min_length=20, description="评估摘要")

    # 关键问题
    critical_issues: List[str] = Field(default_factory=list, description="关键问题")

    # 亮点
    highlights: List[str] = Field(default_factory=list, description="内容亮点")

    # 改进建议
    improvement_suggestions: List[str] = Field(default_factory=list, description="改进建议")

    # 元数据
    evaluation_time_ms: Optional[int] = None
    model_version: Optional[str] = None

    @validator('dimension_scores')
    def validate_dimensions(cls, v):
        """验证所有维度都存在"""
        dimensions = {score.dimension for score in v}
        required_dimensions = set(EvaluationDimension)

        if dimensions != required_dimensions:
            missing = required_dimensions - dimensions
            raise ValueError(f"缺少评估维度: {missing}")

        return v

    @validator('overall_score')
    def validate_overall_score(cls, v, values):
        """验证综合评分与维度评分的一致性"""
        if 'dimension_scores' in values:
            dimension_scores = values['dimension_scores']
            avg_score = sum(s.score for s in dimension_scores) / len(dimension_scores)

            # 允许10%的偏差
            if abs(v - avg_score) > 0.1:
                raise ValueError(f"综合评分 {v} 与维度平均分 {avg_score:.2f} 偏差过大")

        return v


class RewardComponents(BaseModel):
    """奖励组成部分"""

    # 质量奖励（来自 Critic）
    quality_reward: float = Field(..., ge=0.0, le=1.0, description="质量奖励")

    # 预测奖励（基于历史数据）
    predicted_engagement: float = Field(..., ge=0.0, le=1.0, description="预测互动率")
    predicted_completion: float = Field(..., ge=0.0, le=1.0, description="预测完播率")
    predicted_conversion: float = Field(..., ge=0.0, le=1.0, description="预测转化率")

    # 策略多样性奖励
    diversity_bonus: float = Field(default=0.0, ge=0.0, le=0.2, description="多样性奖励")

    # GEO 优化奖励
    geo_bonus: float = Field(default=0.0, ge=0.0, le=0.2, description="GEO优化奖励")

    # 创新奖励
    innovation_bonus: float = Field(default=0.0, ge=0.0, le=0.2, description="创新奖励")


class RewardScore(BaseModel):
    """奖励分数"""

    # 奖励组成
    components: RewardComponents

    # 总奖励
    total_reward: float = Field(..., ge=0.0, le=2.0, description="总奖励（0-2）")

    # 目标权重
    goal_weights: Dict[str, float] = Field(
        default_factory=lambda: {
            "engagement": 0.4,
            "completion": 0.3,
            "conversion": 0.3
        },
        description="目标权重"
    )

    # 计算详情
    calculation_details: Optional[Dict[str, Any]] = None

    @validator('total_reward')
    def validate_total_reward(cls, v, values):
        """验证总奖励计算"""
        if 'components' in values and 'goal_weights' in values:
            comp = values['components']
            weights = values['goal_weights']

            # 计算预期总奖励
            predicted_reward = (
                comp.predicted_engagement * weights.get("engagement", 0.4) +
                comp.predicted_completion * weights.get("completion", 0.3) +
                comp.predicted_conversion * weights.get("conversion", 0.3)
            )

            expected_total = (
                comp.quality_reward * 0.5 +  # 质量占50%
                predicted_reward * 0.5 +      # 预测占50%
                comp.diversity_bonus +
                comp.geo_bonus +
                comp.innovation_bonus
            )

            # 允许5%的偏差
            if abs(v - expected_total) > 0.1:
                raise ValueError(f"总奖励 {v} 与计算值 {expected_total:.2f} 不一致")

        return v


class CriticResult(BaseModel):
    """Critic 完整结果"""
    content_id: str
    evaluation: CriticEvaluation
    reward: RewardScore
    approved: bool

    # 元数据
    action: Dict[str, str]
    timestamp: Optional[str] = None
