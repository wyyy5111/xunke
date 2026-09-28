"""9. QualityCheckAgent：对工作流产物做质量校验。"""
from __future__ import annotations
import json
from typing import Any

from app.agents.base import BaseAgent
from app.models.knowledge import KnowledgePoint
from app.models.resource import GeneratedResource
from app.services import quality_service
from app.services.llm_client import llm_client
from app.agents.prompts import quality_prompt


class QualityCheckAgent(BaseAgent):
    name = "QualityCheckAgent"
    purpose = "quality_check"

    def handle(self, input_summary: Any) -> dict:
        course_id = input_summary.get("course_id")
        resource_ids = input_summary.get("resource_ids", [])
        kps = self.db.query(KnowledgePoint).filter(KnowledgePoint.course_id == course_id).all()
        results = []
        for rid in resource_ids:
            r = self.db.get(GeneratedResource, rid)
            if not r:
                continue
            cites = json.loads(r.citations or "[]")
            rep = quality_service.score_resource(self.db, r, kps, cites, course_id)
            system, prompt = quality_prompt(
                {"id": r.id, "type": r.rtype, "title": r.title, "content": r.content,
                 "heuristic_score": rep.score,
                 # In Mock mode the local evaluator mirrors these persisted,
                 # deterministic measurements instead of inventing a fixed
                 # model score. In real mode they remain useful evaluation
                 # evidence for the remote quality reviewer.
                 "coverage": round(rep.coverage * 100, 1),
                 "citation_hit": round(rep.citation_hit * 100, 1),
                 "answer_consistency": round(rep.answer_consistency * 100, 1),
                 "difficulty_match": round(rep.difficulty_match * 100, 1),
                 "structure": round(rep.structure * 100, 1),
                 "duplicate": round(rep.duplicate * 100, 1),
                 "risk": round(rep.risk * 100, 1)},
                cites,
                [kp.name for kp in kps],
            )
            ai_check = llm_client.chat_json(prompt, system=system, purpose=self.purpose,
                                            trace_id=self.trace_id, max_tokens=1600)
            ai_score = ai_check.get("score")
            if isinstance(ai_score, (int, float)):
                rep.score = round(rep.score * 0.55 + max(0, min(float(ai_score), 100)) * 0.45, 1)
                r.quality_score = rep.score
            suggestions = json.loads(rep.suggestions or "[]")
            suggestions.extend(str(x) for x in (ai_check.get("suggestions") or []) if str(x).strip())
            rep.suggestions = json.dumps(list(dict.fromkeys(suggestions))[:10], ensure_ascii=False)
            extra = json.loads(r.extra or "{}")
            extra["quality_check"] = {
                "score": rep.score,
                "publishable": ai_check.get("publishable"),
                "checks": ai_check.get("checks") or {},
                "risks": ai_check.get("risks") or [],
                "suggestions": list(dict.fromkeys(suggestions))[:10],
                "trace_id": self.trace_id,
                "mode": llm_client.last_call_info.get("mode"),
            }
            r.extra = json.dumps(extra, ensure_ascii=False)
            # 标风险
            if rep.risk > 0 or rep.score < 70 or ai_check.get("publishable") is False:
                r.review_status = "risk"
            elif r.review_status == "risk":
                r.review_status = "pending"
            results.append({"resource_id": rid, "score": rep.score, "risk": rep.risk,
                            "publishable": ai_check.get("publishable"),
                            "suggestions": suggestions[:5]})
        self.db.commit()
        avg = round(sum(x["score"] for x in results) / max(1, len(results)), 1) if results else 0
        return {"checked": len(results), "avg_score": avg, "details": results,
                "citations": sum(len(json.loads((self.db.get(GeneratedResource, rid).citations or "[]")))
                                 for rid in resource_ids if self.db.get(GeneratedResource, rid))}
