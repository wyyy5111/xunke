"""管理员：用户/配置/日志/看板。"""
from __future__ import annotations
from datetime import datetime, timezone
import json
from threading import RLock

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import Base, get_db
from app.core.deps import admin_only
from app.models.user import User
from app.models.course import Course, CourseEnrollment, CourseFile
from app.models.chunk import DocumentChunk
from app.models.learning import LearningPath, LearningRecord, WrongQuestion
from app.models.profile import KnowledgeMastery, StudentProfile
from app.models.quality import QualityReport
from app.models.question import Question
from app.models.resource import GeneratedResource, ResourceReview
from app.models.agent import AgentRun, AgentLog
from app.models.system import SystemConfig, LLMCallLog
from app.models.test import AssessmentAttempt, PostTest, PreTest, TestAnswer
from app.schemas.user import UserOut, UserRoleUpdate, UserUpdate
from app.schemas.common import R

router = APIRouter(prefix="/api/admin", tags=["admin"])
_user_governance_lock = RLock()


def _is_sensitive_key(key: str) -> bool:
    lowered = str(key or "").lower()
    return any(part in lowered for part in (
        "key", "secret", "token", "password", "credential", "private", "certificate"
    ))


def _llm_identity(provider: str, model: str) -> tuple[str, str]:
    """Hide obsolete local-engine labels without altering audit semantics."""
    provider_name = str(provider or "").lower()
    model_name = str(model or "").lower()
    if provider_name in {"builtin", "local"} or model_name in {"xunkeflow-builtin", "rule-engine"}:
        return "mock", "local-course-engine"
    return provider or "mock", model or "local-course-engine"


def _iso(value: datetime | None) -> str:
    return value.isoformat() if value else ""


def _count(db: Session, model: type) -> int:
    return int(db.query(func.count(model.id)).scalar() or 0)


def _count_by(db: Session, model: type, column) -> dict[str, int]:
    return {
        str(label if label not in {None, ""} else "unknown"): int(count)
        for label, count in db.query(column, func.count(model.id)).group_by(column).all()
    }


def _protect_last_active_admin(
    db: Session,
    target: User,
    *,
    next_role: str | None = None,
    next_active: bool | None = None,
) -> None:
    """Keep at least one enabled administrator after every user mutation.

    ``with_for_update`` serializes competing role/deactivation requests on
    databases that support row locks. The endpoint-level process lock provides
    the equivalent guard for the single-process SQLite competition runtime.
    """
    role_after = next_role if next_role is not None else target.role
    active_after = next_active if next_active is not None else target.is_active
    removes_active_admin = (
        target.role == "admin"
        and target.is_active
        and (role_after != "admin" or not active_after)
    )
    if not removes_active_admin:
        return
    active_admins = (
        db.query(User)
        .filter(User.role == "admin", User.is_active.is_(True))
        .with_for_update()
        .all()
    )
    if len(active_admins) <= 1:
        raise HTTPException(409, "系统必须保留至少一个启用的管理员账号")


def _database_backend_label() -> str:
    scheme = settings.DATABASE_URL.split(":", 1)[0].lower()
    return {
        "sqlite": "SQLite",
        "postgresql": "PostgreSQL",
        "postgresql+psycopg": "PostgreSQL",
        "mysql": "MySQL",
        "mysql+pymysql": "MySQL",
    }.get(scheme, "SQL 数据库")


def _runtime_status(db: Session, request: Request) -> dict:
    from app.services.llm_client import llm_client

    db.execute(select(1)).scalar_one()
    ai = llm_client.status()
    started_at = getattr(request.app.state, "started_at", None)
    now = datetime.now(timezone.utc)
    uptime_seconds = max(0, int((now - started_at).total_seconds())) if started_at else 0
    last_run = db.query(AgentRun).order_by(AgentRun.id.desc()).first()
    return {
        "database": {
            "status": "healthy",
            "backend": _database_backend_label(),
        },
        "ai": {
            "status": "healthy" if ai["mode"] == "real" else "demo",
            "mode": ai["mode"],
            "provider": ai["active_provider"],
            "model": ai["model"],
            "api_key_configured": ai["api_key_configured"],
            "degraded": bool(ai["last_call"].get("fallback_used")),
        },
        "agents": {
            "status": "running" if db.query(AgentRun).filter(AgentRun.status == "running").count() else "ready",
            "total": _count(db, AgentRun),
            "running": db.query(AgentRun).filter(AgentRun.status == "running").count(),
            "success": db.query(AgentRun).filter(AgentRun.status == "success").count(),
            "failed": db.query(AgentRun).filter(AgentRun.status == "failed").count(),
            "last_run_at": _iso(last_run.started_at if last_run else None),
        },
        "application": {
            "status": "healthy",
            "version": request.app.version,
            "started_at": _iso(started_at),
            "uptime_seconds": uptime_seconds,
        },
    }


