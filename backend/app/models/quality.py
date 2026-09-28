"""质量评分报告。"""
from sqlalchemy import String, Text, Integer, Float, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.models._base import PkMixin, TimestampMixin
from app.core.database import Base


class QualityReport(Base, PkMixin, TimestampMixin):
    __tablename__ = "quality_reports"
    resource_id: Mapped[int] = mapped_column(Integer, ForeignKey("generated_resources.id"), index=True)
    coverage: Mapped[float] = mapped_column(Float, default=0.0, comment="知识点覆盖率")
    citation_hit: Mapped[float] = mapped_column(Float, default=0.0, comment="引用命中率")
    answer_consistency: Mapped[float] = mapped_column(Float, default=0.0, comment="答案一致性")
    difficulty_match: Mapped[float] = mapped_column(Float, default=0.0, comment="难度匹配度")
    structure: Mapped[float] = mapped_column(Float, default=0.0, comment="结构完整度")
    diversity: Mapped[float] = mapped_column(Float, default=0.0, comment="多样性")
    duplicate: Mapped[float] = mapped_column(Float, default=0.0, comment="重复比例")
    risk: Mapped[float] = mapped_column(Float, default=0.0, comment="高风险比例")
    score: Mapped[float] = mapped_column(Float, default=0.0, comment="综合 0-100")
    suggestions: Mapped[str] = mapped_column(Text, default="[]", comment="修改建议 JSON")
