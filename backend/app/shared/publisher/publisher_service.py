"""
发布服务

用于管理内容发布、排程、状态追踪
"""

import logging
from typing import List, Dict, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum
import asyncio

from sqlalchemy import Column, String, Integer, DateTime, Boolean, JSON, Enum as SQLEnum, Text, ForeignKey
from sqlalchemy.orm import Session, relationship
from app.core.database import Base
from app.publisher.account_pool import AccountPool, XHSAccount

logger = logging.getLogger(__name__)


class PublishStatus(str, Enum):
    """发布状态"""
    DRAFT = 'draft'  # 草稿
    SCHEDULED = 'scheduled'  # 已排程
    PUBLISHING = 'publishing'  # 发布中
    PUBLISHED = 'published'  # 已发布
    FAILED = 'failed'  # 失败
    DELETED = 'deleted'  # 已删除


class ContentType(str, Enum):
    """内容类型"""
    NOTE = 'note'  # 图文笔记
    VIDEO = 'video'  # 视频
    LIVE = 'live'  # 直播


# ==================== 数据库模型 ====================

class PublishTask(Base):
    """发布任务表"""
    __tablename__ = 'publish_tasks'

    task_id = Column(String(64), primary_key=True, comment='任务ID')
    generation_id = Column(String(64), ForeignKey('generations.generation_id'), comment='生成ID')

    # 内容信息
    content_type = Column(SQLEnum(ContentType), default=ContentType.NOTE, comment='内容类型')
    title = Column(String(512), nullable=False, comment='标题')
    text = Column(Text, nullable=False, comment='正文')
    cover_path = Column(String(512), comment='封面路径')
    image_paths = Column(JSON, comment='图片路径列表')

    # 发布信息
    account_id = Column(String(64), ForeignKey('xhs_accounts.account_id'), comment='账号ID')
    status = Column(SQLEnum(PublishStatus), default=PublishStatus.DRAFT, comment='发布状态')
    scheduled_time = Column(DateTime, comment='排程时间')
    published_time = Column(DateTime, comment='实际发布时间')

    # 发布结果
    note_id = Column(String(64), comment='小红书笔记ID')
    publish_url = Column(String(512), comment='发布链接')
    error_message = Column(Text, comment='错误信息')
    retry_count = Column(Integer, default=0, comment='重试次数')

    # 元数据
    created_at = Column(DateTime, default=datetime.now, comment='创建时间')
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment='更新时间')
    metadata = Column(JSON, comment='其他元数据')

    # 关系
    generation = relationship("Generation", back_populates="publish_tasks")
    account = relationship("XHSAccount")


class ContentAsset(Base):
    """内容资产表"""
    __tablename__ = 'content_assets'

    asset_id = Column(String(64), primary_key=True, comment='资产ID')
    task_id = Column(String(64), ForeignKey('publish_tasks.task_id'), comment='任务ID')

    # 资产信息
    asset_type = Column(String(32), comment='资产类型（cover/image/video/audio）')
    file_path = Column(String(512), nullable=False, comment='文件路径')
    file_size = Column(Integer, comment='文件大小（字节）')
    file_hash = Column(String(64), comment='文件哈希')

    # 版本信息
    version = Column(Integer, default=1, comment='版本号')
    is_active = Column(Boolean, default=True, comment='是否激活')

    # 元数据
    created_at = Column(DateTime, default=datetime.now, comment='创建时间')
    metadata = Column(JSON, comment='其他元数据')

    # 关系
    task = relationship("PublishTask")


@dataclass
class PublishResult:
    """发布结果"""
    success: bool
    task_id: str
    note_id: Optional[str] = None
    publish_url: Optional[str] = None
    error_message: Optional[str] = None