def _build_data_snapshot(db: Session, request: Request) -> dict:
    """Create an explicit, non-restorable operational snapshot.

    Only allowlisted public fields and aggregate metrics are exported. In
    particular, configuration values, password hashes, auth material, raw
    document contents, filenames and storage paths never enter the payload.
    """
    table_counts = {
        table.name: int(db.execute(select(func.count()).select_from(table)).scalar_one())
        for table in Base.metadata.sorted_tables
    }
    users = db.query(User).order_by(User.id).all()
    courses = db.query(Course).order_by(Course.id).all()
    avg_pre = float(db.query(func.avg(PreTest.score)).scalar() or 0)
    avg_post = float(db.query(func.avg(PostTest.score)).scalar() or 0)
    avg_quality = float(db.query(func.avg(QualityReport.score)).scalar() or 0)
    avg_agent_duration = float(db.query(func.avg(AgentRun.duration_ms)).scalar() or 0)
    llm_total = _count(db, LLMCallLog)
    llm_success = db.query(LLMCallLog).filter(LLMCallLog.success.is_(True)).count()
    return {
        "snapshot": {
            "format": "xunkeflow-admin-snapshot-v1",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "application": settings.APP_NAME,
            "version": request.app.version,
            "restorable": False,
            "scope": "公开字段与业务聚合统计",
        },
        "table_counts": table_counts,
        "users": [
            {
                "id": row.id,
                "username": row.username,
                "full_name": row.full_name,
                "email": row.email,
                "role": row.role,
                "is_active": row.is_active,
                "created_at": _iso(row.created_at),
            }
            for row in users
        ],
        "courses": [
            {
                "id": row.id,
                "name": row.name,
                "code": row.code,
                "teacher_id": row.teacher_id,
                "status": row.status,
                "created_at": _iso(row.created_at),
            }
            for row in courses
        ],
        "business_summary": {
            "accounts": {
                "total": len(users),
                "active": sum(1 for row in users if row.is_active),
                "by_role": _count_by(db, User, User.role),
            },
            "course_operations": {
                "total": len(courses),
                "by_status": _count_by(db, Course, Course.status),
                "enrollments": _count(db, CourseEnrollment),
                "questions": _count(db, Question),
            },
            "knowledge_base": {
                "files": _count(db, CourseFile),
                "indexed_files": db.query(CourseFile).filter(CourseFile.indexed.is_(True)).count(),
                "by_parse_status": _count_by(db, CourseFile, CourseFile.parse_status),
                "by_file_type": _count_by(db, CourseFile, CourseFile.file_type),
                "chunks": _count(db, DocumentChunk),
            },
            "learning": {
                "profiles": _count(db, StudentProfile),
                "mastery_records": _count(db, KnowledgeMastery),
                "learning_paths": _count(db, LearningPath),
                "learning_records": _count(db, LearningRecord),
                "wrong_questions": _count(db, WrongQuestion),
                "resolved_wrong_questions": db.query(WrongQuestion).filter(WrongQuestion.resolved.is_(True)).count(),
            },
            "assessments": {
                "pre_tests": _count(db, PreTest),
                "post_tests": _count(db, PostTest),
                "answers": _count(db, TestAnswer),
                "attempts": _count(db, AssessmentAttempt),
                "attempts_by_status": _count_by(db, AssessmentAttempt, AssessmentAttempt.status),
                "average_pre_score": round(avg_pre, 2),
                "average_post_score": round(avg_post, 2),
            },
            "resources": {
                "total": _count(db, GeneratedResource),
                "published": db.query(GeneratedResource).filter(GeneratedResource.published.is_(True)).count(),
                "personalized": db.query(GeneratedResource).filter(GeneratedResource.is_personalized.is_(True)).count(),
                "reviews": _count(db, ResourceReview),
                "by_type": _count_by(db, GeneratedResource, GeneratedResource.rtype),
                "by_review_status": _count_by(db, GeneratedResource, GeneratedResource.review_status),
            },
            "quality": {
                "reports": _count(db, QualityReport),
                "average_score": round(avg_quality, 2),
            },
            "agents": {
                "runs": _count(db, AgentRun),
                "logs": _count(db, AgentLog),
                "by_status": _count_by(db, AgentRun, AgentRun.status),
                "by_workflow": _count_by(db, AgentRun, AgentRun.workflow),
                "average_duration_ms": round(avg_agent_duration, 2),
            },
            "ai_calls": {
                "total": llm_total,
                "successful": llm_success,
                "fallbacks": db.query(LLMCallLog).filter(LLMCallLog.fallback_used.is_(True)).count(),
                "success_rate": round(llm_success / llm_total * 100, 2) if llm_total else 100.0,
                "by_provider": _count_by(db, LLMCallLog, LLMCallLog.provider),
            },
        },
    }


