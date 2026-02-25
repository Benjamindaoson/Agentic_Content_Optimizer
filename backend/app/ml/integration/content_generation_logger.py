"""
集成日志记录到内容生成流程

在现有的 /api/generate/content 端点中添加 ML 训练数据记录
ML 表已迁入 PostgreSQL，与主库统一
"""

import uuid
import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from typing import Optional

from app.core.config import get_settings
from app.ml.training.schemas import GenerationTrace

logger = logging.getLogger(__name__)

# 使用主库 PostgreSQL（同步引擎，供 ML 日志使用）
def _get_ml_engine():
    settings = get_settings()
    url = settings.DATABASE_URL
    if url.startswith("postgresql+asyncpg"):
        url = url.replace("postgresql+asyncpg://", "postgresql://")
    return create_engine(url, pool_pre_ping=True)

_ml_engine = None

def _get_ml_session():
    global _ml_engine
    if _ml_engine is None:
        _ml_engine = _get_ml_engine()
    return sessionmaker(autocommit=False, autoflush=False, bind=_ml_engine)


def _normalize_content_for_trace(content: dict) -> dict:
    """将多种格式的生成内容统一为 log_generation_trace 所需格式"""
    if not content:
        return {}
    # 格式1: text_structure (orchestration/writer output)
    ts = content.get("text_structure")
    if ts:
        if isinstance(ts, dict):
            return {
                "hook": ts.get("hook", ""),
                "body": ts.get("body", ""),
                "cta": ts.get("cta", ""),
                "title": content.get("title") or (ts.get("hook", "")[:50] if ts.get("hook") else ""),
                "text": ts.get("full_text", ""),
            }
        return {
            "hook": getattr(ts, "hook", ""),
            "body": getattr(ts, "body", ""),
            "cta": getattr(ts, "cta", ""),
            "title": content.get("title") or (getattr(ts, "hook", "")[:50] if getattr(ts, "hook", None) else ""),
            "text": getattr(ts, "full_text", ""),
        }
    # 格式2: 扁平 hook/body/cta
    return {
        "hook": content.get("hook", ""),
        "body": content.get("body", ""),
        "cta": content.get("cta", ""),
        "title": content.get("title", ""),
        "text": content.get("text", content.get("full_text", "")),
    }


def log_generation_trace(
    platform: str,
    topic: str,
    category: str,
    target_audience: str,
    style_preference: str,
    generated_content: dict,
    generation_time_ms: int,
    model_id: str,
    quality_score: float,
    predicted_score: float,
    *,
    policy_id: Optional[str] = None,
    constraints: Optional[dict] = None,
    retrieved_context: Optional[list] = None,
) -> str:
    """
    记录内容生成到 ML 训练数据库

    Args:
        platform: 平台（xiaohongshu, douyin）
        topic: 主题
        category: 分类
        target_audience: 目标受众
        style_preference: 风格偏好
        generated_content: 生成的内容（包含 title, text, hook, body, cta）
        generation_time_ms: 生成耗时（毫秒）
        model_id: 模型 ID
        quality_score: 质量分数
        predicted_score: 预测分数

    Returns:
        trace_id: 生成记录 ID
    """
    SessionLocal = _get_ml_session()
    ml_db = SessionLocal()

    try:
        # 统一内容格式
        normalized = _normalize_content_for_trace(generated_content)
        if not normalized.get("hook") and not normalized.get("body") and not normalized.get("text"):
            logger.warning("log_generation_trace: 无法从 generated_content 提取有效内容，跳过")
            return None

        # 构建 prompt（用于训练）
        prompt_parts = [f"平台: {platform}"]
        if category:
            prompt_parts.append(f"分类: {category}")
        if target_audience:
            prompt_parts.append(f"目标受众: {target_audience}")
        if style_preference:
            prompt_parts.append(f"风格: {style_preference}")
        prompt_parts.append(f"主题: {topic}")

        prompt = "\n".join(prompt_parts)

        # 构建输出内容
        output_parts = []
        if normalized.get("title"):
            output_parts.append(f"标题: {normalized['title']}")
        if normalized.get("hook"):
            output_parts.append(f"\n开头: {normalized['hook']}")
        if normalized.get("body"):
            output_parts.append(f"\n正文: {normalized['body']}")
        if normalized.get("cta"):
            output_parts.append(f"\n结尾: {normalized['cta']}")

        output = "\n".join(output_parts)

        # 创建 GenerationTrace
        trace = GenerationTrace(
            id=str(uuid.uuid4()),
            platform=platform,
            persona=target_audience,  # 使用 target_audience 作为 persona
            niche=category,  # 使用 category 作为 niche
            topic=topic,
            prompt=prompt,
            system_prompt=f"你是{platform}平台的专业内容创作者，擅长{category}领域",
            constraints=constraints,
            retrieved_context=retrieved_context,
            output=output or normalized.get("text", ""),
            title=normalized.get("title") or None,
            tags=[category, topic] if category and topic else [],
            policy_id=policy_id,
            model_id=model_id,
            generation_time_ms=generation_time_ms,
            token_count=len(output),  # 简单估算
        )

        ml_db.add(trace)
        ml_db.commit()
        ml_db.refresh(trace)

        return trace.id

    except Exception as e:
        ml_db.rollback()
        logger.error(f"记录 GenerationTrace 失败: {e}")
        return None

    finally:
        ml_db.close()


# 使用示例：在 api.py 的 generate_content 函数中添加
"""
@app.post("/api/generate/content")
async def generate_content(...):
    try:
        # ... 现有的生成逻辑 ...

        start_time = time.time()
        candidates = await generator.generate(request, db)
        generation_time_ms = int((time.time() - start_time) * 1000)

        # 记录第一个候选内容到 ML 训练数据库
        if candidates:
            best_candidate = candidates[0]
            trace_id = log_generation_trace(
                platform="xiaohongshu",  # 或从请求中获取
                topic=topic,
                category=category,
                target_audience=target_audience,
                style_preference=style_preference,
                generated_content={
                    "title": best_candidate.title,
                    "text": best_candidate.text,
                    "hook": best_candidate.hook,
                    "body": best_candidate.body,
                    "cta": best_candidate.cta,
                },
                generation_time_ms=generation_time_ms,
                model_id=llm_provider,
                quality_score=best_candidate.quality_score,
                predicted_score=best_candidate.predicted_score,
            )

        return {
            "status": "success",
            "trace_id": trace_id,  # 返回 trace_id 用于后续反馈收集
            "total": len(candidates),
            "candidates": [...]
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"生成失败: {str(e)}")
"""
