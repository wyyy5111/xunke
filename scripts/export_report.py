"""命令行导出学习/教学报告。"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from app.core.database import SessionLocal
from app.models.course import Course, CourseEnrollment
from app.models.user import User
from app.services import report_service


def main():
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--type", choices=["student", "class"], default="student")
    p.add_argument("--course-id", type=int, default=None, help="有效课程 ID；省略时自动选择第一门有效课程")
    p.add_argument("--student-id", type=int, default=None, help="已加入课程的学生 ID；省略时自动选择")
    p.add_argument("--out", default="report.md")
    args = p.parse_args()

    db = SessionLocal()
    try:
        course = (
            db.query(Course).filter(Course.id == args.course_id, Course.status == "active").first()
            if args.course_id
            else db.query(Course).filter(Course.status == "active").order_by(Course.id).first()
        )
        if not course:
            raise SystemExit("未找到可导出的有效课程，请先初始化演示数据或传入有效 --course-id。")
        if args.type == "student":
            enrollment_q = db.query(CourseEnrollment).join(
                User, User.id == CourseEnrollment.student_id
            ).filter(
                CourseEnrollment.course_id == course.id,
                User.role == "student",
                User.is_active == True,
            )
            if args.student_id:
                enrollment_q = enrollment_q.filter(CourseEnrollment.student_id == args.student_id)
            enrollment = enrollment_q.order_by(CourseEnrollment.student_id).first()
            if not enrollment:
                raise SystemExit("未找到已加入该课程的有效学生，请检查 --student-id。")
            md = report_service.build_student_markdown(db, enrollment.student_id, course.id)
        else:
            md = report_service.build_class_markdown(db, course.id)
        Path(args.out).write_text(md, encoding="utf-8")
        print(f"[OK] 报告已导出：{args.out}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
