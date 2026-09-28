"""系统配置与 LLM 调用日志。"""
from datetime import datetime
from sqlalchemy import String, Text, Integer, Float, DateTime, Boolean
from sqlalchemy.orm import Mapped, mapped_column
from typing import Optional

from app.models._base import PkMixin, TimestampMixin
from app.core.database import Base


class SystemConfig(Base, PkMixin, TimestampMixin):
    __tablename__ = "system_configs"
    key: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    value: Mapped[str] = mapped_column(Text, default="")
    category: Mapped[str] = mapped_column(String(32), default="llm", comment="llm/retrieval/general")
    remark: Mapped[str] = mapped_column(String(256), default="")


class LLMCallLog(Base, PkMixin, TimestampMixin):
    __tablename__ = "llm_call_logs"
    provider: Mapped[str] = mapped_column(String(32), index=True)
    model: Mapped[str] = mapped_column(String(64))
    purpose: Mapped[str] = mapped_column(String(64), default="", comment="调用目的")
    trace_id: Mapped[str] = mapped_column(String(64), default="", index=True)
    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    response_chars: Mapped[int] = mapped_column(Integer, default=0)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    fallback_used: Mapped[bool] = mapped_column(Boolean, default=False)
    estimated_cost: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True, comment="预估调用成本；无可靠价格口径时为空"
    )
    success: Mapped[bool] = mapped_column(Boolean, default=True)
    error: Mapped[str] = mapped_column(Text, default="")
