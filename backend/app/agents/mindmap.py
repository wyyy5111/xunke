"""6. MindMapAgent：思维导图 / 知识图谱 Mermaid。"""
from __future__ import annotations
import json
from typing import Any

from app.agents.base import BaseAgent
from app.models.knowledge import KnowledgePoint, KnowledgeRelation
from app.models.resource import GeneratedResource
from app.rag.retriever import retrieve, format_citations
from app.models.course import Course
from app.services.llm_client import llm_client
from app.agents.prompts import mindmap_prompt
from app.services import quality_service


class MindMapAgent(BaseAgent):
    name = "MindMapAgent"
    purpose = "mindmap"

    def handle(self, input_summary: Any) -> dict:
        course_id = input_summary["course_id"]
        kps = self.db.query(KnowledgePoint).filter(KnowledgePoint.course_id == course_id).all()
        rels = self.db.query(KnowledgeRelation).filter(KnowledgeRelation.course_id == course_id).all()
        course = self.db.get(Course, course_id)

        # 生成 mermaid graph
        lines = ["graph LR"]
        for kp in kps:
            safe = f"K{kp.id}"
            lines.append(f'    {safe}["{kp.name}"]')
        for r in rels:
            ls = "-->"
            label = ""
            if r.relation == "prerequisite":
                ls = "-- 先修 -->"
            elif r.relation == "相似":
                ls = "-.- 相似 ->"
            elif r.relation == "易混":
                ls = "== 易混 =>"
            lines.append(f"    K{r.source_id} {ls} K{r.target_id}")
        mermaid = "\n".join(lines)

        topic = kps[0].name if kps else (course.name if course else "课程知识体系")
        cites = format_citations(retrieve(self.db, course_id, topic, top_k=4))
        system, prompt = mindmap_prompt(
            course.name if course else "当前课程",
            [{"name": kp.name, "description": kp.description, "difficulty": kp.difficulty} for kp in kps[:30]],
            cites,
        )
        mindmap = llm_client.chat(prompt, system=system, purpose=self.purpose,
                                  trace_id=self.trace_id, max_tokens=1600).strip()
        call = llm_client.last_call_info
        mindmap = mindmap.replace("```mermaid", "").replace("```", "").strip()
        if not mindmap.startswith("mindmap"):
            mindmap = "mindmap\n  root((%s))\n%s" % (
                course.name if course else "课程知识体系",
                "\n".join(f"    {kp.name}" for kp in kps[:20]),
            )

        content = f"# 知识图谱 / 思维导图\n\n## 知识关系图\n\n```mermaid\n{mermaid}\n```\n\n## 全局思维导图\n\n```mermaid\n{mindmap}\n```\n"
        res = GeneratedResource(course_id=course_id, rtype="mindmap",
                                title=f"{topic} 知识图谱",
                                content=content, citations=json.dumps(cites, ensure_ascii=False),
                                extra=json.dumps({
                                    "generation_mode": call.get("mode"),
                                    "fallback_used": call.get("fallback_used", False),
                                    "warning": "真实 AI 服务调用失败，当前使用本地结果" if call.get("fallback_used") else "",
                                    "trace_id": self.trace_id,
                                }, ensure_ascii=False),
                                agent_run_id=self.run.id)
        self.db.add(res)
        self.db.commit()
        rep = quality_service.score_resource(self.db, res, kps, cites, course_id)
        return {"resource_id": res.id, "nodes": len(kps), "edges": len(rels),
                "quality": rep.score, "citations": len(cites)}
