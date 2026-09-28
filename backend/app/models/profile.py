"""学生画像与知识点掌握度。"""
from sqlalchemy import String, Text, Integer, Float, ForeignKey, Boolean
from sqlalchemy.orm import Mapped, mapped_column
from typing import Optional

from app.models._base import PkMixin, TimestampMixin
from app.core.database import Base


class StudentProfile(Base, PkMixin, TimestampMixin):
    __tablename__ = "student_profiles"
    student_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), index=True)
    course_id: Mapped[int] = mapped_column(Integer, ForeignKey("courses.id"), index=True)
    stage: Mapped[str] = mapped_column(String(32), default="pre_test", comment="pre_test/learning/post_test")
    goal: Mapped[str] = mapped_column(String(256), default="")
    weekly_hours: Mapped[int] = mapped_column(Integer, default=6)
    base_level: Mapped[str] = mapped_column(String(16), default="basic", comment="basic/intermediate/advanced")
    pref_format: Mapped[str] = mapped_column(String(64), default="文字,图解,案例", comment="偏好学习形式")
    pref_style: Mapped[str] = mapped_column(String(32), default="理解型", comment="记忆/理解/实践型")
    learning_speed: Mapped[str] = mapped_column(String(16), default="normal", comment="slow/normal/fast")
    pre_score: Mapped[float] = mapped_column(Float, default=0.0)
    post_score: Mapped[float] = mapped_column(Float, default=0.0)
    weak_points: Mapped[str] = mapped_column(Text, default="[]", comment="薄弱知识点 JSON")
    recommendation: Mapped[str] = mapped_column(Text, default="", comment="推荐学习策略")
    extra: Mapped[str] = mapped_column(Text, default="{}", comment="扩展字段 JSON")


class KnowledgeMastery(Base, PkMixin, TimestampMixin):
    __tablename__ = "knowledge_mastery"
    student_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), index=True)
    course_id: Mapped[int] = mapped_column(Integer, ForeignKey("courses.id"), index=True)
    kp_id: Mapped[int] = mapped_column(Integer, ForeignKey("knowledge_points.id"), index=True)
    mastery_score: Mapped[float] = mapped_column(Float, default=0.0, comment="0-100")
    status: Mapped[str] = mapped_column(String(16), default="weak", comment="weak/consolidated/mastered")
    pre_score: Mapped[float] = mapped_column(Float, default=0.0)
    post_score: Mapped[float] = mapped_column(Float, default=0.0)
