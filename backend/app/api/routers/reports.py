"""报告导出：Markdown / HTML在线预览 / PDF。"""
from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response, PlainTextResponse, HTMLResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import student_only, teacher_or_admin
from app.models.course import Course, CourseEnrollment
from app.models.user import User
from app.services import report_service

router = APIRouter(prefix="/api/reports", tags=["report"])


@router.get("/student/{course_id}.md")
def student_md(course_id: int, db: Session = Depends(get_db),
               user: User = Depends(student_only)):
    _require_enrollment(db, user.id, course_id)
    md = _student_report(db, user.id, course_id)
    return PlainTextResponse(md, media_type="text/markdown; charset=utf-8")


@router.get("/student/{course_id}.html", response_class=HTMLResponse)
def student_html(course_id: int, db: Session = Depends(get_db),
                 user: User = Depends(student_only)):
    """在线预览（带样式，浏览器可直接打印为 PDF）。"""
    _require_enrollment(db, user.id, course_id)
    md = _student_report(db, user.id, course_id)
    return report_service.md_to_html(md)


@router.get("/student/{course_id}.pdf")
def student_pdf(course_id: int, db: Session = Depends(get_db),
                user: User = Depends(student_only)):
    _require_enrollment(db, user.id, course_id)
    md = _student_report(db, user.id, course_id)
    data, is_pdf = report_service.md_to_pdf_bytes(md)
    if is_pdf:
        return Response(content=data, media_type="application/pdf",
                        headers={"Content-Disposition": f'attachment; filename="student_report_{course_id}.pdf"'})
    # 无 weasyprint：返回 HTML 让浏览器渲染（避免假 PDF 乱码）
    return Response(content=data, media_type="text/html; charset=utf-8")


@router.get("/class/{course_id}.md")
def class_md(course_id: int, db: Session = Depends(get_db),
             user: User = Depends(teacher_or_admin)):
    _managed_course(db, course_id, user)
    md = _class_report(db, course_id)
    return PlainTextResponse(md, media_type="text/markdown; charset=utf-8")


@router.get("/class/{course_id}.html", response_class=HTMLResponse)
def class_html(course_id: int, db: Session = Depends(get_db),
               user: User = Depends(teacher_or_admin)):
    _managed_course(db, course_id, user)
    md = _class_report(db, course_id)
    return report_service.md_to_html(md)


@router.get("/class/{course_id}.pdf")
def class_pdf(course_id: int, db: Session = Depends(get_db),
              user: User = Depends(teacher_or_admin)):
    _managed_course(db, course_id, user)
    md = _class_report(db, course_id)
    data, is_pdf = report_service.md_to_pdf_bytes(md)
    if is_pdf:
        return Response(content=data, media_type="application/pdf",
                        headers={"Content-Disposition": f'attachment; filename="class_report_{course_id}.pdf"'})
    return Response(content=data, media_type="text/html; charset=utf-8")


def _managed_course(db: Session, course_id: int, user: User) -> Course:
    course = db.get(Course, course_id)
    if not course:
        raise HTTPException(404, "课程不存在")
    if user.role == "teacher" and course.teacher_id != user.id:
        raise HTTPException(403, "无权导出其他教师的班级报告")
    return course


def _require_enrollment(db: Session, student_id: int, course_id: int) -> None:
    course = db.get(Course, course_id)
    if not course:
        raise HTTPException(404, "课程不存在")
    if not db.query(CourseEnrollment).filter(
        CourseEnrollment.course_id == course_id,
        CourseEnrollment.student_id == student_id,
    ).first():
        raise HTTPException(403, "请先加入该课程")


def _student_report(db: Session, student_id: int, course_id: int) -> str:
    try:
        return report_service.build_student_markdown(db, student_id, course_id)
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc


def _class_report(db: Session, course_id: int) -> str:
    try:
        return report_service.build_class_markdown(db, course_id)
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc
