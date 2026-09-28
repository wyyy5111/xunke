"""错题本与补救。"""
from __future__ import annotations
from sqlalchemy.orm import Session

from app.models.learning import WrongQuestion
from app.models.question import Question


def add_wrong(db: Session, student_id: int, course_id: int, question_id: int,
              wrong_answer: str, reason: str = "", commit: bool = True) -> WrongQuestion:
    q = db.get(Question, question_id)
    if not q:
        raise ValueError("题目不存在")
    if q.course_id != course_id:
        raise ValueError("题目不属于当前课程")
    wq = db.query(WrongQuestion).filter(
        WrongQuestion.student_id == student_id,
        WrongQuestion.course_id == course_id,
        WrongQuestion.question_id == question_id,
        WrongQuestion.resolved == False,
    ).first()
    if not wq:
        wq = WrongQuestion(student_id=student_id, course_id=course_id,
                           question_id=question_id, kp_id=q.kp_id if q else None)
        db.add(wq)
    wq.wrong_answer = wrong_answer
    wq.reason = reason or _guess_reason(q, wrong_answer)
    wq.reviewed = False
    if commit:
        db.commit()
    else:
        db.flush()
    return wq


def _guess_reason(q: Question | None, ans: str) -> str:
    if not q:
        return "概念不清"
    if q.qtype in ("single", "multiple"):
        return "选项混淆"
    if q.qtype == "judge":
        return "判断失误"
    if q.qtype == "fill":
        return "记忆不牢"
    return "应用不足"


def list_wrong(db: Session, student_id: int, course_id: int) -> list[dict]:
    rows = db.query(WrongQuestion, Question).join(
        Question, Question.id == WrongQuestion.question_id
    ).filter(
        WrongQuestion.student_id == student_id,
        WrongQuestion.course_id == course_id,
        WrongQuestion.resolved == False,
    ).order_by(WrongQuestion.id.desc()).all()
    out = []
    for w, q in rows:
        out.append({
            "id": w.id, "question_id": q.id, "stem": q.stem, "qtype": q.qtype,
            "your": w.wrong_answer, "correct": q.answer, "analysis": q.analysis,
            "kp_id": q.kp_id, "reason": w.reason, "difficulty": q.difficulty,
            "created_at": w.created_at.isoformat() if w.created_at else "",
        })
    return out


def mark_correct(db: Session, student_id: int, course_id: int,
                 question_id: int, commit: bool = True) -> int:
    """答对同一道题后关闭对应未解决错题，返回关闭数量。"""
    rows = db.query(WrongQuestion).filter(
        WrongQuestion.student_id == student_id,
        WrongQuestion.course_id == course_id,
        WrongQuestion.question_id == question_id,
        WrongQuestion.resolved == False,
    ).all()
    for row in rows:
        row.resolved = True
        row.reviewed = True
    if rows:
        if commit:
            db.commit()
        else:
            db.flush()
    return len(rows)


def resolve(db: Session, wrong_id: int, student_id: int | None = None,
            commit: bool = True) -> WrongQuestion | None:
    q = db.query(WrongQuestion).filter(WrongQuestion.id == wrong_id)
    if student_id is not None:
        q = q.filter(WrongQuestion.student_id == student_id)
    w = q.first()
    if not w:
        return None
    w.resolved = True
    w.reviewed = True
    if commit:
        db.commit()
    else:
        db.flush()
    return w
