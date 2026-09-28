"""通用响应 schema。"""
from __future__ import annotations
from typing import Any, Generic, TypeVar, Optional, List
from pydantic import BaseModel

T = TypeVar("T")


class R(BaseModel):
    """统一响应包装。"""
    code: int = 0
    msg: str = "ok"
    data: Any | None = None

    @classmethod
    def ok(cls, data: Any = None, msg: str = "ok") -> "R":
        return cls(code=0, msg=msg, data=data)

    @classmethod
    def fail(cls, msg: str = "fail", code: int = -1, data: Any = None) -> "R":
        return cls(code=code, msg=msg, data=data)


class Page(BaseModel, Generic[T]):
    items: List[T]
    total: int
    page: int
    page_size: int


class IdOut(BaseModel):
    id: int


class StrOut(BaseModel):
    value: str
