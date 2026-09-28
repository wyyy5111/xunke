"""知识点与关系（知识图谱）。"""
from sqlalchemy import String, Text, Integer, Float, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import Optional

from app.models._base import PkMixin, TimestampMixin
from app.core.database import Base


class KnowledgePoint(Base, PkMixin, TimestampMixin):
    __tablename__ = "knowledge_points"
    course_id: Mapped[int] = mapped_column(Integer, ForeignKey("courses.id"), index=True)
    chapter_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("course_chapters.id"), nullable=True)
    name: Mapped[str] = mapped_column(String(128), index=True, comment="知识点名称")
    description: Mapped[str] = mapped_column(Text, default="")
    difficulty: Mapped[int] = mapped_column(Integer, default=3, comment="1-5 难度")
    importance: Mapped[float] = mapped_column(Float, default=0.5, comment="知识点权重 0-1")
    keywords: Mapped[str] = mapped_column(String(256), default="", comment="关键词，逗号分隔")


class KnowledgeRelation(Base, PkMixin, TimestampMixin):
    __tablename__ = "knowledge_relations"
    course_id: Mapped[int] = mapped_column(Integer, ForeignKey("courses.id"), index=True)
    source_id: Mapped[int] = mapped_column(Integer, ForeignKey("knowledge_points.id"), index=True)
    target_id: Mapped[int] = mapped_column(Integer, ForeignKey("knowledge_points.id"), index=True)
    relation: Mapped[str] = mapped_column(String(32), default="prerequisite",
                                          comment="prerequisite 包含 相似 易混")
    weight: Mapped[float] = mapped_column(Float, default=1.0)
