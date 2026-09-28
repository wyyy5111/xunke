"""学生画像 / 学习路径 / 掌握度。"""
from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import student_only
from app.models.course import Course, CourseEnrollment
from app.models.knowledge import KnowledgePoint
from app.models.resource import GeneratedResource
from app.models.user import User
from app.models.learning import LearningPath
from app.services import profile_service, learning_path_service
from app.schemas.common import R
from app.schemas.profile import LearningRecordIn, PathProgressIn
from app.utils.time_util import safe_json_loads

router = APIRouter(prefix="/api/profiles", tags=["profile"])


@router.get("/{course_id}", response_model=R)
def get_profile(course_id: int, db: Session = Depends(get_db),
                user: User = Depends(student_only)):
    _require_enrollment(db, user.id, course_id)
    p = profile_service.get_profile(db, user.id, course_id)
    if not p:
        raise HTTPException(404, "尚未生成画像，请先完成前测")
    # Legacy rows may still contain the pre-test snapshot after a completed
    # post-test. Reconcile from KnowledgeMastery before building the response.
    profile_service.sync_profile_mastery_summary(db, p, commit=True)
    point_names = dict(db.query(KnowledgePoint.id, KnowledgePoint.name).filter(
        KnowledgePoint.course_id == course_id,
    ).all())
    weak_points = _current_point_names(safe_json_loads(p.weak_points, []), point_names)
    extra = safe_json_loads(p.extra, {})
    if isinstance(extra, dict):
        extra["mastered"] = _current_point_names(extra.get("mastered", []), point_names)
    data = {
        "id": p.id, "student_id": p.student_id, "course_id": p.course_id,
        "stage": p.stage, "goal": p.goal, "weekly_hours": p.weekly_hours,
        "base_level": p.base_level, "pref_format": p.pref_format, "pref_style": p.pref_style,
        "learning_speed": p.learning_speed, "pre_score": p.pre_score, "post_score": p.post_score,
        "weak_points": weak_points, "recommendation": p.recommendation,
        "extra": extra,
    }
    return R.ok(data)


@router.get("/{course_id}/mastery", response_model=R)
def mastery(course_id: int, db: Session = Depends(get_db), user: User = Depends(student_only)):
    _require_enrollment(db, user.id, course_id)
    return R.ok(profile_service.mastery_list(db, user.id, course_id))


@router.get("/{course_id}/path", response_model=R)
def get_path(course_id: int, db: Session = Depends(get_db), user: User = Depends(student_only)):
    _require_enrollment(db, user.id, course_id)
    lp = db.query(LearningPath).filter(LearningPath.student_id == user.id,
                                       LearningPath.course_id == course_id).first()
    if not lp:
        lp = learning_path_service.plan_path(db, user.id, course_id)
    nodes = safe_json_loads(lp.nodes, [])
    point_names = dict(db.query(KnowledgePoint.id, KnowledgePoint.name).filter(
        KnowledgePoint.course_id == course_id,
    ).all())
    refreshed_nodes = _current_point_names(nodes, point_names)
    if refreshed_nodes != nodes:
        from app.utils.time_util import safe_json_dumps
        lp.nodes = safe_json_dumps(refreshed_nodes)
        db.commit()
    return R.ok({"id": lp.id, "nodes": refreshed_nodes,
                 "total_minutes": lp.total_minutes, "completed_nodes": lp.completed_nodes})


@router.post("/{course_id}/plan", response_model=R)
def plan(course_id: int, db: Session = Depends(get_db), user: User = Depends(student_only)):
    _require_enrollment(db, user.id, course_id)
    lp = learning_path_service.plan_path(db, user.id, course_id)
    return R.ok({"id": lp.id, "nodes": safe_json_loads(lp.nodes, []), "total_minutes": lp.total_minutes,
                 "completed_nodes": lp.completed_nodes})


@router.post("/{course_id}/path/progress", response_model=R)
def update_path_progress(course_id: int, body: PathProgressIn,
                         db: Session = Depends(get_db),
                         user: User = Depends(student_only)):
    _require_enrollment(db, user.id, course_id)
    _validate_resource(db, body.resource_id, course_id, user.id)
    try:
        lp = learning_path_service.update_path_progress(
            db,
            user.id,
            course_id,
            body.kp_id,
            status=body.status,
            duration=body.duration,
            resource_id=body.resource_id,
        )
    except ValueError as exc:
        db.rollback()
        raise HTTPException(400, str(exc)) from exc
    return R.ok({
        "id": lp.id,
        "nodes": safe_json_loads(lp.nodes, []),
        "total_minutes": lp.total_minutes,
        "completed_nodes": lp.completed_nodes,
    })


@router.get("/{course_id}/records", response_model=R)
def records(course_id: int, limit: int = 100,
            db: Session = Depends(get_db),
            user: User = Depends(student_only)):
    _require_enrollment(db, user.id, course_id)
    return R.ok(learning_path_service.learning_records(db, user.id, course_id, limit))


@router.post("/{course_id}/records", response_model=R)
def add_record(course_id: int, body: LearningRecordIn,
               db: Session = Depends(get_db),
               user: User = Depends(student_only)):
    _require_enrollment(db, user.id, course_id)
    _validate_resource(db, body.resource_id, course_id, user.id)
    try:
        row = learning_path_service.add_learning_record(
            db,
            user.id,
            course_id,
            body.action,
            duration=body.duration,
            resource_id=body.resource_id,
            kp_id=body.kp_id,
        )
    except ValueError as exc:
        db.rollback()
        raise HTTPException(400, str(exc)) from exc
    return R.ok({"id": row.id, "action": row.action, "happened_at": row.happened_at.isoformat()})


def _require_enrollment(db: Session, student_id: int, course_id: int) -> CourseEnrollment:
    course = db.get(Course, course_id)
    if not course or course.status != "active":
        raise HTTPException(404, "课程不存在或已归档")
    enrollment = db.query(CourseEnrollment).filter(
        CourseEnrollment.course_id == course_id,
        CourseEnrollment.student_id == student_id,
    ).first()
    if not enrollment:
        raise HTTPException(403, "请先加入该课程")
    return enrollment


def _validate_resource(db: Session, resource_id: int | None,
                       course_id: int, student_id: int) -> None:
    if resource_id is None:
        return
    resource = db.get(GeneratedResource, resource_id)
    if not resource or resource.course_id != course_id:
        raise HTTPException(404, "资源不存在")
    if not resource.published or resource.student_id not in (None, student_id):
        raise HTTPException(403, "无权记录该资源的学习行为")


def _current_point_names(items: object, point_names: dict[int, str]) -> list:
    """Resolve denormalised labels from current knowledge-point IDs.

    Profiles and learning paths intentionally retain point IDs for history.
    A teacher may later improve an extracted label; returning the current name
    prevents stale sentence fragments from surviving in student-facing views.
    """
    if not isinstance(items, list):
        return []
    refreshed = []
    for item in items:
        if not isinstance(item, dict):
            refreshed.append(item)
            continue
        current = dict(item)
        try:
            point_id = int(current.get("id") or current.get("kp_id") or 0)
        except (TypeError, ValueError):
            point_id = 0
        if point_id in point_names:
            current["name"] = point_names[point_id]
        refreshed.append(current)
    return refreshed
