"""
账号人设层 (Persona Layer)

用于管理账号的人设、语言风格、受众画像，影响生成和评分
"""

import logging
from typing import List, Dict, Optional, Set
from dataclasses import dataclass, field
from enum import Enum

from sqlalchemy import Column, String, Integer, Float, DateTime, Boolean, JSON, Text, ForeignKey
from sqlalchemy.orm import Session
from app.core.database import Base
from datetime import datetime

logger = logging.getLogger(__name__)


class VoiceStyle(str, Enum):
    """语言风格"""
    PROFESSIONAL = 'professional'  # 专业
    CASUAL = 'casual'  # 随意
    FRIENDLY = 'friendly'  # 友好
    AUTHORITATIVE = 'authoritative'  # 权威
    HUMOROUS = 'humorous'  # 幽默
    INSPIRATIONAL = 'inspirational'  # 励志


# ==================== 数据库模型 ====================

class AccountPersona(Base):
    """账号人设表"""
    __tablename__ = 'account_personas'

    persona_id = Column(String(64), primary_key=True, comment='人设ID')
    account_id = Column(String(64), ForeignKey('xhs_accounts.account_id'), nullable=False, comment='账号ID')

    # 基础人设
    persona_name = Column(String(128), comment='人设名称')
    description = Column(Text, comment='人设描述')

    # 语言风格
    voice_style = Column(String(32), comment='语言风格')
    tone = Column(String(32), comment='语气（serious/humorous/inspirational）')
    formality_level = Column(Float, comment='正式程度（0-1）')

    # 常用表达
    common_phrases = Column(JSON, comment='常用短语列表')
    signature_words = Column(JSON, comment='标志性用词')
    emoji_preference = Column(JSON, comment='emoji 偏好')

    # 禁用词
    forbidden_words = Column(JSON, comment='禁用词列表')
    forbidden_topics = Column(JSON, comment='禁用话题列表')

    # 受众画像
    target_audience = Column(JSON, comment='目标受众')
    audience_age_range = Column(JSON, comment='受众年龄范围')
    audience_interests = Column(JSON, comment='受众兴趣')

    # 内容偏好
    preferred_topics = Column(JSON, comment='偏好话题')
    content_length_preference = Column(JSON, comment='内容长度偏好 {"min": 100, "max": 500}')
    structure_preference = Column(JSON, comment='结构偏好')

    # 品牌信息
    brand_values = Column(JSON, comment='品牌价值观')
    brand_keywords = Column(JSON, comment='品牌关键词')

    # 元数据
    created_at = Column(DateTime, default=datetime.now, comment='创建时间')
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment='更新时间')
    is_active = Column(Boolean, default=True, comment='是否激活')
    metadata = Column(JSON, comment='其他元数据')


@dataclass
class Persona:
    """人设数据类"""
    persona_id: str
    account_id: str
    persona_name: str

    # 语言风格
    voice_style: VoiceStyle
    tone: str
    formality_level: float = 0.5

    # 常用表达
    common_phrases: List[str] = field(default_factory=list)
    signature_words: List[str] = field(default_factory=list)
    emoji_preference: Dict[str, float] = field(default_factory=dict)

    # 禁用词
    forbidden_words: Set[str] = field(default_factory=set)
    forbidden_topics: Set[str] = field(default_factory=set)

    # 受众画像
    target_audience: str = ''
    audience_age_range: tuple = (18, 35)
    audience_interests: List[str] = field(default_factory=list)

    # 内容偏好
    preferred_topics: List[str] = field(default_factory=list)
    content_length_preference: Dict[str, int] = field(default_factory=lambda: {'min': 100, 'max': 500})

    # 品牌信息
    brand_values: List[str] = field(default_factory=list)
    brand_keywords: List[str] = field(default_factory=list)


