"""智能体工作流 / 日志查询。"""
from __future__ import annotations
from datetime import timedelta
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.core.database import get_db
from app.core.deps import any_role, get_current_user
from app.models.agent import AgentRun, AgentLog
from app.models.course import Course, CourseFile, CourseEnrollment
from app.models.resource import GeneratedResource
from app.models.system import LLMCallLog
from app.models.user import User
from app.models.profile import StudentProfile
from app.models.quality import QualityReport
from app.agents.orchestrator import create_full_pipeline_run, execute_full_pipeline_task
from app.rag.retriever import current_resource_citations
from app.schemas.agent import RunWorkflowIn, AgentRunOut, AgentLogOut
from app.schemas.common import R
import json

from app.utils.time_util import utc_now

router = APIRouter(prefix="/api/agents", tags=["agent"])

_STALE_RUN_ERROR = "任务执行进程中断或超时，系统已回收；可从失败记录重新发起。"


@router.post("/run", response_model=R)
def run(body: RunWorkflowIn, background: BackgroundTasks, db: Session = Depends(get_db),
       user: User = Depends(any_role)):
    _reap_stale_runs(db, body.course_id)
    course = _ensure_course_access(db, body.course_id, user)
    if course.status != "active":
        raise HTTPException(409, "课程已归档，不能启动新的智能体任务")
    if user.role == "student":
        if body.student_id is not None and body.student_id != user.id:
            raise HTTPException(403, "学生不能为其他学生启动个性化任务")
        sid = user.id
    else:
        sid = body.student_id
    if sid:
        student = db.get(User, sid)
        enrolled = db.query(CourseEnrollment).filter(
            CourseEnrollment.course_id == body.course_id,
            CourseEnrollment.student_id == sid,
        ).first()
        if not student or student.role != "student" or not enrolled:
            raise HTTPException(400, "指定学生不存在或尚未加入该课程")
    profile = None
    if sid:
        profile = db.query(StudentProfile).filter(
            StudentProfile.course_id == body.course_id,
            StudentProfile.student_id == sid
        ).order_by(StudentProfile.id.asc()).first()
    else:
        # 教师/管理员录制演示时自动补齐代表学生画像，让诊断与路径规划节点也真实执行。
        profile = db.query(StudentProfile).filter(
            StudentProfile.course_id == body.course_id
        ).order_by(StudentProfile.id.asc()).first()
        sid = profile.student_id if profile else None

    course_file = db.query(CourseFile).filter(
        CourseFile.course_id == body.course_id
    ).order_by(CourseFile.indexed.desc(), CourseFile.id.desc()).first()

    existing = db.query(AgentRun).filter(
        AgentRun.course_id == body.course_id,
        AgentRun.student_id == sid,
        AgentRun.workflow == "full_pipeline",
        AgentRun.status == "running",
    ).order_by(AgentRun.id.desc()).first()
    if existing:
        return R.ok({
            "trace_id": existing.trace_id,
            "run_id": existing.id,
            "status": existing.status,
            "deduplicated": True,
        })

    run = create_full_pipeline_run(
        db, body.course_id, sid, file_id=course_file.id if course_file else None
    )
    background.add_task(
        execute_full_pipeline_task,
        run.id,
        profile.goal if profile else "",
        profile.weekly_hours if profile else 6,
        None,
        course_file.id if course_file else None,
    )
    return R.ok({"trace_id": run.trace_id, "run_id": run.id, "status": run.status})


