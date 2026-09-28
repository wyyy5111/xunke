"""ORM 公共基类：统一 id / 时间戳。"""
from datetime import datetime
from sqlalchemy import Integer, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class PkMixin:
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
