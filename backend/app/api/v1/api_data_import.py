"""
数据导入 API 路由

提供 CSV/JSON 手动导入笔记和反馈数据的 REST 接口。
当爬虫不可用时，这是系统数据闭环的备用通道。
"""

from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional
import json
import logging

from app.db import get_db_session
from app.data.data_engineering.data_importer import DataImporter, ImportResult

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/data/import", tags=["数据导入"])

# 单例
_importer = DataImporter()


# ---------------------------------------------------------------------------
# Template
# ---------------------------------------------------------------------------

@router.get("/template")
async def get_import_template(template_type: str = "notes"):
    """
    获取导入模板

    Args:
        template_type: "notes" (笔记) 或 "feedback" (反馈指标)

    Returns:
        模板字段定义 + 示例数据
    """
    if template_type not in ("notes", "feedback"):
        raise HTTPException(status_code=400, detail="template_type 必须为 'notes' 或 'feedback'")

    template = _importer.get_template(template_type)
    return {
        "template_type": template_type,
        "fields": template["fields"],
        "example": template["example"],
    }


# ---------------------------------------------------------------------------
# Import notes
# ---------------------------------------------------------------------------

@router.post("/notes")
async def import_notes(
    data: List[Dict[str, Any]],
    db: Session = Depends(get_db_session),
):
    """
    通过 JSON 批量导入笔记

    Request body: JSON 数组，每个元素包含笔记字段。
    必填字段: note_id, title, text
    可选字段: author_name, category, tags, views, likes, comments 等

    示例:
    ```json
    [
        {
            "note_id": "note_001",
            "title": "AI 写作技巧",
            "text": "今天分享几个实用技巧...",
            "category": "科技",
            "views": 5000,
            "likes": 200
        }
    ]
    ```
    """
    if not data:
        raise HTTPException(status_code=400, detail="数据不能为空")

    if len(data) > 5000:
        raise HTTPException(status_code=400, detail="单次导入不能超过 5000 条")

    result = _importer.import_notes_json(data, db)
    return _result_to_response(result)


@router.post("/notes/csv")
async def import_notes_csv(
    file: UploadFile = File(..., description="CSV 文件 (UTF-8 编码)"),
    db: Session = Depends(get_db_session),
):
    """
    通过 CSV 文件导入笔记

    CSV 首行为表头，字段名参考 GET /api/data/import/template 返回的 fields。
    必填列: note_id, title, text
    """
    if not file.filename or not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="请上传 .csv 文件")

    content = await file.read()
    try:
        csv_str = content.decode("utf-8-sig")  # 兼容带 BOM 的文件
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="文件编码错误，请使用 UTF-8 编码")

    result = _importer.import_notes_csv(csv_str, db)
    return _result_to_response(result)


# ---------------------------------------------------------------------------
# Import feedback
# ---------------------------------------------------------------------------

@router.post("/feedback")
async def import_feedback(
    data: List[Dict[str, Any]],
    db: Session = Depends(get_db_session),
):
    """
    批量导入/更新反馈指标

    用于补充或更新已导入笔记的真实互动数据。
    note_id 必须已存在，否则该行将被跳过。

    示例:
    ```json
    [
        {
            "note_id": "note_001",
            "views": 15000,
            "likes": 800,
            "comments": 120,
            "engagement_rate": 0.085
        }
    ]
    ```
    """
    if not data:
        raise HTTPException(status_code=400, detail="数据不能为空")

    if len(data) > 5000:
        raise HTTPException(status_code=400, detail="单次导入不能超过 5000 条")

    result = _importer.import_feedback_json(data, db)
    return _result_to_response(result)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _result_to_response(result: ImportResult) -> Dict[str, Any]:
    """将 ImportResult 转为 API 响应"""
    response = {
        "task_id": result.task_id,
        "status": result.status,
        "summary": {
            "total": result.total,
            "success": result.success,
            "skipped": result.skipped,
            "failed": result.failed,
        },
    }
    if result.errors:
        # 最多返回前 50 条错误
        response["errors"] = result.errors[:50]
        if len(result.errors) > 50:
            response["errors_truncated"] = True
            response["total_errors"] = len(result.errors)
    return response
