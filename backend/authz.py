"""认证与角色权限依赖。"""

from typing import Callable, Optional

from fastapi import Header, HTTPException

from .config import settings
from .database import VALID_ROLES, get_user_by_token


def effective_role(user: dict) -> str:
    """环境配置的管理员 ID 始终拥有 admin 角色。"""
    if settings.admin_user_id and str(user.get("id")) == settings.admin_user_id:
        return "admin"
    role = user.get("role") or "consumer"
    return role if role in VALID_ROLES else "consumer"


def require_roles(*allowed_roles: str) -> Callable:
    allowed = set(allowed_roles)

    def dependency(authorization: Optional[str] = Header(None)) -> dict:
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(
                status_code=401,
                detail="请先登录",
                headers={"WWW-Authenticate": "Bearer"},
            )
        user = get_user_by_token(authorization[7:].strip())
        if not user:
            raise HTTPException(
                status_code=401,
                detail="登录已失效，请重新登录",
                headers={"WWW-Authenticate": "Bearer"},
            )
        user = dict(user)
        user["role"] = effective_role(user)
        if user["role"] not in allowed:
            raise HTTPException(status_code=403, detail="无权访问该资源")
        return user

    return dependency
