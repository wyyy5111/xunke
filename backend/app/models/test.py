"""前测/后测与答题记录。"""
from datetime import datetime
from sqlalchemy import String, Text, Integer, Float, DateTime, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column
from typing import Optional

from app.models._base import PkMixin, TimestampMixin
from app.core.database import Base


class PreTest(Base, PkMixin, TimestampMixin):
    __tablename__ = "pre_tests"
    student_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), index=True)
    course_id: Mapped[int] = mapped_column(Integer, ForeignKey("courses.id"), index=True)
    question_ids: Mapped[str] = mapped_column(Text, default="[]", comment="题目ID JSON")
    total: Mapped[int] = mapped_column(Integer, default=0)
    correct: Mapped[int] = mapped_column(Integer, default=0)
    score: Mapped[float] = mapped_column(Float, default=0.0, comment="0-100")
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    diagnosis: Mapped[str] = mapped_column(Text, default="{}", comment="诊断结果 JSON")


class PostTest(Base, PkMixin, TimestampMixin):
    __tablename__ = "post_tests"
    student_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), index=True)
    course_id: Mapped[int] = mapped_column(Integer, ForeignKey("courses.id"), index=True)
    question_ids: Mapped[str] = mapped_column(Text, default="[]")
    total: Mapped[int] = mapped_column(Integer, default=0)
    correct: Mapped[int] = mapped_column(Integer, default=0)
    score: Mapped[float] = mapped_column(Float, default=0.0)
    pre_score: Mapped[float] = mapped_column(Float, default=0.0)
    improvement: Mapped[float] = mapped_column(Float, default=0.0)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    by_kp: Mapped[str] = mapped_column(Text, default="{}", comment="按知识点提升 JSON")


class TestAnswer(Base, PkMixin, TimestampMixin):
    __tablename__ = "test_answers"
    student_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), index=True)
    course_id: Mapped[int] = mapped_column(Integer, ForeignKey("courses.id"), index=True)
    test_type: Mapped[str] = mapped_column(String(16), default="pre", comment="pre/post/practice")
    test_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    question_id: Mapped[int] = mapped_column(Integer, ForeignKey("questions.id"), index=True)
    answer: Mapped[str] = mapped_column(Text, default="")
    is_correct: Mapped[bool] = mapped_column(default=False)


class AssessmentAttempt(Base, PkMixin, TimestampMixin):
    """One immutable pre/post assessment paper assigned to one student."""
    __tablename__ = "assessment_attempts"
    student_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), index=True)
    course_id: Mapped[int] = mapped_column(Integer, ForeignKey("courses.id"), index=True)
    test_type: Mapped[str] = mapped_column(String(16), index=True, comment="pre/post")
    question_ids: Mapped[str] = mapped_column(Text, default="[]")
    status: Mapped[str] = mapped_column(String(16), default="open", index=True)
    test_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    submitted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
