"""8. MultimodalResourceAgent：PPT 大纲、视频脚本、实验任务、拓展阅读。"""
from __future__ import annotations
import json
from typing import Any

from app.agents.base import BaseAgent
from app.models.course import Course
from app.models.knowledge import KnowledgePoint
from app.models.resource import GeneratedResource
from app.rag.retriever import retrieve, format_citations
from app.services.llm_client import llm_client
from app.agents.prompts import multimodal_prompt
from app.services import quality_service


class MultimodalResourceAgent(BaseAgent):
    name = "MultimodalResourceAgent"
    purpose = "multimodal"

    def handle(self, input_summary: Any) -> dict:
        course_id = input_summary["course_id"]
        requested_types = input_summary.get("rtypes") or [input_summary.get("rtype", "ppt")]
        requested_types = [rtype for rtype in requested_types if rtype in {"ppt", "video", "experiment", "reading"}]
        if not requested_types:
            requested_types = ["ppt"]
        kp_id = input_summary.get("kp_id")
        kp = self.db.get(KnowledgePoint, kp_id) if kp_id else None
        course = self.db.get(Course, course_id)
        if not kp:
            kp = self.db.query(KnowledgePoint).filter(
                KnowledgePoint.course_id == course_id
            ).order_by(KnowledgePoint.id).first()
        topic = kp.name if kp else (course.name if course else "课程核心知识")
        course_name = course.name if course else "当前课程"

        cites_raw = retrieve(self.db, course_id, topic, top_k=3)
        cites = format_citations(cites_raw)
        context = "\n".join(c["snippet"] for c in cites[:2])

        titles = {"ppt": "PPT 大纲", "video": "视频脚本", "experiment": "实验任务", "reading": "拓展阅读"}
        kps = self.db.query(KnowledgePoint).filter(KnowledgePoint.course_id == course_id).all()
        resource_ids = []
        scores = []
        for rtype in requested_types:
            system, prompt = multimodal_prompt(rtype, course_name, topic, cites)
            content = llm_client.chat(prompt, system=system, purpose=f"{self.purpose}_{rtype}",
                                      trace_id=self.trace_id, max_tokens=2600)
            call = llm_client.last_call_info
            res = GeneratedResource(course_id=course_id, kp_id=kp.id if kp else kp_id, rtype=rtype,
                                    title=f"{topic} · {titles.get(rtype, rtype)}",
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
            resource_ids.append(res.id)
            scores.append(rep.score)
        return {
            "resource_id": resource_ids[0] if len(resource_ids) == 1 else None,
            "resource_ids": resource_ids,
            "rtypes": requested_types,
            "quality": round(sum(scores) / max(1, len(scores)), 1),
            "citations": len(cites),
        }
