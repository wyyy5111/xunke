from __future__ import annotations
from datetime import datetime
from typing import Optional, Any, List, Literal
from pydantic import BaseModel, ConfigDict


class RunWorkflowIn(BaseModel):
    course_id: int
    student_id: Optional[int] = None
    workflow: Literal["full_pipeline"] = "full_pipeline"


class AgentLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    run_id: int
    trace_id: str
    agent: str
    step: int
    status: str
    input_summary: Any
    output_summary: Any
    duration_ms: int
    error: str
    created_at: datetime

class AgentRunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    trace_id: str
    student_id: Optional[int]
    course_id: Optional[int]
    workflow: str
    status: str
    started_at: datetime
    finished_at: Optional[datetime]
    duration_ms: int
    progress: float
    input_summary: Any
    output_summary: Any
    error: str
    logs: List[AgentLogOut] = []
