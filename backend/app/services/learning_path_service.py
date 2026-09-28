"""学习路径规划：基于知识图谱先修关系 + 学生薄弱点排序。"""
from __future__ import annotations
from collections import defaultdict, deque
from datetime import datetime
from typing import List
from sqlalchemy.orm import Session

from app.models.knowledge import KnowledgePoint, KnowledgeRelation
from app.models.profile import StudentProfile, KnowledgeMastery
from app.models.learning import LearningPath, LearningRecord
from app.models.resource import GeneratedResource
from app.utils.time_util import safe_json_dumps, safe_json_loads


def plan_path(db: Session, student_id: int, course_id: int) -> LearningPath:
    kps = db.query(KnowledgePoint).filter(KnowledgePoint.course_id == course_id).all()
    rels = db.query(KnowledgeRelation).filter(
        KnowledgeRelation.course_id == course_id,
        KnowledgeRelation.relation == "prerequisite",
    ).all()
    mastery = {m.kp_id: m.mastery_score for m in db.query(KnowledgeMastery).filter(
        KnowledgeMastery.student_id == student_id, KnowledgeMastery.course_id == course_id).all()}
    profile = db.query(StudentProfile).filter(
        StudentProfile.student_id == student_id, StudentProfile.course_id == course_id).first()

    # 拓扑排序（先修关系）
    indeg = {kp.id: 0 for kp in kps}
    adj = defaultdict(list)
    for r in rels:
        adj[r.source_id].append(r.target_id)
        indeg[r.target_id] = indeg.get(r.target_id, 0) + 1

    # 优先：薄弱 + 基础（入度小、难度低）
    q = sorted([kp for kp in kps if indeg[kp.id] == 0],
               key=lambda kp: (mastery.get(kp.id, 50), kp.difficulty, -kp.importance))
    queue = deque(q)
    visited = set()
    order: List[int] = []
    while queue:
        kp = queue.popleft()
        if kp.id in visited:
            continue
        visited.add(kp.id)
        order.append(kp.id)
        nexts = []
        for tid in adj[kp.id]:
            indeg[tid] -= 1
            if indeg[tid] <= 0:
                nexts.append(tid)
        # 子节点按薄弱度排序
        nexts_kps = [k for k in kps if k.id in nexts]
        nexts_kps.sort(key=lambda k: (mastery.get(k.id, 50), k.difficulty))
        for k in nexts_kps:
            queue.append(k)

    # 补漏
    for kp in kps:
        if kp.id not in visited:
            order.append(kp.id)

    existing_path = db.query(LearningPath).filter(
        LearningPath.student_id == student_id, LearningPath.course_id == course_id).first()
    previous_nodes = safe_json_loads(existing_path.nodes, []) if existing_path else []
    previous_status = {
        int(n.get("kp_id")): n.get("status", "pending")
        for n in previous_nodes if isinstance(n, dict) and n.get("kp_id") is not None
    }

    # 构造节点
    kp_map = {kp.id: kp for kp in kps}
    nodes = []
    total_min = 0
    for idx, kid in enumerate(order, 1):
        kp = kp_map[kid]
        score = mastery.get(kid, 50)
        minutes = max(20, int(60 * (1 - score / 100) + kp.difficulty * 10))
        total_min += minutes
        nodes.append({
            "order": idx,
            "kp_id": kp.id,
            "name": kp.name,
            "difficulty": kp.difficulty,
            "mastery": score,
            "estimated_minutes": minutes,
            "status": previous_status.get(kp.id, "pending"),
        })

    lp = existing_path
    if not lp:
        lp = LearningPath(student_id=student_id, course_id=course_id)
        db.add(lp)
    lp.nodes = safe_json_dumps(nodes)
    lp.total_minutes = total_min
    lp.completed_nodes = sum(1 for n in nodes if n["status"] == "done")
    if profile:
        lp.profile_id = profile.id
    db.commit()
    return lp


def add_learning_record(db: Session, student_id: int, course_id: int,
                        action: str, duration: int = 0,
                        resource_id: int | None = None,
                        kp_id: int | None = None,
                        commit: bool = True) -> LearningRecord:
    if action not in {"view", "finish", "practice", "answer", "pre_test", "post_test"}:
        raise ValueError("不支持的学习记录类型")
    if resource_id is not None:
        resource = db.get(GeneratedResource, resource_id)
        if not resource or resource.course_id != course_id:
            raise ValueError("资源不存在或不属于当前课程")
    if kp_id is not None:
        kp = db.get(KnowledgePoint, kp_id)
        if not kp or kp.course_id != course_id:
            raise ValueError("知识点不存在或不属于当前课程")
    row = LearningRecord(
        student_id=student_id,
        course_id=course_id,
        resource_id=resource_id,
        kp_id=kp_id,
        action=action,
        duration=max(0, int(duration or 0)),
        happened_at=datetime.now(),
    )
    db.add(row)
    if commit:
        db.commit()
        db.refresh(row)
    else:
        db.flush()
    return row


def update_path_progress(db: Session, student_id: int, course_id: int,
                         kp_id: int, status: str = "done", duration: int = 0,
                         resource_id: int | None = None) -> LearningPath:
    if status not in {"pending", "learning", "done"}:
        raise ValueError("学习节点状态不合法")
    lp = db.query(LearningPath).filter(
        LearningPath.student_id == student_id,
        LearningPath.course_id == course_id,
    ).first()
    if not lp:
        lp = plan_path(db, student_id, course_id)
    nodes = safe_json_loads(lp.nodes, []) or []
    target = None
    for node in nodes:
        if isinstance(node, dict) and int(node.get("kp_id", 0)) == kp_id:
            target = node
            break
    if target is None:
        raise ValueError("学习路径中不存在该知识点")
    target["status"] = status
    lp.nodes = safe_json_dumps(nodes)
    lp.completed_nodes = sum(
        1 for node in nodes if isinstance(node, dict) and node.get("status") == "done"
    )
    add_learning_record(
        db,
        student_id,
        course_id,
        action="finish" if status == "done" else "view",
        duration=duration,
        resource_id=resource_id,
        kp_id=kp_id,
        commit=False,
    )
    db.commit()
    db.refresh(lp)
    return lp


def learning_records(db: Session, student_id: int, course_id: int,
                     limit: int = 100) -> list[dict]:
    rows = db.query(LearningRecord).filter(
        LearningRecord.student_id == student_id,
        LearningRecord.course_id == course_id,
    ).order_by(LearningRecord.id.desc()).limit(max(1, min(limit, 500))).all()
    return [{
        "id": row.id,
        "course_id": row.course_id,
        "resource_id": row.resource_id,
        "kp_id": row.kp_id,
        "action": row.action,
        "duration": row.duration,
        "happened_at": row.happened_at.isoformat() if row.happened_at else "",
    } for row in rows]
