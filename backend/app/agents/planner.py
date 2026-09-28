"""4. PlannerAgent：根据画像 + 图谱规划学习路径。"""
from __future__ import annotations
from typing import Any
import json

from app.agents.base import BaseAgent
from app.services import learning_path_service


class PlannerAgent(BaseAgent):
    name = "PlannerAgent"
    purpose = "planner"

    def handle(self, input_summary: Any) -> dict:
        student_id = input_summary.get("student_id")
        course_id = input_summary.get("course_id")
        lp = learning_path_service.plan_path(self.db, student_id, course_id)
        nodes = json.loads(lp.nodes or "[]")
        return {"path_id": lp.id, "nodes": len(nodes), "total_minutes": lp.total_minutes,
                "first_node": nodes[0]["name"] if nodes else ""}