@router.post("/runs/{run_id}/retry", response_model=R)
def retry_run(run_id: int, background: BackgroundTasks,
              db: Session = Depends(get_db), user: User = Depends(any_role)):
    """Retry a failed full pipeline as a new trace, preserving the old audit log."""
    original = db.get(AgentRun, run_id)
    if not original:
        raise HTTPException(404, "运行不存在")
    _ensure_run_access(db, original, user)
    if original.workflow != "full_pipeline" or original.status != "failed":
        raise HTTPException(409, "只有失败的完整协作任务可以重试")
    _reap_stale_runs(db, int(original.course_id or 0))
    course = db.get(Course, original.course_id)
    if not course or course.status != "active":
        raise HTTPException(409, "课程不存在或已归档，不能重试任务")

    active = db.query(AgentRun).filter(
        AgentRun.course_id == original.course_id,
        AgentRun.student_id == original.student_id,
        AgentRun.workflow == "full_pipeline",
        AgentRun.status == "running",
    ).order_by(AgentRun.id.desc()).first()
    if active:
        return R.ok({
            "trace_id": active.trace_id,
            "run_id": active.id,
            "status": active.status,
            "deduplicated": True,
        })

    input_summary = _json_loads(original.input_summary, {})
    file_id = input_summary.get("file_id")
    course_file = db.get(CourseFile, file_id) if file_id else None
    if course_file and course_file.course_id != original.course_id:
        course_file = None
    if not course_file:
        course_file = db.query(CourseFile).filter(
            CourseFile.course_id == original.course_id,
        ).order_by(CourseFile.indexed.desc(), CourseFile.id.desc()).first()
    profile = None
    if original.student_id:
        profile = db.query(StudentProfile).filter(
            StudentProfile.course_id == original.course_id,
            StudentProfile.student_id == original.student_id,
        ).order_by(StudentProfile.id.asc()).first()
    rerun = create_full_pipeline_run(
        db,
        int(original.course_id or 0),
        original.student_id,
        file_id=course_file.id if course_file else None,
    )
    background.add_task(
        execute_full_pipeline_task,
        rerun.id,
        profile.goal if profile else "",
        profile.weekly_hours if profile else 6,
        None,
        course_file.id if course_file else None,
    )
    return R.ok({
        "trace_id": rerun.trace_id,
        "run_id": rerun.id,
        "status": rerun.status,
        "retried_from": original.id,
    })


@router.get("/runs", response_model=R)
def list_runs(limit: int = 20, course_id: int = 0, db: Session = Depends(get_db),
              user: User = Depends(any_role)):
    _reap_stale_runs(db, course_id or None)
    query = db.query(AgentRun)
    if course_id:
        _ensure_course_access(db, course_id, user)
        query = query.filter(AgentRun.course_id == course_id)
    if user.role == "student":
        query = query.filter(AgentRun.student_id == user.id)
    elif user.role == "teacher":
        course_ids = [row[0] for row in db.query(Course.id).filter(Course.teacher_id == user.id).all()]
        query = query.filter(AgentRun.course_id.in_(course_ids or [-1]))
    rows = query.order_by(AgentRun.id.desc()).limit(min(max(limit, 1), 100)).all()
    return R.ok([_run(r, with_logs=False) for r in rows])


