"""课程 / 章节 / 选课。"""
from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import teacher_only, teacher_or_admin, student_only, any_role
from app.models.course import Course, CourseChapter, CourseEnrollment
from app.models.knowledge import KnowledgePoint
from app.models.profile import StudentProfile
from app.models.user import User
from app.schemas.course import CourseCreate, CourseUpdate, CourseOut, ChapterCreate, ChapterOut, EnrollIn
from app.schemas.common import R

router = APIRouter(prefix="/api/courses", tags=["course"])


@router.get("", response_model=R)
def list_courses(keyword: str = "", include_archived: bool = False, db: Session = Depends(get_db),
                 user: User = Depends(any_role)):
    q = db.query(Course)
    # 学生的课程发现页始终只展示 active；历史归档课程仅可通过本人选课列表查看。
    if user.role == "student" or not include_archived:
        q = q.filter(Course.status == "active")
    if keyword:
        q = q.filter(Course.name.contains(keyword))
    if user.role == "teacher":
        q = q.filter(Course.teacher_id == user.id)
    items = q.order_by(Course.id.desc()).all()
    return R.ok([CourseOut.model_validate(c).model_dump(mode="json") for c in items])


@router.post("", response_model=R)
def create_course(body: CourseCreate, db: Session = Depends(get_db),
                  user: User = Depends(teacher_only)):
    if body.code and db.query(Course).filter(Course.code == body.code).first():
        raise HTTPException(400, "课程代码已存在")
    c = Course(name=body.name, code=body.code, description=body.description,
               cover=body.cover, tags=body.tags, teacher_id=user.id)
    db.add(c)
    db.commit()
    db.refresh(c)
    return R.ok(CourseOut.model_validate(c).model_dump(mode="json"))


@router.put("/{cid}", response_model=R)
def update_course(cid: int, body: CourseUpdate, db: Session = Depends(get_db),
                  user: User = Depends(teacher_or_admin)):
    c = _managed_course(db, cid, user)
    changes = body.model_dump(exclude_unset=True, exclude_none=True)
    if "code" in changes and changes["code"] and db.query(Course).filter(
        Course.code == changes["code"], Course.id != cid
    ).first():
        raise HTTPException(400, "课程代码已存在")
    for k, v in changes.items():
        setattr(c, k, v)
    db.commit()
    db.refresh(c)
    return R.ok(CourseOut.model_validate(c).model_dump(mode="json"))


@router.delete("/{cid}", response_model=R)
def delete_course(cid: int, db: Session = Depends(get_db),
                  user: User = Depends(teacher_or_admin)):
    c = _managed_course(db, cid, user)
    try:
        db.delete(c)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "课程已有学习或资源数据，请先归档而不是删除") from exc
    return R.ok({"id": cid})


@router.get("/{cid}/chapters", response_model=R)
def list_chapters(cid: int, db: Session = Depends(get_db),
                  user: User = Depends(any_role)):
    _accessible_course(db, cid, user)
    items = db.query(CourseChapter).filter(CourseChapter.course_id == cid).order_by(
        CourseChapter.order_index).all()
    return R.ok([ChapterOut.model_validate(c).model_dump(mode="json") for c in items])


@router.post("/{cid}/chapters", response_model=R)
def add_chapter(cid: int, body: ChapterCreate, db: Session = Depends(get_db),
                user: User = Depends(teacher_or_admin)):
    _managed_course(db, cid, user)
    ch = CourseChapter(course_id=cid, title=body.title, summary=body.summary,
                       order_index=body.order_index)
    db.add(ch)
    db.commit()
    db.refresh(ch)
    return R.ok(ChapterOut.model_validate(ch).model_dump(mode="json"))


@router.put("/{cid}/chapters/{chapter_id}", response_model=R)
def update_chapter(cid: int, chapter_id: int, body: ChapterCreate,
                   db: Session = Depends(get_db),
                   user: User = Depends(teacher_or_admin)):
    _managed_course(db, cid, user)
    chapter = db.get(CourseChapter, chapter_id)
    if not chapter or chapter.course_id != cid:
        raise HTTPException(404, "章节不存在或不属于当前课程")
    chapter.title = body.title
    chapter.summary = body.summary
    chapter.order_index = body.order_index
    db.commit()
    db.refresh(chapter)
    return R.ok(ChapterOut.model_validate(chapter).model_dump(mode="json"))