class PersonaManager:
    """
    人设管理器

    功能：
    1. 人设创建与管理
    2. 人设应用到生成
    3. 人设一致性检查
    4. 人设评分调整
    """

    def __init__(self, db: Session):
        self.db = db

    def create_persona(
        self,
        account_id: str,
        persona_name: str,
        voice_style: VoiceStyle,
        tone: str,
        description: Optional[str] = None,
        **kwargs
    ) -> AccountPersona:
        """
        创建人设

        Args:
            account_id: 账号ID
            persona_name: 人设名称
            voice_style: 语言风格
            tone: 语气
            description: 人设描述
            **kwargs: 其他人设属性

        Returns:
            人设对象
        """
        import uuid

        persona_id = f"persona_{uuid.uuid4().hex[:16]}"

        persona = AccountPersona(
            persona_id=persona_id,
            account_id=account_id,
            persona_name=persona_name,
            description=description,
            voice_style=voice_style.value,
            tone=tone,
            formality_level=kwargs.get('formality_level', 0.5),
            common_phrases=kwargs.get('common_phrases', []),
            signature_words=kwargs.get('signature_words', []),
            emoji_preference=kwargs.get('emoji_preference', {}),
            forbidden_words=kwargs.get('forbidden_words', []),
            forbidden_topics=kwargs.get('forbidden_topics', []),
            target_audience=kwargs.get('target_audience', {}),
            audience_age_range=kwargs.get('audience_age_range', [18, 35]),
            audience_interests=kwargs.get('audience_interests', []),
            preferred_topics=kwargs.get('preferred_topics', []),
            content_length_preference=kwargs.get('content_length_preference', {'min': 100, 'max': 500}),
            brand_values=kwargs.get('brand_values', []),
            brand_keywords=kwargs.get('brand_keywords', [])
        )

        self.db.add(persona)
        self.db.commit()

        logger.info(f"✅ 人设已创建: {persona_id} ({persona_name})")

        return persona

    def get_persona(self, account_id: str) -> Optional[Persona]:
        """
        获取账号人设

        Args:
            account_id: 账号ID

        Returns:
            人设对象
        """
        persona_db = self.db.query(AccountPersona).filter(
            AccountPersona.account_id == account_id,
            AccountPersona.is_active == True
        ).first()

        if not persona_db:
            return None

        return Persona(
            persona_id=persona_db.persona_id,
            account_id=persona_db.account_id,
            persona_name=persona_db.persona_name,
            voice_style=VoiceStyle(persona_db.voice_style),
            tone=persona_db.tone,
            formality_level=persona_db.formality_level,
            common_phrases=persona_db.common_phrases or [],
            signature_words=persona_db.signature_words or [],
            emoji_preference=persona_db.emoji_preference or {},
            forbidden_words=set(persona_db.forbidden_words or []),
            forbidden_topics=set(persona_db.forbidden_topics or []),
            target_audience=persona_db.target_audience or '',
            audience_age_range=tuple(persona_db.audience_age_range) if persona_db.audience_age_range else (18, 35),
            audience_interests=persona_db.audience_interests or [],
            preferred_topics=persona_db.preferred_topics or [],
            content_length_preference=persona_db.content_length_preference or {'min': 100, 'max': 500},
            brand_values=persona_db.brand_values or [],
            brand_keywords=persona_db.brand_keywords or []
        )

    def apply_persona_to_prompt(
        self,
        persona: Persona,
        base_prompt: str
    ) -> str:
        """
        将人设应用到 Prompt

        Args:
            persona: 人设
            base_prompt: 基础 Prompt

        Returns:
            增强后的 Prompt
        """
        persona_instructions = []

        # 1. 语言风格
        persona_instructions.append(f"语言风格: {persona.voice_style.value}")
        persona_instructions.append(f"语气: {persona.tone}")

        if persona.formality_level < 0.3:
            persona_instructions.append("使用轻松随意的表达")
        elif persona.formality_level > 0.7:
            persona_instructions.append("使用正式专业的表达")

        # 2. 常用表达
        if persona.common_phrases:
            phrases_str = '、'.join(persona.common_phrases[:5])
            persona_instructions.append(f"常用短语: {phrases_str}")

        if persona.signature_words:
            words_str = '、'.join(persona.signature_words[:5])
            persona_instructions.append(f"标志性用词: {words_str}")

        # 3. 禁用词
        if persona.forbidden_words:
            forbidden_str = '、'.join(list(persona.forbidden_words)[:10])
            persona_instructions.append(f"禁止使用: {forbidden_str}")

        # 4. 受众
        if persona.target_audience:
            persona_instructions.append(f"目标受众: {persona.target_audience}")

        # 5. 品牌
        if persona.brand_values:
            values_str = '、'.join(persona.brand_values)
            persona_instructions.append(f"品牌价值观: {values_str}")

        # 6. 内容长度
        length_pref = persona.content_length_preference
        persona_instructions.append(f"内容长度: {length_pref['min']}-{length_pref['max']} 字")

        # 组合 Prompt
        persona_section = "\n".join([f"- {inst}" for inst in persona_instructions])

        enhanced_prompt = f"""{base_prompt}

## 人设要求
{persona_section}

请严格遵守以上人设要求生成内容。
"""

        return enhanced_prompt

    def check_persona_consistency(
        self,
        persona: Persona,
        title: str,
        text: str
    ) -> tuple[float, List[str]]:
        """
        检查内容与人设的一致性

        Args:
            persona: 人设
            title: 标题
            text: 正文

        Returns:
            (一致性分数, 不一致项列表)
        """
        content = title + ' ' + text
        inconsistencies = []
        score = 1.0

        # 1. 检查禁用词
        if persona.forbidden_words:
            found_forbidden = [
                word for word in persona.forbidden_words
                if word in content
            ]
            if found_forbidden:
                inconsistencies.append(f"包含禁用词: {', '.join(found_forbidden)}")
                score -= 0.3

        # 2. 检查禁用话题
        if persona.forbidden_topics:
            found_topics = [
                topic for topic in persona.forbidden_topics
                if topic in content
            ]
            if found_topics:
                inconsistencies.append(f"涉及禁用话题: {', '.join(found_topics)}")
                score -= 0.3

        # 3. 检查内容长度
        total_length = len(title) + len(text)
        length_pref = persona.content_length_preference

        if total_length < length_pref['min']:
            inconsistencies.append(f"内容过短: {total_length} < {length_pref['min']}")
            score -= 0.2
        elif total_length > length_pref['max']:
            inconsistencies.append(f"内容过长: {total_length} > {length_pref['max']}")
            score -= 0.1

        # 4. 检查品牌关键词
        if persona.brand_keywords:
            found_keywords = sum(
                1 for kw in persona.brand_keywords
                if kw in content
            )
            keyword_coverage = found_keywords / len(persona.brand_keywords)

            if keyword_coverage < 0.3:
                inconsistencies.append(f"品牌关键词覆盖不足: {keyword_coverage:.1%}")
                score -= 0.2

        score = max(0.0, score)

        return score, inconsistencies

    def adjust_score_by_persona(
        self,
        persona: Persona,
        title: str,
        text: str,
        base_score: float
    ) -> float:
        """
        根据人设调整分数

        Args:
            persona: 人设
            title: 标题
            text: 正文
            base_score: 基础分数

        Returns:
            调整后的分数
        """
        consistency_score, _ = self.check_persona_consistency(persona, title, text)

        # 人设一致性权重 30%
        adjusted_score = base_score * 0.7 + consistency_score * 0.3

        return adjusted_score

    def get_persona_prompt_template(self, persona: Persona) -> str:
        """
        获取人设 Prompt 模板

        Args:
            persona: 人设

        Returns:
            Prompt 模板
        """
        template = f"""你是一个内容创作者，具有以下人设特征：

**语言风格**: {persona.voice_style.value}
**语气**: {persona.tone}
**正式程度**: {'正式' if persona.formality_level > 0.7 else '随意' if persona.formality_level < 0.3 else '适中'}

**目标受众**: {persona.target_audience}
**受众年龄**: {persona.audience_age_range[0]}-{persona.audience_age_range[1]}岁

**品牌价值观**: {', '.join(persona.brand_values) if persona.brand_values else '无'}

**内容要求**:
- 长度: {persona.content_length_preference['min']}-{persona.content_length_preference['max']} 字
- 必须包含品牌关键词: {', '.join(persona.brand_keywords[:5]) if persona.brand_keywords else '无'}
- 禁止使用: {', '.join(list(persona.forbidden_words)[:10]) if persona.forbidden_words else '无'}

请严格遵守以上人设要求创作内容。
"""

        return template


