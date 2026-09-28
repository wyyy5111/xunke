"""前后测：组卷、判分、对比。"""
from __future__ import annotations
import random
from datetime import datetime
from typing import List
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from app.models.knowledge import KnowledgePoint
from app.models.question import Question
from app.models.profile import KnowledgeMastery, StudentProfile
from app.models.resource import GeneratedResource
from app.models.test import PreTest, PostTest, TestAnswer
from app.utils.time_util import safe_json_dumps, safe_json_loads


def pick_questions(db: Session, course_id: int, count: int, difficulty: int = 3,
                   kp_ids: List[int] | None = None,
                   student_id: int | None = None) -> List[int]:
    personalized_scope = (
        or_(GeneratedResource.student_id.is_(None), GeneratedResource.student_id == student_id)
        if student_id is not None
        else GeneratedResource.student_id.is_(None)
    )
    eligible_ai = and_(
        Question.source == "ai",
        Question.ai_resource_id.is_not(None),
        GeneratedResource.published.is_(True),
        personalized_scope,
    )
    q = db.query(Question).outerjoin(
        GeneratedResource, GeneratedResource.id == Question.ai_resource_id
    ).filter(
        Question.course_id == course_id,
        or_(Question.source.in_(["manual", "seed"]), eligible_ai),
    )
    if kp_ids:
        q = q.filter(Question.kp_id.in_(kp_ids))
    all_q = q.order_by(Question.id.desc()).all()
    if not all_q:
        return []
    unique_q = []
    seen_stems = set()
    for item in all_q:
        normalized = "".join((item.stem or "").split())
        if normalized in seen_stems:
            continue
        seen_stems.add(normalized)
        unique_q.append(item)
    all_q = unique_q
    # 在目标难度附近分层抽样，保证同分时仍有随机性。
    random.shuffle(all_q)
    all_q.sort(key=lambda item: abs((item.difficulty or 3) - difficulty))
    picked = all_q[:max(1, min(int(count), 100))]
    return [p.id for p in picked]


def grade_answers(db: Session, course_id: int, student_id: int, test_type: str,
                  answers: list[dict], pre_score: float | None = None) -> dict:
    if test_type not in {"pre", "post"}:
        raise ValueError("测评类型仅支持 pre 或 post")
    graded = _grade(db, course_id, student_id, answers)
    details = graded["details"]
    total = graded["total"]
    correct = graded["correct"]
    score = graded["score"]
    qids = graded["question_ids"]

    if test_type == "pre":
        pt = PreTest(student_id=student_id, course_id=course_id,
                     question_ids=safe_json_dumps(qids), total=total, correct=correct,
                     score=score, finished_at=datetime.now())
        db.add(pt)
        db.flush()
        _save_answers(db, student_id, course_id, "pre", details, pt.id)
        db.commit()
        return {"test_id": pt.id, "total": total, "correct": correct, "score": score, "details": details}

    # 后测只使用本次答题计算 mastery，先更新 mastery，再持久化 by_kp。
    answer_rows = _save_answers(db, student_id, course_id, "post", details, None)
    db.flush()
    from app.services import profile_service, wrong_question_service, learning_path_service

    kps = db.query(KnowledgePoint).filter(KnowledgePoint.course_id == course_id).all()
    scores = profile_service.compute_mastery(db, student_id, course_id, answer_rows, kps)
    profile_service.save_mastery(db, student_id, course_id, scores, kps, pre=False, commit=False)
    assessed_kp_ids = {
        int(item["kp_id"]) for item in details if item.get("kp_id") is not None
    }
    by_kp = _by_kp(db, student_id, course_id, assessed_kp_ids)
    if pre_score is None:
        previous = db.query(PreTest).filter(
            PreTest.student_id == student_id,
            PreTest.course_id == course_id,
        ).order_by(PreTest.id.desc()).first()
        pre_score = previous.score if previous else 0.0
    improvement = round(score - (pre_score or 0.0), 1)
    pt = PostTest(student_id=student_id, course_id=course_id,
                 question_ids=safe_json_dumps(qids), total=total, correct=correct,
                 score=score, pre_score=pre_score or 0.0, improvement=improvement,
                 finished_at=datetime.now(), by_kp=safe_json_dumps(by_kp))
    db.add(pt)
    db.flush()
    for row in answer_rows:
        row.test_id = pt.id

    profile = db.query(StudentProfile).filter(
        StudentProfile.student_id == student_id,
        StudentProfile.course_id == course_id,
    ).first()
    if profile:
        profile.post_score = score
        profile.stage = "post_test"
        profile_service.sync_profile_mastery_summary(db, profile, commit=False)

    for item in details:
        if item["is_correct"]:
            wrong_question_service.mark_correct(
                db, student_id, course_id, item["question_id"], commit=False
            )
        else:
            wrong_question_service.add_wrong(
                db, student_id, course_id, item["question_id"], item["your"], commit=False
            )
    learning_path_service.add_learning_record(
        db, student_id, course_id, action="post_test", commit=False
    )
    db.commit()
    return {"test_id": pt.id, "total": total, "correct": correct, "score": score,
            "improvement": improvement, "by_kp": by_kp, "details": details}


