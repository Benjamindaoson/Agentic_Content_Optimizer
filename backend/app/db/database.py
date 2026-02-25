"""
数据库初始化和连接管理
"""

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import NullPool
from contextlib import contextmanager
from typing import Generator
import os
from pathlib import Path

from app.db.models import Base

# 数据库配置
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:postgres@localhost:5432/viral_flywheel"
)

# 创建引擎
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
    echo=False  # 生产环境设为 False
)

# 创建会话工厂
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db():
    """初始化数据库（创建所有表）"""
    Base.metadata.create_all(bind=engine)
    print("✅ 数据库表创建完成")


def drop_db():
    """删除所有表（危险操作！）"""
    Base.metadata.drop_all(bind=engine)
    print("⚠️ 数据库表已删除")


@contextmanager
def get_db() -> Generator[Session, None, None]:
    """
    获取数据库会话（上下文管理器）

    使用示例：
        with get_db() as db:
            note = db.query(XHSNote).filter_by(note_id="xxx").first()
    """
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception as e:
        db.rollback()
        raise e
    finally:
        db.close()


def get_db_session() -> Session:
    """
    获取数据库会话（用于依赖注入）

    使用示例（FastAPI）：
        @app.get("/notes")
        def get_notes(db: Session = Depends(get_db_session)):
            return db.query(XHSNote).all()
    """
    db = SessionLocal()
    try:
        return db
    finally:
        pass  # 由调用方负责关闭


# 数据库健康检查
def check_db_health() -> bool:
    """检查数据库连接是否正常"""
    try:
        with get_db() as db:
            db.execute(text("SELECT 1"))
        return True
    except Exception as e:
        print(f"❌ 数据库连接失败: {e}")
        return False
