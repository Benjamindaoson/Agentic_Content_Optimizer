"""
简化的 API 启动脚本

只启动核心功能和 ML 训练相关的 API
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 创建 FastAPI 应用
app = FastAPI(
    title="Growth Flywheel ML API",
    description="ML 训练和数据收集 API",
    version="1.0.0"
)

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册 ML 训练 API
try:
    from app.api_ml_training import router as ml_training_router
    app.include_router(ml_training_router)
    logger.info("✅ ML 训练 API 路由已注册")
except Exception as e:
    logger.warning(f"⚠️  ML 训练 API 注册失败: {e}")

# 注册 ML 反馈收集 API
try:
    from app.api_ml_feedback import router as ml_feedback_router
    app.include_router(ml_feedback_router)
    logger.info("✅ ML 反馈收集 API 路由已注册")
except Exception as e:
    logger.warning(f"⚠️  ML 反馈收集 API 注册失败: {e}")

# 注册数据收集 API
try:
    from app.api_data_collection import router as data_collection_router
    app.include_router(data_collection_router)
    logger.info("✅ 数据收集 API 路由已注册")
except Exception as e:
    logger.warning(f"⚠️  数据收集 API 注册失败: {e}")


@app.get("/")
async def root():
    """根路径"""
    return {
        "message": "Growth Flywheel ML API",
        "version": "1.0.0",
        "docs": "/docs",
        "endpoints": {
            "ml_training": "/api/ml/*",
            "ml_feedback": "/api/ml/feedback/*",
            "data_collection": "/api/data-collection/*"
        }
    }


@app.get("/health")
async def health():
    """健康检查"""
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn

    logger.info("=" * 80)
    logger.info("🚀 启动 Growth Flywheel ML API")
    logger.info("=" * 80)
    logger.info("\n📚 API 文档: http://localhost:8000/docs")
    logger.info("🏥 健康检查: http://localhost:8000/health")
    logger.info("\n")

    uvicorn.run(
        "app.main_ml:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