@router.get("/command_center", response_model=R)
def command_center(course_id: int = 0, db: Session = Depends(get_db),
                   user: User = Depends(any_role)):
    """面向演示与答辩的 AI 智能体指挥舱聚合数据。"""
    _reap_stale_runs(db, course_id or None)
    if course_id:
        _ensure_course_access(db, course_id, user)
    run_q = db.query(AgentRun)
    if course_id:
        run_q = run_q.filter(AgentRun.course_id == course_id)
    if user.role == "student":
        run_q = run_q.filter(AgentRun.student_id == user.id)
    elif user.role == "teacher":
        course_ids = [row[0] for row in db.query(Course.id).filter(Course.teacher_id == user.id).all()]
        run_q = run_q.filter(AgentRun.course_id.in_(course_ids or [-1]))

    runs = run_q.order_by(AgentRun.id.desc()).limit(12).all()
    # The command center always renders the complete ten-step collaboration
    # pipeline. A newer one-step parse/generate run must remain visible in the
    # history table, but must not replace the active full-pipeline snapshot or
    # the page would report 100% while showing only one completed agent.
    latest = next((item for item in runs if item.workflow == "full_pipeline"), None)
    if latest is None:
        latest = runs[0] if runs else None
    latest_logs = []
    if latest:
        latest_logs = db.query(AgentLog).filter(AgentLog.run_id == latest.id).order_by(AgentLog.step).all()

    llm_q = db.query(LLMCallLog)
    if latest:
        trace_ids = [r.trace_id for r in runs]
        llm_q = llm_q.filter(LLMCallLog.trace_id.in_(trace_ids))
    elif not latest:
        llm_q = llm_q.filter(LLMCallLog.id == -1)
    llm_logs = llm_q.order_by(LLMCallLog.id.desc()).limit(24).all()

    res_q = db.query(GeneratedResource)
    if course_id:
        res_q = res_q.filter(GeneratedResource.course_id == course_id)
    elif latest and latest.course_id:
        res_q = res_q.filter(GeneratedResource.course_id == latest.course_id)
    if user.role == "student":
        enrolled_ids = [row[0] for row in db.query(CourseEnrollment.course_id).filter(
            CourseEnrollment.student_id == user.id
        ).all()]
        res_q = res_q.filter(
            GeneratedResource.course_id.in_(enrolled_ids or [-1]),
            GeneratedResource.published == True,
            (GeneratedResource.student_id == user.id) | (GeneratedResource.student_id.is_(None)),
        )
    elif user.role == "teacher":
        managed_ids = [row[0] for row in db.query(Course.id).filter(Course.teacher_id == user.id).all()]
        res_q = res_q.filter(GeneratedResource.course_id.in_(managed_ids or [-1]))
    resources = res_q.order_by(GeneratedResource.id.desc()).limit(16).all()
    if latest:
        latest_resources = db.query(GeneratedResource).filter(
            GeneratedResource.agent_run_id == latest.id
        )
        if user.role == "student":
            latest_resources = latest_resources.filter(
                GeneratedResource.published == True,
                (GeneratedResource.student_id == user.id) | (GeneratedResource.student_id.is_(None)),
            )
        latest_resources = latest_resources.order_by(GeneratedResource.id.desc()).all()
        if latest_resources:
            resources = latest_resources

    total_runs = run_q.count()
    success_runs = run_q.filter(AgentRun.status == "success").count()
    # Timeout/interruption runs use the operational timeout threshold as their
    # duration.  Mixing those failures into the normal latency KPI would make
    # a healthy millisecond-scale workflow look minutes long.
    avg_duration = run_q.filter(
        AgentRun.status == "success"
    ).with_entities(func.avg(AgentRun.duration_ms)).scalar() or 0
    total_tokens = sum((l.prompt_tokens or 0) + (l.completion_tokens or 0) for l in llm_logs)
    avg_quality = round(sum(r.quality_score for r in resources) / max(1, len(resources)), 1) if resources else 0
    resource_citation_map = current_resource_citations(db, resources)
    citation_count = 0
    evidence = []
    for r in resources:
        cites = resource_citation_map.get(r.id, [])
        citation_count += len(cites)
        for c in cites[:3]:
            if len(evidence) >= 24:
                break
            evidence.append({
                "resource_id": r.id,
                "resource": r.title,
                "rtype": r.rtype,
                "source": c.get("source", "课程资料"),
                "page": c.get("page", 1),
                "score": round(float(c.get("score", 0)) * 100),
                "snippet": c.get("snippet", "")[:120],
            })

    course = db.get(Course, latest.course_id) if latest and latest.course_id else None
    if not course and course_id:
        course = db.get(Course, course_id)

    profiles_q = db.query(StudentProfile)
    if course or course_id:
        profiles_q = profiles_q.filter(StudentProfile.course_id == (course.id if course else course_id))
    if user.role == "student":
        profiles_q = profiles_q.filter(StudentProfile.student_id == user.id)
    elif user.role == "teacher":
        managed_ids = [row[0] for row in db.query(Course.id).filter(Course.teacher_id == user.id).all()]
        profiles_q = profiles_q.filter(StudentProfile.course_id.in_(managed_ids or [-1]))
    profiles = profiles_q.limit(80).all()
    completed_profiles = [p for p in profiles if float(p.post_score or 0) > 0]
    comparison_profiles = completed_profiles or profiles
    pre_avg = round(
        sum(p.pre_score for p in comparison_profiles) / max(1, len(comparison_profiles)), 1
    ) if comparison_profiles else 0
    post_avg = round(
        sum(p.post_score for p in completed_profiles) / max(1, len(completed_profiles)), 1
    ) if completed_profiles else 0

    agent_nodes = _agent_nodes(latest_logs)
    model_stream = _model_stream(latest, latest_logs, llm_logs, course, resources)
    quality_gates = _quality_gates(resources, avg_quality, citation_count)
    reports = []
    if resources:
        reports = db.query(QualityReport).filter(
            QualityReport.resource_id.in_([resource.id for resource in resources])
        ).all()
    quality_metrics = _quality_metrics(reports, resources)

    return R.ok({
        "course": {"id": course.id, "name": course.name, "code": course.code} if course else None,
        "hero": {
            "headline": "AI 智能体指挥舱",
            "subtitle": "把课程资料、学生画像、RAG 证据、模型生成和质量审核压缩到一条可追溯智能流水线。",
            "active_trace": latest.trace_id if latest else "",
            "active_workflow": latest.workflow if latest else "",
        },
        "active_run": _run(latest, with_logs=False) if latest else None,
        "kpis": {
            "total_runs": total_runs,
            "success_rate": round(success_runs / total_runs * 100, 1) if total_runs else 100,
            "avg_duration_ms": round(avg_duration),
            "total_tokens": total_tokens,
            "avg_quality": avg_quality,
            "rag_evidence": citation_count,
            "pre_avg": pre_avg,
            "post_avg": post_avg,
            "improvement": round(post_avg - pre_avg, 1) if completed_profiles else 0,
            "post_completed_count": len(completed_profiles),
        },
        "agent_nodes": agent_nodes,
        "model_stream": model_stream,
        "quality_gates": quality_gates,
        "quality_metrics": quality_metrics,
        "evidence": evidence,
        "recent_runs": [_run(r, with_logs=False) for r in runs],
        "model_calls": [{
            "id": l.id,
            "provider": l.provider,
            "model": l.model,
            "purpose": l.purpose,
            "trace_id": l.trace_id,
            "tokens": (l.prompt_tokens or 0) + (l.completion_tokens or 0),
            "duration_ms": l.duration_ms,
            "success": l.success,
            "created_at": l.created_at.isoformat() if l.created_at else "",
        } for l in llm_logs],
        "resources": [{
            "id": r.id,
            "title": r.title,
            "rtype": r.rtype,
            "quality_score": r.quality_score,
            "review_status": r.review_status,
            "citations": len(resource_citation_map.get(r.id, [])),
            "published": r.published,
            "extra": _json_loads(r.extra, {}),
        } for r in resources[:8]],
        "talk_track": [
            "第一步：上传课程资料后，解析智能体把 PDF/Markdown 切成可检索知识片段。",
            "第二步：知识图谱智能体把知识点连接成先修、相似、易混关系，后续所有生成都受图谱约束。",
            "第三步：大模型不直接裸生成，而是先读取学生画像和 RAG 证据，再输出讲义、练习、PPT 与视频脚本。",
            "第四步：质量门控会检查覆盖度、引用、结构、难度和风险词，低分资源进入人工审核队列。",
            "第五步：系统把前测、后测、错题和资源学习效果回写报告，形成完整教学闭环。"
        ]
    })


