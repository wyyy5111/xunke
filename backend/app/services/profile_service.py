"""学生画像与知识点掌握度计算。"""
from __future__ import annotations
from typing import List, Optional
from sqlalchemy.orm import Session

from app.models.profile import StudentProfile, KnowledgeMastery
from app.models.knowledge import KnowledgePoint
from app.models.question import Question
from app.models.test import PreTest, TestAnswer
from app.models.user import User
from app.services.llm_client import llm_client
from app.utils.time_util import safe_json_dumps, safe_json_loads


def compute_mastery(db: Session, student_id: int, course_id: int,
                    answers: List[TestAnswer], kps: List[KnowledgePoint]) -> dict:
    """根据答题正确率 + 题目难度 + 知识点权重计算 mastery_score。

    mastery = 100 * Σ(正确 * 难度权重 * 知识点权重) / Σ(难度权重 * 知识点权重)
    """
    kp_map = {kp.id: kp for kp in kps}
    # 按题目聚合答案
    qids = [a.question_id for a in answers]
    questions = db.query(Question).filter(Question.id.in_(qids)).all() if qids else []
    qmap = {q.id: q for q in questions}

    # 每个知识点：总分母、总分子的累加
    acc = {kp.id: {"denom": 0.0, "num": 0.0, "correct": 0, "total": 0} for kp in kps}

    for a in answers:
        q = qmap.get(a.question_id)
        if not q or q.kp_id is None:
            continue
        if q.kp_id not in acc:
            continue
        diff_w = max(0.2, q.difficulty / 5.0)  # 难度越高权重越大
        kp = kp_map.get(q.kp_id)
        imp = kp.importance if kp else 0.5
        w = diff_w * imp
        acc[q.kp_id]["denom"] += w
        acc[q.kp_id]["total"] += 1
        if a.is_correct:
            acc[q.kp_id]["num"] += w
            acc[q.kp_id]["correct"] += 1

    result = {}
    for kp in kps:
        a = acc[kp.id]
        score = (a["num"] / a["denom"] * 100) if a["denom"] > 0 else 50.0
        status = "mastered" if score >= 80 else ("consolidated" if score >= 60 else "weak")
        result[kp.id] = {"score": round(score, 1), "status": status,
                         "correct": a["correct"], "total": a["total"]}
    return result


def save_mastery(db: Session, student_id: int, course_id: int, scores: dict,
                 kps: List[KnowledgePoint], pre: bool = True,
                 commit: bool = True) -> None:
    for kp in kps:
        item = scores.get(kp.id, {"score": 50.0, "status": "weak"})
        row = db.query(KnowledgeMastery).filter(
            KnowledgeMastery.student_id == student_id,
            KnowledgeMastery.course_id == course_id,
            KnowledgeMastery.kp_id == kp.id,
        ).first()
        if not row:
            row = KnowledgeMastery(student_id=student_id, course_id=course_id, kp_id=kp.id)
            db.add(row)
        if pre:
            row.mastery_score = item["score"]
            row.status = item["status"]
            row.pre_score = item["score"]
        else:
            # 后测未覆盖的知识点沿用前测值，避免“没抽到题”被错误写成 50 分。
            post_score = item["score"] if item.get("total", 0) > 0 else (
                row.pre_score if row.pre_score is not None else row.mastery_score
            )
            row.post_score = post_score
            row.mastery_score = post_score
            row.status = "mastered" if post_score >= 80 else (
                "consolidated" if post_score >= 60 else "weak")
    if commit:
        db.commit()


