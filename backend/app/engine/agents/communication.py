"""
Multi-Agent Communication and Collaboration System
多智能体通信与协作系统
"""

from typing import List, Dict, Any, Optional, Set
from enum import Enum
import asyncio
import logging
from datetime import datetime
from collections import defaultdict

logger = logging.getLogger(__name__)


class MessageType(str, Enum):
    """消息类型"""
    REQUEST = "request"  # 请求协助
    RESPONSE = "response"  # 响应请求
    BROADCAST = "broadcast"  # 广播消息
    NOTIFICATION = "notification"  # 通知
    QUERY = "query"  # 查询
    RESULT = "result"  # 结果


class MessagePriority(str, Enum):
    """消息优先级"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class Message:
    """消息"""

    def __init__(
        self,
        from_agent: str,
        to_agent: str,
        message_type: MessageType,
        content: Dict[str, Any],
        priority: MessagePriority = MessagePriority.MEDIUM,
        requires_response: bool = False
    ):
        self.id = self._generate_id()
        self.from_agent = from_agent
        self.to_agent = to_agent
        self.message_type = message_type
        self.content = content
        self.priority = priority
        self.requires_response = requires_response
        self.timestamp = datetime.now().isoformat()
        self.status = "pending"  # pending, delivered, read, responded

    def _generate_id(self) -> str:
        """生成消息 ID"""
        import uuid
        return str(uuid.uuid4())

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "from": self.from_agent,
            "to": self.to_agent,
            "type": self.message_type.value,
            "content": self.content,
            "priority": self.priority.value,
            "requires_response": self.requires_response,
            "timestamp": self.timestamp,
            "status": self.status
        }


class AgentCommunicationHub:
    """
    智能体通信中心

    功能:
    1. 消息路由
    2. 消息队列管理
    3. 广播消息
    4. 消息持久化
    5. 消息统计
    """

    def __init__(self):
        # 消息队列 (agent_name -> messages)
        self.message_queues = defaultdict(list)

        # 已注册的 Agent
        self.registered_agents: Set[str] = set()

        # 消息历史
        self.message_history = []

        # 统计信息
        self.stats = {
            "total_messages": 0,
            "messages_by_type": defaultdict(int),
            "messages_by_agent": defaultdict(int)
        }

    def register_agent(self, agent_name: str):
        """注册 Agent"""
        self.registered_agents.add(agent_name)
        logger.info(f"Agent registered: {agent_name}")

    def unregister_agent(self, agent_name: str):
        """注销 Agent"""
        self.registered_agents.discard(agent_name)
        logger.info(f"Agent unregistered: {agent_name}")

    async def send_message(self, message: Message) -> bool:
        """
        发送消息

        Args:
            message: 消息对象

        Returns:
            是否发送成功
        """
        # 检查接收者是否注册
        if message.to_agent not in self.registered_agents:
            logger.warning(f"Agent {message.to_agent} not registered")
            return False

        # 添加到接收者的消息队列
        self.message_queues[message.to_agent].append(message)

        # 更新消息状态
        message.status = "delivered"

        # 记录历史
        self.message_history.append(message)

        # 更新统计
        self.stats["total_messages"] += 1
        self.stats["messages_by_type"][message.message_type.value] += 1
        self.stats["messages_by_agent"][message.from_agent] += 1

        logger.debug(
            f"Message sent: {message.from_agent} -> {message.to_agent} "
            f"(type: {message.message_type.value})"
        )

        return True

    async def broadcast_message(
        self,
        from_agent: str,
        content: Dict[str, Any],
        exclude_agents: Optional[List[str]] = None
    ):
        """
        广播消息给所有 Agent

        Args:
            from_agent: 发送者
            content: 消息内容
            exclude_agents: 排除的 Agent 列表
        """
        exclude_agents = exclude_agents or []

        for agent_name in self.registered_agents:
            if agent_name != from_agent and agent_name not in exclude_agents:
                message = Message(
                    from_agent=from_agent,
                    to_agent=agent_name,
                    message_type=MessageType.BROADCAST,
                    content=content
                )
                await self.send_message(message)

        logger.info(f"Broadcast message from {from_agent} to {len(self.registered_agents) - 1} agents")

    async def receive_messages(
        self,
        agent_name: str,
        mark_as_read: bool = True
    ) -> List[Message]:
        """
        接收消息

        Args:
            agent_name: Agent 名称
            mark_as_read: 是否标记为已读

        Returns:
            消息列表
        """
        messages = self.message_queues[agent_name].copy()

        if mark_as_read:
            for message in messages:
                message.status = "read"

            # 清空队列
            self.message_queues[agent_name] = []

        return messages

    async def request_help(
        self,
        from_agent: str,
        to_agent: str,
        task: str,
        context: Dict[str, Any],
        priority: MessagePriority = MessagePriority.MEDIUM
    ) -> str:
        """
        请求其他 Agent 协助

        Args:
            from_agent: 请求者
            to_agent: 被请求者
            task: 任务描述
            context: 上下文信息
            priority: 优先级

        Returns:
            消息 ID
        """
        message = Message(
            from_agent=from_agent,
            to_agent=to_agent,
            message_type=MessageType.REQUEST,
            content={
                "task": task,
                "context": context
            },
            priority=priority,
            requires_response=True
        )

        await self.send_message(message)

        return message.id

    async def respond_to_request(
        self,
        from_agent: str,
        request_id: str,
        result: Dict[str, Any]
    ):
        """
        响应请求

        Args:
            from_agent: 响应者
            request_id: 请求消息 ID
            result: 结果
        """
        # 查找原始请求
        original_request = next(
            (msg for msg in self.message_history if msg.id == request_id),
            None
        )

        if not original_request:
            logger.warning(f"Request {request_id} not found")
            return

        # 发送响应
        response = Message(
            from_agent=from_agent,
            to_agent=original_request.from_agent,
            message_type=MessageType.RESPONSE,
            content={
                "request_id": request_id,
                "result": result
            }
        )

        await self.send_message(response)

        # 更新原始请求状态
        original_request.status = "responded"

    def get_pending_requests(self, agent_name: str) -> List[Message]:
        """获取待处理的请求"""
        messages = self.message_queues[agent_name]

        return [
            msg for msg in messages
            if msg.message_type == MessageType.REQUEST and msg.status == "delivered"
        ]

    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "total_messages": self.stats["total_messages"],
            "messages_by_type": dict(self.stats["messages_by_type"]),
            "messages_by_agent": dict(self.stats["messages_by_agent"]),
            "registered_agents": list(self.registered_agents),
            "pending_messages": {
                agent: len(messages)
                for agent, messages in self.message_queues.items()
            }
        }

    def get_message_history(
        self,
        agent_name: Optional[str] = None,
        message_type: Optional[MessageType] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """获取消息历史"""
        history = self.message_history

        # 过滤
        if agent_name:
            history = [
                msg for msg in history
                if msg.from_agent == agent_name or msg.to_agent == agent_name
            ]

        if message_type:
            history = [
                msg for msg in history
                if msg.message_type == message_type
            ]

        # 限制数量
        history = history[-limit:]

        return [msg.to_dict() for msg in history]


class AgentCollaborationOrchestrator:
    """
    智能体协作编排器

    功能:
    1. 任务分解
    2. Agent 分配
    3. 协作流程管理
    4. 结果聚合
    """

    def __init__(self, communication_hub: AgentCommunicationHub):
        self.hub = communication_hub
        self.active_collaborations = {}

    async def start_collaboration(
        self,
        task: str,
        context: Dict[str, Any],
        agents: List[str],
        strategy: str = "parallel"  # parallel, sequential, hierarchical
    ) -> str:
        """
        启动协作任务

        Args:
            task: 任务描述
            context: 上下文
            agents: 参与的 Agent 列表
            strategy: 协作策略

        Returns:
            协作 ID
        """
        import uuid
        collaboration_id = str(uuid.uuid4())

        # 分解任务
        subtasks = await self._decompose_task(task, context, len(agents))

        # 创建协作记录
        self.active_collaborations[collaboration_id] = {
            "task": task,
            "context": context,
            "agents": agents,
            "strategy": strategy,
            "subtasks": subtasks,
            "results": {},
            "status": "in_progress",
            "started_at": datetime.now().isoformat()
        }

        # 根据策略分配任务
        if strategy == "parallel":
            await self._parallel_execution(collaboration_id, agents, subtasks)
        elif strategy == "sequential":
            await self._sequential_execution(collaboration_id, agents, subtasks)
        elif strategy == "hierarchical":
            await self._hierarchical_execution(collaboration_id, agents, subtasks)

        return collaboration_id

    async def _decompose_task(
        self,
        task: str,
        context: Dict[str, Any],
        num_subtasks: int
    ) -> List[Dict[str, Any]]:
        """分解任务"""
        from app.llm.unified import unified_llm

        prompt = f"""Task: {task}

