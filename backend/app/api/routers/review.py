"""教师审核资源。"""
from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import teacher_or_admin
from app.models.course import Course
from app.models.resource import GeneratedResource, ResourceReview
from app.models.user import User
from app.schemas.resource import ReviewIn
from app.schemas.common import R
from app.rag.retriever import current_resource_citations

router = APIRouter(prefix="/api/review", tags=["review"])


@router.get("/pending", response_model=R)
def pending(course_id: int, db: Session = Depends(get_db),
            user: User = Depends(teacher_or_admin)):
    _managed_course(db, course_id, user)
    rows = db.query(GeneratedResource).filter(
        GeneratedResource.course_id == course_id,
        GeneratedResource.review_status.in_(["pending", "risk"]),
    ).order_by(GeneratedResource.id.desc()).all()
    citation_map = current_resource_citations(db, rows)
    return R.ok([_out(r, citation_map.get(r.id, [])) for r in rows])


@router.post("/{rid}", response_model=R)
def review(rid: int, body: ReviewIn, db: Session = Depends(get_db),
           user: User = Depends(teacher_or_admin)):
    r = db.get(GeneratedResource, rid)
    if not r:
        raise HTTPException(404, "资源不存在")
    _managed_course(db, r.course_id, user)
    if r.is_personalized and r.student_id is None:
        raise HTTPException(409, "个性化资源缺少学生归属，请重新生成后再审核")
    rv = ResourceReview(resource_id=rid, teacher_id=user.id, decision=body.decision,
                        comment=body.comment, revised_content=body.revised_content)
    db.add(rv)
    if body.decision == "approved":
        if body.revised_content:
            r.content = body.revised_content
        r.review_status = "approved"
        r.published = False
    elif body.decision == "rejected":
        r.review_status = "rejected"
        r.published = False
    elif body.decision == "risk":
        r.review_status = "risk"
        r.published = False
    elif body.decision == "needs_edit":
        r.review_status = "pending"
        r.published = False
        if body.revised_content:
            r.content = body.revised_content
    db.commit()
    return R.ok({"id": rid, "review_status": r.review_status, "published": r.published})


@router.post("/{rid}/publish", response_model=R)
def publish(rid: int, db: Session = Depends(get_db),
            user: User = Depends(teacher_or_admin)):
    r = db.get(GeneratedResource, rid)
    if not r:
        raise HTTPException(404, "资源不存在")
    _managed_course(db, r.course_id, user)
    if r.is_personalized and r.student_id is None:
        raise HTTPException(409, "个性化资源缺少学生归属，请重新生成后再发布")
    if r.review_status not in {"approved", "published"}:
        raise HTTPException(409, "资源必须先审核通过后才能发布")
    r.published = True
    r.review_status = "published"
    db.commit()
    return R.ok({"id": rid, "published": True})


@router.post("/{rid}/unpublish", response_model=R)
def unpublish(rid: int, db: Session = Depends(get_db),
              user: User = Depends(teacher_or_admin)):
    """Withdraw a published resource while preserving its approved revision."""
    resource = db.get(GeneratedResource, rid)
    if not resource:
        raise HTTPException(404, "资源不存在")
    _managed_course(db, resource.course_id, user)
    if not resource.published or resource.review_status != "published":
        raise HTTPException(409, "资源当前未处于发布状态")
    resource.published = False
    resource.review_status = "approved"
    db.commit()
    return R.ok({"id": rid, "published": False, "review_status": "approved"})


def _out(r: GeneratedResource, citations: list[dict]) -> dict:
    return {
        "id": r.id, "rtype": r.rtype, "title": r.title, "quality_score": r.quality_score,
        "review_status": r.review_status, "published": r.published,
        "is_personalized": r.is_personalized,
        "student_id": r.student_id, "kp_id": r.kp_id,
        "content": r.content,
        "citations": citations,
        "created_at": r.created_at.isoformat() if r.created_at else "",
    }


def _managed_course(db: Session, course_id: int, user: User) -> Course:
    course = db.get(Course, course_id)
    if not course:
        raise HTTPException(404, "课程不存在")
    if user.role == "teacher" and course.teacher_id != user.id:
        raise HTTPException(403, "无权审核其他教师的课程资源")
    return course