@router.get("/users", response_model=R)
def users(db: Session = Depends(get_db), user: User = Depends(admin_only)):
    rows = db.query(User).order_by(User.id.desc()).all()
    return R.ok([UserOut.model_validate(u).model_dump(mode="json") for u in rows])


@router.put("/users/{uid}", response_model=R)
def update_user(uid: int, body: UserUpdate, db: Session = Depends(get_db),
                user: User = Depends(admin_only)):
    with _user_governance_lock:
        u = db.get(User, uid)
        if not u:
            raise HTTPException(404, "用户不存在")
        changes = body.model_dump(exclude_unset=True, exclude_none=True)
        _protect_last_active_admin(db, u, next_active=changes.get("is_active"))
        for k, v in changes.items():
            setattr(u, k, v)
        db.commit()
        db.refresh(u)
    return R.ok(UserOut.model_validate(u).model_dump(mode="json"))


@router.patch("/users/{uid}/role", response_model=R)
def update_user_role(uid: int, body: UserRoleUpdate, db: Session = Depends(get_db),
                     user: User = Depends(admin_only)):
    if uid == user.id:
        raise HTTPException(409, "为避免权限锁定，不能修改自己的管理员角色")
    with _user_governance_lock:
        target = db.get(User, uid)
        if not target:
            raise HTTPException(404, "用户不存在")
        _protect_last_active_admin(db, target, next_role=body.role)
        target.role = body.role
        db.commit()
        db.refresh(target)
    return R.ok(UserOut.model_validate(target).model_dump(mode="json"), "角色已更新")


@router.get("/data-snapshot", response_class=Response)
def export_data_snapshot(request: Request, db: Session = Depends(get_db),
                         user: User = Depends(admin_only)):
    snapshot = _build_data_snapshot(db, request)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    payload = json.dumps(snapshot, ensure_ascii=False, indent=2).encode("utf-8")
    return Response(
        content=payload,
        media_type="application/json; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="xunkeflow-data-snapshot-{stamp}.json"',
            "Cache-Control": "no-store",
            "X-Snapshot-Format": "xunkeflow-admin-snapshot-v1",
        },
    )


@router.get("/configs", response_model=R)
def configs(db: Session = Depends(get_db), user: User = Depends(admin_only)):
    rows = db.query(SystemConfig).order_by(SystemConfig.category, SystemConfig.key).all()
    return R.ok([{"id": r.id, "key": r.key,
                  "value": "(已安全配置)" if _is_sensitive_key(r.key) and r.value else r.value,
                  "configured": bool(r.value), "category": r.category,
                  "remark": r.remark} for r in rows])


@router.post("/configs", response_model=R)
def upsert_config(body: dict, db: Session = Depends(get_db),
                  user: User = Depends(admin_only)):
    key = body.get("key")
    if not key or _is_sensitive_key(str(key)):
        raise HTTPException(400, "敏感配置不能通过前端保存，请使用服务器 .env")
    val = body.get("value", "")
    cat = body.get("category", "general")
    row = db.query(SystemConfig).filter(SystemConfig.key == key).first()
    if not row:
        row = SystemConfig(key=key, value=val, category=cat)
        db.add(row)
    else:
        row.value = val
        row.category = cat
    db.commit()
    return R.ok({"key": key, "value": val})


