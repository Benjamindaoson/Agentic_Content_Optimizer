"""
创建数据收集相关的数据库表

直接使用 SQLAlchemy 创建表，不依赖 Alembic
"""

import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from app.core.database import engine, Base
from app.models.data_collection import ContentGenerationLog, UserFeedbackLog, ABTestLog


def create_tables():
    """创建数据收集相关的表"""
    print("=" * 80)
    print("📊 创建数据收集系统表")
    print("=" * 80)

    try:
        # 创建所有表
        print("\n🔄 正在创建表...")
        Base.metadata.create_all(bind=engine)

        print("\n✅ 表创建成功！")
        print("   - content_generation_logs (内容生成日志)")
        print("   - user_feedback_logs (用户反馈日志)")
        print("   - ab_test_logs (A/B 测试日志)")

        print("\n📋 表结构：")
        print("\n1. content_generation_logs:")
        print("   - 记录每次内容生成的完整信息")
        print("   - 包括输入参数、生成配置、输出内容、质量评分等")

        print("\n2. user_feedback_logs:")
        print("   - 记录用户对生成内容的所有反馈行为")
        print("   - 包括点赞、收藏、分享、评论、转化等")

        print("\n3. ab_test_logs:")
        print("   - 记录 A/B 测试的配置和结果")
        print("   - 用于对比不同模型/策略的效果")

        print("\n" + "=" * 80)
        print("✅ 数据收集系统已就绪！")
        print("=" * 80)

        print("\n下一步：")
        print("1. 运行 python scripts/test_data_collection.py 测试数据插入")
        print("2. 启动 API 服务: uvicorn app.main:app --reload")
        print("3. 测试 API 端点: curl http://localhost:8000/api/data-collection/stats/daily")

    except Exception as e:
        print(f"\n❌ 创建表失败: {e}")
        print("\n可能的原因：")
        print("1. 数据库连接失败 - 检查 .env 中的 DATABASE_URL")
        print("2. 表已存在 - 使用 DROP TABLE 删除现有表")
        print("3. 权限不足 - 确保数据库用户有创建表的权限")
        sys.exit(1)


if __name__ == "__main__":
    create_tables()