@router.get("/runs/{run_id}", response_model=R)
def run_detail(run_id: int, db: Session = Depends(get_db),
               user: User = Depends(any_role)):
    r = db.get(AgentRun, run_id)
    if not r:
        raise HTTPException(404, "运行不存在")
    _ensure_run_access(db, r, user)
    return R.ok(_run(r, with_logs=True, db=db))


@router.get("/trace/{trace_id}", response_model=R)
def by_trace(trace_id: str, db: Session = Depends(get_db),
             user: User = Depends(any_role)):
    r = db.query(AgentRun).filter(AgentRun.trace_id == trace_id).first()
    if not r:
        raise HTTPException(404, "trace 不存在")
    _ensure_run_access(db, r, user)
    return R.ok(_run(r, with_logs=True, db=db))


def _run(r: AgentRun, with_logs: bool, db: Session | None = None) -> dict:
    data = {
        "id": r.id, "trace_id": r.trace_id, "student_id": r.student_id,
        "course_id": r.course_id, "workflow": r.workflow, "status": r.status,
        "started_at": r.started_at.isoformat() if r.started_at else "",
        "finished_at": r.finished_at.isoformat() if r.finished_at else "",
        "duration_ms": r.duration_ms, "progress": r.progress,
        "input_summary": json.loads(r.input_summary or "{}"),
        "output_summary": json.loads(r.output_summary or "{}"),
        "error": r.error,
    }
    if with_logs:
        logs = db_query_logs(db, r.id) if db else []
        data["logs"] = logs
    return data


