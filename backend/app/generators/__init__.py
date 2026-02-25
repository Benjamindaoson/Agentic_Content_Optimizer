"""
生成器模块初始化
"""

from app.generators.viral_generator import (
    ViralGenerator,
    GenerationCandidate,
    GenerationRequest
)

from app.generators.cover_suggester import (
    CoverSuggester,
    CoverSuggestion
)

__all__ = [
    # 生成器
    'ViralGenerator',
    'CoverSuggester',

    # 数据结构
    'GenerationCandidate',
    'GenerationRequest',
    'CoverSuggestion'
]