@router.delete("/{cid}/chapters/{chapter_id}", response_model=R)
def delete_chapter(cid: int, chapter_id: int, db: Session = Depends(get_db),
                   user: User = Depends(teacher_or_admin)):
    _managed_course(db, cid, user)
    chapter = db.get(CourseChapter, chapter_id)
    if not chapter or chapter.course_id != cid:
        raise HTTPException(404, "章节不存在或不属于当前课程")
    # 删除章节不会删除知识点；相关知识点回到“未归类”，避免误删教学资产。
    db.query(KnowledgePoint).filter(
        KnowledgePoint.course_id == cid,
        KnowledgePoint.chapter_id == chapter_id,
    ).update({KnowledgePoint.chapter_id: None}, synchronize_session=False)
    db.delete(chapter)
    db.commit()
    return R.ok({"id": chapter_id, "detached_knowledge_points": True})


@router.post("/enroll", response_model=R)
def enroll(body: EnrollIn, db: Session = Depends(get_db),
           user: User = Depends(student_only)):
    course = db.get(Course, body.course_id)
    if not course or course.status != "active":
        raise HTTPException(404, "课程不存在或已归档")
    if not 1 <= body.weekly_hours <= 80:
        raise HTTPException(400, "每周学习时长应在 1 到 80 小时之间")
    e = db.query(CourseEnrollment).filter_by(course_id=body.course_id, student_id=user.id).first()
    if not e:
        e = CourseEnrollment(course_id=body.course_id, student_id=user.id,
                             goal=body.goal, weekly_hours=body.weekly_hours)
        db.add(e)
    else:
        e.goal = body.goal
        e.weekly_hours = body.weekly_hours
    db.commit()
    return R.ok({"course_id": body.course_id, "student_id": user.id})


@router.get("/mine/enrolled", response_model=R)
def my_courses(db: Session = Depends(get_db), user: User = Depends(student_only)):
    rows = db.query(Course, CourseEnrollment).join(
        CourseEnrollment, CourseEnrollment.course_id == Course.id).filter(
        CourseEnrollment.student_id == user.id).all()
    course_ids = [c.id for c, _ in rows]
    profiled_course_ids = {
        course_id
        for (course_id,) in db.query(StudentProfile.course_id).filter(
            StudentProfile.student_id == user.id,
            StudentProfile.course_id.in_(course_ids),
        ).all()
    } if course_ids else set()
    out = []
    for c, e in rows:
        d = CourseOut.model_validate(c).model_dump(mode="json")
        d["goal"] = e.goal
        d["weekly_hours"] = e.weekly_hours
        # 前端据此避免在尚未完成前测时请求不存在的画像端点，
        # 从而把正常的“待前测”状态误记为浏览器 404 错误。
        d["has_profile"] = c.id in profiled_course_ids
        out.append(d)
    return R.ok(out)


def _managed_course(db: Session, course_id: int, user: User) -> Course:
    course = db.get(Course, course_id)
    if not course:
        raise HTTPException(404, "课程不存在")
    if user.role == "teacher" and course.teacher_id != user.id:
        raise HTTPException(403, "无权管理其他教师的课程")
    return course


def _accessible_course(db: Session, course_id: int, user: User) -> Course:
    course = db.get(Course, course_id)
    if not course:
        raise HTTPException(404, "课程不存在")
    if user.role == "admin":
        return course
    if user.role == "teacher":
        if course.teacher_id != user.id:
            raise HTTPException(403, "无权访问其他教师的课程")
        return course
    enrolled = db.query(CourseEnrollment).filter(
        CourseEnrollment.course_id == course_id,
        CourseEnrollment.student_id == user.id,
    ).first()
    if not enrolled:
        raise HTTPException(403, "请先加入该课程")
    return course
