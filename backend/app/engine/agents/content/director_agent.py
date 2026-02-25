from typing import Dict, Any, List, Tuple, Optional
import random

from app.engine.agents.base import BaseAgent, AgentConfig, AgentResponse
from app.ml.rl.action_space import action_space
import logging

logger = logging.getLogger(__name__)


class DirectorAgent(BaseAgent):
    """
    Director Agent - 策略导演

    职责：
    1. 在离散动作空间采样 K 组 H/B/C
    2. ε-greedy 探索策略
    3. 基于历史 Episode 优化采样
    4. 返回排序后的动作组
    """

    def __init__(self, config: Optional[AgentConfig] = None):
        if config is None:
            config = AgentConfig(
                name="DirectorAgent",
                description="离散策略采样",
                model="",  # 不需要 LLM
                temperature=0
            )
        super().__init__(config)

        self.epsilon = 0.1  # 探索率
        self.action_space = action_space

    async def execute(self, input_data: Dict[str, Any]) -> AgentResponse:
        """
        执行策略采样

        输入：
        - geo_constraints: GEO 约束
        - references: 参考内容
        - group_size: 采样数量（默认 8）
        - exploration: 是否强制探索

        输出：
        - actions: 采样的动作组 [(H, B, C), ...]
        - rationales: 每个动作的选择理由
        """
        try:
            geo_constraints = input_data.get("geo_constraints", {})
            references = input_data.get("references", [])
            group_size = input_data.get("group_size", 8)
            exploration = input_data.get("exploration", False)

            # 1. 采样动作组
            actions = await self._sample_actions(
                geo_constraints=geo_constraints,
                references=references,
                k=group_size,
                force_exploration=exploration
            )

            # 2. 生成选择理由
            rationales = await self._generate_rationales(
                actions=actions,
                geo_constraints=geo_constraints,
                references=references
            )

            # 3. 计算多样性分数
            diversity_score = self._calculate_diversity(actions)

            response_data = {
                "actions": [
                    {
                        "hook": action[0],
                        "body": action[1],
                        "cta": action[2],
                        "hook_name": self.action_space.get_action_name(action[0]),
                        "body_name": self.action_space.get_action_name(action[1]),
                        "cta_name": self.action_space.get_action_name(action[2]),
                        "rationale": rationales[i]
                    }
                    for i, action in enumerate(actions)
                ],
                "diversity_score": diversity_score,
                "total_actions": len(actions)
            }

            self._log_execution(input_data, AgentResponse(success=True, data=response_data))

            return AgentResponse(
                success=True,
                data=response_data,
                metadata={
                    "agent": self.config.name,
                    "group_size": group_size,
                    "diversity_score": diversity_score
                }
            )

        except Exception as e:
            return await self._handle_error(e)

    async def _sample_actions(
        self,
        geo_constraints: Dict[str, Any],
        references: List[Dict[str, Any]],
        k: int,
        force_exploration: bool
    ) -> List[Tuple[str, str, str]]:
        """采样 K 个动作"""

        # ε-greedy 策略
        if force_exploration or random.random() < self.epsilon:
            # 探索：随机采样
            return self.action_space.sample_actions(k)
        else:
            # 利用：基于参考内容的结构采样
            return await self._exploit_sampling(references, k)

    async def _exploit_sampling(
        self,
        references: List[Dict[str, Any]],
        k: int
    ) -> List[Tuple[str, str, str]]:
        """基于参考内容的利用采样"""

        if not references:
            # 没有参考，随机采样
            return self.action_space.sample_actions(k)

        # 提取参考内容的结构
        ref_structures = []
        for ref in references:
            structure = ref.get("structure", {})
            hook = structure.get("hook")
            body = structure.get("body")
            cta = structure.get("cta")

            if hook and body and cta:
                ref_structures.append((hook, body, cta))

        if not ref_structures:
            return self.action_space.sample_actions(k)

        # 基于参考结构进行微创新采样
        actions = []
        for _ in range(k):
            # 随机选择一个参考结构
            base_action = random.choice(ref_structures)

            # 以一定概率变异每个维度
            mutated_action = self._mutate_action(base_action, mutation_rate=0.3)
            actions.append(mutated_action)

        return actions

    def _mutate_action(
        self,
        action: Tuple[str, str, str],
        mutation_rate: float = 0.3
    ) -> Tuple[str, str, str]:
        """变异动作（微创新）"""
        hook, body, cta = action

        # Hook 变异
        if random.random() < mutation_rate:
            hook = random.choice(list(self.action_space.HOOKS.keys()))

        # Body 变异
        if random.random() < mutation_rate:
            body = random.choice(list(self.action_space.BODIES.keys()))

        # CTA 变异
        if random.random() < mutation_rate:
            cta = random.choice(list(self.action_space.CTAS.keys()))

        return (hook, body, cta)

    async def _generate_rationales(
        self,
        actions: List[Tuple[str, str, str]],
        geo_constraints: Dict[str, Any],
        references: List[Dict[str, Any]]
    ) -> List[str]:
        """生成选择理由"""
        rationales = []

        for action in actions:
            hook, body, cta = action
            hook_name = self.action_space.get_action_name(hook)
            body_name = self.action_space.get_action_name(body)
            cta_name = self.action_space.get_action_name(cta)

            # 简单的理由生成（后续可以用 LLM 优化）
            rationale = f"{hook_name}适合吸引注意，{body_name}结构清晰，{cta_name}促进互动"
            rationales.append(rationale)

        return rationales

    def _calculate_diversity(self, actions: List[Tuple[str, str, str]]) -> float:
        """计算动作组的多样性分数"""
        if not actions:
            return 0.0

        # 统计不同动作的数量
        unique_hooks = len(set(a[0] for a in actions))
        unique_bodies = len(set(a[1] for a in actions))
        unique_ctas = len(set(a[2] for a in actions))

        # 归一化
        max_hooks = min(len(actions), len(self.action_space.HOOKS))
        max_bodies = min(len(actions), len(self.action_space.BODIES))
        max_ctas = min(len(actions), len(self.action_space.CTAS))

        diversity = (
            unique_hooks / max_hooks +
            unique_bodies / max_bodies +
            unique_ctas / max_ctas
        ) / 3.0

        return round(diversity, 3)
