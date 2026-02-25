from typing import Tuple, List, Dict
import random
from pydantic import BaseModel


class ActionSpace(BaseModel):
    """离散动作空间定义"""

    # 10种 Hook 策略
    HOOKS: Dict[str, str] = {
        "H01": "利益点前置",
        "H02": "痛点反问",
        "H03": "数字冲击",
        "H04": "反常识",
        "H05": "身份认同",
        "H06": "场景代入",
        "H07": "悬念设置",
        "H08": "对比震撼",
        "H09": "权威背书",
        "H10": "限时紧迫"
    }

    # 8种 Body 结构
    BODIES: Dict[str, str] = {
        "B01": "避坑指南",
        "B02": "分点教学",
        "B03": "对比测评",
        "B04": "故事叙事",
        "B05": "数据说话",
        "B06": "案例展示",
        "B07": "步骤拆解",
        "B08": "清单罗列"
    }

    # 5种 CTA 策略
    CTAS: Dict[str, str] = {
        "C01": "互动指令",
        "C02": "利益诱导",
        "C03": "悬念引导",
        "C04": "社交证明",
        "C05": "限时促销"
    }

    @property
    def total_actions(self) -> int:
        """总动作数"""
        return len(self.HOOKS) * len(self.BODIES) * len(self.CTAS)

    def sample_action(self) -> Tuple[str, str, str]:
        """随机采样一个动作"""
        hook = random.choice(list(self.HOOKS.keys()))
        body = random.choice(list(self.BODIES.keys()))
        cta = random.choice(list(self.CTAS.keys()))
        return (hook, body, cta)

    def sample_actions(self, k: int) -> List[Tuple[str, str, str]]:
        """采样 K 个动作"""
        actions = []
        for _ in range(k):
            actions.append(self.sample_action())
        return actions

    def action_to_index(self, action: Tuple[str, str, str]) -> int:
        """动作转索引"""
        hook, body, cta = action
        h_idx = list(self.HOOKS.keys()).index(hook)
        b_idx = list(self.BODIES.keys()).index(body)
        c_idx = list(self.CTAS.keys()).index(cta)
        return h_idx * len(self.BODIES) * len(self.CTAS) + b_idx * len(self.CTAS) + c_idx

    def index_to_action(self, idx: int) -> Tuple[str, str, str]:
        """索引转动作"""
        total_ctas = len(self.CTAS)
        total_bodies = len(self.BODIES)

        h_idx = idx // (total_bodies * total_ctas)
        remainder = idx % (total_bodies * total_ctas)
        b_idx = remainder // total_ctas
        c_idx = remainder % total_ctas

        hook = list(self.HOOKS.keys())[h_idx]
        body = list(self.BODIES.keys())[b_idx]
        cta = list(self.CTAS.keys())[c_idx]

        return (hook, body, cta)

    def get_action_name(self, code: str) -> str:
        """获取动作名称"""
        if code in self.HOOKS:
            return self.HOOKS[code]
        elif code in self.BODIES:
            return self.BODIES[code]
        elif code in self.CTAS:
            return self.CTAS[code]
        return "未知动作"

    def validate_action(self, action: Tuple[str, str, str]) -> bool:
        """验证动作是否合法"""
        hook, body, cta = action
        return hook in self.HOOKS and body in self.BODIES and cta in self.CTAS


# 全局动作空间实例
action_space = ActionSpace()
