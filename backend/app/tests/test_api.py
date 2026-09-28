"""核心 API 与服务层测试。"""
import io
import zipfile

import pytest
from fastapi import HTTPException

from app.core.security import hash_password, verify_password, create_access_token, decode_token
from app.services import quality_service, test_service
from app.rag.chunker import chunk_text, chunk_pages
from app.rag.retriever import retrieve
from app.api.routers.files import _resolve_stored_path, _validate_upload_content
from app.utils.redaction import redact_sensitive


# ---------- 安全模块 ----------
def test_password_hash_verify():
    h = hash_password("secret123", rounds=10_000)
    assert h != "secret123"
    assert verify_password("secret123", h)
    assert not verify_password("wrong", h)
    legacy = "$pbkdf2-sha256$29000$bGVnYWN5LXNhbHQtMTIzNA$pqiJEyja5XxvvmaHUKUyOWh8NSls9HKXO.IHMrBWRUQ"
    assert verify_password("secret123", legacy)


def test_sensitive_log_values_are_redacted():
    fake_api_key = "sk-" + "example-secret-value"
    fake_bearer = "secret-" + "token-value"
    text = redact_sensitive(
        f"Authorization: Bearer {fake_bearer} DEEPSEEK_API_KEY={fake_api_key}",
        secrets=(fake_bearer,),
    )
    assert fake_bearer not in text
    assert fake_api_key not in text
    assert "REDACTED" in text


def test_database_url_credentials_are_redacted():
    raw = "postgresql+psycopg://demo-user:demo-password@db.internal/xunkeflow"
    text = redact_sensitive(raw)
    assert "demo-user" not in text
    assert "demo-password" not in text
    assert text == "postgresql+psycopg://[REDACTED]@db.internal/xunkeflow"


