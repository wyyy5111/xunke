from __future__ import annotations
from datetime import datetime
from typing import Literal, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator


class RegisterIn(BaseModel):
    username: str = Field(min_length=3, max_length=32)
    password: str = Field(min_length=8, max_length=64)
    email: str
    # 路由层会明确拒绝教师/管理员自注册，并返回可理解的权限错误。
    role: Literal["student", "teacher", "admin"] = "student"
    full_name: str = ""
    student_no: str = ""

    @field_validator("password")
    @classmethod
    def _password_complexity(cls, value: str) -> str:
        if not any(char.isalpha() for char in value) or not any(char.isdigit() for char in value):
            raise ValueError("密码至少包含一个字母和一个数字")
        return value


class LoginIn(BaseModel):
    username: str = Field(min_length=1, max_length=128)
    password: str = Field(min_length=1, max_length=128)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    email: str
    role: str
    full_name: str
    student_no: str
    learning_goal: str
    weekly_hours: int
    learning_preferences: str
    avatar: str
    is_active: bool
    created_at: datetime

class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    user: UserOut


class UserUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    full_name: Optional[str] = None
    avatar: Optional[str] = None
    email: Optional[str] = None
    student_no: Optional[str] = None
    is_active: Optional[bool] = None


class UserRoleUpdate(BaseModel):
    """管理员角色调整输入：仅接受平台定义的三类角色。"""

    model_config = ConfigDict(extra="forbid")

    role: Literal["student", "teacher", "admin"]


LearningPreference = Literal[
    "文本精读", "视觉图解", "实践演练", "案例研讨", "音视频学习"
]


class StudentSettingsUpdate(BaseModel):
    """学生个人与学习策略设置；角色、用户名和账号状态不在可写范围。"""

    model_config = ConfigDict(extra="forbid")

    full_name: str = Field(min_length=1, max_length=64)
    email: str = Field(min_length=3, max_length=128)
    course_id: Optional[int] = Field(default=None, gt=0)
    learning_goal: str = Field(default="", max_length=256)
    weekly_hours: int = Field(default=6, ge=1, le=80)
    learning_preferences: list[LearningPreference] = Field(min_length=1, max_length=5)

    @field_validator("full_name", "email", "learning_goal")
    @classmethod
    def _strip_text(cls, value: str) -> str:
        return value.strip()

    @field_validator("email")
    @classmethod
    def _valid_email(cls, value: str) -> str:
        if value.count("@") != 1 or "." not in value.rsplit("@", 1)[-1]:
            raise ValueError("请输入有效邮箱")
        return value

    @field_validator("learning_preferences")
    @classmethod
    def _unique_preferences(cls, value: list[LearningPreference]) -> list[LearningPreference]:
        if len(set(value)) != len(value):
            raise ValueError("学习偏好不能重复")
        return value