def build_profile(db: Session, student_id: int, course_id: int,
                  goal: str = "", weekly_hours: int = 6,
                  trace_id: Optional[str] = None,
                  answers: Optional[List[TestAnswer]] = None) -> StudentProfile:
    """根据前测结果 + LLM 诊断生成画像。"""
    kps = db.query(KnowledgePoint).filter(KnowledgePoint.course_id == course_id).all()
    student = db.get(User, student_id)
    declared_preferences = [
        item.strip()
        for item in ((student.learning_preferences if student else "") or "").split(",")
        if item.strip()
    ]
    if answers is None:
        latest = db.query(PreTest).filter(
            PreTest.student_id == student_id,
            PreTest.course_id == course_id,
        ).order_by(PreTest.id.desc()).first()
        q = db.query(TestAnswer).filter(
            TestAnswer.student_id == student_id,
            TestAnswer.course_id == course_id,
            TestAnswer.test_type == "pre",
        )
        if latest:
            q = q.filter(TestAnswer.test_id == latest.id)
        answers = q.all()
    scores = compute_mastery(db, student_id, course_id, answers, kps)
    save_mastery(db, student_id, course_id, scores, kps, pre=True)

    weak = [{"id": kp.id, "name": kp.name, "score": scores[kp.id]["score"]}
            for kp in kps if scores[kp.id]["status"] == "weak"]
    consolidated = [{"id": kp.id, "name": kp.name, "score": scores[kp.id]["score"]}
                    for kp in kps if scores[kp.id]["status"] == "consolidated"]
    mastered = [{"id": kp.id, "name": kp.name} for kp in kps if scores[kp.id]["status"] == "mastered"]

    correct = sum(1 for a in answers if a.is_correct)
    total = len(answers)
    pre_score = round(correct / total * 100, 1) if total else 0.0

    # 调用诊断 Agent（LLM）
    diag_prompt = (
        f"请根据以下学生前测数据生成学生画像 JSON（字段：base_level, pref_style, pref_format, "
        f"learning_speed, weak_points 列表, recommendation）。\n"
        f"学习目标：{goal}；每周学时：{weekly_hours}；"
        f"学生主动选择的学习偏好：{declared_preferences or ['文本精读', '视觉图解', '实践演练']}；"
        f"前测正确率：{pre_score}%。\n"
        f"薄弱知识点：{[w['name'] for w in weak]}。\n"
        f"已掌握知识点：{[m['name'] for m in mastered]}。\n"
        f"只返回 JSON。"
    )
    diag = llm_client.chat_json(
        diag_prompt,
        purpose="diagnosis",
        trace_id=trace_id,
        max_tokens=900,
    )
    if not isinstance(diag, dict):
        diag = {}

    weak_names = [w["name"] for w in weak]
    recommendation = diag.get("recommendation") or (
        f"建议优先补强 {len(weak_names)} 个薄弱知识点：{', '.join(weak_names[:5])}；"
        f"已掌握 {len(mastered)} 个知识点，可适度挑战综合题。"
    )
    recommendation = str(recommendation)[:4000]

    profile = db.query(StudentProfile).filter(
        StudentProfile.student_id == student_id,
        StudentProfile.course_id == course_id,
    ).first()
    if not profile:
        profile = StudentProfile(student_id=student_id, course_id=course_id)
        db.add(profile)
    profile.stage = "learning"
    profile.goal = goal
    profile.weekly_hours = weekly_hours
    fallback_level = "basic" if pre_score < 60 else "intermediate" if pre_score < 85 else "advanced"
    level = str(diag.get("base_level", fallback_level)).lower()
    speed = str(diag.get("learning_speed", "slow" if pre_score < 50 else "normal")).lower()
    profile.base_level = level if level in {"basic", "intermediate", "advanced"} else fallback_level
    if declared_preferences:
        profile.pref_format = ",".join(declared_preferences)[:64]
        profile.pref_style = (
            "实践型" if "实践演练" in declared_preferences
            else "图解型" if "视觉图解" in declared_preferences
            else "探究型" if "案例研讨" in declared_preferences
            else "理解型"
        )
    else:
        profile.pref_style = str(diag.get("pref_style") or "理解型")[:32]
        profile.pref_format = str(diag.get("pref_format") or "文字,图解,案例")[:64]
    profile.learning_speed = speed if speed in {"slow", "normal", "fast"} else "normal"
    profile.pre_score = pre_score
    profile.weak_points = safe_json_dumps(weak)
    profile.recommendation = recommendation
    profile.extra = safe_json_dumps({
        "mastered": mastered,
        "consolidated": consolidated,
        "diagnosis": diag,
    })
    db.commit()
    return profile


def get_profile(db: Session, student_id: int, course_id: int) -> StudentProfile | None:
    return db.query(StudentProfile).filter(
        StudentProfile.student_id == student_id,
        StudentProfile.course_id == course_id,
    ).first()


def mastery_list(db: Session, student_id: int, course_id: int) -> list[dict]:
    rows = db.query(KnowledgeMastery, KnowledgePoint).join(
        KnowledgePoint, KnowledgePoint.id == KnowledgeMastery.kp_id
    ).filter(
        KnowledgeMastery.student_id == student_id,
        KnowledgeMastery.course_id == course_id,
    ).all()
    return [{"kp_id": m.kp_id, "name": kp.name, "mastery_score": m.mastery_score,
             "status": m.status, "pre_score": m.pre_score, "post_score": m.post_score}
            for m, kp in rows]


def sync_profile_mastery_summary(
    db: Session,
    profile: StudentProfile,
    *,
    commit: bool = False,
) -> dict[str, list[dict]]:
    """Synchronize profile labels/counts with the mastery source of truth."""
    rows = db.query(KnowledgeMastery, KnowledgePoint).join(
        KnowledgePoint, KnowledgePoint.id == KnowledgeMastery.kp_id
    ).filter(
        KnowledgeMastery.student_id == profile.student_id,
        KnowledgeMastery.course_id == profile.course_id,
    ).order_by(KnowledgePoint.id.asc()).all()
    groups: dict[str, list[dict]] = {
        "weak": [],
        "consolidated": [],
        "mastered": [],
    }
    for mastery, point in rows:
        status = mastery.status if mastery.status in groups else (
            "mastered" if mastery.mastery_score >= 80
            else "consolidated" if mastery.mastery_score >= 60
            else "weak"
        )
        groups[status].append({
            "id": point.id,
            "name": point.name,
            "score": round(float(mastery.mastery_score or 0), 1),
        })

    profile.weak_points = safe_json_dumps(groups["weak"])
    extra = safe_json_loads(profile.extra, {})
    if not isinstance(extra, dict):
        extra = {}
    extra["mastered"] = groups["mastered"]
    extra["consolidated"] = groups["consolidated"]
    profile.extra = safe_json_dumps(extra)

    if profile.stage == "post_test" or float(profile.post_score or 0) > 0:
        weak_names = [item["name"] for item in groups["weak"][:5]]
        consolidated_names = [item["name"] for item in groups["consolidated"][:5]]
        summary = (
            f"当前已掌握 {len(groups['mastered'])} 个知识点，"
            f"待巩固 {len(groups['consolidated'])} 个，"
            f"薄弱 {len(groups['weak'])} 个。"
        )
        actions = []
        if weak_names:
            actions.append(f"优先补强：{', '.join(weak_names)}")
        if consolidated_names:
            actions.append(f"随后巩固：{', '.join(consolidated_names)}")
        if not actions:
            actions.append("建议进入综合应用与迁移练习")
        profile.recommendation = summary + "；".join(actions) + "。"

    if commit:
        db.commit()
    return groups