def test_ooxml_zip_bomb_ratio_is_rejected():
    payload = io.BytesIO()
    with zipfile.ZipFile(payload, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", "<Types />")
        archive.writestr("word/document.xml", "A" * (11 * 1024 * 1024))
    with pytest.raises(HTTPException, match="压缩比异常"):
        _validate_upload_content("docx", payload.getvalue(), "application/octet-stream")


def test_ooxml_path_traversal_and_stored_path_escape_are_rejected(tmp_path):
    payload = io.BytesIO()
    with zipfile.ZipFile(payload, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", "<Types />")
        archive.writestr("word/document.xml", "课程正文")
        archive.writestr("../outside.txt", "escape")
    with pytest.raises(HTTPException, match="不安全条目"):
        _validate_upload_content("docx", payload.getvalue(), "application/octet-stream")

    with pytest.raises(HTTPException, match="文件存储路径无效"):
        _resolve_stored_path(str(tmp_path / "outside.md"))


def test_jwt_create_decode():
    tok = create_access_token(42, {"role": "admin"})
    payload = decode_token(tok)
    assert payload is not None
    assert payload["sub"] == "42"
    assert payload["role"] == "admin"
    assert payload["iss"]
    assert payload["aud"]
    assert payload["jti"]


def test_jwt_invalid_returns_none():
    assert decode_token("invalid.token.here") is None


def test_signed_token_with_non_numeric_subject_returns_401(client):
    token = create_access_token("not-a-user-id", {"role": "student"})
    response = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401


# ---------- 认证 API ----------
def test_register_and_login(client):
    r = client.post("/api/auth/register", json={
        "username": "newstu", "email": "new@x.com", "password": "abc12345",
        "role": "student", "full_name": "新生"
    })
    assert r.status_code == 200
    r2 = client.post("/api/auth/login", json={"username": "newstu", "password": "abc12345"})
    assert r2.status_code == 200
    data = r2.json()["data"]
    assert data["role"] == "student"
    assert data["access_token"]


def test_login_wrong_password(client):
    r = client.post("/api/auth/login", json={"username": "admin", "password": "wrong"})
    assert r.status_code == 401


def test_login_failures_are_rate_limited(client):
    statuses = []
    response = None
    for _ in range(5):
        response = client.post(
            "/api/auth/login",
            json={"username": "rate-limit-probe", "password": "wrong-password"},
        )
        statuses.append(response.status_code)
    assert statuses[:4] == [401, 401, 401, 401]
    assert statuses[-1] == 429
    assert response is not None
    assert int(response.headers["Retry-After"]) >= 1


def test_registration_rejects_weak_password(client):
    response = client.post("/api/auth/register", json={
        "username": "weakstu",
        "email": "weakstu@example.com",
        "password": "abcdefgh",
        "role": "student",
    })
    assert response.status_code == 422


def test_me_requires_auth(client):
    r = client.get("/api/auth/me")
    assert r.status_code == 401


def test_me_with_token(client, admin_token):
    r = client.get("/api/auth/me", headers={"Authorization": f"Bearer {admin_token}"})
    assert r.status_code == 200
    assert r.json()["data"]["username"] == "admin"


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_security_headers_and_host_validation(client):
    response = client.get("/api/health")
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["x-permitted-cross-domain-policies"] == "none"

    malformed = client.get("/api/health", headers={"Host": "evil.test/path?bypass="})
    assert malformed.status_code == 400


# ---------- 课程 API ----------
def test_create_course(client, teacher_token):
    r = client.post("/api/courses", json={"name": "测试课程", "code": "T001"},
                    headers={"Authorization": f"Bearer {teacher_token}"})
    assert r.status_code == 200
    assert r.json()["data"]["name"] == "测试课程"


def test_list_courses(client, teacher_token):
    client.post("/api/courses", json={"name": "C1"}, headers={"Authorization": f"Bearer {teacher_token}"})
    r = client.get("/api/courses", headers={"Authorization": f"Bearer {teacher_token}"})
    assert r.status_code == 200
    assert isinstance(r.json()["data"], list)


def test_course_graph_and_question_state_values_are_validated(client, teacher_token):
    headers = {"Authorization": f"Bearer {teacher_token}"}
    course = client.post(
        "/api/courses",
        json={"name": "状态约束课程", "code": "STATE-VALIDATION"},
        headers=headers,
    ).json()["data"]

    invalid_status = client.put(
        f"/api/courses/{course['id']}",
        json={"status": "deleted"},
        headers=headers,
    )
    assert invalid_status.status_code == 422

    ignored_null = client.put(
        f"/api/courses/{course['id']}",
        json={"name": None},
        headers=headers,
    )
    assert ignored_null.status_code == 200
    assert ignored_null.json()["data"]["name"] == "状态约束课程"

    invalid_relation = client.post(
        "/api/knowledge/relation",
        json={
            "course_id": course["id"],
            "source_id": 1,
            "target_id": 2,
            "relation": "arbitrary-value",
        },
        headers=headers,
    )
    assert invalid_relation.status_code == 422

    valid_question = {
        "course_id": course["id"],
        "qtype": "single",
        "stem": "哪一项符合课程资料要求？",
        "answer": "A",
        "analysis": "A 与正确选项一致。",
        "difficulty": 3,
        "options": [
            {"key": "A", "content": "依据证据回答", "is_correct": True},
            {"key": "B", "content": "忽略证据猜测", "is_correct": False},
        ],
    }
    created = client.post("/api/questions", json=valid_question, headers=headers)
    assert created.status_code == 200

    invalid_question = dict(valid_question)
    invalid_question["answer"] = "B"
    rejected = client.post("/api/questions", json=invalid_question, headers=headers)
    assert rejected.status_code == 422


def test_enrolled_courses_expose_profile_readiness(client, db_session):
    from app.models.course import Course, CourseEnrollment
    from app.models.profile import StudentProfile
    from app.models.user import User

    teacher = db_session.query(User).filter(User.role == "teacher").first()
    student = User(
        username="profile_state_student",
        email="profile-state@test.com",
        hashed_password=hash_password("123456", rounds=10_000),
        role="student",
        full_name="画像状态学生",
    )
    course_row = Course(name="画像状态课程", code="PROFILE-STATE", teacher_id=teacher.id)
    db_session.add_all([student, course_row])
    db_session.flush()
    db_session.add(CourseEnrollment(course_id=course_row.id, student_id=student.id))
    db_session.commit()

    login = client.post("/api/auth/login", json={"username": student.username, "password": "123456"})
    headers = {"Authorization": f"Bearer {login.json()['data']['access_token']}"}
    before = client.get("/api/courses/mine/enrolled", headers=headers)
    assert before.status_code == 200
    assert before.json()["data"][0]["has_profile"] is False

    db_session.add(StudentProfile(student_id=student.id, course_id=course_row.id, pre_score=60))
    db_session.commit()
    after = client.get("/api/courses/mine/enrolled", headers=headers)
    assert after.status_code == 200
    assert after.json()["data"][0]["has_profile"] is True


# ---------- RAG ----------
def test_chunk_text_basic():
    # 用换行分隔的多段落，确保 chunker 会拆分
    text = "\n".join([f"这是第{i}个段落的详细内容，包含足够长的文字用于测试分块。" for i in range(50)])
    chunks = chunk_text(text, chunk_size=80, overlap=15)
    assert len(chunks) > 1
    assert all(len(c) >= 8 for c in chunks)


def test_chunk_pages_keeps_page():
    pages = [{"text": "内容一" * 50, "page": 1}, {"text": "内容二" * 50, "page": 2}]
    out = chunk_pages(pages, chunk_size=80, overlap=10)
    assert len(out) >= 2
    assert "page" in out[0]


def test_retriever_isolates_courses(db_session):
    from app.models.chunk import DocumentChunk
    from app.models.course import Course
    from app.models.user import User
    teacher = db_session.query(User).filter(User.role == "teacher").first()
    course_a = Course(name="金融消费者权益保护", teacher_id=teacher.id)
    course_b = Course(name="中国古代文学", teacher_id=teacher.id)
    db_session.add_all([course_a, course_b]); db_session.flush()
    db_session.add_all([
        DocumentChunk(course_id=course_a.id, file_id=1, chunk_index=0,
                      text="产品适当性要求匹配客户风险承受能力。", source_name="金融讲义.md"),
        DocumentChunk(course_id=course_b.id, file_id=2, chunk_index=0,
                      text="古典诗歌阅读需要结合意象与时代语境。", source_name="文学讲义.md"),
    ])
    db_session.commit()
    rows = retrieve(db_session, course_a.id, "客户风险承受能力", top_k=5)
    assert len(rows) == 1
    assert rows[0]["source"] == "金融讲义.md"
    assert rows[0]["file_id"] == 1


def test_citation_payload_is_fully_traceable():
    from app.rag.retriever import format_citations
    rows = format_citations([{
        "file_id": 9,
        "source": "金融治理讲义.pdf",
        "chapter": "风险治理",
        "chunk_id": 21,
        "text": "金融机构应建立风险识别、评估和处置机制。",
        "score": 0.82,
        "page": 6,
    }])
    citation = rows[0]
    assert citation["source_file_id"] == 9
    assert citation["source_file_name"] == "金融治理讲义.pdf"
    assert citation["chapter"] == "风险治理"
    assert citation["chunk_id"] == 21
    assert citation["excerpt"]
    assert citation["relevance_score"] == 0.82
    assert citation["page_number"] == 6


def test_retriever_bounds_top_k(db_session):
    from app.models.chunk import DocumentChunk
    from app.models.course import Course
    from app.models.user import User
    teacher = db_session.query(User).filter(User.role == "teacher").first()
    course = Course(name="创新创业项目管理", teacher_id=teacher.id)
    db_session.add(course); db_session.flush()
    db_session.add_all([
        DocumentChunk(course_id=course.id, file_id=1, chunk_index=index,
                      text=f"项目风险识别与应对策略 {index}", source_name="项目讲义.md")
        for index in range(20)
    ])
    db_session.commit()
    rows = retrieve(db_session, course.id, "项目风险", top_k=99)
    assert len(rows) == 12


# ---------- 质量评分 ----------
def test_quality_score_basic(db_session):
    from app.models.resource import GeneratedResource
    from app.models.knowledge import KnowledgePoint
    from app.models.course import Course
    from app.models.user import User
    user = db_session.query(User).first()
    c = Course(name="qc", teacher_id=user.id)
    db_session.add(c); db_session.flush()
    kp = KnowledgePoint(course_id=c.id, name="事务", keywords="事务,隔离")
    db_session.add(kp); db_session.flush()
    res = GeneratedResource(course_id=c.id, rtype="lecture", title="t",
                            content="# 事务\n## ACID\n- 原子性\n事务是核心概念\n```sql\nBEGIN;\n```")
    db_session.add(res); db_session.commit()
    rep = quality_service.score_resource(db_session, res, [kp], [], c.id)
    assert 0 <= rep.score <= 100
    assert res.quality_score == rep.score


# ---------- 前后测对比空数据 ----------
def test_compare_empty(db_session):
    out = test_service.compare(db_session, 999, 999)
    assert out["pre_score"] == 0
    assert out["post_score"] == 0


def test_denormalized_profile_labels_follow_current_knowledge_point_names():
    from app.api.routers.profiles import _current_point_names

    original = [{"id": 8, "name": "本课程把", "score": 42}, {"kp_id": 9, "name": "旧名称"}]
    refreshed = _current_point_names(original, {8: "星槎证据链", 9: "课程知识库"})
    assert refreshed[0]["name"] == "星槎证据链"
    assert refreshed[1]["name"] == "课程知识库"
    assert original[0]["name"] == "本课程把"


def test_stale_agent_runs_are_reaped_without_deleting_audit_trace(db_session):
    from datetime import timedelta
    from app.api.routers.agents import _STALE_RUN_ERROR, _reap_stale_runs
    from app.models.agent import AgentRun
    from app.utils.time_util import utc_now

    stale = AgentRun(
        trace_id="stale-trace",
        course_id=1,
        workflow="full_pipeline",
        status="running",
        started_at=utc_now() - timedelta(minutes=30),
    )
    recent = AgentRun(
        trace_id="recent-trace",
        course_id=1,
        workflow="full_pipeline",
        status="running",
        started_at=utc_now(),
    )
    legacy_recovered = AgentRun(
        trace_id="legacy-recovered-trace",
        course_id=1,
        workflow="full_pipeline",
        status="failed",
        started_at=utc_now() - timedelta(hours=6),
        finished_at=utc_now(),
        duration_ms=6 * 60 * 60 * 1000,
        error=_STALE_RUN_ERROR,
    )
    db_session.add_all([stale, recent, legacy_recovered])
    db_session.commit()

    assert _reap_stale_runs(db_session, 1) == 1
    db_session.refresh(stale)
    db_session.refresh(recent)
    db_session.refresh(legacy_recovered)
    assert stale.status == "failed"
    assert stale.finished_at is not None
    assert stale.duration_ms == 15 * 60 * 1000
    assert "回收" in stale.error
    assert recent.status == "running"
    assert legacy_recovered.duration_ms == 15 * 60 * 1000


def test_orchestrator_errors_are_redacted(monkeypatch):
    from app.agents.orchestrator import _safe_error
    from app.core.config import settings

    fake_api_key = "sk-" + "example-secret-value"
    monkeypatch.setattr(settings, "DEEPSEEK_API_KEY", fake_api_key)
    fake_bearer = "top-secret-" + "token"
    message = _safe_error(
        f"Authorization: Bearer {fake_bearer}; DEEPSEEK_API_KEY={fake_api_key}"
    )
    assert fake_bearer not in message
    assert fake_api_key not in message
    assert "REDACTED" in message
