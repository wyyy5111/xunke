"""文档分块：SQLite 是课程检索片段与引用元数据的唯一事实来源。"""
from sqlalchemy import String, Text, Integer, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.models._base import PkMixin, TimestampMixin
from app.core.database import Base


class DocumentChunk(Base, PkMixin, TimestampMixin):
    __tablename__ = "document_chunks"
    course_id: Mapped[int] = mapped_column(Integer, ForeignKey("courses.id"), index=True)
    file_id: Mapped[int] = mapped_column(Integer, ForeignKey("course_files.id"), index=True)
    chunk_index: Mapped[int] = mapped_column(Integer, default=0)
    text: Mapped[str] = mapped_column(Text, default="")
    page: Mapped[int] = mapped_column(Integer, default=0)
    source_name: Mapped[str] = mapped_column(String(256), default="")
    # Legacy competition demo databases contain this NOT NULL column. The
    # current retriever no longer depends on a process-local vector id, but we
    # keep a deterministic compatibility value so new chunks can be inserted
    # without forcing users to discard their existing course data.
    vector_id: Mapped[int] = mapped_column(Integer, default=0)
    tokens: Mapped[int] = mapped_column(Integer, default=0)