def db_query_logs(db: Session, run_id: int) -> list[dict]:
    rows = db.query(AgentLog).filter(AgentLog.run_id == run_id).order_by(AgentLog.step).all()
    return [{
        "id": l.id, "agent": l.agent, "step": l.step, "status": l.status,
        "role_description": l.role_description,
        "input_summary": _json_loads(l.input_summary, {}),
        "output_summary": _json_loads(l.output_summary, {}),
        "duration_ms": l.duration_ms, "error": l.error,
        "model_provider": l.model_provider, "model_name": l.model_name,
        "citation_count": l.citation_count, "quality_score": l.quality_score,
        "retry_count": l.retry_count,
        "created_at": l.created_at.isoformat() if l.created_at else "",
    } for l in rows]


def _json_loads(text: str, default):
    try:
        return json.loads(text or "")
    except Exception:
        return default


def _agent_nodes(logs: list[AgentLog]) -> list[dict]:
    order = [
        ("CourseParserAgent", "课程解析", "资料切片与结构抽取"),
        ("KnowledgeGraphAgent", "知识图谱", "先修/相似/易混关系"),
        ("DiagnosisAgent", "学生诊断", "前测薄弱点识别"),
        ("PlannerAgent", "路径规划", "个性化学习序列"),
        ("LectureAgent", "讲义生成", "RAG 增强讲解"),
        ("MindMapAgent", "思维导图", "结构化知识可视化"),
        ("ExerciseAgent", "练习生成", "分层题目与解析"),
        ("MultimodalResourceAgent", "多模态资源", "PPT/视频/实验"),
        ("QualityCheckAgent", "质量门控", "覆盖/引用/风险评分"),
        ("TeacherReviewAgent", "教师预审", "发布建议与风险提示"),
    ]
    by_agent = {}
    for log in logs:
        by_agent[log.agent] = log
    nodes = []
    for idx, (agent_name, label, desc) in enumerate(order, start=1):
        log = by_agent.get(agent_name)
        out = _json_loads(log.output_summary, {}) if log else {}
        score = out.get("quality") or out.get("avg_score") or out.get("score")
        nodes.append({
            "step": idx,
            "agent": agent_name,
            "label": label,
            "desc": desc,
            "status": log.status if log else "waiting",
            "duration_ms": log.duration_ms if log else 0,
            "summary": _compact_summary(out) if log else "等待上游任务",
            "score": round(float(score), 1) if isinstance(score, (int, float)) else None,
            "role_description": log.role_description if log else desc,
            "input_summary": _json_loads(log.input_summary, {}) if log else {},
            "output_summary": out,
            "model_provider": log.model_provider if log else "",
            "model_name": log.model_name if log else "",
            "citation_count": log.citation_count if log else 0,
            "quality_score": log.quality_score if log else 0,
            "retry_count": log.retry_count if log else 0,
            "error": log.error if log else "",
            "execution_logs": [
                f"步骤 {idx}：{label}",
                f"状态：{log.status if log else 'waiting'}",
                f"耗时：{log.duration_ms if log else 0}ms",
            ],
        })
    return nodes


