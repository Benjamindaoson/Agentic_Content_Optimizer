"""
数据导入服务

当爬虫不可用时，允许用户通过 CSV/JSON 手动导入笔记数据和反馈数据，
保障系统数据闭环不中断。

支持:
- JSON/CSV 文件解析 → XHSNote + XHSMetrics 数据模型
- 数据校验（必填字段、格式验证、去重检查）
- 批量导入 + 事务回滚
- 导入进度跟踪
"""

import csv
import io
import json
import uuid
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.db.models import XHSNote, XHSMetrics

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class ImportResult:
    """导入结果"""
    task_id: str
    status: str  # "completed" | "partial" | "failed"
    total: int = 0
    success: int = 0
    skipped: int = 0
    failed: int = 0
    errors: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class ValidationError:
    """校验错误"""
    row: int
    field: str
    message: str


# ---------------------------------------------------------------------------
# Templates
# ---------------------------------------------------------------------------

NOTES_TEMPLATE = {
    "fields": [
        {"name": "note_id", "required": True, "type": "string", "description": "笔记唯一ID"},
        {"name": "title", "required": True, "type": "string", "description": "笔记标题"},
        {"name": "text", "required": True, "type": "string", "description": "笔记正文"},
        {"name": "author_name", "required": False, "type": "string", "description": "作者昵称"},
        {"name": "author_id", "required": False, "type": "string", "description": "作者ID"},
        {"name": "category", "required": False, "type": "string", "description": "分类 (美妆/穿搭/美食等)"},
        {"name": "tags", "required": False, "type": "list[string]", "description": "标签列表"},
        {"name": "cover_url", "required": False, "type": "string", "description": "封面图URL"},
        {"name": "publish_time", "required": False, "type": "datetime", "description": "发布时间 (ISO 8601)"},
        {"name": "views", "required": False, "type": "integer", "description": "浏览量"},
        {"name": "likes", "required": False, "type": "integer", "description": "点赞数"},
        {"name": "comments", "required": False, "type": "integer", "description": "评论数"},
        {"name": "collects", "required": False, "type": "integer", "description": "收藏数"},
        {"name": "shares", "required": False, "type": "integer", "description": "分享数"},
    ],
    "example": {
        "note_id": "note_abc123",
        "title": "5 个 AI 写作技巧",
        "text": "今天分享 5 个超实用的 AI 写作技巧...",
        "author_name": "小红书创作者",
        "category": "科技",
        "tags": ["AI", "写作", "效率"],
        "views": 10000,
        "likes": 500,
        "comments": 80,
        "collects": 200,
    },
}

FEEDBACK_TEMPLATE = {
    "fields": [
        {"name": "note_id", "required": True, "type": "string", "description": "笔记ID (必须已存在)"},
        {"name": "views", "required": False, "type": "integer", "description": "浏览量"},
        {"name": "likes", "required": False, "type": "integer", "description": "点赞数"},
        {"name": "comments", "required": False, "type": "integer", "description": "评论数"},
        {"name": "collects", "required": False, "type": "integer", "description": "收藏数"},
        {"name": "shares", "required": False, "type": "integer", "description": "分享数"},
        {"name": "engagement_rate", "required": False, "type": "float", "description": "互动率"},
    ],
    "example": {
        "note_id": "note_abc123",
        "views": 15000,
        "likes": 800,
        "comments": 120,
        "collects": 350,
        "shares": 45,
        "engagement_rate": 0.085,
    },
}


# ---------------------------------------------------------------------------
# DataImporter
# ---------------------------------------------------------------------------

