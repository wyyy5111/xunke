"""错题本。"""
from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import student_only
from app.models.course import Course, CourseEnrollment
from app.models.learning import WrongQuestion
from app.models.user import User
from app.services import wrong_question_service
from app.schemas.common import R

router = APIRouter(prefix="/api/wrong", tags=["wrong"])


@router.get("/{course_id}", response_model=R)
def list_wrong(course_id: int, db: Session = Depends(get_db),
               user: User = Depends(student_only)):
    _require_enrollment(db, user.id, course_id)
    return R.ok(wrong_question_service.list_wrong(db, user.id, course_id))


@router.post("/{wrong_id}/resolve", response_model=R)
def resolve(wrong_id: int, db: Session = Depends(get_db),
            user: User = Depends(student_only)):
    row = db.get(WrongQuestion, wrong_id)
    if not row:
        raise HTTPException(404, "错题记录不存在")
    _require_enrollment(db, user.id, row.course_id)
    if row.student_id != user.id:
        raise HTTPException(403, "无权修改其他学生的错题")
    if not wrong_question_service.resolve(db, wrong_id, student_id=user.id):
        raise HTTPException(404, "错题记录不存在")
    return R.ok({"id": wrong_id, "resolved": True})


def _require_enrollment(db: Session, student_id: int, course_id: int) -> None:
    course = db.get(Course, course_id)
    if not course:
        raise HTTPException(404, "课程不存在")
    if not db.query(CourseEnrollment).filter(
        CourseEnrollment.course_id == course_id,
        CourseEnrollment.student_id == student_id,
    ).first():
        raise HTTPException(403, "请先加入该课程")
