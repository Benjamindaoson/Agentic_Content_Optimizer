"""
数据库模型定义

核心约束：note_id 作为唯一主键（SSOT），保证封面、指标、分析结果一一对应
"""

from sqlalchemy import (
    Column, String, Integer, Float, DateTime, Text, Boolean,
    ForeignKey, UniqueConstraint, Index, JSON, LargeBinary
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import datetime
from typing import Optional, Dict, List, Any

Base = declarative_base()


class XHSNote(Base):
    """
    小红书笔记主表

    核心字段：note_id（唯一主键）
    """
    __tablename__ = 'xhs_notes'

    note_id = Column(String(64), primary_key=True, comment='笔记ID（唯一主键）')
    title = Column(String(512), nullable=False, comment='标题')
    text = Column(Text, nullable=False, comment='正文')

    # 封面与图集
    cover_url = Column(String(1024), comment='封面URL')
    image_urls = Column(JSON, comment='图集URLs（JSONB数组）')

    # 元数据
    author_id = Column(String(64), index=True, comment='作者ID')
    author_name = Column(String(256), comment='作者昵称')
    publish_time = Column(DateTime, index=True, comment='发布时间')
    category = Column(String(64), index=True, comment='分类')
    tags = Column(JSON, comment='标签（JSONB数组）')

    # 采集信息
    crawled_at = Column(DateTime, default=func.now(), comment='采集时间')
    raw_metadata = Column(JSON, comment='原始元数据（JSONB）')

    # 状态标记
    is_viral = Column(Boolean, default=False, index=True, comment='是否爆款')
    analysis_status = Column(String(32), default='pending', comment='分析状态：pending/processing/completed/failed')

    # 关联关系
    metrics = relationship("XHSMetrics", back_populates="note", uselist=False, cascade="all, delete-orphan")
    cover = relationship("XHSCover", back_populates="note", uselist=False, cascade="all, delete-orphan")
    analysis = relationship("XHSAnalysis", back_populates="note", uselist=False, cascade="all, delete-orphan")
    pattern_samples = relationship("PatternSample", back_populates="note", cascade="all, delete-orphan")

    # 索引
    __table_args__ = (
        Index('idx_xhs_notes_category_viral', 'category', 'is_viral'),
        Index('idx_xhs_notes_publish_time', 'publish_time'),
    )


class XHSMetrics(Base):
    """
    小红书笔记指标表

    与 note_id 一一对应
    """
    __tablename__ = 'xhs_metrics'

    note_id = Column(String(64), ForeignKey('xhs_notes.note_id', ondelete='CASCADE'),
                     primary_key=True, comment='笔记ID（外键）')

    # 绝对指标
    views = Column(Integer, default=0, comment='浏览量')
    likes = Column(Integer, default=0, comment='点赞数')
    comments = Column(Integer, default=0, comment='评论数')
    collects = Column(Integer, default=0, comment='收藏数')
    shares = Column(Integer, default=0, comment='分享数')
    follows = Column(Integer, default=0, comment='关注数')

    # 计算指标
    engagement_rate = Column(Float, default=0.0, comment='互动率')
    viral_score = Column(Float, default=0.0, index=True, comment='爆款分数')

    # 相对指标
    views_percentile = Column(Float, default=0.0, comment='浏览量百分位')
    engagement_percentile = Column(Float, default=0.0, comment='互动率百分位')

    # 速度指标
    velocity_score = Column(Float, default=0.0, comment='速度分数')
    growth_rate_24h = Column(Float, default=0.0, comment='24小时增长率')

    # 更新时间
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), comment='更新时间')

    # 关联关系
    note = relationship("XHSNote", back_populates="metrics")


class XHSCover(Base):
    """
    小红书笔记封面表

    与 note_id 一一对应，存储封面图本地路径和视觉特征
    """
    __tablename__ = 'xhs_covers'

    note_id = Column(String(64), ForeignKey('xhs_notes.note_id', ondelete='CASCADE'),
                     primary_key=True, comment='笔记ID（外键）')

    # 存储信息
    local_path = Column(String(512), comment='本地存储路径')
    image_hash = Column(String(64), index=True, comment='图片哈希（去重）')
    width = Column(Integer, comment='宽度')
    height = Column(Integer, comment='高度')
    file_size = Column(Integer, comment='文件大小（字节）')

    # 视觉特征
    cover_embedding = Column(LargeBinary, comment='封面embedding（向量）')
    layout = Column(String(64), comment='布局类型：left_text_right_image/top_image_bottom_text/center_text等')
    dominant_color = Column(String(32), comment='主色调（HEX）')
    objects = Column(JSON, comment='检测到的对象（JSONB）')
    text_regions = Column(JSON, comment='文字区域（JSONB）')

    # 下载信息
    download_status = Column(String(32), default='pending', comment='下载状态：pending/success/failed')
    download_method = Column(String(32), comment='下载方式：spider/downloader/playwright')
    downloaded_at = Column(DateTime, comment='下载时间')

    # 更新时间
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), comment='更新时间')

    # 关联关系
    note = relationship("XHSNote", back_populates="cover")


