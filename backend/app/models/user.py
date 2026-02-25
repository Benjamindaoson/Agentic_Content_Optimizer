from sqlalchemy import Column, String, Enum as SQLEnum
from sqlalchemy.orm import relationship
import enum
from app.models.base import BaseModel


class UserRole(str, enum.Enum):
    """用户角色"""

    ADMIN = "admin"
    USER = "user"


class User(BaseModel):
    """用户模型"""

    __tablename__ = "users"

    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(100))
    role = Column(SQLEnum(UserRole), default=UserRole.USER, nullable=False)

    # 关系
    projects = relationship("Project", back_populates="user", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<User(id={self.id}, email={self.email}, role={self.role})>"
