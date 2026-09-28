from __future__ import annotations
from datetime import datetime
from typing import Literal, Optional
from pydantic import BaseModel, ConfigDict, Field


class CourseCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    code: str = Field(default="", max_length=64)
    description: str = Field(default="", max_length=20_000)
    cover: str = Field(default="", max_length=256)
    tags: str = Field(default="", max_length=256)


class CourseUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=128)
    code: Optional[str] = Field(default=None, max_length=64)
    description: Optional[str] = Field(default=None, max_length=20_000)
    cover: Optional[str] = Field(default=None, max_length=256)
    tags: Optional[str] = Field(default=None, max_length=256)
    status: Optional[Literal["active", "archived"]] = None


class CourseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    code: str
    description: str
    cover: str
    teacher_id: int
    status: str
    tags: str
    created_at: datetime

class ChapterCreate(BaseModel):
    title: str = Field(min_length=1, max_length=128)
    summary: str = Field(default="", max_length=10_000)
    order_index: int = Field(default=0, ge=0, le=10_000)


class ChapterOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    course_id: int
    title: str
    summary: str
    order_index: int

class FileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    course_id: int
    filename: str
    file_type: str
    size: int
    parse_status: str
    parse_summary: str
    indexed: bool
    created_at: datetime

class EnrollIn(BaseModel):
    course_id: int
    goal: str = Field(default="", max_length=256)
    weekly_hours: int = Field(default=6, ge=1, le=80)
