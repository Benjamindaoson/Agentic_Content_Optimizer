"""
数据质量服务

用于持续审计数据完整性、自动修复、质量评分
"""

import logging
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum
import asyncio

from sqlalchemy import Column, String, Integer, Float, DateTime, Boolean, JSON, Enum as SQLEnum, Text
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_
from app.core.database import Base
from app.db import XHSNote, XHSMetrics, XHSCover, XHSAnalysis, OnlineMetrics

logger = logging.getLogger(__name__)


class DataIssueType(str, Enum):
    """数据问题类型"""
    MISSING_METRICS = 'missing_metrics'  # 缺失指标
    MISSING_COVER = 'missing_cover'  # 缺失封面
    MISSING_ANALYSIS = 'missing_analysis'  # 缺失分析
    MISSING_ONLINE_METRICS = 'missing_online_metrics'  # 缺失线上指标
    DUPLICATE_NOTE = 'duplicate_note'  # 重复笔记
    MISMATCHED_DATA = 'mismatched_data'  # 数据错配
    INVALID_DATA = 'invalid_data'  # 无效数据


class IssueSeverity(str, Enum):
    """问题严重程度"""
    LOW = 'low'  # 低
    MEDIUM = 'medium'  # 中
    HIGH = 'high'  # 高
    CRITICAL = 'critical'  # 严重


# ==================== 数据库模型 ====================

class DataQualityReport(Base):
    """数据质量报告表"""
    __tablename__ = 'data_quality_reports'

    report_id = Column(String(64), primary_key=True, comment='报告ID')

    # 审计信息
    audit_time = Column(DateTime, default=datetime.now, comment='审计时间')
    audit_scope = Column(String(64), comment='审计范围（all/category/date_range）')

    # 质量评分
    overall_score = Column(Float, comment='总体质量分数（0-1）')
    completeness_score = Column(Float, comment='完整性分数')
    consistency_score = Column(Float, comment='一致性分数')
    validity_score = Column(Float, comment='有效性分数')

    # 统计信息
    total_notes = Column(Integer, comment='总笔记数')
    issues_found = Column(Integer, comment='发现问题数')
    issues_fixed = Column(Integer, comment='已修复问题数')

    # 详细结果
    issues_by_type = Column(JSON, comment='按类型统计的问题')
    issues_by_severity = Column(JSON, comment='按严重程度统计的问题')

    # 元数据
    metadata = Column(JSON, comment='其他元数据')


class DataIssue(Base):
    """数据问题表"""
    __tablename__ = 'data_issues'

    issue_id = Column(String(64), primary_key=True, comment='问题ID')
    report_id = Column(String(64), comment='报告ID')

    # 问题信息
    issue_type = Column(SQLEnum(DataIssueType), nullable=False, comment='问题类型')
    severity = Column(SQLEnum(IssueSeverity), nullable=False, comment='严重程度')
    description = Column(Text, comment='问题描述')

    # 关联数据
    note_id = Column(String(64), comment='笔记ID')
    affected_table = Column(String(64), comment='受影响的表')

    # 修复信息
    is_fixed = Column(Boolean, default=False, comment='是否已修复')
    fix_method = Column(String(64), comment='修复方法')
    fixed_at = Column(DateTime, comment='修复时间')

    # 元数据
    detected_at = Column(DateTime, default=datetime.now, comment='检测时间')
    metadata = Column(JSON, comment='其他元数据')


@dataclass
class QualityMetrics:
    """质量指标"""
    total_notes: int
    complete_notes: int
    completeness_rate: float

    notes_with_metrics: int
    notes_with_cover: int
    notes_with_analysis: int

    duplicate_count: int
    mismatch_count: int
    invalid_count: int

    overall_score: float


