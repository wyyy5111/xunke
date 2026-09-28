from __future__ import annotations
from typing import Optional, List, Any, Literal
from pydantic import BaseModel, ConfigDict, Field


class ProfileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    student_id: int
    course_id: int
    stage: str
    goal: str
    weekly_hours: int
    base_level: str
    pref_format: str
    pref_style: str
    learning_speed: str
    pre_score: float
    post_score: float
    weak_points: Any
    recommendation: str
    extra: Any

class MasteryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    kp_id: int
    name: str
    mastery_score: float
    status: str
    pre_score: float
    post_score: float

class PathProgressIn(BaseModel):
    kp_id: int
    status: Literal["pending", "learning", "done"] = "done"
    duration: int = Field(default=0, ge=0, le=24 * 60 * 60)
    resource_id: Optional[int] = None


class LearningRecordIn(BaseModel):
    action: Literal["view", "finish", "practice", "answer"]
    duration: int = Field(default=0, ge=0, le=24 * 60 * 60)
    resource_id: Optional[int] = None
    kp_id: Optional[int] = None