def grade_practice(db: Session, course_id: int, student_id: int,
                   answers: list[dict], resource_id: int | None = None,
                   duration: int = 0) -> dict:
    """提交普通练习，写答题记录、错题本和学习记录。"""
    graded = _grade(db, course_id, student_id, answers, resource_id=resource_id)
    details = graded["details"]
    _save_answers(db, student_id, course_id, "practice", details, None)

    from app.services import learning_path_service, wrong_question_service
    wrong_added = 0
    resolved = 0
    kp_ids = {item["kp_id"] for item in details if item.get("kp_id") is not None}
    for item in details:
        if item["is_correct"]:
            resolved += wrong_question_service.mark_correct(
                db, student_id, course_id, item["question_id"], commit=False
            )
        else:
            wrong_question_service.add_wrong(
                db, student_id, course_id, item["question_id"], item["your"], commit=False
            )
            wrong_added += 1
    learning_path_service.add_learning_record(
        db,
        student_id,
        course_id,
        action="practice",
        duration=duration,
        resource_id=resource_id,
        kp_id=next(iter(kp_ids)) if len(kp_ids) == 1 else None,
        commit=False,
    )
    db.commit()
    return {
        "test_id": None,
        "total": graded["total"],
        "correct": graded["correct"],
        "score": graded["score"],
        "details": details,
        "wrong_added": wrong_added,
        "resolved": resolved,
    }


def _grade(db: Session, course_id: int, student_id: int,
           answers: list[dict], resource_id: int | None = None) -> dict:
    if not answers:
        raise ValueError("答题内容不能为空")
    qids = [int(item["question_id"]) for item in answers]
    if len(set(qids)) != len(qids):
        raise ValueError("同一道题不能重复提交")
    questions = db.query(Question).filter(
        Question.course_id == course_id,
        Question.id.in_(qids),
    ).all()
    qmap = {q.id: q for q in questions}
    missing = [qid for qid in qids if qid not in qmap]
    if missing:
        raise ValueError("提交中包含不存在或不属于当前课程的题目")

    ai_resource_ids = {
        question.ai_resource_id for question in questions
        if question.source == "ai" and question.ai_resource_id is not None
    }
    resources = db.query(GeneratedResource).filter(
        GeneratedResource.id.in_(ai_resource_ids or [-1])
    ).all()
    resource_map = {resource.id: resource for resource in resources}
    for question in questions:
        if resource_id is not None and question.ai_resource_id != resource_id:
            raise ValueError("提交题目与当前练习资源不匹配")
        if question.source != "ai":
            continue
        resource = resource_map.get(question.ai_resource_id)
        if (
            not resource
            or resource.course_id != course_id
            or not resource.published
            or resource.student_id not in (None, student_id)
        ):
            raise ValueError("提交中包含未发布或无权访问的题目")

    details = []
    correct = 0
    for item in answers:
        question = qmap[int(item["question_id"])]
        answer = str(item.get("answer") or "")
        is_ok = _judge(question, answer)
        correct += int(is_ok)
        details.append({
            "question_id": question.id,
            "your": answer,
            "correct": question.answer,
            "is_correct": is_ok,
            "analysis": question.analysis,
            "stem": question.stem,
            "kp_id": question.kp_id,
            "qtype": question.qtype,
        })
    total = len(details)
    return {
        "question_ids": qids,
        "total": total,
        "correct": correct,
        "score": round(correct / total * 100, 1),
        "details": details,
    }


