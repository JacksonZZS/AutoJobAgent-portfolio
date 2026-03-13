"""
认证 API 路由
封装 core/auth_manager.py 和 core/auth_service.py 提供 REST API
"""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from datetime import datetime
from typing import Optional

# 导入核心业务模块（保持不变）
from core.auth_manager import get_auth_manager
from core.auth_service import (
    issue_login_token,
    verify_login_token,
    revoke_token,
    get_user_by_id as get_user_by_id_from_token
)
from core.user_identity import get_user_identity_manager

# 导入 Pydantic 数据模型
from backend.models.schemas import (
    LoginRequest,
    RegisterRequest,
    LoginResponse,
    UserInfo,
    MessageResponse
)

router = APIRouter(prefix="/auth", tags=["Authentication"])

# HTTP Bearer 认证方案
security = HTTPBearer()


# ============================================================
# 依赖注入：获取当前用户
# ============================================================

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> UserInfo:
    """
    依赖注入：从 JWT token 获取当前用户信息

    Args:
        credentials: HTTP Bearer 认证凭据

    Returns:
        用户信息

    Raises:
        HTTPException: 如果 token 无效或用户不存在
    """
    token = credentials.credentials

    # 验证 token
    user_id = verify_login_token(token)
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 获取用户信息
    auth_mgr = get_auth_manager()
    user_data = auth_mgr.get_user_by_id(user_id)

    if not user_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    # 从 user_identity 获取完整信息
    identity_mgr = get_user_identity_manager()
    identity = identity_mgr.get_user_identity(str(user_id))

    # 转换为字典以便访问（identity 是 UserIdentity 对象）
    identity_dict = identity.to_dict() if identity else {}

    return UserInfo(
        id=user_data["id"],
        username=user_data["username"],
        email=user_data.get("email") or identity_dict.get("email", ""),
        real_name=identity_dict.get("real_name", user_data["username"]),
        phone=identity_dict.get("phone", ""),
        linkedin=identity_dict.get("linkedin"),
        github=identity_dict.get("github"),
        created_at=datetime.fromisoformat(user_data["created_at"])
    )


# ============================================================
# API 端点
# ============================================================

@router.post("/register", response_model=MessageResponse, status_code=status.HTTP_201_CREATED)
async def register(request: RegisterRequest):
    """
    用户注册

    - 创建新用户账户
    - 自动同步到 SQLite 和 users_db.json
    - 密码自动加密存储
    """
    auth_mgr = get_auth_manager()

    # 调用核心模块的注册函数
    success, message = auth_mgr.register(
        username=request.username,
        password=request.password,
        email=request.email,
        real_name=request.real_name,
        phone=request.phone,
        linkedin=request.linkedin,
        github=request.github
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=message
        )

    return MessageResponse(
        message=message,
        status="success",
        data={"username": request.username}
    )


@router.post("/login", response_model=LoginResponse)
async def login(request: LoginRequest):
    """
    用户登录

    - 验证用户名和密码
    - 返回 JWT access token（有效期 7 天）
    - 更新最后登录时间
    """
    auth_mgr = get_auth_manager()

    # 验证登录凭据
    success, user_data, message = auth_mgr.login(
        username=request.username,
        password=request.password
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=message,
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 颁发 JWT token
    user_id = user_data["id"]
    access_token, expires_at = issue_login_token(user_id, ttl_days=7)

    # 获取完整用户信息
    identity_mgr = get_user_identity_manager()
    identity = identity_mgr.get_user_identity(str(user_id))

    # 转换为字典以便访问（identity 是 UserIdentity 对象）
    identity_dict = identity.to_dict() if identity else {}

    # 构造用户信息
    user_info = UserInfo(
        id=user_data["id"],
        username=user_data["username"],
        email=user_data.get("email") or identity_dict.get("email", ""),
        real_name=identity_dict.get("real_name", user_data["username"]),
        phone=identity_dict.get("phone", ""),
        linkedin=identity_dict.get("linkedin"),
        github=identity_dict.get("github"),
        created_at=datetime.fromisoformat(user_data["created_at"])
    )

    return LoginResponse(
        access_token=access_token,
        token_type="bearer",
        user=user_info
    )


@router.post("/logout", response_model=MessageResponse)
async def logout(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """
    用户登出

    - 撤销当前 token
    - 前端需要清除本地存储的 token
    """
    token = credentials.credentials

    success = revoke_token(token)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid token or already revoked"
        )

    return MessageResponse(
        message="Logged out successfully",
        status="success"
    )


@router.get("/me", response_model=UserInfo)
async def get_current_user_info(current_user: UserInfo = Depends(get_current_user)):
    """
    获取当前用户信息

    - 需要在 Header 中提供有效的 Bearer token
    - 用于前端验证登录状态和获取用户资料
    """
    return current_user


@router.get("/validate-token", response_model=MessageResponse)
async def validate_token(current_user: UserInfo = Depends(get_current_user)):
    """
    验证 token 是否有效

    - 前端可用于检查 token 是否过期
    - 如果 token 无效会返回 401 错误
    """
    return MessageResponse(
        message="Token is valid",
        status="success",
        data={
            "user_id": current_user.id,
            "username": current_user.username
        }
    )
