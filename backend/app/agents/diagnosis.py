"""3. DiagnosisAgent：前测 -> 学生画像。"""
from __future__ import annotations
from typing import Any

from app.agents.base import BaseAgent
from app.services import profile_service


class DiagnosisAgent(BaseAgent):
    name = "DiagnosisAgent"
    purpose = "diagnosis"

    def handle(self, input_summary: Any) -> dict:
        student_id = input_summary.get("student_id")
        course_id = input_summary.get("course_id")
        goal = input_summary.get("goal", "")
        weekly_hours = input_summary.get("weekly_hours", 6)
        profile = profile_service.build_profile(
            self.db, student_id, course_id, goal, weekly_hours, trace_id=self.trace_id
        )
        return {"profile_id": profile.id, "pre_score": profile.pre_score,
                "base_level": profile.base_level, "weak_count": len(__import__("json").loads(profile.weak_points or "[]"))}
