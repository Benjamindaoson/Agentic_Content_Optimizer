from sqlalchemy import Column, String, Integer, ForeignKey, Enum as SQLEnum, JSON, Float
from sqlalchemy.orm import relationship
import enum
from app.models.base import BaseModel


class Platform(str, enum.Enum):
    """平台类型"""

    XIAOHONGSHU = "xiaohongshu"
    DOUYIN = "douyin"
    TIKTOK = "tiktok"
    KUAISHOU = "kuaishou"


class GoalMetric(str, enum.Enum):
    """目标指标"""

    ENGAGEMENT = "engagement"  # 互动率
    COMPLETION = "completion"  # 完播率
    CONVERSION = "conversion"  # 转化率


class ProjectStatus(str, enum.Enum):
    """项目状态"""

    ACTIVE = "active"
    PAUSED = "paused"
    ARCHIVED = "archived"


class Project(BaseModel):
    """项目模型"""

    __tablename__ = "projects"

    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    topic = Column(String(200), nullable=False)
    platform = Column(SQLEnum(Platform), nullable=False)
    goal_metric = Column(SQLEnum(GoalMetric), nullable=False)
    status = Column(SQLEnum(ProjectStatus), default=ProjectStatus.ACTIVE)

    # 统计数据
    total_episodes = Column(Integer, default=0)
    avg_geo_score = Column(Float, default=0.0)
    total_token_cost = Column(Integer, default=0)

    # 关系
    user = relationship("User", back_populates="projects")
    strategy_specs = relationship(
        "StrategySpec", back_populates="project", cascade="all, delete-orphan"
    )
    episodes = relationship(
        "Episode", back_populates="project", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<Project(id={self.id}, topic={self.topic}, platform={self.platform})>"


class StrategySpec(BaseModel):
    """策略规格"""

    __tablename__ = "strategy_specs"

    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False, index=True)
    topic_id = Column(String(100), nullable=False)
    geo_constraints = Column(JSON, default=dict)  # GEO 约束
    target_audience = Column(String(200))
    content_style = Column(String(100))
    status = Column(String(50), default="active")

    # 关系
    project = relationship("Project", back_populates="strategy_specs")

    def __repr__(self):
        return f"<StrategySpec(id={self.id}, topic_id={self.topic_id})>"
