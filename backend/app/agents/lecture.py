"""5. LectureAgent：生成个性化讲义（也承担错题复盘/补救资源生成）。"""
from __future__ import annotations
import json
from typing import Any

from app.agents.base import BaseAgent
from app.models.course import Course
from app.models.knowledge import KnowledgePoint
from app.models.profile import StudentProfile
from app.models.resource import GeneratedResource
from app.rag.retriever import retrieve, format_citations
from app.services import quality_service
from app.services.llm_client import llm_client
from app.agents.prompts import COMMON_SYSTEM, lecture_prompt


class LectureAgent(BaseAgent):
    name = "LectureAgent"
    purpose = "lecture"

    def handle(self, input_summary: Any) -> dict:
        course_id = input_summary["course_id"]
        kp_id = input_summary.get("kp_id")
        student_id = input_summary.get("student_id")
        personalized = input_summary.get("personalized", False)
        force_rtype = input_summary.get("force_rtype")  # wrong_review / remedial

        kp = self.db.get(KnowledgePoint, kp_id) if kp_id else None
        course = self.db.get(Course, course_id)
        if not kp:
            kp = self.db.query(KnowledgePoint).filter(
                KnowledgePoint.course_id == course_id
            ).order_by(KnowledgePoint.id).first()
        topic = kp.name if kp else (course.name if course else "课程核心知识")
        course_name = course.name if course else "当前课程"
        profile = None
        if student_id:
            profile = self.db.query(StudentProfile).filter(
                StudentProfile.student_id == student_id, StudentProfile.course_id == course_id).first()

        # RAG 检索
        cites_raw = retrieve(self.db, course_id, topic, top_k=5)
        cites = format_citations(cites_raw)
        context = "\n".join([c["snippet"] for c in cites[:3]])

        profile_data = {
            "level": profile.base_level if profile else "未诊断",
            "preferred_style": profile.pref_style if profile else "结构化讲解",
            "preferred_format": profile.pref_format if profile else "文字,图解,案例",
            "learning_speed": profile.learning_speed if profile else "normal",
            "weak_points": json.loads(profile.weak_points or "[]")[:8] if profile else [],
        }

        # 按 force_rtype 决定 prompt 与标题
        if force_rtype == "wrong_review":
            system = COMMON_SYSTEM + "\n当前职责：高校课程错题复盘。不得编造错题数量。"
            prompt = (f"课程名称：{course_name}\n知识点：{topic}\n学生画像：{json.dumps(profile_data, ensure_ascii=False)}\n"
                      f"<course_context>{context}</course_context>\n"
                      "生成 Markdown 错题复盘：错因分类、证据回看、纠错步骤、变式练习与达标检查。")
            title = f"{topic} · 错题复盘"
            rtype = "wrong_review"
            purpose = "wrong_review"
        elif force_rtype == "remedial":
            system = COMMON_SYSTEM + "\n当前职责：高校课程补救教学。采用更短、更清晰的二次讲解。"
            prompt = (f"课程名称：{course_name}\n知识点：{topic}\n学生画像：{json.dumps(profile_data, ensure_ascii=False)}\n"
                      f"<course_context>{context}</course_context>\n"
                      "生成 Markdown 补救资源包：一句话框架、分步讲解、记忆卡、变式题、15分钟计划、达标检查。")
            title = f"{topic} · 补救资源包"
            rtype = "remedial"
            purpose = "remedial"
        else:
            system, prompt = lecture_prompt(course_name, topic, profile_data, cites)
            title = f"{topic} · 讲义"
            rtype = "lecture"
            purpose = self.purpose

        content = llm_client.chat(prompt, system=system, purpose=purpose,
                                  trace_id=self.trace_id, max_tokens=3200)
        call = llm_client.last_call_info

        res = GeneratedResource(course_id=course_id, student_id=student_id if personalized else None,
                                kp_id=kp.id if kp else kp_id, rtype=rtype, title=title,
                                content=content, citations=json.dumps(cites, ensure_ascii=False),
                                extra=json.dumps({
                                    "generation_mode": call.get("mode"),
                                    "fallback_used": call.get("fallback_used", False),
                                    "warning": "真实 AI 服务调用失败，当前使用本地结果" if call.get("fallback_used") else "",
                                    "trace_id": self.trace_id,
                                }, ensure_ascii=False),
                                is_personalized=personalized, agent_run_id=self.run.id)
        self.db.add(res)
        self.db.commit()

        kps = self.db.query(KnowledgePoint).filter(KnowledgePoint.course_id == course_id).all()
        rep = quality_service.score_resource(self.db, res, kps, cites, course_id)
        return {"resource_id": res.id, "quality": rep.score, "citations": len(cites), "rtype": rtype,
                "generation_mode": call.get("mode"), "fallback_used": call.get("fallback_used", False)}
