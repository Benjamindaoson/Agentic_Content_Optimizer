"""
构建 RAG 知识库

将历史数据索引到 Qdrant 向量数据库
"""

import asyncio
import sys
import os
from pathlib import Path

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy.orm import Session
from sqlalchemy import text
from app.db.database import SessionLocal, engine
from app.rag.retrievers.qdrant_retriever import QdrantRetriever
from app.llm.unified import unified_llm
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def build_content_knowledge_base(db: Session, retriever: QdrantRetriever):
    """
    构建内容知识库

    索引历史成功内容到向量数据库
    """
    logger.info("📚 开始构建内容知识库...")

    # 查询统一内容记录
    result = db.execute(text("""
        SELECT content_id, title, body, content_type, topic, tags, created_at
        FROM unified_content_records
        ORDER BY created_at DESC
        LIMIT 1000
    """))

    contents = result.fetchall()

    if not contents:
        logger.warning("⚠️  没有找到内容记录,跳过内容知识库构建")
        return 0

    indexed_count = 0

    for content in contents:
        try:
            # 生成内容文本
            content_text = f"{content.title}\n{content.body or ''}"
            if content.topic:
                content_text += f"\nTopic: {content.topic}"

            # 生成向量嵌入
            embeddings = await unified_llm.embedding(content_text)
            vector = embeddings[0] if embeddings else None

            if not vector:
                logger.warning(f"⚠️  无法为内容 {content.content_id} 生成向量")
                continue

            # 构建元数据
            metadata = {
                "content_id": content.content_id,
                "title": content.title,
                "content_type": content.content_type or "unknown",
                "topic": content.topic or "",
                "type": "content"
            }

            # 插入到 Qdrant
            await retriever.upsert_reference(
                ref_id=content.content_id,
                vector=vector,
                metadata=metadata
            )

            indexed_count += 1

            if indexed_count % 10 == 0:
                logger.info(f"✅ 已索引 {indexed_count} 条内容")

        except Exception as e:
            logger.error(f"❌ 索引内容 {content.content_id} 失败: {e}")
            continue

    logger.info(f"✅ 内容知识库构建完成,共索引 {indexed_count} 条内容")
    return indexed_count


async def build_causal_knowledge_base(db: Session, retriever: QdrantRetriever):
    """
    构建因果关系知识库

    索引历史因果效应到向量数据库
    """
    logger.info("📚 开始构建因果关系知识库...")

    # 查询显著因果效应 (p_value < 0.05)
    result = db.execute(text("""
        SELECT effect_id, treatment, outcome, effect_size, p_value,
               confidence_interval_lower, confidence_interval_upper,
               common_causes, estimation_method, sample_size
        FROM causal_effects
        WHERE p_value < 0.05
        ORDER BY effect_size DESC
        LIMIT 500
    """))

    effects = result.fetchall()

    if not effects:
        logger.warning("⚠️  没有找到显著因果效应,跳过因果知识库构建")
        return 0

    indexed_count = 0

    for effect in effects:
        try:
            # 生成因果关系文本
            effect_text = f"{effect.treatment} causes {effect.outcome}"
            effect_text += f"\nEffect size: {effect.effect_size}"
            effect_text += f"\nMethod: {effect.estimation_method or 'unknown'}"

            # 生成向量嵌入
            embeddings = await unified_llm.embedding(effect_text)
            vector = embeddings[0] if embeddings else None

            if not vector:
                logger.warning(f"⚠️  无法为因果效应 {effect.effect_id} 生成向量")
                continue

            # 构建元数据
            metadata = {
                "effect_id": effect.effect_id,
                "treatment": effect.treatment,
                "outcome": effect.outcome,
                "effect_size": float(effect.effect_size) if effect.effect_size else 0.0,
                "p_value": float(effect.p_value) if effect.p_value else 1.0,
                "confidence_interval": f"[{effect.confidence_interval_lower}, {effect.confidence_interval_upper}]" if effect.confidence_interval_lower else None,
                "common_causes": effect.common_causes or [],
                "type": "causal_effect"
            }

            # 插入到 Qdrant
            await retriever.upsert_reference(
                ref_id=effect.effect_id,
                vector=vector,
                metadata=metadata
            )

            indexed_count += 1

            if indexed_count % 10 == 0:
                logger.info(f"✅ 已索引 {indexed_count} 条因果效应")

        except Exception as e:
            logger.error(f"❌ 索引因果效应 {effect.effect_id} 失败: {e}")
            continue

    logger.info(f"✅ 因果关系知识库构建完成,共索引 {indexed_count} 条因果效应")
    return indexed_count