Context: {context}

Decompose this task into {num_subtasks} subtasks that can be executed by different agents.

Respond in JSON format:
{{
  "subtasks": [
    {{"id": 1, "description": "...", "dependencies": []}},
    {{"id": 2, "description": "...", "dependencies": [1]}},
    ...
  ]
}}"""

        try:
            response = await unified_llm.structured_output(
                messages=[{"role": "user", "content": prompt}],
                schema={"subtasks": "array"},
                provider="claude",
                model="sonnet-4.5",
                temperature=0.7
            )

            return response.get("subtasks", [])

        except Exception as e:
            logger.error(f"Task decomposition error: {e}")
            # 默认分解
            return [
                {"id": i + 1, "description": f"Subtask {i + 1}", "dependencies": []}
                for i in range(num_subtasks)
            ]

    async def _parallel_execution(
        self,
        collaboration_id: str,
        agents: List[str],
        subtasks: List[Dict[str, Any]]
    ):
        """并行执行"""
        # 分配任务给每个 Agent
        for i, agent in enumerate(agents):
            if i < len(subtasks):
                subtask = subtasks[i]

                await self.hub.send_message(Message(
                    from_agent="orchestrator",
                    to_agent=agent,
                    message_type=MessageType.REQUEST,
                    content={
                        "collaboration_id": collaboration_id,
                        "subtask": subtask
                    },
                    requires_response=True
                ))

    async def _sequential_execution(
        self,
        collaboration_id: str,
        agents: List[str],
        subtasks: List[Dict[str, Any]]
    ):
        """顺序执行"""
        # 按顺序分配任务
        for i, subtask in enumerate(subtasks):
            agent = agents[i % len(agents)]

            await self.hub.send_message(Message(
                from_agent="orchestrator",
                to_agent=agent,
                message_type=MessageType.REQUEST,
                content={
                    "collaboration_id": collaboration_id,
                    "subtask": subtask,
                    "wait_for_previous": i > 0
                },
                requires_response=True
            ))

    async def _hierarchical_execution(
        self,
        collaboration_id: str,
        agents: List[str],
        subtasks: List[Dict[str, Any]]
    ):
        """分层执行 (主 Agent + 子 Agent)"""
        # 第一个 Agent 作为主 Agent
        main_agent = agents[0]
        sub_agents = agents[1:]

        # 主 Agent 负责协调
        await self.hub.send_message(Message(
            from_agent="orchestrator",
            to_agent=main_agent,
            message_type=MessageType.REQUEST,
            content={
                "collaboration_id": collaboration_id,
                "role": "coordinator",
                "subtasks": subtasks,
                "sub_agents": sub_agents
            },
            requires_response=True
        ))

    async def collect_results(self, collaboration_id: str) -> Dict[str, Any]:
        """收集协作结果"""
        if collaboration_id not in self.active_collaborations:
            raise ValueError(f"Collaboration {collaboration_id} not found")

        collaboration = self.active_collaborations[collaboration_id]

        # 等待所有结果
        while len(collaboration["results"]) < len(collaboration["subtasks"]):
            await asyncio.sleep(0.1)

        # 聚合结果
        aggregated_result = await self._aggregate_results(
            collaboration["results"],
            collaboration["task"]
        )

        collaboration["status"] = "completed"
        collaboration["completed_at"] = datetime.now().isoformat()
        collaboration["aggregated_result"] = aggregated_result

        return aggregated_result

    async def _aggregate_results(
        self,
        results: Dict[str, Any],
        original_task: str
    ) -> Dict[str, Any]:
        """聚合结果"""
        from app.llm.unified import unified_llm

        prompt = f"""Original task: {original_task}

Subtask results:
{json.dumps(results, ensure_ascii=False, indent=2)}

Please aggregate these results into a final comprehensive result.

Respond in JSON format with the aggregated result."""

        try:
            response = await unified_llm.chat(
                messages=[{"role": "user", "content": prompt}],
                provider="claude",
                model="sonnet-4.5",
                temperature=0.5
            )

            import json
            return json.loads(response)

        except Exception as e:
            logger.error(f"Result aggregation error: {e}")
            return {"results": results}


# 全局实例
communication_hub = AgentCommunicationHub()
collaboration_orchestrator = AgentCollaborationOrchestrator(communication_hub)
