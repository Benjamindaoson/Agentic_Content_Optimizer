"""
StrategyDNAExtractor: 策略基因提取器 (Stage 2)

核心目标：从非线性的反馈数据中提取具有“跨平台传染力”的核心基因（Viral DNA）。
通过识别高因果增益的内容特征组合来实现。
"""

import numpy as np
from typing import List, Dict, Any, Tuple
import logging

logger = logging.getLogger(__name__)

class StrategyDNAExtractor:
    """
    策略基因提取器
    """
    def __init__(self):
        # 预定义的“模式特征”及其跨平台潜力系数
        self.gene_map = {
            "suspense_hook": 0.85,    # 悬念开头：跨平台极强
            "listicle_body": 0.70,    # 干货合集：图文强，视频中等
            "social_proof_cta": 0.90, # 社会认同：普适性强
            "visual_contrast": 0.95   # 视觉对比：所有平台流量密码
        }

    def extract_dna(self, successful_episodes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        从一系列成功的交互（Episode）中提取 Viral DNA
        """
        logger.info(f"🧬 正在从 {len(successful_episodes)} 条成功案例中蒸馏核心基因...")
        
        # 1. 特征频率统计与因果加权
        dna_scores = {}
        for ep in successful_episodes:
            # 提取特征（此处简化为从 content 中识别关键词）
            content = ep.get("content", {})
            features = self._identify_features(content)
            causal_lift = ep.get("causal_lift", 0.1) # 权重
            
            for feat in features:
                dna_scores[feat] = dna_scores.get(feat, 0) + (1.0 * causal_lift)
                
        # 2. 归一化并排序
        sorted_dna = sorted(dna_scores.items(), key=lambda x: x[1], reverse=True)
        
        # 3. 封装为 DNA 对象
        viral_dna = []
        for feat, score in sorted_dna[:3]: # 只取 Top 3 核心基因
            viral_dna.append({
                "gene_id": feat,
                "intensity": float(score),
                "cross_platform_score": self.gene_map.get(feat, 0.5),
                "description": f"高价值特征: {feat}"
            })
            
        return viral_dna

    def _identify_features(self, content: Dict[str, str]) -> List[str]:
        features = []
        text = f"{content.get('title', '')} {content.get('text', '')}".lower()
        
        if "?" in text or "为什么" in text: features.append("suspense_hook")
        if "1." in text or "首先" in text: features.append("listicle_body")
        if "点赞" in text or "收藏" in text: features.append("social_proof_cta")
        
        return features
