"""
MultiModalAligner: 图文对齐与审美评估 (Stage 2)

核心目标：计算文本（标题/正文）与视觉素材（Prompt/生成的图片）之间的语义对齐度。
Stage 2 使用基于语义嵌入的模拟 CLIP 实现。
"""

import numpy as np
from typing import Dict, Any, List, Optional
import logging

logger = logging.getLogger(__name__)

class MultiModalAligner:
    """
    多模态对齐评分器
    """
    def __init__(self):
        # 模拟 CLIP 的文本和图像映射矩阵
        self.latent_dim = 128
        # 预设一些视觉情绪关键词的向量
        self.emotion_vectors = {
            "vibrant": np.random.randn(self.latent_dim),
            "minimalist": np.random.randn(self.latent_dim),
            "emotional": np.random.randn(self.latent_dim),
            "professional": np.random.randn(self.latent_dim)
        }

    def score_alignment(
        self,
        text_content: Dict[str, str],
        visual_plan: Dict[str, Any]
    ) -> Dict[str, float]:
        """
        评估图文一致性
        """
        # 1. 语义对齐 (Semantic Consistency)
        # 检查文本中的关键词是否在视觉计划中体现
        text_str = f"{text_content.get('title', '')} {text_content.get('text', '')}"
        prompt_str = visual_plan.get("prompt", "")
        
        semantic_score = self._calculate_semantic_overlap(text_str, prompt_str)
        
        # 2. 风格一致性 (Style Consistency)
        target_style = visual_plan.get("style", "default")
        text_sentiment = self._estimate_sentiment(text_str)
        
        style_match = 0.8 # 默认
        if "治愈" in text_str and target_style in ["nature", "soft"]:
            style_match = 0.95
        elif "硬核" in text_str and target_style in ["tech", "sharp"]:
            style_match = 0.95
            
        # 3. 视觉引导分 (Visual Hook Strength)
        # 检查视觉计划是否包含强引导元素（如文字叠加、对比色）
        v_hook_score = 0.5
        if visual_plan.get("text_overlay") or "bright colors" in prompt_str:
            v_hook_score = 0.9

        return {
            "semantic_alignment": float(semantic_score),
            "style_consistency": float(style_match),
            "visual_hook_score": float(v_hook_score),
            "overall_mm_score": float(0.4 * semantic_score + 0.3 * style_match + 0.3 * v_hook_score)
        }

    def _calculate_semantic_overlap(self, text: str, prompt: str) -> float:
        # 模拟向量检索
        # 如果 text 中的核心词出现在 prompt 中，分数升高
        common_words = set(text.lower().split()) & set(prompt.lower().split())
        return float(np.clip(len(common_words) / 5.0, 0.2, 1.0))

    def _estimate_sentiment(self, text: str) -> str:
        # 极简情感判断
        if any(w in text for w in ["开心", "温暖", "治愈"]): return "warm"
        if any(w in text for w in ["深度", "干货", "科技"]): return "cool"
        return "neutral"
