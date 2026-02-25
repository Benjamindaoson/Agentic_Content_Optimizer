"""
账号池管理器

用于管理小红书账号，支持账号轮换、状态监控、风控策略
"""

import logging
from typing import List, Dict, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum
import asyncio

from sqlalchemy import Column, String, Integer, Float, DateTime, Boolean, JSON, Enum as SQLEnum
from sqlalchemy.orm import Session
from app.core.database import Base

logger = logging.getLogger(__name__)


class AccountStatus(str, Enum):
    """账号状态"""
    ACTIVE = 'active'  # 正常
    LIMITED = 'limited'  # 受限（限流）
    BANNED = 'banned'  # 封禁
    COOLING = 'cooling'  # 冷却中
    MAINTENANCE = 'maintenance'  # 维护中


class AccountType(str, Enum):
    """账号类型"""
    PERSONAL = 'personal'  # 个人号
    BUSINESS = 'business'  # 企业号
    PRO = 'pro'  # 专业号


# ==================== 数据库模型 ====================

class XHSAccount(Base):
    """小红书账号表"""
    __tablename__ = 'xhs_accounts'

    account_id = Column(String(64), primary_key=True, comment='账号ID')
    username = Column(String(128), nullable=False, comment='用户名')
    nickname = Column(String(128), comment='昵称')
    account_type = Column(SQLEnum(AccountType), default=AccountType.PERSONAL, comment='账号类型')

    # 认证信息
    cookies = Column(JSON, comment='登录凭证')
    token = Column(String(512), comment='访问令牌')

    # 状态信息
    status = Column(SQLEnum(AccountStatus), default=AccountStatus.ACTIVE, comment='账号状态')
    last_used = Column(DateTime, comment='最后使用时间')
    last_check = Column(DateTime, comment='最后检查时间')

    # 统计信息
    total_posts = Column(Integer, default=0, comment='总发布数')
    success_posts = Column(Integer, default=0, comment='成功发布数')
    failed_posts = Column(Integer, default=0, comment='失败发布数')

    # 限流信息
    daily_limit = Column(Integer, default=10, comment='每日发布限制')
    hourly_limit = Column(Integer, default=3, comment='每小时发布限制')
    posts_today = Column(Integer, default=0, comment='今日已发布')
    posts_this_hour = Column(Integer, default=0, comment='本小时已发布')

    # 风控信息
    risk_score = Column(Float, default=0.0, comment='风险分数')
    ban_count = Column(Integer, default=0, comment='封禁次数')
    last_ban_time = Column(DateTime, comment='最后封禁时间')
    cooling_until = Column(DateTime, comment='冷却截止时间')

    # 元数据
    created_at = Column(DateTime, default=datetime.now, comment='创建时间')
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment='更新时间')
    metadata = Column(JSON, comment='其他元数据')


@dataclass
class AccountHealth:
    """账号健康度"""
    account_id: str
    status: AccountStatus
    health_score: float  # 0.0 到 1.0
    is_available: bool
    daily_quota_remaining: int
    hourly_quota_remaining: int
    risk_level: str  # 'low', 'medium', 'high'
    recommendation: str  # 'use', 'rest', 'check', 'retire'


