#!/usr/bin/env python3
"""
启动 ML API 服务

简化版本，只包含 ML 训练相关的 API
"""

import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

from app.main_ml import app
import uvicorn
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

if __name__ == "__main__":
    logger.info("=" * 80)
    logger.info("🚀 启动 Growth Flywheel ML API")
    logger.info("=" * 80)
    logger.info("\n📚 API 文档: http://localhost:8001/docs")
    logger.info("🏥 健康检查: http://localhost:8001/health")
    logger.info("📊 反馈统计: http://localhost:8001/api/ml/feedback/stats")
    logger.info("\n按 Ctrl+C 停止服务\n")

    uvicorn.run(
        "app.main_ml:app",
        host="0.0.0.0",
        port=8001,
        log_level="info",
        reload=False,
    )
