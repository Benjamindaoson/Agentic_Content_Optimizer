"""
项目初始化脚本

初始化数据库、创建目录结构、下载依赖
"""

import os
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.db import init_db, check_db_health


def create_directories():
    """创建必要的目录结构"""
    directories = [
        "data/covers",
        "data/images",
        "data/viral",
        "data/exports",
        "logs",
        "models/metric_predictors",
    ]

    for directory in directories:
        path = project_root / directory
        path.mkdir(parents=True, exist_ok=True)
        print(f"✅ 创建目录: {path}")


def initialize_database():
    """初始化数据库"""
    print("\n检查数据库连接...")

    if not check_db_health():
        print("❌ 数据库连接失败！")
        print("请确保 PostgreSQL 已启动，并配置正确的 DATABASE_URL")
        return False

    print("✅ 数据库连接成功")

    print("\n初始化数据库表...")
    try:
        init_db()
        print("✅ 数据库表创建完成")
        return True
    except Exception as e:
        print(f"❌ 数据库初始化失败: {e}")
        return False


def check_environment():
    """检查环境变量"""
    print("\n检查环境变量...")

    required_vars = [
        "DATABASE_URL",
    ]

    optional_vars = [
        "REDIS_URL",
        "QDRANT_URL",
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
    ]

    missing_required = []
    missing_optional = []

    for var in required_vars:
        if not os.getenv(var):
            missing_required.append(var)
        else:
            print(f"✅ {var}: 已配置")

    for var in optional_vars:
        if not os.getenv(var):
            missing_optional.append(var)
        else:
            print(f"✅ {var}: 已配置")

    if missing_required:
        print(f"\n❌ 缺少必需的环境变量: {', '.join(missing_required)}")
        print("请在 .env 文件中配置这些变量")
        return False

    if missing_optional:
        print(f"\n⚠️  缺少可选的环境变量: {', '.join(missing_optional)}")
        print("某些功能可能无法使用")

    return True


def main():
    """主函数"""
    print("=" * 80)
    print("Viral Flywheel v3.0 - 项目初始化")
    print("=" * 80)

    # 1. 检查环境变量
    if not check_environment():
        print("\n❌ 环境检查失败，请配置环境变量后重试")
        return 1

    # 2. 创建目录结构
    print("\n" + "=" * 80)
    print("创建目录结构")
    print("=" * 80)
    create_directories()

    # 3. 初始化数据库
    print("\n" + "=" * 80)
    print("初始化数据库")
    print("=" * 80)
    if not initialize_database():
        print("\n❌ 数据库初始化失败")
        return 1

    # 4. 完成
    print("\n" + "=" * 80)
    print("✅ 项目初始化完成！")
    print("=" * 80)

    print("\n下一步:")
    print("1. 启动 API 服务: python app/api.py")
    print("2. 或使用 uvicorn: uvicorn app.api:app --reload --host 0.0.0.0 --port 8000")
    print("3. 访问 API 文档: http://localhost:8000/docs")

    return 0


if __name__ == "__main__":
    sys.exit(main())