class AccountPool:
    """
    账号池管理器

    功能：
    1. 账号轮换策略
    2. 状态监控
    3. 限流管理
    4. 风控策略
    5. 自动恢复
    """

    def __init__(
        self,
        db: Session,
        default_daily_limit: int = 10,
        default_hourly_limit: int = 3,
        cooling_period_hours: int = 24,
        risk_threshold: float = 0.7
    ):
        self.db = db
        self.default_daily_limit = default_daily_limit
        self.default_hourly_limit = default_hourly_limit
        self.cooling_period_hours = cooling_period_hours
        self.risk_threshold = risk_threshold

    def add_account(
        self,
        account_id: str,
        username: str,
        nickname: str,
        account_type: AccountType,
        cookies: Dict,
        token: Optional[str] = None
    ) -> XHSAccount:
        """
        添加账号

        Args:
            account_id: 账号ID
            username: 用户名
            nickname: 昵称
            account_type: 账号类型
            cookies: 登录凭证
            token: 访问令牌

        Returns:
            账号对象
        """
        account = XHSAccount(
            account_id=account_id,
            username=username,
            nickname=nickname,
            account_type=account_type,
            cookies=cookies,
            token=token,
            status=AccountStatus.ACTIVE,
            daily_limit=self.default_daily_limit,
            hourly_limit=self.default_hourly_limit
        )

        self.db.add(account)
        self.db.commit()

        logger.info(f"✅ 账号已添加: {account_id} ({nickname})")

        return account

    def get_available_account(
        self,
        strategy: str = 'round_robin'
    ) -> Optional[XHSAccount]:
        """
        获取可用账号

        Args:
            strategy: 选择策略
                - round_robin: 轮询
                - least_used: 最少使用
                - best_health: 最佳健康度

        Returns:
            账号对象
        """
        # 1. 筛选可用账号
        now = datetime.now()

        available_accounts = self.db.query(XHSAccount).filter(
            XHSAccount.status == AccountStatus.ACTIVE,
            XHSAccount.posts_today < XHSAccount.daily_limit,
            XHSAccount.posts_this_hour < XHSAccount.hourly_limit
        ).all()

        if not available_accounts:
            logger.warning("没有可用账号")
            return None

        # 2. 根据策略选择
        if strategy == 'round_robin':
            # 选择最久未使用的
            account = min(
                available_accounts,
                key=lambda a: a.last_used or datetime.min
            )

        elif strategy == 'least_used':
            # 选择今日使用最少的
            account = min(
                available_accounts,
                key=lambda a: a.posts_today
            )

        elif strategy == 'best_health':
            # 选择健康度最高的
            health_scores = {}
            for acc in available_accounts:
                health = self.check_account_health(acc.account_id)
                health_scores[acc.account_id] = health.health_score

            account = max(
                available_accounts,
                key=lambda a: health_scores.get(a.account_id, 0)
            )

        else:
            account = available_accounts[0]

        # 3. 更新使用时间
        account.last_used = now
        self.db.commit()

        logger.info(f"选择账号: {account.account_id} ({account.nickname})")

        return account

    def mark_post_success(self, account_id: str):
        """标记发布成功"""
        account = self.db.query(XHSAccount).filter(
            XHSAccount.account_id == account_id
        ).first()

        if not account:
            return

        account.success_posts += 1
        account.total_posts += 1
        account.posts_today += 1
        account.posts_this_hour += 1

        # 降低风险分数
        account.risk_score = max(0, account.risk_score - 0.05)

        self.db.commit()

        logger.info(f"✅ 发布成功: {account_id}")

    def mark_post_failure(
        self,
        account_id: str,
        error_type: str = 'unknown'
    ):
        """
        标记发布失败

        Args:
            account_id: 账号ID
            error_type: 错误类型
                - rate_limit: 限流
                - banned: 封禁
                - network: 网络错误
                - unknown: 未知错误
        """
        account = self.db.query(XHSAccount).filter(
            XHSAccount.account_id == account_id
        ).first()

        if not account:
            return

        account.failed_posts += 1
        account.total_posts += 1

        # 根据错误类型调整状态
        if error_type == 'rate_limit':
            account.status = AccountStatus.LIMITED
            account.risk_score = min(1.0, account.risk_score + 0.2)

        elif error_type == 'banned':
            account.status = AccountStatus.BANNED
            account.ban_count += 1
            account.last_ban_time = datetime.now()
            account.risk_score = 1.0

            # 设置冷却期
            account.cooling_until = datetime.now() + timedelta(
                hours=self.cooling_period_hours
            )

        else:
            account.risk_score = min(1.0, account.risk_score + 0.1)

        self.db.commit()

        logger.warning(f"❌ 发布失败: {account_id}, 错误类型={error_type}")

    def check_account_health(self, account_id: str) -> AccountHealth:
        """
        检查账号健康度

        Args:
            account_id: 账号ID

        Returns:
            健康度信息
        """
        account = self.db.query(XHSAccount).filter(
            XHSAccount.account_id == account_id
        ).first()

        if not account:
            raise ValueError(f"账号不存在: {account_id}")

        # 1. 计算健康分数
        health_score = 1.0

        # 成功率
        if account.total_posts > 0:
            success_rate = account.success_posts / account.total_posts
            health_score *= success_rate

        # 风险分数
        health_score *= (1.0 - account.risk_score)

        # 封禁次数
        health_score *= (0.9 ** account.ban_count)

        # 2. 判断可用性
        is_available = (
            account.status == AccountStatus.ACTIVE and
            account.posts_today < account.daily_limit and
            account.posts_this_hour < account.hourly_limit
        )

        # 3. 计算剩余配额
        daily_quota_remaining = account.daily_limit - account.posts_today
        hourly_quota_remaining = account.hourly_limit - account.posts_this_hour

        # 4. 风险等级
        if account.risk_score < 0.3:
            risk_level = 'low'
        elif account.risk_score < 0.7:
            risk_level = 'medium'
        else:
            risk_level = 'high'

        # 5. 推荐操作
        if account.status == AccountStatus.BANNED:
            recommendation = 'retire'
        elif account.risk_score > self.risk_threshold:
            recommendation = 'rest'
        elif not is_available:
            recommendation = 'check'
        else:
            recommendation = 'use'

        return AccountHealth(
            account_id=account_id,
            status=account.status,
            health_score=health_score,
            is_available=is_available,
            daily_quota_remaining=daily_quota_remaining,
            hourly_quota_remaining=hourly_quota_remaining,
            risk_level=risk_level,
            recommendation=recommendation
        )

    async def reset_daily_counters(self):
        """重置每日计数器（定时任务）"""
        accounts = self.db.query(XHSAccount).all()

        for account in accounts:
            account.posts_today = 0

            # 如果在冷却期，检查是否可以恢复
            if account.status == AccountStatus.COOLING:
                if account.cooling_until and datetime.now() > account.cooling_until:
                    account.status = AccountStatus.ACTIVE
                    account.cooling_until = None
                    logger.info(f"账号已恢复: {account.account_id}")

        self.db.commit()

        logger.info("✅ 每日计数器已重置")

    async def reset_hourly_counters(self):
        """重置每小时计数器（定时任务）"""
        accounts = self.db.query(XHSAccount).all()

        for account in accounts:
            account.posts_this_hour = 0

        self.db.commit()

        logger.info("✅ 每小时计数器已重置")

    def get_pool_stats(self) -> Dict:
        """获取账号池统计"""
        accounts = self.db.query(XHSAccount).all()

        status_counts = {}
        for status in AccountStatus:
            status_counts[status.value] = sum(
                1 for a in accounts if a.status == status
            )

        total_posts = sum(a.total_posts for a in accounts)
        success_posts = sum(a.success_posts for a in accounts)
        success_rate = success_posts / total_posts if total_posts > 0 else 0

        available_count = sum(
            1 for a in accounts
            if a.status == AccountStatus.ACTIVE and
            a.posts_today < a.daily_limit and
            a.posts_this_hour < a.hourly_limit
        )

        return {
            'total_accounts': len(accounts),
            'status_distribution': status_counts,
            'available_accounts': available_count,
            'total_posts': total_posts,
            'success_posts': success_posts,
            'success_rate': success_rate,
            'avg_risk_score': sum(a.risk_score for a in accounts) / len(accounts) if accounts else 0
        }


# ==================== 使用示例 ====================

async def example_usage():
    """使用示例"""
    from app.db import get_db

    db = next(get_db())

    # 1. 创建账号池
    pool = AccountPool(
        db=db,
        default_daily_limit=10,
        default_hourly_limit=3,
        cooling_period_hours=24
    )

    # 2. 添加账号
    account = pool.add_account(
        account_id='xhs_001',
        username='user001',
        nickname='测试账号1',
        account_type=AccountType.PERSONAL,
        cookies={'session': 'xxx'},
        token='token_xxx'
    )

    # 3. 获取可用账号
    available = pool.get_available_account(strategy='best_health')
    if available:
        print(f"可用账号: {available.nickname}")

        # 4. 发布内容
        try:
            # ... 发布逻辑
            pool.mark_post_success(available.account_id)
        except Exception as e:
            pool.mark_post_failure(available.account_id, error_type='network')

    # 5. 检查健康度
    health = pool.check_account_health('xhs_001')
    print(f"健康度: {health.health_score:.2f}")
    print(f"推荐: {health.recommendation}")

    # 6. 获取统计
    stats = pool.get_pool_stats()
    print(f"账号池统计: {stats}")
