"""知识点 / 关系 / 图谱。"""
from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import teacher_or_admin, any_role
from app.models.course import Course, CourseChapter, CourseEnrollment
from app.models.knowledge import KnowledgePoint, KnowledgeRelation
from app.models.user import User
from app.schemas.knowledge import KPCreate, KPOut, RelationCreate, RelationOut, GraphOut
from app.schemas.common import R

router = APIRouter(prefix="/api/knowledge", tags=["knowledge"])


@router.get("/course/{course_id}", response_model=R)
def list_kp(course_id: int, db: Session = Depends(get_db),
            user: User = Depends(any_role)):
    _accessible_course(db, course_id, user)
    rows = db.query(KnowledgePoint).filter(KnowledgePoint.course_id == course_id).all()
    return R.ok([KPOut.model_validate(r).model_dump(mode="json") for r in rows])


@router.post("", response_model=R)
def add_kp(body: KPCreate, db: Session = Depends(get_db),
           user: User = Depends(teacher_or_admin)):
    _managed_course(db, body.course_id, user)
    _validate_chapter(db, body.course_id, body.chapter_id)
    kp = KnowledgePoint(**body.model_dump())
    db.add(kp)
    db.commit()
    db.refresh(kp)
    return R.ok(KPOut.model_validate(kp).model_dump(mode="json"))


@router.put("/{kp_id}", response_model=R)
def update_kp(kp_id: int, body: KPCreate, db: Session = Depends(get_db),
              user: User = Depends(teacher_or_admin)):
    kp = db.get(KnowledgePoint, kp_id)
    if not kp:
        raise HTTPException(404, "知识点不存在")
    _managed_course(db, kp.course_id, user)
    if body.course_id != kp.course_id:
        _managed_course(db, body.course_id, user)
    _validate_chapter(db, body.course_id, body.chapter_id)
    for k, v in body.model_dump().items():
        setattr(kp, k, v)
    db.commit()
    return R.ok(KPOut.model_validate(kp).model_dump(mode="json"))


@router.delete("/{kp_id}", response_model=R)
def del_kp(kp_id: int, db: Session = Depends(get_db),
           user: User = Depends(teacher_or_admin)):
    kp = db.get(KnowledgePoint, kp_id)
    if not kp:
        raise HTTPException(404, "知识点不存在")
    _managed_course(db, kp.course_id, user)
    db.delete(kp)
    db.commit()
    return R.ok({"id": kp_id})


@router.get("/graph/{course_id}", response_model=R)
def graph(course_id: int, db: Session = Depends(get_db),
          user: User = Depends(any_role)):
    _accessible_course(db, course_id, user)
    kps = db.query(KnowledgePoint).filter(KnowledgePoint.course_id == course_id).all()
    rels = db.query(KnowledgeRelation).filter(KnowledgeRelation.course_id == course_id).all()
    nodes = [{"id": kp.id, "name": kp.name, "difficulty": kp.difficulty,
              "category": _category(kp.difficulty)} for kp in kps]
    edges = [{"id": r.id, "source": r.source_id, "target": r.target_id, "relation": r.relation,
              "weight": r.weight} for r in rels]
    return R.ok(GraphOut(nodes=nodes, edges=edges).model_dump(mode="json"))


def _category(difficulty: int) -> str:
    """跨学科通用分层，避免把某一专业的固定术语带入其他课程。"""
    if difficulty <= 2:
        return "基础认知"
    if difficulty == 3:
        return "核心理解"
    if difficulty == 4:
        return "综合应用"
    return "高阶实践"


@router.post("/relation", response_model=R)
def add_relation(body: RelationCreate, db: Session = Depends(get_db),
                 user: User = Depends(teacher_or_admin)):
    _managed_course(db, body.course_id, user)
    _validate_relation_points(db, body)
    r = KnowledgeRelation(**body.model_dump())
    db.add(r)
    db.commit()
    db.refresh(r)
    return R.ok(RelationOut.model_validate(r).model_dump(mode="json"))


@router.put("/relation/{relation_id}", response_model=R)
def update_relation(relation_id: int, body: RelationCreate,
                    db: Session = Depends(get_db),
                    user: User = Depends(teacher_or_admin)):
    item = db.get(KnowledgeRelation, relation_id)
    if not item:
        raise HTTPException(404, "知识关系不存在")
    _managed_course(db, item.course_id, user)
    if body.course_id != item.course_id:
        raise HTTPException(400, "知识关系不能移动到其他课程")
    _validate_relation_points(db, body)
    item.source_id = body.source_id
    item.target_id = body.target_id
    item.relation = body.relation
    item.weight = body.weight
    db.commit()
    db.refresh(item)
    return R.ok(RelationOut.model_validate(item).model_dump(mode="json"))


@router.delete("/relation/{relation_id}", response_model=R)
def delete_relation(relation_id: int, db: Session = Depends(get_db),
                    user: User = Depends(teacher_or_admin)):
    item = db.get(KnowledgeRelation, relation_id)
    if not item:
        raise HTTPException(404, "知识关系不存在")
    _managed_course(db, item.course_id, user)
    db.delete(item)
    db.commit()
    return R.ok({"id": relation_id})


def _validate_relation_points(db: Session, body: RelationCreate) -> None:
    source = db.get(KnowledgePoint, body.source_id)
    target = db.get(KnowledgePoint, body.target_id)
    if not source or not target:
        raise HTTPException(404, "关系中的知识点不存在")
    if source.course_id != body.course_id or target.course_id != body.course_id:
        raise HTTPException(400, "知识点关系必须位于同一课程")
    if source.id == target.id:
        raise HTTPException(400, "知识点不能与自身建立关系")


def _managed_course(db: Session, course_id: int, user: User) -> Course:
    course = db.get(Course, course_id)
    if not course:
        raise HTTPException(404, "课程不存在")
    if user.role == "teacher" and course.teacher_id != user.id:
        raise HTTPException(403, "无权管理其他教师的课程知识图谱")
    return course


def _accessible_course(db: Session, course_id: int, user: User) -> Course:
    course = db.get(Course, course_id)
    if not course:
        raise HTTPException(404, "课程不存在")
    if user.role == "admin":
        return course
    if user.role == "teacher":
        if course.teacher_id != user.id:
            raise HTTPException(403, "无权访问其他教师的课程知识图谱")
        return course
    enrolled = db.query(CourseEnrollment).filter(
        CourseEnrollment.course_id == course_id,
        CourseEnrollment.student_id == user.id,
    ).first()
    if not enrolled:
        raise HTTPException(403, "请先加入该课程")
    return course


def _validate_chapter(db: Session, course_id: int, chapter_id: int | None) -> None:
    if chapter_id is None:
        return
    chapter = db.get(CourseChapter, chapter_id)
    if not chapter or chapter.course_id != course_id:
        raise HTTPException(400, "章节不存在或不属于当前课程")
