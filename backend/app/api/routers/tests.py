"""前测 / 后测 / 答题 / 对比。"""
from __future__ import annotations
import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import student_only
from app.models.course import Course, CourseEnrollment
from app.models.resource import GeneratedResource
from app.models.user import User
from app.models.question import Question
from app.models.test import AssessmentAttempt, PreTest, PostTest, TestAnswer
from app.services import test_service, profile_service, learning_path_service
from app.schemas.test import SubmitTestIn, PracticeSubmitIn
from app.schemas.common import R
from app.utils.time_util import safe_json_dumps, safe_json_loads, utc_now

router = APIRouter(prefix="/api/tests", tags=["test"])


@router.get("/pre/{course_id}", response_model=R)
def gen_pre(course_id: int, count: int = 10, test_type: str = "practice",
            db: Session = Depends(get_db),
            user: User = Depends(student_only)):
    """Get practice questions or the student's immutable pre/post paper."""
    _require_enrollment(db, user.id, course_id)
    if test_type not in {"pre", "post", "practice"}:
        raise HTTPException(400, "test_type 仅支持 pre、post 或 practice")
    if test_type == "practice":
        qids = test_service.pick_questions(
            db, course_id, count=count, difficulty=3, student_id=user.id
        )
    else:
        qids = _assessment_questions(db, user.id, course_id, test_type, count)
    qs = db.query(Question).filter(Question.id.in_(qids)).all() if qids else []
    qmap = {q.id: q for q in qs}
    return R.ok([_student_question(qmap[qid]) for qid in qids if qid in qmap])


@router.post("/submit", response_model=R)
def submit(body: SubmitTestIn, db: Session = Depends(get_db),
           user: User = Depends(student_only)):
    enrollment = _require_enrollment(db, user.id, body.course_id)
    attempt = db.query(AssessmentAttempt).filter(
        AssessmentAttempt.student_id == user.id,
        AssessmentAttempt.course_id == body.course_id,
        AssessmentAttempt.test_type == body.test_type,
        AssessmentAttempt.status == "open",
    ).order_by(AssessmentAttempt.id.desc()).first()
    if not attempt:
        raise HTTPException(409, "请先获取本次测评题目，或该测评已经提交")
    answers = [a.model_dump() for a in body.answers]
    expected_ids = [int(qid) for qid in safe_json_loads(attempt.question_ids, [])]
    submitted_ids = [int(item["question_id"]) for item in answers]
    if len(submitted_ids) != len(expected_ids) or set(submitted_ids) != set(expected_ids):
        raise HTTPException(409, "提交题目与本次测评试卷不一致")
    pre_score = None
    if body.test_type == "post":
        pre = db.query(PreTest).filter(PreTest.student_id == user.id,
                                       PreTest.course_id == body.course_id).order_by(
            PreTest.id.desc()).first()
        if not pre:
            raise HTTPException(409, "请先完成前测再提交后测")
        pre_score = pre.score
    try:
        result = test_service.grade_answers(
            db, body.course_id, user.id, body.test_type, answers, pre_score
        )
    except ValueError as exc:
        db.rollback()
        raise HTTPException(400, str(exc)) from exc

    if body.test_type == "pre":
        trace_id = uuid.uuid4().hex[:16]
        attempt_answers = db.query(TestAnswer).filter(
            TestAnswer.student_id == user.id,
            TestAnswer.course_id == body.course_id,
            TestAnswer.test_type == "pre",
            TestAnswer.test_id == result["test_id"],
        ).all()
        profile = profile_service.build_profile(
            db,
            user.id,
            body.course_id,
            enrollment.goal,
            enrollment.weekly_hours,
            trace_id=trace_id,
            answers=attempt_answers,
        )
        path = learning_path_service.plan_path(db, user.id, body.course_id)
        learning_path_service.add_learning_record(
            db, user.id, body.course_id, action="pre_test"
        )
        result.update({
            "profile_id": profile.id,
            "path_id": path.id,
            "diagnosis_trace_id": trace_id,
        })
    attempt = db.get(AssessmentAttempt, attempt.id)
    if attempt:
        attempt.status = "submitted"
        attempt.test_id = result["test_id"]
        attempt.submitted_at = utc_now()
        db.commit()
    return R.ok(result)


@router.post("/practice/submit", response_model=R)
def submit_practice(body: PracticeSubmitIn, db: Session = Depends(get_db),
                    user: User = Depends(student_only)):
    _require_enrollment(db, user.id, body.course_id)
    if body.resource_id is not None:
        resource = db.get(GeneratedResource, body.resource_id)
        if not resource or resource.course_id != body.course_id:
            raise HTTPException(404, "练习资源不存在")
        if resource.rtype != "exercise":
            raise HTTPException(400, "resource_id 必须对应练习资源")
        if not resource.published or (resource.student_id not in (None, user.id)):
            raise HTTPException(403, "无权提交该练习资源")
    try:
        result = test_service.grade_practice(
            db,
            body.course_id,
            user.id,
            [answer.model_dump() for answer in body.answers],
            resource_id=body.resource_id,
            duration=body.duration,
        )
    except ValueError as exc:
        db.rollback()
        raise HTTPException(400, str(exc)) from exc
    return R.ok(result)


@router.get("/compare/{course_id}", response_model=R)
def compare(course_id: int, db: Session = Depends(get_db),
            user: User = Depends(student_only)):
    _require_enrollment(db, user.id, course_id)
    return R.ok(test_service.compare(db, user.id, course_id))


def _student_question(q: Question) -> dict:
    """测评下发只包含作答所需字段，绝不泄露答案和正确选项。"""
    return {
        "id": q.id, "qtype": q.qtype, "stem": q.stem,
        "difficulty": q.difficulty, "tags": q.tags,
        "kp_id": q.kp_id,
        "options": [{"key": option.key, "content": option.content} for option in q.options],
    }


def _assessment_questions(db: Session, student_id: int, course_id: int,
                          test_type: str, count: int) -> list[int]:
    existing = db.query(AssessmentAttempt).filter(
        AssessmentAttempt.student_id == student_id,
        AssessmentAttempt.course_id == course_id,
        AssessmentAttempt.test_type == test_type,
        AssessmentAttempt.status == "open",
    ).order_by(AssessmentAttempt.id.desc()).first()
    if existing:
        return [int(qid) for qid in safe_json_loads(existing.question_ids, [])]

    completed_model = PreTest if test_type == "pre" else PostTest
    completed = db.query(completed_model).filter(
        completed_model.student_id == student_id,
        completed_model.course_id == course_id,
    ).first()
    if completed:
        label = "前测" if test_type == "pre" else "后测"
        raise HTTPException(409, f"{label}已经完成，如需重测请由教师重置")

    qids = test_service.pick_questions(
        db, course_id, count=count, difficulty=3, student_id=student_id
    )
    if not qids:
        return []
    attempt = AssessmentAttempt(
        student_id=student_id,
        course_id=course_id,
        test_type=test_type,
        question_ids=safe_json_dumps(qids),
        status="open",
    )
    db.add(attempt)
    db.commit()
    return qids


def _require_enrollment(db: Session, student_id: int, course_id: int) -> CourseEnrollment:
    course = db.get(Course, course_id)
    if not course or course.status != "active":
        raise HTTPException(404, "课程不存在或已归档")
    enrollment = db.query(CourseEnrollment).filter(
        CourseEnrollment.course_id == course_id,
        CourseEnrollment.student_id == student_id,
    ).first()
    if not enrollment:
        raise HTTPException(403, "请先选择并加入该课程")
    return enrollment
