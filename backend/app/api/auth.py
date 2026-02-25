from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.core.security import (
    verify_password,
    get_password_hash,
    create_access_token,
    create_refresh_token,
    decode_token,
    verify_token_type,
)
from app.core.redis import get_redis
from app.models.user import User
from app.schemas.auth import (
    UserCreate,
    UserLogin,
    UserResponse,
    Token,
    RefreshTokenRequest,
    SuccessResponse,
)
from app.api.deps import get_current_user

security = HTTPBearer()

router = APIRouter()


@router.post("/register", response_model=SuccessResponse, status_code=status.HTTP_201_CREATED)
async def register(
    user_data: UserCreate,
    db: AsyncSession = Depends(get_db),
):
    """用户注册"""

    # 检查邮箱是否已存在
    result = await db.execute(select(User).where(User.email == user_data.email))
    existing_user = result.scalar_one_or_none()

    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="该邮箱已被注册",
        )

    # 创建新用户
    new_user = User(
        email=user_data.email,
        password_hash=get_password_hash(user_data.password),
        full_name=user_data.full_name,
    )

    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)

    return SuccessResponse(
        message="注册成功",
        data={
            "user": {
                "id": new_user.id,
                "email": new_user.email,
                "full_name": new_user.full_name,
                "role": new_user.role.value,
            }
        },
    )


@router.post("/login", response_model=SuccessResponse)
async def login(
    credentials: UserLogin,
    db: AsyncSession = Depends(get_db),
):
    """用户登录"""

    # 查询用户
    result = await db.execute(select(User).where(User.email == credentials.email))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="邮箱或密码错误",
        )

    # 验证密码
    if not verify_password(credentials.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="邮箱或密码错误",
        )

    # 生成令牌
    token_data = {
        "sub": user.id,
        "email": user.email,
        "role": user.role.value,
    }

    access_token = create_access_token(token_data)
    refresh_token = create_refresh_token(token_data)

    return SuccessResponse(
        message="登录成功",
        data={
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "user": {
                "id": user.id,
                "email": user.email,
                "full_name": user.full_name,
                "role": user.role.value,
            },
        },
    )


@router.post("/refresh", response_model=SuccessResponse)
async def refresh_token(
    request: RefreshTokenRequest,
    db: AsyncSession = Depends(get_db),
):
    """刷新访问令牌"""

    # 解码刷新令牌
    payload = decode_token(request.refresh_token)

    # 验证令牌类型
    verify_token_type(payload, "refresh")

    # 获取用户 ID
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的刷新令牌",
        )

    # 查询用户
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在",
        )

    # 生成新的访问令牌
    token_data = {
        "sub": user.id,
        "email": user.email,
        "role": user.role.value,
    }

    new_access_token = create_access_token(token_data)

    return SuccessResponse(
        message="令牌刷新成功",
        data={
            "access_token": new_access_token,
            "token_type": "bearer",
        },
    )


@router.get("/me", response_model=SuccessResponse)
async def get_current_user_info(
    current_user: User = Depends(get_current_user),
):
    """获取当前用户信息"""
    return SuccessResponse(
        data={
            "user": {
                "id": current_user.id,
                "email": current_user.email,
                "full_name": current_user.full_name,
                "role": current_user.role.value,
                "created_at": current_user.created_at.isoformat(),
            }
        },
    )


@router.post("/logout", response_model=SuccessResponse)
async def logout(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    current_user: User = Depends(get_current_user),
):
    """用户登出"""
    token = credentials.credentials
    payload = decode_token(token)
    jti = payload.get("jti")
    if jti:
        exp = payload.get("exp", 0)
        from datetime import datetime
        now = int(datetime.utcnow().timestamp())
        ttl = max(exp - now, 0)
        if ttl > 0:
            redis = await get_redis()
            await redis.blacklist_token(jti, ttl)
    return SuccessResponse(message="登出成功")
