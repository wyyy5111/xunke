from __future__ import annotations
from datetime import datetime
from typing import Optional, Any, List, Literal
from pydantic import BaseModel, ConfigDict


class ResourceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    course_id: int
    student_id: Optional[int]
    kp_id: Optional[int]
    rtype: str
    title: str
    content: str
    citations: Any
    quality_score: float
    review_status: str
    published: bool
    is_personalized: bool
    created_at: datetime

class GenerateResourceIn(BaseModel):
    course_id: int
    rtype: Literal["lecture", "mindmap", "exercise", "experiment", "reading", "ppt", "video", "wrong_review", "remedial"]
    kp_id: Optional[int] = None
    student_id: Optional[int] = None
    personalized: bool = False


class ReviewIn(BaseModel):
    decision: Literal["approved", "rejected", "risk", "needs_edit"]
    comment: str = ""
    revised_content: str = ""
