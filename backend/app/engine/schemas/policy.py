from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from datetime import datetime


class Experience(BaseModel):
    """单条经验"""

    # 状态
    topic: str
    platform: str
    goal_metric: str
    geo_keywords: List[str]

    # 动作
    action: Dict[str, str]  # {"hook": "H01", "body": "B01", "cta": "C01"}

    # 奖励
    reward: float

    # 生成的内容
    generated_content: Dict[str, Any]

    # 评估结果
    evaluation: Dict[str, Any]

    # 元数据
    episode_id: str
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())
    approved: bool = False


class Episode(BaseModel):
    """一个完整的生成回合"""

    episode_id: str
    topic: str
    platform: str
    goal_metric: str

    # 生成的所有经验（一个group）
    experiences: List[Experience]

    # 统计信息
    total_experiences: int
    approved_count: int
    avg_reward: float
    max_reward: float
    min_reward: float

    # 元数据
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())
    user_id: Optional[int] = None
    project_id: Optional[int] = None


class PolicyState(BaseModel):
    """策略状态"""

    # 动作概率分布（简化版：每个动作的选择概率）
    action_probs: Dict[str, float] = Field(
        default_factory=dict,
        description="动作概率分布"
    )

    # 动作价值估计（Q值）
    action_values: Dict[str, float] = Field(
        default_factory=dict,
        description="动作价值估计"
    )

    # 访问计数
    action_counts: Dict[str, int] = Field(
        default_factory=dict,
        description="动作访问计数"
    )

    # 策略版本
    version: int = 1

    # 更新时间
    last_updated: str = Field(default_factory=lambda: datetime.now().isoformat())

    # 统计信息
    total_episodes: int = 0
    total_updates: int = 0


class GRPOUpdate(BaseModel):
    """GRPO 更新记录"""

    episode_id: str

    # 更新前后的策略状态
    policy_before: Dict[str, float]
    policy_after: Dict[str, float]

    # 相对奖励
    relative_rewards: List[float]

    # 策略梯度
    policy_gradients: Dict[str, float]

    # 更新幅度
    update_magnitude: float

    # 元数据
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())
    learning_rate: float = 0.01
