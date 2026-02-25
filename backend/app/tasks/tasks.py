"""
Celery 任务定义

包含所有后台任务
"""

from typing import Dict, Any, List
from datetime import datetime
import asyncio

from app.tasks.celery_config import task
from app.db import get_db
from app.data.crawlers import XHSCrawler
from app.analyzers import ViralAnalyzer, SuccessFactorExtractor
from app.generators import ViralGenerator, CoverSuggester, GenerationRequest
from app.ml.rl import (
    HybridRewardModelV2,
    DiversityScorer,
    ThompsonSamplingSelector,
    OnlineMetricsCollector,
    GRPOTrainer
)
from app.viral import PatternLibrary


# ==================== 采集任务 ====================

@task(name='app.tasks.crawl.crawl_viral_notes')
def crawl_viral_notes_task(
    task_id: str,
    category: str,
    time_window: str,
    limit: int
) -> Dict[str, Any]:
    """
    采集爆款笔记任务

    Args:
        task_id: 任务 ID
        category: 分类
        time_window: 时间窗口
        limit: 采集数量

    Returns:
        采集结果
    """
    from app.db import CrawlTask

    with get_db() as db:
        # 更新任务状态
        task = db.query(CrawlTask).filter_by(task_id=task_id).first()
        if not task:
            return {'status': 'error', 'message': '任务不存在'}

        task.status = 'running'
        task.started_at = datetime.now()
        db.commit()

        try:
            # 执行采集
            crawler = XHSCrawler()
            loop = asyncio.get_event_loop()
            stats = loop.run_until_complete(
                crawler.crawl_and_save(
                    category=category,
                    time_window=time_window,
                    limit=limit,
                    db=db
                )
            )

            # 更新任务状态
            task.status = 'completed'
            task.finished_at = datetime.now()
            task.total_notes = stats['total']
            task.viral_notes = stats['success']
            task.failed_notes = stats['failed']
            task.progress = 1.0
            db.commit()

            return {
                'status': 'success',
                'task_id': task_id,
                'stats': stats
            }

        except Exception as e:
            # 更新任务状态
            task.status = 'failed'
            task.finished_at = datetime.now()
            task.error_message = str(e)
            db.commit()

            return {
                'status': 'error',
                'task_id': task_id,
                'message': str(e)
            }


# ==================== 分析任务 ====================

@task(name='app.tasks.analyze.analyze_note')
def analyze_note_task(note_id: str) -> Dict[str, Any]:
    """
    分析单个笔记任务

    Args:
        note_id: 笔记 ID

    Returns:
        分析结果
    """
    from app.db import XHSNote, XHSAnalysis

    with get_db() as db:
        # 查询笔记
        note = db.query(XHSNote).filter_by(note_id=note_id).first()
        if not note:
            return {'status': 'error', 'message': '笔记不存在'}

        try:
            # 执行分析
            analyzer = ViralAnalyzer()
            loop = asyncio.get_event_loop()
            analysis = loop.run_until_complete(
                analyzer.analyze(
                    note_id=note.note_id,
                    title=note.title,
                    text=note.text,
                    cover_path=note.cover.local_path if note.cover else None,
                    metrics={
                        'views': note.metrics.views,
                        'likes': note.metrics.likes,
                        'comments': note.metrics.comments,
                        'collects': note.metrics.collects
                    } if note.metrics else None,
                    publish_time=note.publish_time
                )
            )

            # 保存分析结果
            analysis_record = XHSAnalysis(
                note_id=note_id,
                structure=analysis.structure.__dict__,
                emotion=analysis.emotion.__dict__,
                topics=analysis.topics.__dict__,
                visual=analysis.visual.__dict__ if analysis.visual else None,
                timing=analysis.timing.__dict__ if analysis.timing else None,
                audience=analysis.audience.__dict__,
                overall_score=analysis.overall_score,
                analyzed_at=datetime.now()
            )

            db.add(analysis_record)
            note.analysis_status = 'completed'
            db.commit()

            return {
                'status': 'success',
                'note_id': note_id,
                'overall_score': analysis.overall_score
            }

        except Exception as e:
            note.analysis_status = 'failed'
            db.commit()

            return {
                'status': 'error',
                'note_id': note_id,
                'message': str(e)
            }