class XHSAnalysis(Base):
    """
    小红书笔记分析结果表

    与 note_id 一一对应，存储多维度分析结果
    """
    __tablename__ = 'xhs_analysis'

    note_id = Column(String(64), ForeignKey('xhs_notes.note_id', ondelete='CASCADE'),
                     primary_key=True, comment='笔记ID（外键）')

    # 结构分析
    structure = Column(JSON, comment='结构分析：hook/body/cta/rhythm等（JSONB）')

    # 情感分析
    emotion = Column(JSON, comment='情感分析：主情绪/强度/曲线/触发词等（JSONB）')

    # 话题分析
    topics = Column(JSON, comment='话题分析：核心话题/热点/争议度/痛点等（JSONB）')

    # 视觉分析
    visual = Column(JSON, comment='视觉分析：布局/色彩/对象/文字区等（JSONB）')

    # 时机分析
    timing = Column(JSON, comment='时机分析：发布时间/爆发速度关系等（JSONB）')

    # 受众分析
    audience = Column(JSON, comment='受众分析：目标人群/年龄/兴趣等（JSONB）')

    # 分析元数据
    analyzer_version = Column(String(32), comment='分析器版本')
    analyzed_at = Column(DateTime, default=func.now(), comment='分析时间')
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), comment='更新时间')

    # 关联关系
    note = relationship("XHSNote", back_populates="analysis")


class Pattern(Base):
    """
    爆款模式表

    存储从爆款中提取的可复用模式
    """
    __tablename__ = 'patterns'

    pattern_id = Column(String(64), primary_key=True, comment='模式ID')

    # 基础信息
    category = Column(String(64), index=True, comment='分类')
    name = Column(String(256), comment='模式名称')
    description = Column(Text, comment='模式描述')

    # 模式内容
    hook_template = Column(Text, comment='Hook模板')
    body_structure = Column(JSON, comment='Body结构（JSONB）')
    cta_template = Column(Text, comment='CTA模板')

    # 关键特征
    keywords = Column(JSON, comment='关键词（JSONB数组）')
    emotion_curve = Column(JSON, comment='情绪曲线（JSONB）')

    # 视觉特征
    cover_layout = Column(String(64), comment='封面布局')
    dominant_color = Column(String(32), comment='主色调')
    visual_elements = Column(JSON, comment='视觉元素（JSONB）')

    # 性能指标
    success_rate = Column(Float, default=0.0, index=True, comment='成功率')
    sample_size = Column(Integer, default=0, comment='样本量')
    avg_viral_score = Column(Float, default=0.0, comment='平均爆款分数')
    avg_views = Column(Float, default=0.0, comment='平均浏览量')
    avg_engagement_rate = Column(Float, default=0.0, comment='平均互动率')

    # Thompson Sampling 参数
    thompson_alpha = Column(Float, default=1.0, comment='Thompson Sampling alpha参数')
    thompson_beta = Column(Float, default=1.0, comment='Thompson Sampling beta参数')

    # 适用场景
    platforms = Column(JSON, comment='适用平台（JSONB数组）')
    target_audience = Column(String(256), comment='目标受众')

    # Embedding
    embedding = Column(LargeBinary, comment='模式embedding（向量）')

    # 版本控制
    version = Column(Integer, default=1, comment='版本号')
    parent_pattern_id = Column(String(64), ForeignKey('patterns.pattern_id'), comment='父模式ID')

    # 时间戳
    created_at = Column(DateTime, default=func.now(), comment='创建时间')
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), comment='更新时间')

    # 关联关系
    samples = relationship("PatternSample", back_populates="pattern", cascade="all, delete-orphan")
    generations = relationship("Generation", back_populates="pattern")

    # 索引
    __table_args__ = (
        Index('idx_patterns_category_success', 'category', 'success_rate'),
    )


class PatternSample(Base):
    """
    模式样本关联表

    记录模式与爆款笔记的关联关系（可追溯）
    """
    __tablename__ = 'pattern_samples'

    id = Column(Integer, primary_key=True, autoincrement=True)
    pattern_id = Column(String(64), ForeignKey('patterns.pattern_id', ondelete='CASCADE'),
                        nullable=False, comment='模式ID')
    note_id = Column(String(64), ForeignKey('xhs_notes.note_id', ondelete='CASCADE'),
                     nullable=False, comment='笔记ID')

    # 关联信息
    contribution_score = Column(Float, default=1.0, comment='贡献分数')
    added_at = Column(DateTime, default=func.now(), comment='添加时间')

    # 关联关系
    pattern = relationship("Pattern", back_populates="samples")
    note = relationship("XHSNote", back_populates="pattern_samples")

    # 唯一约束
    __table_args__ = (
        UniqueConstraint('pattern_id', 'note_id', name='uq_pattern_note'),
        Index('idx_pattern_samples_pattern', 'pattern_id'),
        Index('idx_pattern_samples_note', 'note_id'),
    )


