from __future__ import annotations
from typing import Literal, Optional, List
from pydantic import BaseModel, ConfigDict, Field


class KPCreate(BaseModel):
    course_id: int
    chapter_id: Optional[int] = None
    name: str = Field(min_length=1, max_length=128)
    description: str = Field(default="", max_length=20_000)
    difficulty: int = Field(default=3, ge=1, le=5)
    importance: float = Field(default=0.5, ge=0, le=1)
    keywords: str = Field(default="", max_length=256)


class KPOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    course_id: int
    chapter_id: Optional[int]
    name: str
    description: str
    difficulty: int
    importance: float
    keywords: str

class RelationCreate(BaseModel):
    course_id: int
    source_id: int
    target_id: int
    relation: Literal["prerequisite", "相似", "易混"] = "prerequisite"
    weight: float = Field(default=1.0, ge=0, le=1)


class RelationOut(RelationCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int


class GraphOut(BaseModel):
    nodes: List[dict]
    edges: List[dict]


class MindMapOut(BaseModel):
    mermaid: str
    nodes: List[dict]
