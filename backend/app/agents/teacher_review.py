"""10. TeacherReviewAgent：为教师审核提供 AI 预审建议（不替代人工）。"""
from __future__ import annotations
import json
from typing import Any

from app.agents.base import BaseAgent
from app.models.resource import GeneratedResource
from app.services.llm_client import llm_client
from app.agents.prompts import teacher_review_prompt
from app.models.quality import QualityReport


class TeacherReviewAgent(BaseAgent):
    name = "TeacherReviewAgent"
    purpose = "teacher_review"

    def handle(self, input_summary: Any) -> dict:
        resource_ids = input_summary.get("resource_ids", [])
        suggestions = []
        for rid in resource_ids:
            r = self.db.get(GeneratedResource, rid)
            if not r:
                continue
            quality = self.db.query(QualityReport).filter(QualityReport.resource_id == rid).first()
            quality_data = {
                "score": r.quality_score,
                "coverage": quality.coverage if quality else 0,
                "citation_hit": quality.citation_hit if quality else 0,
                "answer_consistency": quality.answer_consistency if quality else 0,
                "difficulty_match": quality.difficulty_match if quality else 0,
                "suggestions": json.loads(quality.suggestions or "[]") if quality else [],
            }
            cites = json.loads(r.citations or "[]")
            system, prompt = teacher_review_prompt(
                {"id": r.id, "type": r.rtype, "title": r.title, "content": r.content},
                quality_data,
                cites,
            )
            review = llm_client.chat_json(prompt, system=system, purpose=self.purpose,
                                          trace_id=self.trace_id, max_tokens=1400)
            decision = review.get("decision") or ("risk" if r.quality_score < 70 else "needs_edit")
            if decision == "risk":
                r.review_status = "risk"
            elif r.review_status not in {"risk", "rejected"}:
                r.review_status = "pending"
            extra = json.loads(r.extra or "{}")
            extra["teacher_review_suggestion"] = review
            extra["teacher_review_trace_id"] = self.trace_id
            r.extra = json.dumps(extra, ensure_ascii=False)
            suggestions.append({"resource_id": rid, "label": decision,
                                "advice": review.get("summary") or "请教师核对引用与内容后决定是否发布。",
                                "checklist": review.get("checklist") or [],
                                "revision_suggestions": review.get("revision_suggestions") or []})
        self.db.commit()
        return {"suggestions": suggestions, "reviewed": len(suggestions),
                "citations": sum(len(json.loads((self.db.get(GeneratedResource, rid).citations or "[]")))
                                 for rid in resource_ids if self.db.get(GeneratedResource, rid))}
