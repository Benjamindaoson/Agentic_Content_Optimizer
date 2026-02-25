"""
SwarmCoordinator: 3.0 蜂群协调器实现
实现基于竞价的任务分配和黑板模式。
"""

import asyncio
import logging
from typing import List, Dict, Any, Optional
from app.core.swarm_protocol import SwarmTask, AgentBid, AgentResult, IAgent, Blackboard

logger = logging.getLogger(__name__)

class SwarmCoordinator:
    def __init__(self):
        self.blackboard = Blackboard()
        self.running = False

    def register_agent(self, agent: IAgent):
        self.blackboard.agents.append(agent)
        logger.info(f"✅ Agent {agent.agent_id} 已加入蜂群")

    async def submit_task(self, description: str, caps: List[Any], priority: Any = None, context: Dict[str, Any] = None) -> str:
        from app.core.swarm_protocol import SwarmTask, TaskPriority
        task = SwarmTask(
            description=description,
            required_capabilities=caps,
            priority=priority or TaskPriority.MEDIUM,
            context=context or {}
        )
        self.blackboard.publish_task(task)
        logger.info(f"📝 新任务发布: {task.task_id} - {description}")
        return task.task_id

    async def run_until_complete(self, interval: float = 1.0):
        self.running = True
        logger.info("🐝 蜂群协调器启动...")
        
        while self.running:
            # 1. 触发竞价逻辑
            await self._process_bidding()
            
            # 2. 触发执行逻辑
            await self._process_execution()
            
            # 3. 检查是否所有任务完成
            pending_count = sum(1 for t in self.blackboard.active_tasks.values() if t.status != "completed")
            if pending_count == 0 and len(self.blackboard.active_tasks) > 0:
                logger.info("🏁 所有任务已完成")
                break
                
            await asyncio.sleep(interval)

    async def _process_bidding(self):
        for task_id, task in self.blackboard.active_tasks.items():
            if task.status == "pending":
                logger.info(f"🔍 任务 {task_id} 开始竞价...")
                task.status = "bidding"
                bids: List[AgentBid] = []
                
                # 并发收集竞价
                bid_tasks = [agent.bid(task) for agent in self.blackboard.agents]
                results = await asyncio.gather(*bid_tasks)
                
                for b in results:
                    if b: bids.append(b)
                
                if not bids:
                    logger.warning(f"⚠️ 任务 {task_id} 无人竞价，等待中...")
                    task.status = "pending"
                    continue
                
                # 选出信心值最高的
                best_bid = max(bids, key=lambda x: x.confidence_score)
                task.winning_agent = best_bid.agent_id
                task.status = "active"
                logger.info(f"🏆 任务 {task_id} 由 {best_bid.agent_id} 中标 (信心值: {best_bid.confidence_score})")

    async def _process_execution(self):
        active_tasks = [t for t in self.blackboard.active_tasks.values() if t.status == "active" and t.winning_agent]
        
        for task in active_tasks:
            # 找到中标的 agent
            agent = next((a for a in self.blackboard.agents if a.agent_id == task.winning_agent), None)
            if not agent:
                task.status = "pending"
                continue
            
            # 执行
            logger.info(f"⚡ Agent {agent.agent_id} 正在执行任务 {task.task_id}...")
            try:
                result = await agent.execute(task, self.blackboard.shared_memory)
                self.blackboard.completed_tasks.append(result)
                task.status = "completed"
                logger.info(f"✅ 任务 {task.task_id} 执行成功")
                
                # 如果有子任务，发布出去
                for sub in result.sub_tasks:
                    self.blackboard.publish_task(sub)
            except Exception as e:
                logger.error(f"❌ 任务 {task.task_id} 执行失败: {e}")
                task.status = "failed"