def _compact_summary(data: dict) -> str:
    if not data:
        return "任务完成"
    labels = {
        "parsed": "解析完成", "pages": "页数", "chunks": "切片", "points": "知识点",
        "nodes": "节点", "edges": "关系", "resource_id": "资源ID", "quality": "质量分",
        "citations": "引用", "checked": "校验数", "avg_score": "均分", "suggestions": "预审建议"
    }
    parts = []
    for k, v in list(data.items())[:5]:
        if isinstance(v, list):
            v = len(v)
        elif isinstance(v, dict):
            v = len(v)
        parts.append(f"{labels.get(k, k)} {v}")
    return " · ".join(parts)


def _model_stream(latest: AgentRun | None, logs: list[AgentLog],
                  llm_logs: list[LLMCallLog], course: Course | None,
                  resources: list[GeneratedResource]) -> list[dict]:
    course_name = course.name if course else "当前课程"
    latest_resource = resources[0] if resources else None
    stream = [
        {
            "phase": "任务识别",
            "title": f"识别教学目标：{course_name}",
            "content": "系统先读取课程、学生、知识点和资源类型，决定调用解析、图谱、诊断、生成、质检与预审链路。",
            "signal": "route"
        },
        {
            "phase": "证据检索",
            "title": "RAG 证据进入模型上下文",
            "content": f"最近资源「{latest_resource.title if latest_resource else '暂无资源'}」已绑定引用证据，模型输出可追踪到课程资料片段。",
            "signal": "rag"
        },
    ]
    for log in logs[:6]:
        out = _json_loads(log.output_summary, {})
        stream.append({
            "phase": "Agent 接力",
            "title": _agent_name_cn(log.agent),
            "content": _compact_summary(out),
            "signal": "agent",
            "duration_ms": log.duration_ms,
        })
    for call in llm_logs[:4]:
        stream.append({
            "phase": "模型调用",
            "title": f"{call.purpose or 'general'} · {call.model}",
            "content": f"输入约 {call.prompt_tokens} tokens，输出约 {call.completion_tokens} tokens，耗时 {call.duration_ms}ms，状态 {'成功' if call.success else '失败'}。",
            "signal": "llm",
            "duration_ms": call.duration_ms,
        })
    return stream[:10]


def _quality_gates(resources: list[GeneratedResource], avg_quality: float, citation_count: int) -> list[dict]:
    risk_count = sum(1 for r in resources if r.review_status == "risk" or r.quality_score < 70)
    published_count = sum(1 for r in resources if r.published or r.review_status in ("approved", "published"))
    return [
        {"name": "覆盖度", "value": avg_quality, "unit": "分", "status": "pass" if avg_quality >= 75 else "warn",
         "desc": "检查资源是否覆盖核心知识点和学习目标"},
        {"name": "引用命中", "value": citation_count, "unit": "条", "status": "pass" if citation_count else "warn",
         "desc": "课程检索证据是否进入生成结果"},
        {"name": "风险拦截", "value": risk_count, "unit": "项", "status": "warn" if risk_count else "pass",
         "desc": "低分、夸大或结构异常资源进入人工复核"},
        {"name": "发布候选", "value": published_count, "unit": "个", "status": "pass",
         "desc": "通过质量门控后可进入教师审核与发布"}
    ]


def _quality_metrics(reports: list[QualityReport], resources: list[GeneratedResource]) -> dict:
    def avg(name: str) -> float:
        values = [float(getattr(report, name, 0) or 0) for report in reports]
        return round(sum(values) / max(1, len(values)) * 100, 1) if values else 0.0

    teacher_advice = []
    for resource in resources:
        extra = _json_loads(resource.extra, {})
        suggestion = extra.get("teacher_review_suggestion") or {}
        if suggestion.get("summary"):
            teacher_advice.append(suggestion["summary"])
    return {
        "knowledge_coverage": avg("coverage"),
        "citation_hit": avg("citation_hit"),
        "answer_consistency": avg("answer_consistency"),
        "difficulty_match": avg("difficulty_match"),
        "structure": avg("structure"),
        "teacher_advice": teacher_advice[:3],
    }


