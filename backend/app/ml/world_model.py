"""
WorldModel: 策略模拟器 (Stage 3)

核心目标：在将策略投放到真实平台之前，在“虚拟环境”中模拟用户反应和互动率。
这是全自洽蜂群进行离线演练（Offline Rollout）的基础。
"""

import numpy as np
from typing import Dict, Any, List, Optional
import logging

logger = logging.getLogger(__name__)

class PolicyRolloutSimulator:
    """
    World Model (世界模型) 模拟器
    """
    def __init__(self, historical_data_summary: Optional[Dict[str, Any]] = None):
        # 基于历史数据的统计基准
        self.stats = historical_data_summary or {
            "avg_ctr": 0.08,
            "style_preferences": {"minimalist": 1.2, "dramatic": 1.1, "educational": 1.05},
            "category_affinity": {"beauty": 1.15, "tech": 1.0}
        }

    def simulate_rollout(
        self,
        content: Dict[str, str],
        strategy_dna: List[Dict[str, Any]],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        模拟一次策略投放并返回预期的虚拟反馈
        """
        logger.info("🔮 世界模型正在进行策略预演 (Rollout)...")
        
        # 1. 基础概率
        base_rate = self.stats["avg_ctr"]
        
        # 2. DNA 组合乘数 (DNA Potency)
        # 如果 DNA 中包含高潜力的基因组合，提升 CTR
        dna_boost = 1.0
        for dna in strategy_dna:
            # 强度越强，提升越明显
            dna_boost += (dna.get("intensity", 0.1) * dna.get("cross_platform_score", 0.5))
            
        # 3. 上下文适配系数
        category = context.get("category", "tech")
        cat_boost = self.stats["category_affinity"].get(category, 1.0)
        
        # 4. 生成虚拟交互
        # 使用 Beta 分布模拟互动的不确定性
        alpha = base_rate * dna_boost * cat_boost * 10
        beta = (1 - base_rate) * 10
        
        simulated_engagement = np.random.beta(max(alpha, 0.1), max(beta, 0.1))
        
        # 5. 生成定性模拟反馈 (Virtual Persona)
        virtual_comments = self._generate_virtual_comments(content, simulated_engagement)
        
        return {
            "simulated_engagement_rate": float(simulated_engagement),
            "potency_score": float(dna_boost),
            "virtual_persona_feedback": virtual_comments,
            "confidence_interval": [float(simulated_engagement * 0.8), float(simulated_engagement * 1.2)]
        }

    def _generate_virtual_comments(self, content: Dict[str, str], engagement: float) -> List[str]:
        if engagement > 0.15:
            return ["这封面太吸引我了！", "求链接！", "博主说得对，我也遇到了同样的问题。"]
        if engagement < 0.05:
            return ["内容有点平，建议加点干货。", "感觉在做广告。"]
        return ["路过支持一下。", "还行吧。"]
