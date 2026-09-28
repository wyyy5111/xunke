"""AI 生成资源与教师审核。"""
from sqlalchemy import String, Text, Integer, Float, ForeignKey, Boolean, JSON, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column
from typing import Optional

from app.models._base import PkMixin, TimestampMixin
from app.core.database import Base


class GeneratedResource(Base, PkMixin, TimestampMixin):
    __tablename__ = "generated_resources"
    __table_args__ = (
        CheckConstraint(
            "is_personalized = 0 OR student_id IS NOT NULL",
            name="ck_generated_resource_personalized_owner",
        ),
        CheckConstraint(
            "review_status IN ('pending','approved','rejected','risk','published','archived')",
            name="ck_generated_resource_review_status",
        ),
    )
    course_id: Mapped[int] = mapped_column(Integer, ForeignKey("courses.id"), index=True)
    student_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True, comment="个性化资源所属学生")
    kp_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("knowledge_points.id"), nullable=True)
    rtype: Mapped[str] = mapped_column(String(32), index=True,
                                        comment="lecture/mindmap/exercise/experiment/reading/ppt/video/wrong_review/remedial")
    title: Mapped[str] = mapped_column(String(256))
    content: Mapped[str] = mapped_column(Text, default="", comment="正文 Markdown / Mermaid / JSON")
    citations: Mapped[str] = mapped_column(Text, default="[]", comment="引用来源 JSON")
    quality_score: Mapped[float] = mapped_column(Float, default=0.0)
    review_status: Mapped[str] = mapped_column(
        String(16), default="pending",
        comment="pending/approved/rejected/risk/published/archived",
    )
    published: Mapped[bool] = mapped_column(Boolean, default=False)
    agent_run_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    extra: Mapped[str] = mapped_column(Text, default="{}")
    is_personalized: Mapped[bool] = mapped_column(Boolean, default=False)


class ResourceReview(Base, PkMixin, TimestampMixin):
    __tablename__ = "resource_reviews"
    resource_id: Mapped[int] = mapped_column(Integer, ForeignKey("generated_resources.id"), index=True)
    teacher_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"))
    decision: Mapped[str] = mapped_column(String(16), comment="approved/rejected/risk/needs_edit")
    comment: Mapped[str] = mapped_column(Text, default="")
    revised_content: Mapped[str] = mapped_column(Text, default="", comment="教师修改后内容")