def _agent_name_cn(agent: str) -> str:
    return {
        "CourseParserAgent": "课程解析智能体",
        "KnowledgeGraphAgent": "知识图谱智能体",
        "DiagnosisAgent": "学生诊断智能体",
        "PlannerAgent": "路径规划智能体",
        "LectureAgent": "讲义生成智能体",
        "MindMapAgent": "思维导图智能体",
        "ExerciseAgent": "练习生成智能体",
        "MultimodalResourceAgent": "多模态资源智能体",
        "QualityCheckAgent": "质量门控智能体",
        "TeacherReviewAgent": "教师预审智能体",
    }.get(agent, agent)


def _ensure_course_access(db: Session, course_id: int, user: User) -> Course:
    course = db.get(Course, course_id)
    if not course:
        raise HTTPException(404, "课程不存在")
    if user.role == "admin":
        return course
    if user.role == "teacher":
        if course.teacher_id != user.id:
            raise HTTPException(403, "无权运行或查看其他教师课程的智能体")
        return course
    enrolled = db.query(CourseEnrollment).filter(
        CourseEnrollment.course_id == course_id,
        CourseEnrollment.student_id == user.id,
    ).first()
    if not enrolled:
        raise HTTPException(403, "请先加入该课程")
    return course


def _ensure_run_access(db: Session, run: AgentRun, user: User) -> None:
    if user.role == "admin":
        return
    if user.role == "student":
        if run.student_id != user.id:
            raise HTTPException(403, "无权查看其他学生的运行记录")
        return
    course = db.get(Course, run.course_id) if run.course_id else None
    if not course or course.teacher_id != user.id:
        raise HTTPException(403, "无权查看其他教师课程的运行记录")


def _reap_stale_runs(db: Session, course_id: int | None = None,
                     stale_after_minutes: int = 15) -> int:
    """Close tasks left ``running`` after a worker/process interruption.

    The longest configured model call plus retries remains below this grace
    period.  Keeping the original trace and marking it failed is preferable to
    silently deleting audit evidence or blocking idempotent retries forever.
    """
    effective_minutes = max(5, stale_after_minutes)
    threshold_ms = effective_minutes * 60 * 1000
    # Older builds calculated a recovered task's duration from the original
    # start time to the next page visit.  That preserved timestamps but could
    # turn a 15-minute timeout into a misleading multi-hour KPI.  Normalize
    # only records carrying this exact system-generated recovery reason.
    legacy_query = db.query(AgentRun).filter(
        AgentRun.status == "failed",
        AgentRun.error == _STALE_RUN_ERROR,
        AgentRun.duration_ms > threshold_ms,
    )
    if course_id:
        legacy_query = legacy_query.filter(AgentRun.course_id == course_id)
    legacy_rows = legacy_query.all()
    for row in legacy_rows:
        row.duration_ms = threshold_ms

    cutoff = utc_now() - timedelta(minutes=effective_minutes)
    query = db.query(AgentRun).filter(
        AgentRun.status == "running",
        AgentRun.started_at < cutoff,
    )
    if course_id:
        query = query.filter(AgentRun.course_id == course_id)
    rows = query.all()
    if not rows and not legacy_rows:
        return 0
    finished_at = utc_now()
    for row in rows:
        row.status = "failed"
        row.finished_at = finished_at
        if not row.duration_ms:
            # The exact duration is unknowable after a process interruption;
            # record the timeout threshold instead of a misleading multi-hour
            # wall-clock gap between process death and the next page visit.
            row.duration_ms = threshold_ms
        if not row.error:
            row.error = _STALE_RUN_ERROR
    db.commit()
    return len(rows)
