"""课程相关模型。"""
from sqlalchemy import String, Text, Integer, ForeignKey, Boolean, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import Optional

from app.models._base import PkMixin, TimestampMixin
from app.core.database import Base


class Course(Base, PkMixin, TimestampMixin):
    __tablename__ = "courses"
    name: Mapped[str] = mapped_column(String(128), index=True, comment="课程名称")
    code: Mapped[str] = mapped_column(String(64), default="", comment="课程代码")
    description: Mapped[str] = mapped_column(Text, default="")
    cover: Mapped[str] = mapped_column(String(256), default="", comment="封面图URL")
    teacher_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), index=True)
    status: Mapped[str] = mapped_column(String(16), default="active", comment="active/archived")
    tags: Mapped[str] = mapped_column(String(256), default="", comment="逗号分隔")

    chapters: Mapped[list["CourseChapter"]] = relationship(back_populates="course", cascade="all, delete-orphan")
    files: Mapped[list["CourseFile"]] = relationship(back_populates="course", cascade="all, delete-orphan")


class CourseChapter(Base, PkMixin, TimestampMixin):
    __tablename__ = "course_chapters"
    course_id: Mapped[int] = mapped_column(Integer, ForeignKey("courses.id"), index=True)
    title: Mapped[str] = mapped_column(String(128))
    summary: Mapped[str] = mapped_column(Text, default="")
    order_index: Mapped[int] = mapped_column(Integer, default=0)

    course: Mapped[Course] = relationship(back_populates="chapters")


class CourseFile(Base, PkMixin, TimestampMixin):
    __tablename__ = "course_files"
    course_id: Mapped[int] = mapped_column(Integer, ForeignKey("courses.id"), index=True)
    uploader_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"))
    filename: Mapped[str] = mapped_column(String(256))
    stored_path: Mapped[str] = mapped_column(String(512))
    file_type: Mapped[str] = mapped_column(String(16), comment="pdf/docx/pptx/txt/md")
    size: Mapped[int] = mapped_column(Integer, default=0)
    parse_status: Mapped[str] = mapped_column(String(16), default="pending", comment="pending/parsed/failed")
    parse_summary: Mapped[str] = mapped_column(Text, default="")
    indexed: Mapped[bool] = mapped_column(Boolean, default=False, comment="是否已建向量索引")

    course: Mapped[Course] = relationship(back_populates="files")


class CourseEnrollment(Base, PkMixin, TimestampMixin):
    __tablename__ = "course_enrollments"
    __table_args__ = (
        UniqueConstraint("course_id", "student_id", name="uq_course_enrollment_student"),
    )
    course_id: Mapped[int] = mapped_column(Integer, ForeignKey("courses.id"), index=True)
    student_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), index=True)
    goal: Mapped[str] = mapped_column(String(256), default="", comment="学习目标")
    weekly_hours: Mapped[int] = mapped_column(Integer, default=6, comment="每周可用学时")
