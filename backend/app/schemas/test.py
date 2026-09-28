from __future__ import annotations
from datetime import datetime
from typing import Optional, List, Any, Literal
from pydantic import BaseModel, Field


class GenerateTestIn(BaseModel):
    course_id: int
    count: int = 10
    difficulty: int = 3


class AnswerItem(BaseModel):
    question_id: int
    answer: str


class SubmitTestIn(BaseModel):
    course_id: int
    test_type: Literal["pre", "post"] = "pre"
    answers: List[AnswerItem] = Field(min_length=1)


class PracticeSubmitIn(BaseModel):
    course_id: int
    answers: List[AnswerItem] = Field(min_length=1)
    resource_id: Optional[int] = None
    duration: int = Field(default=0, ge=0, le=24 * 60 * 60)


class TestResultOut(BaseModel):
    test_id: int
    total: int
    correct: int
    score: float
    details: List[dict]
    diagnosis: Any = None


class CompareOut(BaseModel):
    pre_score: float
    post_score: float
    improvement: float
    by_kp: List[dict]
