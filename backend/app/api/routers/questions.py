"""题库管理。"""
from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import teacher_or_admin
from app.models.course import Course
from app.models.knowledge import KnowledgePoint
from app.models.question import Question, QuestionOption
from app.models.user import User
from app.schemas.question import QuestionCreate, QuestionOut
from app.schemas.common import R

router = APIRouter(prefix="/api/questions", tags=["question"])


@router.get("", response_model=R)
def list_q(course_id: int, kp_id: int = 0, qtype: str = "",
           db: Session = Depends(get_db),
           user: User = Depends(teacher_or_admin)):
    _managed_course(db, course_id, user)
    q = db.query(Question).filter(Question.course_id == course_id)
    if kp_id:
        q = q.filter(Question.kp_id == kp_id)
    if qtype:
        q = q.filter(Question.qtype == qtype)
    rows = q.order_by(Question.id.desc()).limit(400).all()
    # 多次运行工作流时保留历史题目供既有答题记录追溯，但管理页只展示最新的同题版本。
    unique_rows = []
    seen_stems = set()
    for row in rows:
        normalized = "".join((row.stem or "").split())
        if normalized in seen_stems:
            continue
        seen_stems.add(normalized)
        unique_rows.append(row)
        if len(unique_rows) >= 200:
            break
    return R.ok([QuestionOut.model_validate(r).model_dump(mode="json") for r in unique_rows])


@router.post("", response_model=R)
def add_q(body: QuestionCreate, db: Session = Depends(get_db),
          user: User = Depends(teacher_or_admin)):
    _managed_course(db, body.course_id, user)
    if body.kp_id is not None:
        kp = db.get(KnowledgePoint, body.kp_id)
        if not kp or kp.course_id != body.course_id:
            raise HTTPException(400, "知识点不存在或不属于当前课程")
    q = Question(course_id=body.course_id, kp_id=body.kp_id, qtype=body.qtype,
                 stem=body.stem, answer=body.answer, analysis=body.analysis,
                 difficulty=body.difficulty, tags=body.tags, source="manual")
    db.add(q)
    db.flush()
    for opt in body.options:
        db.add(QuestionOption(question_id=q.id, key=opt.key, content=opt.content,
                              is_correct=opt.is_correct, order_index=opt.order_index))
    db.commit()
    db.refresh(q)
    return R.ok(QuestionOut.model_validate(q).model_dump(mode="json"))


@router.delete("/{qid}", response_model=R)
def del_q(qid: int, db: Session = Depends(get_db),
          user: User = Depends(teacher_or_admin)):
    q = db.get(Question, qid)
    if not q:
        raise HTTPException(404, "题目不存在")
    _managed_course(db, q.course_id, user)
    try:
        db.delete(q)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "题目已有答题或错题记录，不能直接删除") from exc
    return R.ok({"id": qid})


def _managed_course(db: Session, course_id: int, user: User) -> Course:
    course = db.get(Course, course_id)
    if not course:
        raise HTTPException(404, "课程不存在")
    if user.role == "teacher" and course.teacher_id != user.id:
        raise HTTPException(403, "无权管理其他教师的题库")
    return course
