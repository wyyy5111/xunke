"""Agent Orchestrator：编排完整工作流，并落 trace。

工作流：
上传资料 → 课程解析 → 知识图谱 → 学生前测(已存) → 学生诊断 → 学习路径规划
→ 讲义生成 → 思维导图 → 练习生成 → 多模态资源 → 质量校验 → 教师预审
"""
from __future__ import annotations
import uuid
import json
from typing import Optional

from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.agent import AgentRun, AgentLog
from app.models.course import CourseFile
from app.models.question import Question
from app.models.resource import GeneratedResource
from app.agents.base import BaseAgent
from app.agents.course_parser import CourseParserAgent
from app.agents.knowledge_graph import KnowledgeGraphAgent
from app.agents.diagnosis import DiagnosisAgent
from app.agents.planner import PlannerAgent
from app.agents.lecture import LectureAgent
from app.agents.mindmap import MindMapAgent
from app.agents.exercise import ExerciseAgent
from app.agents.multimodal import MultimodalResourceAgent
from app.agents.quality_check import QualityCheckAgent
from app.agents.teacher_review import TeacherReviewAgent
from app.utils.time_util import safe_json_dumps, utc_now
from app.utils.logger import logger
from app.utils.redaction import redact_sensitive
from app.core.config import settings


def _safe_error(exc: object) -> str:
    return redact_sensitive(
        exc,
        secrets=(settings.DEEPSEEK_API_KEY, settings.JWT_SECRET),
    )[:1000]


def _run_step(db: Session, run: AgentRun, trace_id: str, step: int, agent: BaseAgent, payload: dict) -> dict:
    return agent.run_agent(step, payload)


def run_full_pipeline(db: Session, course_id: int, student_id: Optional[int] = None,
                      file_id: Optional[int] = None, goal: str = "", weekly_hours: int = 6,
                      personalized_kp_id: Optional[int] = None) -> AgentRun:
    """同步执行完整流水线，主要用于测试和内部任务。"""
    run = create_full_pipeline_run(db, course_id, student_id, file_id)
    return execute_full_pipeline(db, run, goal, weekly_hours, personalized_kp_id, file_id)


def create_full_pipeline_run(db: Session, course_id: int, student_id: Optional[int] = None,
                             file_id: Optional[int] = None) -> AgentRun:
    """创建可被后台执行的工作流记录。"""
    trace_id = uuid.uuid4().hex[:16]
    run = AgentRun(trace_id=trace_id, student_id=student_id, course_id=course_id,
                   workflow="full_pipeline", status="running", started_at=utc_now(),
                   progress=0.0,
                   input_summary=safe_json_dumps({"course_id": course_id, "student_id": student_id,
                                                   "file_id": file_id}))
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


def execute_full_pipeline(db: Session, run: AgentRun, goal: str = "", weekly_hours: int = 6,
                          personalized_kp_id: Optional[int] = None,
                          file_id: Optional[int] = None) -> AgentRun:
    """Execute a pre-created run, committing progress after every agent."""
    trace_id = run.trace_id
    course_id = int(run.course_id or 0)
    student_id = run.student_id
    run.status = "running"
    run.started_at = run.started_at or utc_now()
    db.commit()

    output: dict = {"trace_id": trace_id}
    try:
        # 1. 解析（若有文件）
        if file_id:
            out = _run_step(db, run, trace_id, 1, CourseParserAgent(db, run, trace_id),
                            {"course_id": course_id, "file_id": file_id})
            output["parse"] = out
        else:
            output["parse"] = {"skipped": "no file"}

        # 2. 知识图谱
        out = _run_step(db, run, trace_id, 2, KnowledgeGraphAgent(db, run, trace_id),
                        {"course_id": course_id})
        output["graph"] = out

        # 3. 诊断（仅学生场景）
        if student_id:
            out = _run_step(db, run, trace_id, 3, DiagnosisAgent(db, run, trace_id),
                            {"student_id": student_id, "course_id": course_id, "goal": goal,
                             "weekly_hours": weekly_hours})
            output["diagnosis"] = out

            # 4. 学习路径
            out = _run_step(db, run, trace_id, 4, PlannerAgent(db, run, trace_id),
                            {"student_id": student_id, "course_id": course_id})
            output["planner"] = out

        # 5. 讲义生成（个性化 or 通用）
        lecture_payload = {"course_id": course_id, "kp_id": personalized_kp_id,
                           "student_id": student_id, "personalized": bool(student_id)}
        out = _run_step(db, run, trace_id, 5, LectureAgent(db, run, trace_id), lecture_payload)
        output["lecture"] = out
        resource_ids = [out["resource_id"]] if "resource_id" in out else []

        # 6. 思维导图
        out = _run_step(db, run, trace_id, 6, MindMapAgent(db, run, trace_id),
                        {"course_id": course_id})
        output["mindmap"] = out
        if "resource_id" in out:
            resource_ids.append(out["resource_id"])

        # 7. 练习
        out = _run_step(db, run, trace_id, 7, ExerciseAgent(db, run, trace_id),
                        {"course_id": course_id, "kp_id": personalized_kp_id, "student_id": student_id})
        output["exercise"] = out
        if "resource_id" in out:
            resource_ids.append(out["resource_id"])

        # 8. 多模态资源包（一个 Agent 节点，产出 PPT / 视频 / 实践任务）
        out = _run_step(db, run, trace_id, 8, MultimodalResourceAgent(db, run, trace_id),
                        {"course_id": course_id, "kp_id": personalized_kp_id,
                         "rtypes": ["ppt", "video", "experiment"]})
        mm_ids = out.get("resource_ids") or []
        resource_ids.extend(mm_ids)
        output["multimodal"] = out

        # 9. 质量校验
        out = _run_step(db, run, trace_id, 9, QualityCheckAgent(db, run, trace_id),
                        {"course_id": course_id, "resource_ids": resource_ids})
        output["quality"] = out

        # 10. 教师预审
        out = _run_step(db, run, trace_id, 10, TeacherReviewAgent(db, run, trace_id),
                        {"resource_ids": resource_ids})
        output["teacher_review"] = out

        run.status = "success"
        run.progress = 1.0
        run.output_summary = safe_json_dumps(output)
    except Exception as e:
        logger.exception(f"pipeline failed: {e}")
        db.rollback()
        run = db.get(AgentRun, run.id)
        run.status = "failed"
        run.error = _safe_error(e)
        run.output_summary = safe_json_dumps(output)
    finally:
        run.finished_at = utc_now()
        run.duration_ms = int((run.finished_at - run.started_at).total_seconds() * 1000)
        db.commit()
    return run


