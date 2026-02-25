"""
WriterAgent: 3.0 蜂群写作 Agent
实现竞价和自治写作逻辑。
"""

import logging
from typing import List, Optional, Any
from app.core.swarm_protocol import IAgent, SwarmTask, AgentBid, AgentResult, AgentCapability, SwarmTask, TaskPriority

logger = logging.getLogger(__name__)

class WriterAgent(IAgent):
    def __init__(self, agent_id: str = "writer_01"):
        self._agent_id = agent_id

    @property
    def agent_id(self) -> str: return self._agent_id

    @property
    def capabilities(self) -> List[AgentCapability]:
        return [AgentCapability.CONTENT_WRITING]

    async def bid(self, task: SwarmTask) -> Optional[AgentBid]:
        if AgentCapability.CONTENT_WRITING not in task.required_capabilities:
            return None
        
        # 模拟信心评估：如果任务描述包含"小红书"或"写作"，信心值高
        confidence = 0.9 if "写作" in task.description or "笔记" in task.description else 0.7
        
        return AgentBid(
            agent_id=self.agent_id,
            task_id=task.task_id,
            confidence_score=confidence,
            estimated_tokens=800,
            approach_summary="使用爆款模式库进行多维度内容重构，注重 Hook 的张力。"
        )

    async def execute(self, task: SwarmTask, shared_memory: Any) -> AgentResult:
        logger.info(f"WriterAgent {self.agent_id} 正在撰写: {task.description}")
        
        topic = task.context.get("topic", "未知话题")
        
        # 4.0 Sim-to-Real: 接入真实 LLM (DeepSeek-V3)
        try:
            from langchain_openai import ChatOpenAI
            from langchain_core.prompts import ChatPromptTemplate
            from app.core.config import get_settings
            
            settings = get_settings()
            # 优先使用 DeepSeek，如果未配置则尝试 OpenAI，否则报错回退
            if settings.DEEPSEEK_API_KEY:
                api_key = settings.DEEPSEEK_API_KEY
                base_url = settings.DEEPSEEK_API_BASE
                model = getattr(settings, 'DEEPSEEK_MODEL', 'deepseek-chat')
                logger.info(f"🚀 WriterAgent 使用 {model} ({base_url})")
            elif settings.OPENAI_API_KEY:
                api_key = settings.OPENAI_API_KEY
                base_url = None
                model = "gpt-4-turbo"
                logger.info("🚀 WriterAgent 使用 OpenAI GPT-4")
            else:
                raise ValueError("缺失 DEEPSEEK_API_KEY 或 OPENAI_API_KEY")

            llm = ChatOpenAI(
                model=model, 
                temperature=0.8, # DeepSeek 建议稍高温度以增加创造力
                api_key=api_key,
                base_url=base_url
            )
            
            prompt = ChatPromptTemplate.from_template(
                """你是一个小红书爆款文案专家。请基于话题“{topic}”写一篇笔记。
                要求：
                1. 标题要在 20 字以内，带 emoji，极具吸引力。
                2. 开头 (Hook) 要制造悬念或共鸣。
                3. 正文 (Body) 分点阐述，干货满满。
                4. 结尾 (CTA) 引导关注。
                
                返回 JSON 格式：
                {{
                    "title": "...",
                    "hook": "...",
                    "body": "...",
                    "cta": "..."
                }}
                """
            )
            
            chain = prompt | llm
            response = await chain.ainvoke({"topic": topic})
            
            import json
            # 简单的 JSON 清洗逻辑
            content_str = response.content.replace("```json", "").replace("```", "")
            content = json.loads(content_str)
            
        except Exception as e:
            logger.warning(f"⚠️ LLM 调用失败或未配置，回退到模拟模式: {e}")
            content = {
                "title": f"【模拟】关于{topic}的深度解析",
                "text": f"（这是模拟数据，因 API 未配置）探讨了{topic}的核心秘密...",
                "hook": "你以为你了解这个吗？",
                "body": "第一，第二，第三...",
                "cta": "点个三连支持下！"
            }

        # 3.0 特色：主动发布子任务（例如：请求视觉设计）
        visual_task = SwarmTask(
            description=f"为话题《{topic}》设计封面视觉方案",
            required_capabilities=[AgentCapability.IMAGE_GENERATION],
            priority=TaskPriority.HIGH,
            context={"content_style": "精致、对比鲜明", "text_overlay": content.get("title", "")}
        )
        
        # 请求质量评估子任务
        critic_task = SwarmTask(
            description=f"评估内容的爆款潜力和图文对齐度",
            required_capabilities=[AgentCapability.CRITIC_QUALITY],
            priority=TaskPriority.MEDIUM,
            context={"content": content}
        )

        return AgentResult(
            agent_id=self.agent_id,
            task_id=task.task_id,
            output_data={"content": content},
            metrics={"quality_est": 0.85},
            sub_tasks=[visual_task, critic_task]
        )