@router.get("/llm_logs", response_model=R)
def llm_logs(limit: int = 100, db: Session = Depends(get_db),
             user: User = Depends(admin_only)):
    rows = db.query(LLMCallLog).order_by(LLMCallLog.id.desc()).limit(limit).all()
    return R.ok([{"id": r.id, "provider": _llm_identity(r.provider, r.model)[0],
                  "model": _llm_identity(r.provider, r.model)[1], "purpose": r.purpose,
                  "trace_id": r.trace_id, "prompt_tokens": r.prompt_tokens,
                  "completion_tokens": r.completion_tokens, "duration_ms": r.duration_ms,
                  "response_chars": r.response_chars, "retry_count": r.retry_count,
                  "fallback_used": r.fallback_used,
                  "estimated_cost": r.estimated_cost,
                  "success": r.success, "error": r.error,
                  "created_at": r.created_at.isoformat() if r.created_at else ""} for r in rows])


@router.get("/dashboard", response_model=R)
def dashboard(request: Request, db: Session = Depends(get_db), user: User = Depends(admin_only)):
    """全局统计看板。"""
    active_course_ids = [row[0] for row in db.query(Course.id).filter(Course.status == "active").all()]
    scoped_course_ids = active_course_ids or [-1]
    resource_q = db.query(GeneratedResource).filter(GeneratedResource.course_id.in_(scoped_course_ids))
    run_q = db.query(AgentRun).filter(AgentRun.course_id.in_(scoped_course_ids))
    total_users = db.query(func.count(User.id)).scalar()
    total_courses = len(active_course_ids)
    total_resources = resource_q.count()
    published = resource_q.filter(GeneratedResource.published == True).count()
    approved_rate = round(published / total_resources * 100, 1) if total_resources else 0
    agent_runs = run_q.count()
    success_runs = run_q.filter(AgentRun.status == "success").count()
    failed_runs = run_q.filter(AgentRun.status == "failed").count()
    llm_calls = db.query(func.count(LLMCallLog.id)).scalar()
    llm_success = db.query(func.count(LLMCallLog.id)).filter(LLMCallLog.success == True).scalar()

    role_distribution = [
        {"name": role or "unknown", "value": count}
        for role, count in db.query(User.role, func.count(User.id)).group_by(User.role).all()
    ]
    resource_distribution = [
        {"name": rtype or "unknown", "value": count}
        for rtype, count in db.query(GeneratedResource.rtype, func.count(GeneratedResource.id))
        .filter(GeneratedResource.course_id.in_(scoped_course_ids))
        .group_by(GeneratedResource.rtype).all()
    ]
    review_distribution = [
        {"name": status or "unknown", "value": count}
        for status, count in db.query(GeneratedResource.review_status, func.count(GeneratedResource.id))
        .filter(GeneratedResource.course_id.in_(scoped_course_ids))
        .group_by(GeneratedResource.review_status).all()
    ]
    course_cards = []
    for c in db.query(Course).filter(Course.status == "active").order_by(Course.id).all():
        resources = db.query(func.count(GeneratedResource.id)).filter(GeneratedResource.course_id == c.id).scalar()
        runs = db.query(func.count(AgentRun.id)).filter(AgentRun.course_id == c.id).scalar()
        course_cards.append({
            "id": c.id,
            "name": c.name,
            "code": c.code,
            "tags": c.tags,
            "resources": resources,
            "agent_runs": runs,
        })
    recent_runs = run_q.order_by(AgentRun.id.desc()).limit(8).all()
    recent_llm = db.query(LLMCallLog).order_by(LLMCallLog.id.desc()).limit(8).all()
    return R.ok({
        "total_users": total_users, "total_courses": total_courses,
        "total_resources": total_resources, "published": published,
        "approved_rate": approved_rate, "agent_runs": agent_runs,
        "success_runs": success_runs, "failed_runs": failed_runs,
        "llm_calls": llm_calls,
        "llm_success_rate": round(llm_success / llm_calls * 100, 1) if llm_calls else 100,
        "role_distribution": role_distribution,
        "resource_distribution": resource_distribution,
        "review_distribution": review_distribution,
        "course_cards": course_cards,
        "recent_runs": [{
            "id": r.id,
            "trace_id": r.trace_id,
            "workflow": r.workflow,
            "status": r.status,
            "course_id": r.course_id,
            "duration_ms": r.duration_ms,
            "started_at": r.started_at.isoformat() if r.started_at else "",
        } for r in recent_runs],
        "recent_llm": [{
            "id": l.id,
            "provider": _llm_identity(l.provider, l.model)[0],
            "model": _llm_identity(l.provider, l.model)[1],
            "purpose": l.purpose,
            "success": l.success,
            "duration_ms": l.duration_ms,
            "created_at": l.created_at.isoformat() if l.created_at else "",
        } for l in recent_llm],
        "runtime_status": _runtime_status(db, request),
    })
