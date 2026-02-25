"""
数据库迁移脚本
Database Migration Script

使用 Alembic 进行数据库版本管理
"""

import os
import sys
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from alembic import command
from alembic.config import Config


def get_alembic_config():
    """获取 Alembic 配置"""
    # Alembic 配置文件路径
    alembic_cfg = Config("alembic.ini")

    # 设置脚本位置
    alembic_cfg.set_main_option("script_location", "alembic")

    return alembic_cfg


def create_migration(message: str):
    """
    创建新的迁移脚本

    Args:
        message: 迁移描述
    """
    print(f"[*] Creating migration: {message}")
    alembic_cfg = get_alembic_config()
    command.revision(alembic_cfg, message=message, autogenerate=True)
    print("[✓] Migration created successfully")


def upgrade_database(revision: str = "head"):
    """
    升级数据库到指定版本

    Args:
        revision: 目标版本（默认 head）
    """
    print(f"[*] Upgrading database to: {revision}")
    alembic_cfg = get_alembic_config()
    command.upgrade(alembic_cfg, revision)
    print("[✓] Database upgraded successfully")


def downgrade_database(revision: str):
    """
    降级数据库到指定版本

    Args:
        revision: 目标版本
    """
    print(f"[*] Downgrading database to: {revision}")
    alembic_cfg = get_alembic_config()
    command.downgrade(alembic_cfg, revision)
    print("[✓] Database downgraded successfully")


def show_current_revision():
    """显示当前数据库版本"""
    print("[*] Current database revision:")
    alembic_cfg = get_alembic_config()
    command.current(alembic_cfg)


def show_migration_history():
    """显示迁移历史"""
    print("[*] Migration history:")
    alembic_cfg = get_alembic_config()
    command.history(alembic_cfg)


def init_alembic():
    """初始化 Alembic"""
    print("[*] Initializing Alembic...")
    os.system("alembic init alembic")
    print("[✓] Alembic initialized")
    print("\n[!] Please update alembic.ini and alembic/env.py with your database URL")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Database Migration Tool")
    parser.add_argument("command", choices=["init", "create", "upgrade", "downgrade", "current", "history"],
                       help="Migration command")
    parser.add_argument("-m", "--message", help="Migration message (for create)")
    parser.add_argument("-r", "--revision", default="head", help="Target revision")

    args = parser.parse_args()

    try:
        if args.command == "init":
            init_alembic()
        elif args.command == "create":
            if not args.message:
                print("[!] Error: --message is required for create command")
                sys.exit(1)
            create_migration(args.message)
        elif args.command == "upgrade":
            upgrade_database(args.revision)
        elif args.command == "downgrade":
            if args.revision == "head":
                print("[!] Error: --revision is required for downgrade command")
                sys.exit(1)
            downgrade_database(args.revision)
        elif args.command == "current":
            show_current_revision()
        elif args.command == "history":
            show_migration_history()
    except Exception as e:
        print(f"[✗] Error: {e}")
        sys.exit(1)
