"""资源生成 / 列表 / 详情 / 流式讲义。"""
from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import any_role, teacher_or_admin
from app.models.course import Course, CourseEnrollment
from app.models.knowledge import KnowledgePoint
from app.models.profile import StudentProfile
from app.models.resource import GeneratedResource
from app.models.user import User
from app.agents.orchestrator import run_generate_only
from app.rag.retriever import (
    current_course_citations,
    current_resource_citations,
    retrieve,
    format_citations,
)
from app.services.llm_client import llm_client
from app.services import learning_path_service
from app.agents.prompts import lecture_prompt
from app.schemas.resource import GenerateResourceIn
from app.schemas.common import R
from app.utils.time_util import safe_json_loads

router = APIRouter(prefix="/api/resources", tags=["resource"])


@router.get("", response_model=R)
def list_res(course_id: int, rtype: str = "", student_id: int = 0,
             status: str = "", db: Session = Depends(get_db),
             user: User = Depends(any_role)):
    _accessible_course(db, course_id, user)
    q = db.query(GeneratedResource).filter(GeneratedResource.course_id == course_id)
    if rtype:
        q = q.filter(GeneratedResource.rtype == rtype)
    if user.role == "student":
        q = q.filter(
            GeneratedResource.published == True,
            or_(GeneratedResource.student_id.is_(None), GeneratedResource.student_id == user.id),
        )
    elif student_id:
        q = q.filter(GeneratedResource.student_id == student_id)
    if status:
        q = q.filter(GeneratedResource.review_status == status)
    rows = q.order_by(GeneratedResource.id.desc()).limit(200).all()
    citation_map = current_resource_citations(db, rows)
    return R.ok([_out(r, citation_map.get(r.id, [])) for r in rows])


@router.post("/generate", response_model=R)
def generate(body: GenerateResourceIn, db: Session = Depends(get_db),
             user: User = Depends(any_role)):
    course = _accessible_course(db, body.course_id, user)
    if course.status != "active":
        raise HTTPException(409, "课程已归档，不能生成新的学习资源")
    if body.kp_id is not None:
        kp = db.get(KnowledgePoint, body.kp_id)
        if not kp or kp.course_id != body.course_id:
            raise HTTPException(400, "知识点不存在或不属于当前课程")
    sid = user.id if user.role == "student" else body.student_id
    if body.rtype in {"wrong_review", "remedial"} and sid is None:
        raise HTTPException(400, "错题复盘和补救资源必须指定目标学生")
    if sid is not None:
        student = db.get(User, sid)
        if not student or student.role != "student":
            raise HTTPException(400, "个性化资源的学生账号不存在")
        if not db.query(CourseEnrollment).filter(
            CourseEnrollment.course_id == body.course_id,
            CourseEnrollment.student_id == sid,
        ).first():
            raise HTTPException(400, "该学生尚未加入课程")
    run = run_generate_only(db, body.course_id, body.rtype, body.kp_id, sid)
    if run.status != "success":
        raise HTTPException(502, f"资源生成失败：{run.error or '请稍后重试'}")
    return R.ok({"trace_id": run.trace_id, "run_id": run.id, "status": run.status,
                 "summary": safe_json_loads(run.output_summary, {})})


@router.get("/lecture/stream", response_model=None)
def stream_lecture(course_id: int, kp_id: int = 0, db: Session = Depends(get_db),
                   user: User = Depends(teacher_or_admin)):
    """教师端未发布讲义预览；学生只能读取审核发布后的资源。"""
    course = _accessible_course(db, course_id, user)
    if course.status != "active":
        raise HTTPException(409, "课程已归档，不能生成新的流式讲义")
    kp = db.get(KnowledgePoint, kp_id) if kp_id else None
    if kp and kp.course_id != course_id:
        raise HTTPException(400, "知识点不属于当前课程")
    if not kp:
        kp = (db.query(KnowledgePoint)
              .filter(KnowledgePoint.course_id == course_id)
              .order_by(KnowledgePoint.id.asc())
              .first())
    topic = kp.name if kp else "课程核心知识点"
    cites_raw = retrieve(db, course_id, topic, top_k=3)
    cites = format_citations(cites_raw)
    profile = db.query(StudentProfile).filter(
        StudentProfile.course_id == course_id,
        StudentProfile.student_id == user.id,
    ).first() if user.role == "student" else None
    profile_data = {
        "level": profile.base_level if profile else "未诊断",
        "preferred_style": profile.pref_style if profile else "结构化讲解",
        "preferred_format": profile.pref_format if profile else "文字,图解,案例",
        "learning_speed": profile.learning_speed if profile else "normal",
    }
    system_prompt, prompt = lecture_prompt(course.name, topic, profile_data, cites)

    def gen():
        for chunk in llm_client.stream(prompt, system=system_prompt, purpose="lecture_stream"):
            yield chunk
        yield "\n\n---\n引用：\n" + "\n".join(f"[{c['id']}] {c['source']} p.{c['page']}" for c in cites)

    return StreamingResponse(gen(), media_type="text/plain; charset=utf-8")


@router.get("/{rid}", response_model=R)
def detail(rid: int, db: Session = Depends(get_db),
           user: User = Depends(any_role)):
    r = db.get(GeneratedResource, rid)
    if not r:
        raise HTTPException(404, "资源不存在")
    _accessible_course(db, r.course_id, user)
    if user.role == "student":
        if not r.published or r.student_id not in (None, user.id):
            raise HTTPException(403, "资源尚未发布或不属于当前学生")
        try:
            learning_path_service.add_learning_record(
                db, user.id, r.course_id, action="view",
                resource_id=r.id, kp_id=r.kp_id,
            )
        except ValueError:
            db.rollback()
    return R.ok(_out(r, current_course_citations(db, r.course_id, r.citations)))


def _out(r: GeneratedResource, citations: list[dict]) -> dict:
    return {
        "id": r.id, "course_id": r.course_id, "student_id": r.student_id, "kp_id": r.kp_id,
        "rtype": r.rtype, "title": r.title, "content": r.content,
        "citations": citations,
        "quality_score": r.quality_score,
        "review_status": r.review_status, "published": r.published,
        "is_personalized": r.is_personalized,
        "extra": safe_json_loads(r.extra, {}),
        "created_at": r.created_at.isoformat() if r.created_at else "",
    }


def _accessible_course(db: Session, course_id: int, user: User) -> Course:
    course = db.get(Course, course_id)
    if not course:
        raise HTTPException(404, "课程不存在")
    if user.role == "admin":
        return course
    if user.role == "teacher":
        if course.teacher_id != user.id:
            raise HTTPException(403, "无权访问其他教师的课程资源")
        return course
    enrollment = db.query(CourseEnrollment).filter(
        CourseEnrollment.course_id == course_id,
        CourseEnrollment.student_id == user.id,
    ).first()
    if not enrollment:
        raise HTTPException(403, "请先加入该课程")
    return course
