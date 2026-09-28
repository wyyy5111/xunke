"""智能体运行记录与日志（多智能体可观测）。"""
from datetime import datetime
from sqlalchemy import String, Text, Integer, Float, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from typing import Optional

from app.models._base import PkMixin, TimestampMixin
from app.core.database import Base


class AgentRun(Base, PkMixin, TimestampMixin):
    __tablename__ = "agent_runs"
    trace_id: Mapped[str] = mapped_column(String(64), index=True, comment="一次工作流唯一ID")
    student_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    course_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    workflow: Mapped[str] = mapped_column(String(64), default="full_pipeline",
                                          comment="full_pipeline/parse/diagnose/generate/single_test")
    status: Mapped[str] = mapped_column(String(16), default="running", comment="running/success/failed/pending_review")
    started_at: Mapped[datetime] = mapped_column(DateTime)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    progress: Mapped[float] = mapped_column(Float, default=0.0, comment="0-1")
    input_summary: Mapped[str] = mapped_column(Text, default="{}")
    output_summary: Mapped[str] = mapped_column(Text, default="{}")
    error: Mapped[str] = mapped_column(Text, default="")


class AgentLog(Base, PkMixin, TimestampMixin):
    __tablename__ = "agent_logs"
    run_id: Mapped[int] = mapped_column(Integer, ForeignKey("agent_runs.id"), index=True)
    trace_id: Mapped[str] = mapped_column(String(64), index=True)
    agent: Mapped[str] = mapped_column(String(64), index=True, comment="智能体名称")
    step: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(16), default="success", comment="success/failed/pending_review")
    input_summary: Mapped[str] = mapped_column(Text, default="{}")
    output_summary: Mapped[str] = mapped_column(Text, default="{}")
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    role_description: Mapped[str] = mapped_column(String(256), default="")
    model_provider: Mapped[str] = mapped_column(String(32), default="local")
    model_name: Mapped[str] = mapped_column(String(64), default="rule-engine")
    citation_count: Mapped[int] = mapped_column(Integer, default=0)
    quality_score: Mapped[float] = mapped_column(Float, default=0.0)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str] = mapped_column(Text, default="")
