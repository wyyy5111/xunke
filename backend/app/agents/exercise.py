"""7. ExerciseAgent：生成分层练习题并入库。"""
from __future__ import annotations
import json
from typing import Any

from app.agents.base import BaseAgent
from app.models.course import Course
from app.models.question import Question, QuestionOption
from app.models.knowledge import KnowledgePoint
from app.models.profile import StudentProfile
from app.models.resource import GeneratedResource
from app.rag.retriever import retrieve, format_citations
from app.services.llm_client import llm_client
from app.agents.prompts import exercise_prompt
from app.services import quality_service


class ExerciseAgent(BaseAgent):
    name = "ExerciseAgent"
    purpose = "exercise"

    def handle(self, input_summary: Any) -> dict:
        course_id = input_summary["course_id"]
        kp_id = input_summary.get("kp_id")
        student_id = input_summary.get("student_id")

        kp = self.db.get(KnowledgePoint, kp_id) if kp_id else None
        course = self.db.get(Course, course_id)
        if not kp:
            kp = self.db.query(KnowledgePoint).filter(
                KnowledgePoint.course_id == course_id
            ).order_by(KnowledgePoint.id).first()
        topic = kp.name if kp else (course.name if course else "课程核心知识")
        course_name = course.name if course else "当前课程"
        difficulty = 3
        if student_id:
            prof = self.db.query(StudentProfile).filter(
                StudentProfile.student_id == student_id, StudentProfile.course_id == course_id).first()
            if prof:
                difficulty = {"basic": 2, "intermediate": 3, "advanced": 4}.get(prof.base_level, 3)

        cites_raw = retrieve(self.db, course_id, topic, top_k=3)
        cites = format_citations(cites_raw)
        context = "\n".join(c["snippet"] for c in cites[:2])

        system, prompt = exercise_prompt(course_name, topic, difficulty, cites)
        data = llm_client.chat_json(prompt, system=system, purpose=self.purpose,
                                    trace_id=self.trace_id, max_tokens=2600)
        call = llm_client.last_call_info
        questions = self._valid_questions(data.get("questions") or [], topic, difficulty)
        data = {"questions": questions}

        # Create the reviewable resource first so every generated question can
        # be tied to its publication state and, for personalized runs, owner.
        res = GeneratedResource(
            course_id=course_id,
            student_id=student_id,
            kp_id=kp.id if kp else kp_id,
            rtype="exercise",
            title=f"{topic} · 练习题",
            content=json.dumps(data, ensure_ascii=False),
            citations=json.dumps(cites, ensure_ascii=False),
            extra=json.dumps({
                "generation_mode": call.get("mode"),
                "fallback_used": call.get("fallback_used", False),
                "warning": "真实 AI 服务调用失败，当前使用本地结果" if call.get("fallback_used") else "",
                "trace_id": self.trace_id,
            }, ensure_ascii=False),
            agent_run_id=self.run.id,
            is_personalized=bool(student_id),
        )
        self.db.add(res)
        self.db.flush()

        qids = []
        for q in questions:
            target_kp_id = kp.id if kp else kp_id
            qobj = Question(course_id=course_id, kp_id=target_kp_id, qtype=q.get("qtype", "single"),
                            stem=q.get("stem", ""), answer=q.get("answer", ""),
                            analysis=q.get("analysis", ""), difficulty=q.get("difficulty", difficulty),
                            tags=topic, source="ai", ai_resource_id=res.id,
                            citations=json.dumps(cites, ensure_ascii=False))
            self.db.add(qobj)
            self.db.flush()
            qids.append(qobj.id)
            for opt in q.get("options", []):
                self.db.add(QuestionOption(question_id=qobj.id, key=opt.get("key", "A"),
                                            content=opt.get("content", ""),
                                            is_correct=opt.get("is_correct", False)))
        self.db.commit()
        kps = self.db.query(KnowledgePoint).filter(KnowledgePoint.course_id == course_id).all()
        rep = quality_service.score_resource(self.db, res, kps, cites, course_id)
        return {"resource_id": res.id, "questions": len(qids), "qids": qids,
                "quality": rep.score, "citations": len(cites)}

    @staticmethod
    def _valid_questions(items: list[dict], topic: str, default_difficulty: int) -> list[dict]:
        valid = []
        allowed = {"single", "multiple", "judge", "fill", "short"}
        for item in items[:8]:
            stem = str(item.get("stem") or "").strip()
            answer = str(item.get("answer") or "").strip()
            analysis = str(item.get("analysis") or "").strip()
            qtype = str(item.get("qtype") or "single").strip()
            if not stem or not answer or not analysis or qtype not in allowed:
                continue
            options = item.get("options") if isinstance(item.get("options"), list) else []
            if qtype == "single":
                keys = {str(opt.get("key") or "") for opt in options}
                if answer not in keys or len(options) < 2:
                    continue
            valid.append({
                **item,
                "qtype": qtype,
                "stem": stem,
                "answer": answer,
                "analysis": analysis,
                "options": options,
                "knowledge_point": item.get("knowledge_point") or topic,
                "wrong_reason": item.get("wrong_reason") or "请对照解析检查概念、证据与推理过程。",
                "difficulty": max(1, min(int(item.get("difficulty") or default_difficulty), 5)),
            })
        if not valid:
            raise ValueError("练习题结构校验失败，未生成可保存的题目")
        return valid
