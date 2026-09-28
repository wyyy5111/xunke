"""FastAPI 依赖：当前用户、角色校验。"""
from __future__ import annotations
from typing import List

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import decode_token
from app.models.user import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)

CREDENTIALSExc = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="未认证或认证已过期",
    headers={"WWW-Authenticate": "Bearer"},
)


def get_current_user(
    token: str | None = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    if not token:
        raise CREDENTIALSExc
    payload = decode_token(token)
    if not payload or "sub" not in payload:
        raise CREDENTIALSExc
    try:
        user_id = int(payload["sub"])
    except (TypeError, ValueError):
        raise CREDENTIALSExc
    user = db.get(User, user_id)
    if not user or not user.is_active:
        raise CREDENTIALSExc
    return user


def require_roles(*roles: str):
    """角色守卫工厂。roles 为允许的角色名集合。"""

    def _checker(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(status_code=403, detail=f"权限不足，需要角色: {','.join(roles)}")
        return user

    return _checker


# 常用守卫
student_only = require_roles("student")
teacher_only = require_roles("teacher")
admin_only = require_roles("admin")
teacher_or_admin = require_roles("teacher", "admin")
any_role = require_roles("student", "teacher", "admin")
