from pydantic import BaseModel, EmailStr, Field, validator
from typing import Optional
from datetime import datetime


# ==================== 用户相关 Schema ====================

class UserBase(BaseModel):
    """用户基础 Schema"""
    email: EmailStr
    full_name: Optional[str] = None


class UserCreate(UserBase):
    """用户创建 Schema"""
    password: str = Field(..., min_length=8, max_length=100)

    @validator('password')
    def validate_password(cls, v):
        if len(v) < 8:
            raise ValueError('密码长度至少为 8 个字符')
        if not any(char.isupper() for char in v):
            raise ValueError('密码必须包含至少一个大写字母')
        if not any(char.islower() for char in v):
            raise ValueError('密码必须包含至少一个小写字母')
        if not any(char.isdigit() for char in v):
            raise ValueError('密码必须包含至少一个数字')
        if not any(char in '!@#$%^&*()_+-=[]{}|;:,.<>?/~`' for char in v):
            raise ValueError('密码必须包含至少一个特殊字符')
        return v


class UserLogin(BaseModel):
    """用户登录 Schema"""
    email: EmailStr
    password: str


class UserResponse(UserBase):
    """用户响应 Schema"""
    id: int
    role: str
    created_at: datetime

    class Config:
        from_attributes = True


class UserUpdate(BaseModel):
    """用户更新 Schema"""
    full_name: Optional[str] = None
    password: Optional[str] = None


# ==================== 认证相关 Schema ====================

class Token(BaseModel):
    """令牌响应"""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class TokenPayload(BaseModel):
    """令牌载荷"""
    sub: int  # user_id
    email: str
    role: str
    exp: datetime


class RefreshTokenRequest(BaseModel):
    """刷新令牌请求"""
    refresh_token: str


# ==================== 统一响应 Schema ====================

class ResponseBase(BaseModel):
    """统一响应基类"""
    code: int = 200
    message: str = "success"


class SuccessResponse(ResponseBase):
    """成功响应"""
    data: Optional[dict] = None


class ErrorResponse(ResponseBase):
    """错误响应"""
    code: int = 400
    message: str
    details: Optional[dict] = None
