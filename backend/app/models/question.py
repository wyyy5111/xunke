"""题库与选项。"""
from sqlalchemy import String, Text, Integer, Float, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import Optional

from app.models._base import PkMixin, TimestampMixin
from app.core.database import Base


class Question(Base, PkMixin, TimestampMixin):
    __tablename__ = "questions"
    course_id: Mapped[int] = mapped_column(Integer, ForeignKey("courses.id"), index=True)
    kp_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("knowledge_points.id"), nullable=True, index=True)
    qtype: Mapped[str] = mapped_column(String(16), default="single",
                                        comment="single/multiple/judge/fill/short/code/experiment")
    stem: Mapped[str] = mapped_column(Text, comment="题干")
    answer: Mapped[str] = mapped_column(Text, default="", comment="正确答案")
    analysis: Mapped[str] = mapped_column(Text, default="", comment="解析")
    difficulty: Mapped[int] = mapped_column(Integer, default=3, comment="1-5")
    tags: Mapped[str] = mapped_column(String(128), default="")
    source: Mapped[str] = mapped_column(String(32), default="manual", comment="manual/ai/seed")
    ai_resource_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("generated_resources.id"), nullable=True, index=True
    )
    citations: Mapped[str] = mapped_column(Text, default="[]", comment="引用来源 JSON")

    options: Mapped[list["QuestionOption"]] = relationship(back_populates="question", cascade="all, delete-orphan",
                                                            order_by="QuestionOption.order_index")


class QuestionOption(Base, PkMixin, TimestampMixin):
    __tablename__ = "question_options"
    question_id: Mapped[int] = mapped_column(Integer, ForeignKey("questions.id"), index=True)
    key: Mapped[str] = mapped_column(String(8), comment="A/B/C/D")
    content: Mapped[str] = mapped_column(Text)
    is_correct: Mapped[bool] = mapped_column(default=False)
    order_index: Mapped[int] = mapped_column(Integer, default=0)

    question: Mapped[Question] = relationship(back_populates="options")