class DataImporter:
    """数据导入与校验服务"""

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_template(self, template_type: str = "notes") -> Dict[str, Any]:
        """返回导入模板"""
        if template_type == "feedback":
            return FEEDBACK_TEMPLATE
        return NOTES_TEMPLATE

    def import_notes_json(self, data: List[Dict[str, Any]], db: Session) -> ImportResult:
        """
        从 JSON 数据导入笔记

        Args:
            data: 笔记字典列表
            db: SQLAlchemy session

        Returns:
            ImportResult
        """
        task_id = str(uuid.uuid4())
        result = ImportResult(task_id=task_id, status="completed", total=len(data))

        for idx, row in enumerate(data):
            try:
                errors = self._validate_note(row, idx)
                if errors:
                    result.failed += 1
                    result.errors.extend(
                        [{"row": e.row, "field": e.field, "message": e.message} for e in errors]
                    )
                    continue

                # 去重检查
                existing = db.query(XHSNote).filter_by(note_id=row["note_id"]).first()
                if existing:
                    result.skipped += 1
                    continue

                note, metrics = self._row_to_models(row)
                db.add(note)
                if metrics:
                    db.add(metrics)
                result.success += 1

            except Exception as exc:
                result.failed += 1
                result.errors.append({"row": idx, "field": "__all__", "message": str(exc)})

        # Commit transaction
        try:
            db.commit()
        except Exception as exc:
            db.rollback()
            result.status = "failed"
            result.errors.append({"row": -1, "field": "__all__", "message": f"事务提交失败: {exc}"})
            return result

        if result.failed > 0:
            result.status = "partial"

        logger.info(
            f"[DataImporter] 导入完成: total={result.total} success={result.success} "
            f"skipped={result.skipped} failed={result.failed}"
        )
        return result

    def import_notes_csv(self, csv_content: str, db: Session) -> ImportResult:
        """
        从 CSV 字符串导入笔记

        Args:
            csv_content: CSV 文件内容（UTF-8 字符串）
            db: SQLAlchemy session

        Returns:
            ImportResult
        """
        reader = csv.DictReader(io.StringIO(csv_content))
        rows: List[Dict[str, Any]] = []
        for row in reader:
            # CSV 值均为字符串，需要类型转换
            converted = self._coerce_csv_types(row)
            rows.append(converted)
        return self.import_notes_json(rows, db)

    def import_feedback_json(self, data: List[Dict[str, Any]], db: Session) -> ImportResult:
        """
        批量导入/更新反馈指标

        Args:
            data: 指标字典列表 (必须包含 note_id)
            db: SQLAlchemy session

        Returns:
            ImportResult
        """
        task_id = str(uuid.uuid4())
        result = ImportResult(task_id=task_id, status="completed", total=len(data))

        for idx, row in enumerate(data):
            try:
                note_id = row.get("note_id")
                if not note_id:
                    result.failed += 1
                    result.errors.append({"row": idx, "field": "note_id", "message": "note_id 为必填字段"})
                    continue

                existing_note = db.query(XHSNote).filter_by(note_id=note_id).first()
                if not existing_note:
                    result.failed += 1
                    result.errors.append({"row": idx, "field": "note_id", "message": f"笔记不存在: {note_id}"})
                    continue

                # Upsert metrics
                metrics = db.query(XHSMetrics).filter_by(note_id=note_id).first()
                if not metrics:
                    metrics = XHSMetrics(note_id=note_id)
                    db.add(metrics)

                int_fields = ["views", "likes", "comments", "collects", "shares", "follows"]
                float_fields = ["engagement_rate", "viral_score", "completion_rate", "conversion_rate"]
                for f in int_fields:
                    if f in row and row[f] is not None:
                        setattr(metrics, f, int(row[f]))
                for f in float_fields:
                    if f in row and row[f] is not None:
                        setattr(metrics, f, float(row[f]))

                metrics.updated_at = datetime.now()
                result.success += 1

            except Exception as exc:
                result.failed += 1
                result.errors.append({"row": idx, "field": "__all__", "message": str(exc)})

        try:
            db.commit()
        except Exception as exc:
            db.rollback()
            result.status = "failed"
            result.errors.append({"row": -1, "field": "__all__", "message": f"事务提交失败: {exc}"})
            return result

        if result.failed > 0:
            result.status = "partial"

        logger.info(
            f"[DataImporter] 反馈导入完成: total={result.total} success={result.success} "
            f"failed={result.failed}"
        )
        return result

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _validate_note(self, row: Dict[str, Any], idx: int) -> List[ValidationError]:
        """校验单条笔记数据"""
        errors: List[ValidationError] = []

        # 必填字段
        for field_name in ("note_id", "title", "text"):
            val = row.get(field_name)
            if not val or (isinstance(val, str) and not val.strip()):
                errors.append(ValidationError(row=idx, field=field_name, message=f"{field_name} 为必填字段"))

        # note_id 长度
        note_id = row.get("note_id", "")
        if isinstance(note_id, str) and len(note_id) > 64:
            errors.append(ValidationError(row=idx, field="note_id", message="note_id 长度不能超过 64 字符"))

        # 数值类型检查
        for field_name in ("views", "likes", "comments", "collects", "shares"):
            val = row.get(field_name)
            if val is not None:
                try:
                    int(val)
                except (ValueError, TypeError):
                    errors.append(ValidationError(
                        row=idx, field=field_name, message=f"{field_name} 必须为整数"
                    ))

        return errors

    def _row_to_models(self, row: Dict[str, Any]) -> Tuple[XHSNote, Optional[XHSMetrics]]:
        """将一行数据转换为 ORM 模型对象"""
        publish_time = None
        if row.get("publish_time"):
            try:
                publish_time = datetime.fromisoformat(str(row["publish_time"]))
            except (ValueError, TypeError):
                pass

        tags = row.get("tags")
        if isinstance(tags, str):
            tags = [t.strip() for t in tags.split(",") if t.strip()]

        note = XHSNote(
            note_id=str(row["note_id"]).strip(),
            title=str(row["title"]).strip(),
            text=str(row["text"]).strip(),
            cover_url=row.get("cover_url"),
            author_id=row.get("author_id"),
            author_name=row.get("author_name"),
            publish_time=publish_time,
            category=row.get("category"),
            tags=tags,
            crawled_at=datetime.now(),
            is_viral=False,
            analysis_status="pending",
            raw_metadata={"source": "manual_import", "imported_at": datetime.now().isoformat()},
        )

        # 如果有指标数据则创建 XHSMetrics
        metric_fields = {"views", "likes", "comments", "collects", "shares"}
        has_metrics = any(row.get(f) is not None for f in metric_fields)

        metrics = None
        if has_metrics:
            views = int(row.get("views", 0) or 0)
            likes = int(row.get("likes", 0) or 0)
            comments = int(row.get("comments", 0) or 0)
            collects = int(row.get("collects", 0) or 0)
            shares = int(row.get("shares", 0) or 0)
            total_engagement = likes + comments + collects + shares
            eng_rate = total_engagement / views if views > 0 else 0.0

            metrics = XHSMetrics(
                note_id=note.note_id,
                views=views,
                likes=likes,
                comments=comments,
                collects=collects,
                shares=shares,
                engagement_rate=round(eng_rate, 6),
            )

        return note, metrics

    def _coerce_csv_types(self, row: Dict[str, str]) -> Dict[str, Any]:
        """将 CSV 字符串值转换为合适的 Python 类型"""
        result: Dict[str, Any] = {}
        for key, val in row.items():
            key = key.strip()
            if val is None or val.strip() == "":
                result[key] = None
                continue

            val = val.strip()

            # 已知整数字段
            if key in ("views", "likes", "comments", "collects", "shares", "follows"):
                try:
                    result[key] = int(val)
                except ValueError:
                    result[key] = val
            # 已知浮点字段
            elif key in ("engagement_rate", "viral_score"):
                try:
                    result[key] = float(val)
                except ValueError:
                    result[key] = val
            # tags: 逗号分隔
            elif key == "tags":
                result[key] = [t.strip() for t in val.split(",") if t.strip()]
            else:
                result[key] = val

        return result