class Generation(Base):
    """
    生成记录表

    记录每次内容生成的完整信息
    """
    __tablename__ = 'generations'

    gen_id = Column(String(64), primary_key=True, comment='生成ID')

    # 输入参数
    topic = Column(String(512), comment='话题')
    category = Column(String(64), index=True, comment='分类')
    target_audience = Column(String(256), comment='目标受众')
    constraints = Column(JSON, comment='约束条件（JSONB）')

    # 关联模式
    pattern_id = Column(String(64), ForeignKey('patterns.pattern_id'), comment='使用的模式ID')

    # 生成结果
    candidates = Column(JSON, comment='候选内容（JSONB数组）')
    best_content = Column(JSON, comment='最佳内容（JSONB）')

    # 评分信息
    reward_breakdown = Column(JSON, comment='奖励分解（JSONB）')
    diversity_score = Column(Float, comment='多样性分数')

    # 封面建议
    cover_suggestion = Column(JSON, comment='封面建议（JSONB）')

    # 生成元数据
    generator_version = Column(String(32), comment='生成器版本')
    model_name = Column(String(64), comment='使用的模型')
    temperature = Column(Float, comment='温度参数')

    # 时间戳
    created_at = Column(DateTime, default=func.now(), index=True, comment='创建时间')

    # 关联关系
    pattern = relationship("Pattern", back_populates="generations")
    online_metrics = relationship("OnlineMetrics", back_populates="generation", uselist=False, cascade="all, delete-orphan")

    # 索引
    __table_args__ = (
        Index('idx_generations_category_created', 'category', 'created_at'),
    )


class OnlineMetrics(Base):
    """
    线上指标表

    记录生成内容发布后的真实指标（用于GRPO闭环）
    """
    __tablename__ = 'online_metrics'

    gen_id = Column(String(64), ForeignKey('generations.gen_id', ondelete='CASCADE'),
                    primary_key=True, comment='生成ID（外键）')

    # 发布信息
    platform = Column(String(32), comment='发布平台')
    published_note_id = Column(String(64), index=True, comment='发布后的笔记ID')
    published_at = Column(DateTime, comment='发布时间')

    # 真实指标
    views = Column(Integer, default=0, comment='浏览量')
    likes = Column(Integer, default=0, comment='点赞数')
    comments = Column(Integer, default=0, comment='评论数')
    collects = Column(Integer, default=0, comment='收藏数')
    shares = Column(Integer, default=0, comment='分享数')
    follows = Column(Integer, default=0, comment='关注数')

    # 计算指标
    engagement_rate = Column(Float, default=0.0, comment='互动率')
    completion_rate = Column(Float, default=0.0, comment='完播率')
    conversion_rate = Column(Float, default=0.0, comment='转化率')

    # 更新时间
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), comment='更新时间')

    # 关联关系
    generation = relationship("Generation", back_populates="online_metrics")


class GRPORun(Base):
    """
    GRPO训练运行记录表
    """
    __tablename__ = 'grpo_runs'

    run_id = Column(String(64), primary_key=True, comment='运行ID')

    # 配置信息
    config = Column(JSON, comment='训练配置（JSONB）')

    # 训练数据
    training_samples = Column(Integer, comment='训练样本数')
    episodes = Column(Integer, comment='训练轮数')

    # 性能指标
    metrics = Column(JSON, comment='训练指标（JSONB）')

    # 时间戳
    started_at = Column(DateTime, default=func.now(), comment='开始时间')
    finished_at = Column(DateTime, comment='结束时间')
    status = Column(String(32), default='running', comment='状态：running/completed/failed')

    # 索引
    __table_args__ = (
        Index('idx_grpo_runs_started', 'started_at'),
    )


class CrawlTask(Base):
    """
    采集任务表

    记录采集任务的状态和进度
    """
    __tablename__ = 'crawl_tasks'

    task_id = Column(String(64), primary_key=True, comment='任务ID')

    # 任务参数
    platform = Column(String(32), comment='平台')
    category = Column(String(64), comment='分类')
    time_window = Column(String(32), comment='时间窗口：24h/7d/30d')
    criteria = Column(JSON, comment='筛选条件（JSONB）')

    # 任务状态
    status = Column(String(32), default='pending', index=True, comment='状态：pending/running/completed/failed')
    progress = Column(Float, default=0.0, comment='进度（0-1）')

    # 统计信息
    total_notes = Column(Integer, default=0, comment='总笔记数')
    viral_notes = Column(Integer, default=0, comment='爆款笔记数')
    failed_notes = Column(Integer, default=0, comment='失败笔记数')

    # 错误信息
    error_message = Column(Text, comment='错误信息')

    # 时间戳
    created_at = Column(DateTime, default=func.now(), comment='创建时间')
    started_at = Column(DateTime, comment='开始时间')
    finished_at = Column(DateTime, comment='结束时间')

    # 索引
    __table_args__ = (
        Index('idx_crawl_tasks_status_created', 'status', 'created_at'),
    )