@task(name='app.tasks.analyze.extract_patterns')
def extract_patterns_task(
    category: str,
    min_cluster_size: int = 5
) -> Dict[str, Any]:
    """
    提取模式任务

    Args:
        category: 分类
        min_cluster_size: 最小聚类大小

    Returns:
        提取结果
    """
    from app.db import XHSNote, Pattern

    with get_db() as db:
        # 查询爆款笔记
        notes = db.query(XHSNote).filter(
            XHSNote.category == category,
            XHSNote.is_viral == True,
            XHSNote.analysis_status == 'completed'
        ).limit(100).all()

        if not notes:
            return {'status': 'error', 'message': '没有可用的爆款笔记'}

        try:
            # 获取分析结果
            analyses = [note.analysis for note in notes if note.analysis]

            # 提取模式
            extractor = SuccessFactorExtractor()
            loop = asyncio.get_event_loop()
            patterns = loop.run_until_complete(
                extractor.extract_patterns(
                    notes=notes,
                    analyses=analyses,
                    category=category,
                    min_cluster_size=min_cluster_size
                )
            )

            # 保存模式
            for pattern in patterns:
                pattern_record = Pattern(
                    pattern_id=pattern.pattern_id,
                    category=pattern.category,
                    name=pattern.name,
                    description=pattern.description,
                    hook_template=pattern.hook_template,
                    body_structure=pattern.body_structure,
                    cta_template=pattern.cta_template,
                    keywords=pattern.keywords,
                    emotion_curve=pattern.emotion_curve,
                    cover_layout=pattern.cover_layout,
                    dominant_color=pattern.dominant_color,
                    visual_elements=pattern.visual_elements,
                    sample_size=len(pattern.sample_note_ids),
                    avg_viral_score=pattern.avg_viral_score,
                    success_rate=pattern.avg_viral_score,
                    platforms=pattern.platforms,
                    target_audience=pattern.target_audience,
                    created_at=datetime.now()
                )
                db.add(pattern_record)

            db.commit()

            return {
                'status': 'success',
                'category': category,
                'patterns_count': len(patterns)
            }

        except Exception as e:
            return {
                'status': 'error',
                'category': category,
                'message': str(e)
            }


# ==================== 生成任务 ====================

@task(name='app.tasks.generate.generate_content')
def generate_content_task(
    category: str,
    topic: str,
    target_audience: str = None,
    num_candidates: int = 5
) -> Dict[str, Any]:
    """
    生成内容任务

    Args:
        category: 分类
        topic: 话题
        target_audience: 目标受众
        num_candidates: 候选数量

    Returns:
        生成结果
    """
    with get_db() as db:
        try:
            # 初始化生成器
            pattern_library = PatternLibrary()
            reward_model = HybridRewardModelV2()
            diversity_scorer = DiversityScorer()
            thompson_selector = ThompsonSamplingSelector()

            generator = ViralGenerator(
                pattern_library=pattern_library,
                reward_model=reward_model,
                diversity_scorer=diversity_scorer,
                thompson_selector=thompson_selector,
                llm_client=None
            )

            # 构建请求
            request = GenerationRequest(
                category=category,
                topic=topic,
                target_audience=target_audience,
                num_candidates=num_candidates
            )

            # 生成内容
            loop = asyncio.get_event_loop()
            candidates = loop.run_until_complete(
                generator.generate(request, db)
            )

            return {
                'status': 'success',
                'category': category,
                'topic': topic,
                'candidates_count': len(candidates),
                'candidates': [
                    {
                        'candidate_id': c.candidate_id,
                        'title': c.title,
                        'hybrid_score': c.hybrid_score
                    }
                    for c in candidates
                ]
            }

        except Exception as e:
            return {
                'status': 'error',
                'category': category,
                'topic': topic,
                'message': str(e)
            }


# ==================== GRPO 任务 ====================

@task(name='app.tasks.grpo.collect_metrics')
def collect_metrics_task(
    generation_ids: List[str] = None,
    days: int = 7
) -> Dict[str, Any]:
    """
    收集线上指标任务

    Args:
        generation_ids: 生成记录 ID 列表
        days: 收集最近 N 天

    Returns:
        收集结果
    """
    with get_db() as db:
        try:
            collector = OnlineMetricsCollector()
            loop = asyncio.get_event_loop()

            if generation_ids:
                snapshots = loop.run_until_complete(
                    collector.collect_batch_metrics(generation_ids, db)
                )
            else:
                snapshots = loop.run_until_complete(
                    collector.collect_recent_published(days, db)
                )

            return {
                'status': 'success',
                'snapshots_count': len(snapshots),
                'avg_viral_score': sum(s.viral_score for s in snapshots) / len(snapshots) if snapshots else 0
            }

        except Exception as e:
            return {
                'status': 'error',
                'message': str(e)
            }


@task(name='app.tasks.grpo.train')
def train_grpo_task(
    days: int = 7,
    min_samples_per_pattern: int = 3
) -> Dict[str, Any]:
    """
    GRPO 训练任务

    Args:
        days: 训练数据时间窗口
        min_samples_per_pattern: 每个模式最小样本数

    Returns:
        训练结果
    """
    with get_db() as db:
        try:
            trainer = GRPOTrainer()
            loop = asyncio.get_event_loop()
            result = loop.run_until_complete(
                trainer.train(days, min_samples_per_pattern, db)
            )

            return {
                'status': 'success',
                'run_id': result.run_id,
                'total_samples': result.total_samples,
                'patterns_updated': len(result.pattern_updates),
                'avg_improvement': result.avg_improvement,
                'training_time': result.training_time
            }

        except Exception as e:
            return {
                'status': 'error',
                'message': str(e)
            }


# ==================== 定时任务 ====================

@task(name='app.tasks.scheduled.daily_grpo_training')
def daily_grpo_training_task():
    """每日 GRPO 训练任务"""
    return train_grpo_task(days=7, min_samples_per_pattern=3)


@task(name='app.tasks.scheduled.hourly_metrics_collection')
def hourly_metrics_collection_task():
    """每小时指标收集任务"""
    return collect_metrics_task(days=1)