class PublisherService:
    """
    发布服务

    功能：
    1. 草稿管理
    2. 发布排程
    3. 自动发布
    4. 状态追踪
    5. 失败重试
    """

    def __init__(
        self,
        db: Session,
        account_pool: AccountPool,
        max_retry: int = 3,
        retry_delay_minutes: int = 30
    ):
        self.db = db
        self.account_pool = account_pool
        self.max_retry = max_retry
        self.retry_delay_minutes = retry_delay_minutes

    def create_draft(
        self,
        generation_id: str,
        title: str,
        text: str,
        cover_path: Optional[str] = None,
        image_paths: Optional[List[str]] = None,
        content_type: ContentType = ContentType.NOTE
    ) -> PublishTask:
        """
        创建草稿

        Args:
            generation_id: 生成ID
            title: 标题
            text: 正文
            cover_path: 封面路径
            image_paths: 图片路径列表
            content_type: 内容类型

        Returns:
            发布任务
        """
        import uuid

        task_id = f"task_{uuid.uuid4().hex[:16]}"

        task = PublishTask(
            task_id=task_id,
            generation_id=generation_id,
            content_type=content_type,
            title=title,
            text=text,
            cover_path=cover_path,
            image_paths=image_paths or [],
            status=PublishStatus.DRAFT
        )

        self.db.add(task)
        self.db.commit()

        logger.info(f"✅ 草稿已创建: {task_id}")

        return task

    def schedule_publish(
        self,
        task_id: str,
        scheduled_time: datetime,
        account_id: Optional[str] = None
    ):
        """
        排程发布

        Args:
            task_id: 任务ID
            scheduled_time: 排程时间
            account_id: 指定账号ID（可选）
        """
        task = self.db.query(PublishTask).filter(
            PublishTask.task_id == task_id
        ).first()

        if not task:
            raise ValueError(f"任务不存在: {task_id}")

        if task.status not in [PublishStatus.DRAFT, PublishStatus.FAILED]:
            raise ValueError(f"任务状态不允许排程: {task.status}")

        task.scheduled_time = scheduled_time
        task.account_id = account_id
        task.status = PublishStatus.SCHEDULED

        self.db.commit()

        logger.info(f"✅ 已排程: {task_id}, 时间={scheduled_time}")

    async def publish_now(
        self,
        task_id: str,
        account_id: Optional[str] = None
    ) -> PublishResult:
        """
        立即发布

        Args:
            task_id: 任务ID
            account_id: 指定账号ID（可选）

        Returns:
            发布结果
        """
        task = self.db.query(PublishTask).filter(
            PublishTask.task_id == task_id
        ).first()

        if not task:
            raise ValueError(f"任务不存在: {task_id}")

        # 1. 选择账号
        if account_id:
            account = self.db.query(XHSAccount).filter(
                XHSAccount.account_id == account_id
            ).first()
        else:
            account = self.account_pool.get_available_account(strategy='best_health')

        if not account:
            return PublishResult(
                success=False,
                task_id=task_id,
                error_message='没有可用账号'
            )

        # 2. 更新状态
        task.status = PublishStatus.PUBLISHING
        task.account_id = account.account_id
        self.db.commit()

        # 3. 执行发布
        try:
            result = await self._do_publish(task, account)

            if result.success:
                # 发布成功
                task.status = PublishStatus.PUBLISHED
                task.note_id = result.note_id
                task.publish_url = result.publish_url
                task.published_time = datetime.now()

                self.account_pool.mark_post_success(account.account_id)

                logger.info(f"✅ 发布成功: {task_id}, note_id={result.note_id}")

            else:
                # 发布失败
                task.status = PublishStatus.FAILED
                task.error_message = result.error_message
                task.retry_count += 1

                self.account_pool.mark_post_failure(
                    account.account_id,
                    error_type=self._classify_error(result.error_message)
                )

                logger.error(f"❌ 发布失败: {task_id}, error={result.error_message}")

            self.db.commit()

            return result

        except Exception as e:
            task.status = PublishStatus.FAILED
            task.error_message = str(e)
            task.retry_count += 1
            self.db.commit()

            logger.error(f"❌ 发布异常: {task_id}, error={e}")

            return PublishResult(
                success=False,
                task_id=task_id,
                error_message=str(e)
            )

    async def _do_publish(
        self,
        task: PublishTask,
        account: XHSAccount
    ) -> PublishResult:
        """
        执行发布（实际调用小红书API）

        Args:
            task: 发布任务
            account: 账号

        Returns:
            发布结果
        """
        # TODO: 实际集成小红书发布API
        # 这里是示例代码

        try:
            # 模拟发布
            await asyncio.sleep(1)

            # 模拟成功
            import uuid
            note_id = f"note_{uuid.uuid4().hex[:16]}"
            publish_url = f"https://www.xiaohongshu.com/explore/{note_id}"

            return PublishResult(
                success=True,
                task_id=task.task_id,
                note_id=note_id,
                publish_url=publish_url
            )

        except Exception as e:
            return PublishResult(
                success=False,
                task_id=task.task_id,
                error_message=str(e)
            )

    async def process_scheduled_tasks(self):
        """
        处理排程任务（定时任务）

        每分钟执行一次，检查是否有到期的排程任务
        """
        now = datetime.now()

        # 查询到期的排程任务
        tasks = self.db.query(PublishTask).filter(
            PublishTask.status == PublishStatus.SCHEDULED,
            PublishTask.scheduled_time <= now
        ).all()

        logger.info(f"发现 {len(tasks)} 个到期任务")

        # 逐个发布
        for task in tasks:
            try:
                result = await self.publish_now(task.task_id, task.account_id)

                if not result.success and task.retry_count < self.max_retry:
                    # 失败且未超过重试次数，重新排程
                    new_scheduled_time = now + timedelta(minutes=self.retry_delay_minutes)
                    self.schedule_publish(task.task_id, new_scheduled_time, task.account_id)

                    logger.info(f"任务将重试: {task.task_id}, 时间={new_scheduled_time}")

            except Exception as e:
                logger.error(f"处理排程任务失败: {task.task_id}, error={e}")

    def get_task_status(self, task_id: str) -> Dict:
        """获取任务状态"""
        task = self.db.query(PublishTask).filter(
            PublishTask.task_id == task_id
        ).first()

        if not task:
            raise ValueError(f"任务不存在: {task_id}")

        return {
            'task_id': task.task_id,
            'generation_id': task.generation_id,
            'status': task.status.value,
            'account_id': task.account_id,
            'scheduled_time': task.scheduled_time.isoformat() if task.scheduled_time else None,
            'published_time': task.published_time.isoformat() if task.published_time else None,
            'note_id': task.note_id,
            'publish_url': task.publish_url,
            'error_message': task.error_message,
            'retry_count': task.retry_count
        }

    def get_publish_stats(self) -> Dict:
        """获取发布统计"""
        tasks = self.db.query(PublishTask).all()

        status_counts = {}
        for status in PublishStatus:
            status_counts[status.value] = sum(
                1 for t in tasks if t.status == status
            )

        total_published = status_counts.get(PublishStatus.PUBLISHED.value, 0)
        total_failed = status_counts.get(PublishStatus.FAILED.value, 0)
        success_rate = total_published / (total_published + total_failed) if (total_published + total_failed) > 0 else 0

        return {
            'total_tasks': len(tasks),
            'status_distribution': status_counts,
            'success_rate': success_rate,
            'avg_retry_count': sum(t.retry_count for t in tasks) / len(tasks) if tasks else 0
        }

    def _classify_error(self, error_message: Optional[str]) -> str:
        """分类错误类型"""
        if not error_message:
            return 'unknown'

        error_lower = error_message.lower()

        if 'rate' in error_lower or 'limit' in error_lower or '限流' in error_lower:
            return 'rate_limit'
        elif 'ban' in error_lower or '封禁' in error_lower or '违规' in error_lower:
            return 'banned'
        elif 'network' in error_lower or '网络' in error_lower or 'timeout' in error_lower:
            return 'network'
        else:
            return 'unknown'


# ==================== 使用示例 ====================

async def example_usage():
    """使用示例"""
    from app.db import get_db
    from app.publisher.account_pool import AccountPool

    db = next(get_db())

    # 1. 创建账号池和发布服务
    account_pool = AccountPool(db)
    publisher = PublisherService(db, account_pool)

    # 2. 创建草稿
    task = publisher.create_draft(
        generation_id='gen_123',
        title='测试标题',
        text='测试内容',
        cover_path='/path/to/cover.jpg'
    )

    # 3. 立即发布
    result = await publisher.publish_now(task.task_id)
    print(f"发布结果: {result}")

    # 4. 排程发布
    scheduled_time = datetime.now() + timedelta(hours=2)
    publisher.schedule_publish(task.task_id, scheduled_time)

    # 5. 处理排程任务（定时任务）
    await publisher.process_scheduled_tasks()

    # 6. 获取统计
    stats = publisher.get_publish_stats()
    print(f"发布统计: {stats}")