async def build_cover_knowledge_base(db: Session, retriever: QdrantRetriever):
    """
    构建封面知识库

    索引历史高性能封面到向量数据库
    """
    logger.info("📚 开始构建封面知识库...")

    # 查询高性能封面 (predicted_ctr > 0.05 或 actual_ctr > 0.05)
    result = db.execute(text("""
        SELECT cover_id, generator, prompt, style,
               predicted_ctr, actual_ctr, predicted_engagement, actual_engagement,
               dominant_colors, has_face, text_overlay, text_content
        FROM generated_covers
        WHERE (predicted_ctr > 0.05 OR actual_ctr > 0.05)
        ORDER BY COALESCE(actual_ctr, predicted_ctr) DESC
        LIMIT 500
    """))

    covers = result.fetchall()

    if not covers:
        logger.warning("⚠️  没有找到高性能封面,跳过封面知识库构建")
        return 0

    indexed_count = 0

    for cover in covers:
        try:
            # 生成封面文本描述
            cover_text = f"Cover generated by {cover.generator}"
            if cover.prompt:
                cover_text += f"\nPrompt: {cover.prompt}"
            if cover.style:
                cover_text += f"\nStyle: {cover.style}"
            if cover.text_content:
                cover_text += f"\nText: {cover.text_content}"

            # 生成向量嵌入
            embeddings = await unified_llm.embedding(cover_text)
            vector = embeddings[0] if embeddings else None

            if not vector:
                logger.warning(f"⚠️  无法为封面 {cover.cover_id} 生成向量")
                continue

            # 构建元数据
            metadata = {
                "cover_id": cover.cover_id,
                "generator": cover.generator,
                "style": cover.style or "unknown",
                "predicted_ctr": float(cover.predicted_ctr) if cover.predicted_ctr else 0.0,
                "actual_ctr": float(cover.actual_ctr) if cover.actual_ctr else 0.0,
                "has_face": bool(cover.has_face),
                "text_overlay": bool(cover.text_overlay),
                "type": "cover"
            }

            # 插入到 Qdrant
            await retriever.upsert_reference(
                ref_id=cover.cover_id,
                vector=vector,
                metadata=metadata
            )

            indexed_count += 1

            if indexed_count % 10 == 0:
                logger.info(f"✅ 已索引 {indexed_count} 条封面")

        except Exception as e:
            logger.error(f"❌ 索引封面 {cover.cover_id} 失败: {e}")
            continue

    logger.info(f"✅ 封面知识库构建完成,共索引 {indexed_count} 条封面")
    return indexed_count


async def main():
    """主函数"""
    logger.info("🚀 开始构建 RAG 知识库...")

    # 创建数据库会话
    db = SessionLocal()

    try:
        # 初始化 Qdrant 检索器
        retriever = QdrantRetriever()

        # 创建集合
        logger.info("📦 创建 Qdrant 集合...")
        await retriever.create_collection()

        # 构建内容知识库
        content_count = await build_content_knowledge_base(db, retriever)

        # 构建因果关系知识库
        causal_count = await build_causal_knowledge_base(db, retriever)

        # 构建封面知识库
        cover_count = await build_cover_knowledge_base(db, retriever)

        # 总结
        total_count = content_count + causal_count + cover_count
        logger.info(f"""
╔══════════════════════════════════════════╗
║     RAG 知识库构建完成                    ║
╠══════════════════════════════════════════╣
║  内容知识库: {content_count:>4} 条                  ║
║  因果知识库: {causal_count:>4} 条                  ║
║  封面知识库: {cover_count:>4} 条                  ║
║  总计:      {total_count:>4} 条                  ║
╚══════════════════════════════════════════╝
        """)

        if total_count == 0:
            logger.warning("""
⚠️  警告: 没有索引任何数据到知识库

可能的原因:
1. 数据库中没有历史数据
2. 没有符合条件的内容、因果效应或封面

建议:
- 先运行系统收集一些数据
- 或者降低筛选条件
            """)

    except Exception as e:
        logger.error(f"❌ 构建知识库失败: {e}")
        import traceback
        traceback.print_exc()
        raise

    finally:
        db.close()


if __name__ == "__main__":
    asyncio.run(main())
