"""用户模型。"""
from sqlalchemy import String, Boolean, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import Optional

from app.models._base import PkMixin, TimestampMixin
from app.core.database import Base


class User(Base, PkMixin, TimestampMixin):
    __tablename__ = "users"
    __table_args__ = {"comment": "系统用户：学生/教师/管理员"}

    username: Mapped[str] = mapped_column(String(64), unique=True, index=True, comment="登录名")
    email: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(256))
    role: Mapped[str] = mapped_column(String(16), default="student", comment="student/teacher/admin")
    full_name: Mapped[str] = mapped_column(String(64), default="", comment="姓名")
    student_no: Mapped[str] = mapped_column(String(32), default="", comment="学号")
    learning_goal: Mapped[str] = mapped_column(
        String(256), default="", comment="学生默认学习目标"
    )
    weekly_hours: Mapped[int] = mapped_column(
        Integer, default=6, comment="学生默认每周学习时长"
    )
    learning_preferences: Mapped[str] = mapped_column(
        String(128), default="文本精读,视觉图解,实践演练", comment="学生学习形式偏好"
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    avatar: Mapped[str] = mapped_column(String(256), default="")