class DataQualityService:
    """
    数据质量服务

    功能：
    1. 完整性审计
    2. 一致性检查
    3. 自动修复
    4. 质量评分
    5. 问题追踪
    """

    def __init__(
        self,
        db: Session,
        auto_fix: bool = True,
        alert_threshold: float = 0.8
    ):
        self.db = db
        self.auto_fix = auto_fix
        self.alert_threshold = alert_threshold

    async def run_audit(
        self,
        scope: str = 'all',
        category: Optional[str] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None
    ) -> DataQualityReport:
        """
        运行数据质量审计

        Args:
            scope: 审计范围（all/category/date_range）
            category: 分类过滤
            date_from: 开始日期
            date_to: 结束日期

        Returns:
            质量报告
        """
        import uuid

        logger.info(f"开始数据质量审计: scope={scope}")

        report_id = f"report_{uuid.uuid4().hex[:16]}"

        # 1. 构建查询
        query = self.db.query(XHSNote)

        if scope == 'category' and category:
            query = query.filter(XHSNote.category == category)
        elif scope == 'date_range':
            if date_from:
                query = query.filter(XHSNote.created_at >= date_from)
            if date_to:
                query = query.filter(XHSNote.created_at <= date_to)

        notes = query.all()
        total_notes = len(notes)

        logger.info(f"审计笔记数: {total_notes}")

        # 2. 检查各类问题
        issues = []

        # 完整性检查
        issues.extend(await self._check_completeness(notes))

        # 一致性检查
        issues.extend(await self._check_consistency(notes))

        # 有效性检查
        issues.extend(await self._check_validity(notes))

        # 重复检查
        issues.extend(await self._check_duplicates(notes))

        # 3. 保存问题
        for issue in issues:
            issue.report_id = report_id
            self.db.add(issue)

        # 4. 自动修复
        issues_fixed = 0
        if self.auto_fix:
            issues_fixed = await self._auto_fix_issues(issues)

        # 5. 计算质量分数
        quality_metrics = self._calculate_quality_metrics(notes, issues)

        # 6. 统计问题
        issues_by_type = {}
        issues_by_severity = {}

        for issue in issues:
            issues_by_type[issue.issue_type.value] = issues_by_type.get(issue.issue_type.value, 0) + 1
            issues_by_severity[issue.severity.value] = issues_by_severity.get(issue.severity.value, 0) + 1

        # 7. 创建报告
        report = DataQualityReport(
            report_id=report_id,
            audit_scope=scope,
            overall_score=quality_metrics.overall_score,
            completeness_score=quality_metrics.completeness_rate,
            consistency_score=1.0 - (quality_metrics.mismatch_count / total_notes) if total_notes > 0 else 1.0,
            validity_score=1.0 - (quality_metrics.invalid_count / total_notes) if total_notes > 0 else 1.0,
            total_notes=total_notes,
            issues_found=len(issues),
            issues_fixed=issues_fixed,
            issues_by_type=issues_by_type,
            issues_by_severity=issues_by_severity
        )

        self.db.add(report)
        self.db.commit()

        # 8. 告警
        if quality_metrics.overall_score < self.alert_threshold:
            await self._send_alert(report, quality_metrics)

        logger.info(f"✅ 审计完成: 发现 {len(issues)} 个问题, 修复 {issues_fixed} 个")

        return report

    async def _check_completeness(self, notes: List[XHSNote]) -> List[DataIssue]:
        """检查完整性"""
        issues = []

        for note in notes:
            # 检查指标
            metrics = self.db.query(XHSMetrics).filter(
                XHSMetrics.note_id == note.note_id
            ).first()

            if not metrics:
                issues.append(DataIssue(
                    issue_id=f"issue_{note.note_id}_metrics",
                    issue_type=DataIssueType.MISSING_METRICS,
                    severity=IssueSeverity.HIGH,
                    description=f"笔记缺失指标: {note.note_id}",
                    note_id=note.note_id,
                    affected_table='xhs_metrics'
                ))

            # 检查封面
            cover = self.db.query(XHSCover).filter(
                XHSCover.note_id == note.note_id
            ).first()

            if not cover:
                issues.append(DataIssue(
                    issue_id=f"issue_{note.note_id}_cover",
                    issue_type=DataIssueType.MISSING_COVER,
                    severity=IssueSeverity.MEDIUM,
                    description=f"笔记缺失封面: {note.note_id}",
                    note_id=note.note_id,
                    affected_table='xhs_covers'
                ))

            # 检查分析
            analysis = self.db.query(XHSAnalysis).filter(
                XHSAnalysis.note_id == note.note_id
            ).first()

            if not analysis:
                issues.append(DataIssue(
                    issue_id=f"issue_{note.note_id}_analysis",
                    issue_type=DataIssueType.MISSING_ANALYSIS,
                    severity=IssueSeverity.MEDIUM,
                    description=f"笔记缺失分析: {note.note_id}",
                    note_id=note.note_id,
                    affected_table='xhs_analysis'
                ))

        return issues

    async def _check_consistency(self, notes: List[XHSNote]) -> List[DataIssue]:
        """检查一致性"""
        issues = []

        for note in notes:
            # 检查指标与笔记的一致性
            metrics = self.db.query(XHSMetrics).filter(
                XHSMetrics.note_id == note.note_id
            ).first()

            if metrics:
                # 检查时间一致性
                if metrics.collected_at and note.publish_time:
                    if metrics.collected_at < note.publish_time:
                        issues.append(DataIssue(
                            issue_id=f"issue_{note.note_id}_time_mismatch",
                            issue_type=DataIssueType.MISMATCHED_DATA,
                            severity=IssueSeverity.LOW,
                            description=f"指标采集时间早于发布时间: {note.note_id}",
                            note_id=note.note_id,
                            affected_table='xhs_metrics'
                        ))

        return issues

    async def _check_validity(self, notes: List[XHSNote]) -> List[DataIssue]:
        """检查有效性"""
        issues = []

        for note in notes:
            # 检查标题和正文
            if not note.title or len(note.title.strip()) == 0:
                issues.append(DataIssue(
                    issue_id=f"issue_{note.note_id}_empty_title",
                    issue_type=DataIssueType.INVALID_DATA,
                    severity=IssueSeverity.HIGH,
                    description=f"笔记标题为空: {note.note_id}",
                    note_id=note.note_id,
                    affected_table='xhs_notes'
                ))

            if not note.text or len(note.text.strip()) == 0:
                issues.append(DataIssue(
                    issue_id=f"issue_{note.note_id}_empty_text",
                    issue_type=DataIssueType.INVALID_DATA,
                    severity=IssueSeverity.HIGH,
                    description=f"笔记正文为空: {note.note_id}",
                    note_id=note.note_id,
                    affected_table='xhs_notes'
                ))

            # 检查指标合理性
            metrics = self.db.query(XHSMetrics).filter(
                XHSMetrics.note_id == note.note_id
            ).first()

            if metrics:
                # 检查负数
                if any([
                    metrics.views < 0,
                    metrics.likes < 0,
                    metrics.comments < 0,
                    metrics.collects < 0,
                    metrics.shares < 0
                ]):
                    issues.append(DataIssue(
                        issue_id=f"issue_{note.note_id}_negative_metrics",
                        issue_type=DataIssueType.INVALID_DATA,
                        severity=IssueSeverity.CRITICAL,
                        description=f"指标出现负数: {note.note_id}",
                        note_id=note.note_id,
                        affected_table='xhs_metrics'
                    ))

                # 检查逻辑一致性（点赞数不应大于浏览数）
                if metrics.likes > metrics.views:
                    issues.append(DataIssue(
                        issue_id=f"issue_{note.note_id}_illogical_metrics",
                        issue_type=DataIssueType.INVALID_DATA,
                        severity=IssueSeverity.MEDIUM,
                        description=f"点赞数大于浏览数: {note.note_id}",
                        note_id=note.note_id,
                        affected_table='xhs_metrics'
                    ))

        return issues

    async def _check_duplicates(self, notes: List[XHSNote]) -> List[DataIssue]:
        """检查重复"""
        issues = []

        # 按 note_id 分组，找出重复
        note_ids = [n.note_id for n in notes]
        duplicates = [nid for nid in note_ids if note_ids.count(nid) > 1]

        for note_id in set(duplicates):
            issues.append(DataIssue(
                issue_id=f"issue_{note_id}_duplicate",
                issue_type=DataIssueType.DUPLICATE_NOTE,
                severity=IssueSeverity.HIGH,
                description=f"重复笔记: {note_id}",
                note_id=note_id,
                affected_table='xhs_notes'
            ))

        return issues

    async def _auto_fix_issues(self, issues: List[DataIssue]) -> int:
        """自动修复问题"""
        fixed_count = 0

        for issue in issues:
            try:
                if issue.issue_type == DataIssueType.MISSING_COVER:
                    # 触发封面重新下载
                    await self._trigger_cover_redownload(issue.note_id)
                    issue.is_fixed = True
                    issue.fix_method = 'auto_redownload'
                    issue.fixed_at = datetime.now()
                    fixed_count += 1

                elif issue.issue_type == DataIssueType.MISSING_ANALYSIS:
                    # 触发重新分析
                    await self._trigger_reanalysis(issue.note_id)
                    issue.is_fixed = True
                    issue.fix_method = 'auto_reanalysis'
                    issue.fixed_at = datetime.now()
                    fixed_count += 1

                # 其他类型的问题需要人工处理

            except Exception as e:
                logger.error(f"修复失败: {issue.issue_id}, error={e}")

        return fixed_count

    async def _trigger_cover_redownload(self, note_id: str):
        """触发封面重新下载"""
        # TODO: 发送 Celery 任务
        logger.info(f"触发封面重新下载: {note_id}")

    async def _trigger_reanalysis(self, note_id: str):
        """触发重新分析"""
        # TODO: 发送 Celery 任务
        logger.info(f"触发重新分析: {note_id}")

    def _calculate_quality_metrics(
        self,
        notes: List[XHSNote],
        issues: List[DataIssue]
    ) -> QualityMetrics:
        """计算质量指标"""
        total_notes = len(notes)

        if total_notes == 0:
            return QualityMetrics(
                total_notes=0,
                complete_notes=0,
                completeness_rate=0.0,
                notes_with_metrics=0,
                notes_with_cover=0,
                notes_with_analysis=0,
                duplicate_count=0,
                mismatch_count=0,
                invalid_count=0,
                overall_score=0.0
            )

        # 统计完整性
        notes_with_metrics = sum(
            1 for n in notes
            if self.db.query(XHSMetrics).filter(XHSMetrics.note_id == n.note_id).first()
        )

        notes_with_cover = sum(
            1 for n in notes
            if self.db.query(XHSCover).filter(XHSCover.note_id == n.note_id).first()
        )

        notes_with_analysis = sum(
            1 for n in notes
            if self.db.query(XHSAnalysis).filter(XHSAnalysis.note_id == n.note_id).first()
        )

        complete_notes = sum(
            1 for n in notes
            if all([
                self.db.query(XHSMetrics).filter(XHSMetrics.note_id == n.note_id).first(),
                self.db.query(XHSCover).filter(XHSCover.note_id == n.note_id).first(),
                self.db.query(XHSAnalysis).filter(XHSAnalysis.note_id == n.note_id).first()
            ])
        )

        completeness_rate = complete_notes / total_notes

        # 统计问题
        duplicate_count = sum(1 for i in issues if i.issue_type == DataIssueType.DUPLICATE_NOTE)
        mismatch_count = sum(1 for i in issues if i.issue_type == DataIssueType.MISMATCHED_DATA)
        invalid_count = sum(1 for i in issues if i.issue_type == DataIssueType.INVALID_DATA)

        # 计算总体分数
        overall_score = (
            0.4 * completeness_rate +
            0.3 * (1.0 - duplicate_count / total_notes) +
            0.2 * (1.0 - mismatch_count / total_notes) +
            0.1 * (1.0 - invalid_count / total_notes)
        )

        return QualityMetrics(
            total_notes=total_notes,
            complete_notes=complete_notes,
            completeness_rate=completeness_rate,
            notes_with_metrics=notes_with_metrics,
            notes_with_cover=notes_with_cover,
            notes_with_analysis=notes_with_analysis,
            duplicate_count=duplicate_count,
            mismatch_count=mismatch_count,
            invalid_count=invalid_count,
            overall_score=overall_score
        )

    async def _send_alert(self, report: DataQualityReport, metrics: QualityMetrics):
        """发送告警"""
        logger.warning(f"⚠️ 数据质量告警: 总体分数={metrics.overall_score:.2f}")
        # TODO: 发送邮件/Slack/钉钉通知

    def get_latest_report(self) -> Optional[DataQualityReport]:
        """获取最新报告"""
        return self.db.query(DataQualityReport).order_by(
            DataQualityReport.audit_time.desc()
        ).first()


# ==================== 使用示例 ====================

async def example_usage():
    """使用示例"""
    from app.db import get_db

    db = next(get_db())

    # 1. 创建数据质量服务
    service = DataQualityService(
        db=db,
        auto_fix=True,
        alert_threshold=0.8
    )

    # 2. 运行审计
    report = await service.run_audit(scope='all')

    print(f"总体分数: {report.overall_score:.2f}")
    print(f"发现问题: {report.issues_found}")
    print(f"已修复: {report.issues_fixed}")

    # 3. 获取最新报告
    latest = service.get_latest_report()
    if latest:
        print(f"最新审计: {latest.audit_time}")
