"""2. KnowledgeGraphAgent：构建领域无关的知识点关系。"""
from __future__ import annotations
from typing import Any
from app.agents.base import BaseAgent
from app.agents.prompts import knowledge_graph_prompt
from app.models.course import Course
from app.models.knowledge import KnowledgePoint, KnowledgeRelation
from app.services.llm_client import llm_client


class KnowledgeGraphAgent(BaseAgent):
    name = "KnowledgeGraphAgent"
    purpose = "knowledge_graph"

    def handle(self, input_summary: Any) -> dict:
        course_id = input_summary.get("course_id")
        kps = self.db.query(KnowledgePoint).filter(KnowledgePoint.course_id == course_id).all()
        name_map = {kp.name: kp for kp in kps}
        course = self.db.get(Course, course_id)

        self.db.query(KnowledgeRelation).filter(KnowledgeRelation.course_id == course_id).delete()
        self.db.commit()

        system, prompt = knowledge_graph_prompt(
            course.name if course else "当前课程",
            [{"name": kp.name, "description": kp.description, "difficulty": kp.difficulty,
              "keywords": kp.keywords} for kp in kps[:60]],
        )
        data = llm_client.chat_json(prompt, system=system, purpose=self.purpose,
                                    trace_id=self.trace_id, max_tokens=2200)
        relation_map = {"prerequisite": "prerequisite", "related": "相似", "confusable": "易混"}
        seen: set[tuple[int, int, str]] = set()
        edges = 0
        for item in data.get("relations") or []:
            source = name_map.get(str(item.get("source") or "").strip())
            target = name_map.get(str(item.get("target") or "").strip())
            relation = relation_map.get(str(item.get("relation") or "").strip())
            if not source or not target or not relation or source.id == target.id:
                continue
            key = (source.id, target.id, relation)
            if key in seen:
                continue
            seen.add(key)
            self.db.add(KnowledgeRelation(course_id=course_id, source_id=source.id,
                                           target_id=target.id, relation=relation,
                                           weight=0.9 if relation == "prerequisite" else 0.65))
            edges += 1

        # Structured fallback: order low-difficulty concepts before adjacent higher-difficulty concepts.
        if not edges:
            ordered = sorted(kps, key=lambda kp: (kp.difficulty, -kp.importance, kp.id))
            for source, target in zip(ordered, ordered[1:]):
                self.db.add(KnowledgeRelation(course_id=course_id, source_id=source.id,
                                               target_id=target.id, relation="prerequisite", weight=0.7))
                edges += 1
        self.db.commit()
        return {"nodes": len(kps), "edges": edges, "summary": "已构建先修、关联与易混关系"}