def execute_full_pipeline_task(run_id: int, goal: str = "", weekly_hours: int = 6,
                               personalized_kp_id: Optional[int] = None,
                               file_id: Optional[int] = None) -> None:
    """BackgroundTasks entrypoint with an isolated SQLAlchemy session."""
    db = SessionLocal()
    try:
        run = db.get(AgentRun, run_id)
        if not run:
            return
        execute_full_pipeline(db, run, goal, weekly_hours, personalized_kp_id, file_id)
    except Exception as exc:
        logger.exception("background pipeline failed run_id=%s: %s", run_id, exc)
        db.rollback()
        run = db.get(AgentRun, run_id)
        if run:
            run.status = "failed"
            run.error = _safe_error(exc)
            run.finished_at = utc_now()
            db.commit()
    finally:
        db.close()


def run_parse_only(db: Session, course_id: int, file_id: int) -> AgentRun:
    """单独执行课程解析（教师上传后调用）。"""
    trace_id = uuid.uuid4().hex[:16]
    run = AgentRun(trace_id=trace_id, course_id=course_id, workflow="parse",
                   status="running", started_at=utc_now())
    db.add(run)
    db.commit()
    try:
        agent = CourseParserAgent(db, run, trace_id)
        out = agent.run_agent(1, {"course_id": course_id, "file_id": file_id})
        run.output_summary = safe_json_dumps(out)
        run.status = "success"
    except Exception as e:
        db.rollback()
        run = db.get(AgentRun, run.id)
        run.status = "failed"
        run.error = _safe_error(e)
    finally:
        run.finished_at = utc_now()
        run.duration_ms = int((run.finished_at - run.started_at).total_seconds() * 1000)
        db.commit()
    return run


def run_generate_only(db: Session, course_id: int, rtype: str,
                      kp_id: Optional[int] = None, student_id: Optional[int] = None) -> AgentRun:
    """单独触发某类资源生成（资源中心 / 教师资源生成）。"""
    trace_id = uuid.uuid4().hex[:16]
    run = AgentRun(trace_id=trace_id, course_id=course_id, student_id=student_id,
                   workflow="generate", status="running", started_at=utc_now())
    db.add(run)
    db.commit()
    try:
        if rtype == "lecture":
            agent = LectureAgent(db, run, trace_id)
            out = agent.run_agent(1, {"course_id": course_id, "kp_id": kp_id,
                                      "student_id": student_id, "personalized": bool(student_id)})
        elif rtype == "mindmap":
            agent = MindMapAgent(db, run, trace_id)
            out = agent.run_agent(1, {"course_id": course_id})
        elif rtype == "exercise":
            agent = ExerciseAgent(db, run, trace_id)
            out = agent.run_agent(1, {"course_id": course_id, "kp_id": kp_id, "student_id": student_id})
        elif rtype in ("ppt", "video", "experiment", "reading"):
            agent = MultimodalResourceAgent(db, run, trace_id)
            out = agent.run_agent(1, {"course_id": course_id, "kp_id": kp_id, "rtype": rtype})
        elif rtype in ("wrong_review", "remedial"):
            # 错题复盘 / 补救资源：复用讲义生成器走补救模板
            agent = LectureAgent(db, run, trace_id)
            out = agent.run_agent(1, {"course_id": course_id, "kp_id": kp_id,
                                      "student_id": student_id, "personalized": bool(student_id),
                                      "force_rtype": rtype})
        else:
            raise ValueError(f"unknown rtype {rtype}")
        run.output_summary = safe_json_dumps(out)
        run.status = "success"
    except Exception as e:
        db.rollback()
        run = db.get(AgentRun, run.id)
        run.status = "failed"
        run.error = _safe_error(e)
    finally:
        run.finished_at = utc_now()
        run.duration_ms = int((run.finished_at - run.started_at).total_seconds() * 1000)
        db.commit()
    return run