# ==================== 使用示例 ====================

def example_usage():
    """使用示例"""
    from app.db import get_db

    db = next(get_db())

    # 1. 创建人设管理器
    manager = PersonaManager(db)

    # 2. 创建人设
    persona_db = manager.create_persona(
        account_id='xhs_001',
        persona_name='专业护肤博主',
        voice_style=VoiceStyle.PROFESSIONAL,
        tone='inspirational',
        description='专注于科学护肤的专业博主',
        formality_level=0.7,
        common_phrases=['姐妹们', '干货分享', '亲测有效'],
        signature_words=['科学', '成分', '功效'],
        forbidden_words=['最好', '第一', '绝对', '包治'],
        forbidden_topics=['医疗', '疾病治疗'],
        target_audience='18-35岁关注护肤的女性',
        audience_age_range=[18, 35],
        audience_interests=['护肤', '美妆', '健康'],
        preferred_topics=['护肤', '成分分析', '产品测评'],
        content_length_preference={'min': 200, 'max': 800},
        brand_values=['科学', '专业', '真实'],
        brand_keywords=['护肤', '成分', '科学']
    )

    # 3. 获取人设
    persona = manager.get_persona('xhs_001')
    print(f"人设: {persona.persona_name}")

    # 4. 应用人设到 Prompt
    base_prompt = "请生成一篇关于冬季护肤的笔记"
    enhanced_prompt = manager.apply_persona_to_prompt(persona, base_prompt)
    print(f"增强 Prompt: {enhanced_prompt}")

    # 5. 检查一致性
    title = "冬季护肤科学指南"
    text = "姐妹们，今天给大家分享冬季护肤的科学方法..."

    consistency_score, inconsistencies = manager.check_persona_consistency(
        persona, title, text
    )
    print(f"一致性分数: {consistency_score:.2f}")
    print(f"不一致项: {inconsistencies}")

    # 6. 调整分数
    base_score = 0.8
    adjusted_score = manager.adjust_score_by_persona(
        persona, title, text, base_score
    )
    print(f"调整后分数: {adjusted_score:.2f}")

    # 7. 获取 Prompt 模板
    template = manager.get_persona_prompt_template(persona)
    print(f"Prompt 模板: {template}")
