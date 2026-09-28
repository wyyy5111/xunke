"""学习路径、学习记录、错题本。"""
from datetime import datetime
from sqlalchemy import String, Text, Integer, Float, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import Mapped, mapped_column
from typing import Optional

from app.models._base import PkMixin, TimestampMixin
from app.core.database import Base


class LearningPath(Base, PkMixin, TimestampMixin):
    __tablename__ = "learning_paths"
    student_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), index=True)
    course_id: Mapped[int] = mapped_column(Integer, ForeignKey("courses.id"), index=True)
    profile_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    nodes: Mapped[str] = mapped_column(Text, default="[]", comment="路径节点 JSON")
    total_minutes: Mapped[int] = mapped_column(Integer, default=0)
    completed_nodes: Mapped[int] = mapped_column(Integer, default=0)


class LearningRecord(Base, PkMixin, TimestampMixin):
    __tablename__ = "learning_records"
    student_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), index=True)
    course_id: Mapped[int] = mapped_column(Integer, ForeignKey("courses.id"), index=True)
    resource_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    kp_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    action: Mapped[str] = mapped_column(String(32), comment="view/finish/practice/answer")
    duration: Mapped[int] = mapped_column(Integer, default=0, comment="秒")
    happened_at: Mapped[datetime] = mapped_column(DateTime, index=True)


class WrongQuestion(Base, PkMixin, TimestampMixin):
    __tablename__ = "wrong_questions"
    student_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), index=True)
    course_id: Mapped[int] = mapped_column(Integer, ForeignKey("courses.id"), index=True)
    question_id: Mapped[int] = mapped_column(Integer, ForeignKey("questions.id"), index=True)
    kp_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    wrong_answer: Mapped[str] = mapped_column(Text, default="")
    reason: Mapped[str] = mapped_column(String(128), default="", comment="错因")
    reviewed: Mapped[bool] = mapped_column(Boolean, default=False)
    resolved: Mapped[bool] = mapped_column(Boolean, default=False, comment="已通过补救解决")
