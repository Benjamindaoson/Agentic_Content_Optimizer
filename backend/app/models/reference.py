from sqlalchemy import Column, String, Integer, Float, JSON, Text, DateTime, Enum as SQLEnum
from sqlalchemy.orm import relationship
import enum
from app.models.base import BaseModel


class Platform(str, enum.Enum):
    """平台类型"""

    XIAOHONGSHU = "xiaohongshu"
    DOUYIN = "douyin"
    TIKTOK = "tiktok"
    KUAISHOU = "kuaishou"


class ViralContent(BaseModel):
    """爆款内容库"""

    __tablename__ = "viral_contents"

    # 平台信息
    platform = Column(SQLEnum(Platform), nullable=False, index=True)
    content_id = Column(String(100), unique=True, nullable=False, index=True)
    author_id = Column(String(100), nullable=False, index=True)

    # 内容
    text = Column(Text, nullable=False)
    image_urls = Column(JSON, default=list)
    video_url = Column(String(500))

    # 互动数据
    likes = Column(Integer, default=0)
    comments = Column(Integer, default=0)
    shares = Column(Integer, default=0)
    collects = Column(Integer, default=0)
    engagement_score = Column(Float, default=0, index=True)

    # 结构化标签（AI 分析）
    hook_type = Column(String(50), index=True)
    body_structure = Column(String(50), index=True)
    cta_type = Column(String(50))

    # 视觉分析
    visual_blueprint = Column(JSON)

    # 相对增益
    author_baseline = Column(Float, default=0)
    relative_lift = Column(Float, default=0)

    # GEO 评分
    geo_score = Column(Float)
    geo_keywords = Column(JSON, default=list)

    # 时间戳
    published_at = Column(DateTime(timezone=True))
    scraped_at = Column(DateTime(timezone=True))

    # 关系
    experiments = relationship("ContentExperiment", back_populates="reference")

    def __repr__(self):
        return f"<ViralContent(id={self.id}, content_id={self.content_id}, engagement={self.engagement_score})>"


class ReferenceMetadata(BaseModel):
    """Reference Pool 元数据"""

    __tablename__ = "reference_pool_metadata"

    ref_id = Column(String(100), unique=True, nullable=False, index=True)
    style = Column(String(100))
    scene_tags = Column(JSON, default=list)
    platform = Column(SQLEnum(Platform), nullable=False)
    stats = Column(JSON, default=dict)

    # Qdrant 向量 ID
    vector_id = Column(String(100), unique=True)

    def __repr__(self):
        return f"<ReferenceMetadata(id={self.id}, ref_id={self.ref_id})>"
