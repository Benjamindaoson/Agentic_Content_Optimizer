"""
MultiModalCriticAgent: 3.0 多模态评估 Agent
负责内容质量、视觉审美以及图文一致性的评估。
"""

import logging
from typing import List, Optional, Any
from app.core.swarm_protocol import IAgent, SwarmTask, AgentBid, AgentResult, AgentCapability

logger = logging.getLogger(__name__)

class MultiModalCriticAgent(IAgent):
    def __init__(self, agent_id: str = "critic_mm_01"):
        self._agent_id = agent_id

    @property
    def agent_id(self) -> str: return self._agent_id

    @property
    def capabilities(self) -> List[AgentCapability]:
        return [AgentCapability.CRITIC_QUALITY]

    async def bid(self, task: SwarmTask) -> Optional[AgentBid]:
        if AgentCapability.CRITIC_QUALITY not in task.required_capabilities:
            return None
        
        return AgentBid(
            agent_id=self.agent_id,
            task_id=task.task_id,
            confidence_score=0.95,
            estimated_tokens=500,
            approach_summary="从文本情感、视觉张力、和平台契合度三个维度进行多模态综合打分。"
        )

    async def execute(self, task: SwarmTask, shared_memory: Any) -> AgentResult:
        content = task.context.get("content", {})
        visual_plan = task.context.get("visual_plan", {})
        
        logger.info(f"CriticAgent {self.agent_id} 正在执行深度评估...")
        
        # 1. 基础评分 (初始化)
        scores = {
            "text_hook_score": 0.88,
            "viral_probability": 0.82
        }

        # 4.0 Sim-to-Real: 接入真实 LLM (DeepSeek-V3) 进行纯文本质量评估
        try:
            from langchain_openai import ChatOpenAI
            from langchain_core.prompts import ChatPromptTemplate
            from app.core.config import get_settings
            
            settings = get_settings()
            
            # 使用与 Writer 相同的 DeepSeek 配置
            if settings.DEEPSEEK_API_KEY:
                api_key = settings.DEEPSEEK_API_KEY
                base_url = settings.DEEPSEEK_API_BASE
                model = getattr(settings, 'DEEPSEEK_MODEL', 'deepseek-chat')
                
                critic_llm = ChatOpenAI(
                    model=model, 
                    temperature=0.2, # 评估需要严谨稳定
                    api_key=api_key,
                    base_url=base_url
                )
                logger.info(f"👁️ CriticAgent 使用 {model} 进行纯文本评估")
                
                # 构造 Prompt (通用社交媒体爆款评估，取消图文要求因为只需要纯文本测试)
                prompt_content = f"请作为一位资深的社交媒体（小红书/抖音等）自媒体爆款拆解专家，评估以下内容流传度和爆款潜力。标题：{content.get('title')}，Hook：{content.get('hook')}。请结合用户的痛点（如情绪价值、干货程度、互动诱导），给出一个 0 到 1 之间的潜力打分。仅返回包含数字的文本即可。不要包含 markdown 格式。"
                
                response = await critic_llm.ainvoke(prompt_content)
                
                # 解析评分
                import re
                score_match = re.search(r"(\d+(\.\d+)?)", response.content)
                if score_match:
                    ds_score = float(score_match.group(1))
                    if ds_score > 1.0: ds_score /= 10.0 # 归一化，比如如果它回答 8.5
                    scores["deepseek_text_score"] = ds_score
                    logger.info(f"🤖 DeepSeek 质量打分: {ds_score}")
                else:
                    logger.warning("未能从 DeepSeek 响应中提取数字分数。")
            else:
                logger.warning("未配置 DEEPSEEK_API_KEY，跳过真实评估。")
                    
        except Exception as e:
            logger.warning(f"⚠️ Critic 模型调用失败，回退: {e}")


        # 2. Stage 2: 多模态对齐评估 (从共享内存中获取 Aligner)
        if "mm_aligner" in shared_memory:
            aligner = shared_memory["mm_aligner"]
            mm_results = aligner.score_alignment(content, visual_plan or {})
            scores.update(mm_results)
            logger.info(f"✅ 多模态对齐分: {mm_results['overall_mm_score']:.2f}")

        # 3. Stage 2: 因果归因评估 (剥离背景增益)
        if "causal_scorer" in shared_memory:
            scorer = shared_memory["causal_scorer"]
            # 我们模拟一个观察到的点击率作为输入
            insight = scorer.estimate_causal_reward(
                metrics={"engagement_rate": 0.12},
                context=task.context,
                strategy_action=content
            )
            scores["causal_lift"] = insight.causal_lift
            scores["baseline_impact"] = insight.estimated_baseline
            logger.info(f"✅ 因果归因完成: Lift={insight.causal_lift:.2f}")

        final_score = sum(scores.values()) / len(scores)
        
        refine_needed = final_score < 0.8
        sub_tasks = []
        
        if refine_needed:
            sub_tasks.append(SwarmTask(
                description="基于因果反馈修正内容：策略对结果的贡献度不足，需加强 Hook 的异质性。",
                required_capabilities=[AgentCapability.CONTENT_WRITING],
                context={"old_content": content, "causal_insight": scores.get("causal_lift")}
            ))

        return AgentResult(
            agent_id=self.agent_id,
            task_id=task.task_id,
            output_data={
                "scores": scores,
                "final_score": final_score,
                "recommend_publish": not refine_needed,
                "causal_report": "策略增益显著" if scores.get("causal_lift", 0) > 0.05 else "建议优化策略"
            },
            sub_tasks=sub_tasks
        )
