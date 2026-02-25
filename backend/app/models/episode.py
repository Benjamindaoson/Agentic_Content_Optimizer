from sqlalchemy import Column, String, Integer, ForeignKey, Float, Boolean, JSON, Text
from sqlalchemy.orm import relationship
from app.models.base import BaseModel


class Episode(BaseModel):
    """飞轮事实表 - 记录每次策略采样"""

    __tablename__ = "fact_episodes"

    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False, index=True)
    episode_id = Column(String(50), unique=True, nullable=False, index=True)
    trace_id = Column(String(50), nullable=False, index=True)
    topic_id = Column(String(100), nullable=False)

    # 采样的动作组
    group_actions = Column(JSON, nullable=False)  # [{hook, body, cta}, ...]
    pred_rewards = Column(JSON, nullable=False)  # [0.75, 0.82, ...]
    ranked_actions = Column(JSON, nullable=False)

    # 策略更新
    policy_update_summary = Column(JSON)
    policy_version = Column(String(50))

    # 质量指标
    geo_coverage_avg = Column(Float)
    diversity_score = Column(Float)
    admit_rate = Column(Float)

    # 元数据
    director_version = Column(String(50), default="v1.0")

    # 关系
    project = relationship("Project", back_populates="episodes")
    experiments = relationship(
        "ContentExperiment", back_populates="episode", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<Episode(id={self.id}, episode_id={self.episode_id})>"


class ContentExperiment(BaseModel):
    """内容实验表 - 存储生成的变体"""

    __tablename__ = "content_experiments"

    episode_id = Column(Integer, ForeignKey("fact_episodes.id"), nullable=False, index=True)
    reference_id = Column(Integer, ForeignKey("viral_contents.id"), index=True)

    # 策略三元组
    hook_strategy = Column(String(10), nullable=False)  # H01-H10
    body_strategy = Column(String(10), nullable=False)  # B01-B08
    cta_strategy = Column(String(10), nullable=False)  # C01-C05

    # 生成内容
    generated_text = Column(Text, nullable=False)
    text_structure = Column(JSON, nullable=False)  # {hook, body, cta}
    geo_keywords = Column(JSON, default=list)
    geo_coverage = Column(Float)

    # 拍摄蓝图
    blueprint = Column(JSON, nullable=False)

    # 实验结果
    published = Column(Boolean, default=False)
    actual_engagement = Column(Float)
    reward_score = Column(Float)
    predicted_reward = Column(Float)
    prediction_error = Column(Float)

    # GRPO 组内比较
    group_id = Column(String(50))
    rank_in_group = Column(Integer)
    group_size = Column(Integer)

    # Critic 评估
    critic_approved = Column(Boolean, default=False)
    critic_score = Column(Float)
    critic_feedback = Column(Text)

    # 元数据
    trace_id = Column(String(50))

    # 关系
    episode = relationship("Episode", back_populates="experiments")
    reference = relationship("ViralContent", back_populates="experiments")

    def __repr__(self):
        return f"<ContentExperiment(id={self.id}, {self.hook_strategy}+{self.body_strategy}+{self.cta_strategy})>"