def _save_answers(db: Session, student_id: int, course_id: int,
                  test_type: str, details: list[dict],
                  test_id: int | None) -> list[TestAnswer]:
    rows = []
    for item in details:
        row = TestAnswer(
            student_id=student_id,
            course_id=course_id,
            test_type=test_type,
            test_id=test_id,
            question_id=item["question_id"],
            answer=item["your"],
            is_correct=item["is_correct"],
        )
        db.add(row)
        rows.append(row)
    db.flush()
    return rows


def _judge(q: Question, answer: str) -> bool:
    a = (answer or "").strip().upper()
    b = (q.answer or "").strip().upper()
    if not a or not b:
        return False
    if q.qtype in ("single", "multiple", "judge"):
        return set(a) == set(b.replace("，", ",").replace(",", "")) or a == b
    # 填空/简答：包含关键字
    return b in a or a in b


def _by_kp(db: Session, student_id: int, course_id: int,
           assessed_kp_ids: set[int] | None = None) -> list[dict]:
    rows = db.query(KnowledgeMastery, KnowledgePoint).join(
        KnowledgePoint, KnowledgePoint.id == KnowledgeMastery.kp_id
    ).filter(
        KnowledgeMastery.student_id == student_id,
        KnowledgeMastery.course_id == course_id).all()
    out = []
    for mastery, kp in rows:
        assessed = assessed_kp_ids is None or mastery.kp_id in assessed_kp_ids
        out.append({
            "kp_id": mastery.kp_id,
            "name": kp.name,
            "pre": mastery.pre_score,
            "post": mastery.post_score if assessed else None,
            "improvement": round(mastery.post_score - mastery.pre_score, 1) if assessed else None,
            "assessed": assessed,
        })
    return out


def compare(db: Session, student_id: int, course_id: int) -> dict:
    pre = db.query(PreTest).filter(PreTest.student_id == student_id,
                                   PreTest.course_id == course_id).order_by(PreTest.id.desc()).first()
    post = db.query(PostTest).filter(PostTest.student_id == student_id,
                                     PostTest.course_id == course_id).order_by(PostTest.id.desc()).first()
    pre_score = pre.score if pre else 0.0
    post_score = post.score if post else 0.0
    by_kp = safe_json_loads(post.by_kp, []) if post and post.by_kp else []
    if post and isinstance(by_kp, list):
        assessed_ids = _assessed_kp_ids(db, post)
        current_names = dict(db.query(KnowledgePoint.id, KnowledgePoint.name).filter(
            KnowledgePoint.course_id == course_id,
        ).all())
        for item in by_kp:
            if not isinstance(item, dict):
                continue
            try:
                kp_id = int(item.get("kp_id"))
            except (TypeError, ValueError):
                continue
            stored_assessed = item.get("assessed")
            assessed = (
                bool(stored_assessed)
                if stored_assessed is not None
                else (kp_id in assessed_ids if assessed_ids else item.get("post") is not None)
            )
            if assessed_ids:
                assessed = kp_id in assessed_ids
            item["name"] = current_names.get(kp_id) or item.get("name")
            item["assessed"] = assessed
            if not assessed:
                item["post"] = None
                item["improvement"] = None
    assessed_count = sum(1 for item in by_kp if isinstance(item, dict) and item.get("assessed") is not False)
    return {"pre_score": pre_score, "post_score": post_score,
            "improvement": round(post_score - pre_score, 1), "by_kp": by_kp,
            "assessed_kp_count": assessed_count,
            "pending_kp_count": max(0, len(by_kp) - assessed_count)}


def _assessed_kp_ids(db: Session, post: PostTest) -> set[int]:
    rows = db.query(Question.kp_id).join(
        TestAnswer, TestAnswer.question_id == Question.id
    ).filter(
        TestAnswer.student_id == post.student_id,
        TestAnswer.course_id == post.course_id,
        TestAnswer.test_type == "post",
        TestAnswer.test_id == post.id,
        Question.kp_id.is_not(None),
    ).distinct().all()
    return {int(kp_id) for (kp_id,) in rows if kp_id is not None}
