"""业务闭环与权限隔离集成测试。"""
from datetime import datetime
import json
import pytest

from app.core.security import hash_password
from app.models.chunk import DocumentChunk
from app.models.course import Course, CourseChapter, CourseEnrollment, CourseFile
from app.models.knowledge import KnowledgePoint, KnowledgeRelation
from app.models.learning import WrongQuestion
from app.models.profile import KnowledgeMastery, StudentProfile
from app.models.question import Question, QuestionOption
from app.models.resource import GeneratedResource
from app.models.user import User
from app.models.agent import AgentLog, AgentRun
from app.models.system import LLMCallLog
from app.agents.course_parser import CourseParserAgent
from app.services import profile_service, report_service, test_service


def _login(client, username: str, password: str = "123456") -> str:
    response = client.post("/api/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200
    return response.json()["data"]["access_token"]


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def business_data(db_session, tmp_path):
    teacher = db_session.query(User).filter(User.username == "teacher").one()
    teacher2 = User(
        username="teacher2",
        email="teacher2@test.com",
        hashed_password=hash_password("123456", rounds=10_000),
        role="teacher",
        full_name="李老师",
    )
    student1 = User(
        username="student_a",
        email="student_a@test.com",
        hashed_password=hash_password("123456", rounds=10_000),
        role="student",
        full_name="学生甲",
    )
    student2 = User(
        username="student_b",
        email="student_b@test.com",
        hashed_password=hash_password("123456", rounds=10_000),
        role="student",
        full_name="学生乙",
    )
    db_session.add_all([teacher2, student1, student2])
    db_session.flush()

    course1 = Course(name="高等数学", code="MATH-AUDIT", teacher_id=teacher.id, status="active")
    course2 = Course(name="大学物理", code="PHY-AUDIT", teacher_id=teacher2.id, status="active")
    db_session.add_all([course1, course2])
    db_session.flush()
    chapter2 = CourseChapter(course_id=course2.id, title="物理学章节", order_index=0)
    db_session.add(chapter2)
    db_session.flush()
    db_session.add_all([
        CourseEnrollment(course_id=course1.id, student_id=student1.id, goal="掌握微积分", weekly_hours=6),
        CourseEnrollment(course_id=course1.id, student_id=student2.id, goal="完成课程", weekly_hours=5),
    ])

    kp1 = KnowledgePoint(course_id=course1.id, name="函数极限", difficulty=2, importance=1.0)
    kp2 = KnowledgePoint(course_id=course1.id, name="导数", difficulty=3, importance=1.0)
    db_session.add_all([kp1, kp2])
    db_session.flush()
    q1 = Question(
        course_id=course1.id,
        kp_id=kp1.id,
        qtype="single",
        stem="函数极限的正确描述是？",
        answer="A",
        analysis="极限描述函数在某点附近的变化趋势。",
        difficulty=2,
    )
    q2 = Question(
        course_id=course1.id,
        kp_id=kp2.id,
        qtype="judge",
        stem="判断：导数可以描述瞬时变化率。",
        answer="正确",
        analysis="导数的几何与物理意义均体现瞬时变化率。",
        difficulty=3,
    )
    db_session.add_all([q1, q2])
    db_session.flush()
    db_session.add_all([
        QuestionOption(question_id=q1.id, key="A", content="描述邻域变化趋势", is_correct=True),
        QuestionOption(question_id=q1.id, key="B", content="只表示函数值", is_correct=False),
    ])

    resources = {
        "general": GeneratedResource(
            course_id=course1.id, rtype="lecture", title="公开讲义",
            content="公开内容", published=True, review_status="published",
        ),
        "own": GeneratedResource(
            course_id=course1.id, student_id=student1.id, rtype="lecture", title="甲的讲义",
            content="个性化内容", published=True, review_status="published", is_personalized=True,
        ),
        "other": GeneratedResource(
            course_id=course1.id, student_id=student2.id, rtype="lecture", title="乙的讲义",
            content="其他学生内容", published=True, review_status="published", is_personalized=True,
        ),
        "pending": GeneratedResource(
            course_id=course1.id, rtype="lecture", title="待审核讲义",
            content="待审核", published=False, review_status="pending",
        ),
    }
    db_session.add_all(resources.values())

    stored = tmp_path / "course.md"
    stored.write_text("课程资料", encoding="utf-8")
    course_file = CourseFile(
        course_id=course1.id,
        uploader_id=teacher.id,
        filename="course.md",
        stored_path=str(stored),
        file_type="md",
        size=12,
        parse_status="parsed",
        indexed=True,
    )
    db_session.add(course_file)
    db_session.commit()
    return {
        "teacher": teacher,
        "teacher2": teacher2,
        "student1": student1,
        "student2": student2,
        "course1": course1,
        "course2": course2,
        "chapter2": chapter2,
        "kp1": kp1,
        "kp2": kp2,
        "q1": q1,
        "q2": q2,
        "resources": resources,
        "file": course_file,
    }


def test_public_registration_cannot_create_privileged_account(client):
    response = client.post("/api/auth/register", json={
        "username": "bad_admin",
        "email": "bad_admin@test.com",
        "password": "abc12345",
        "role": "admin",
    })
    assert response.status_code == 403
    assert "公开注册仅支持学生账号" in response.json()["detail"]

    response = client.post("/api/auth/register", json={
        "username": "normal_student",
        "email": "normal_student@test.com",
        "password": "abc12345",
    })
    assert response.status_code == 200
    assert response.json()["data"]["role"] == "student"


def test_pretest_requires_enrollment_and_never_leaks_answer(client, business_data):
    token = _login(client, "student_a")
    response = client.get(
        f"/api/tests/pre/{business_data['course1'].id}",
        headers=_headers(token),
    )
    assert response.status_code == 200
    questions = response.json()["data"]
    assert questions
    assert all("answer" not in question and "analysis" not in question for question in questions)
    assert all("is_correct" not in option for question in questions for option in question["options"])

    response = client.get(f"/api/tests/pre/{business_data['course1'].id}")
    assert response.status_code == 401


def test_pretest_submission_builds_profile_mastery_and_path(
    client, db_session, business_data, monkeypatch
):
    monkeypatch.setattr(profile_service.llm_client, "chat_json", lambda *args, **kwargs: {
        "base_level": "basic",
        "pref_style": "理解型",
        "pref_format": "文字,图解",
        "learning_speed": "normal",
        "recommendation": "先理解概念，再完成分层练习。",
    })
    token = _login(client, "student_a")
    paper = client.get(
        f"/api/tests/pre/{business_data['course1'].id}",
        headers=_headers(token),
        params={"count": 2, "test_type": "pre"},
    )
    assert paper.status_code == 200
    assert {item["id"] for item in paper.json()["data"]} == {
        business_data["q1"].id, business_data["q2"].id
    }
    mismatch = client.post(
        "/api/tests/submit",
        headers=_headers(token),
        json={
            "course_id": business_data["course1"].id,
            "test_type": "pre",
            "answers": [{"question_id": business_data["q1"].id, "answer": "B"}],
        },
    )
    assert mismatch.status_code == 409
    response = client.post(
        "/api/tests/submit",
        headers=_headers(token),
        json={
            "course_id": business_data["course1"].id,
            "test_type": "pre",
            "answers": [
                {"question_id": business_data["q1"].id, "answer": "B"},
                {"question_id": business_data["q2"].id, "answer": "正确"},
            ],
        },
    )
    assert response.status_code == 200
    result = response.json()["data"]
    assert result["profile_id"] and result["path_id"] and result["diagnosis_trace_id"]
    assert db_session.query(StudentProfile).filter_by(
        student_id=business_data["student1"].id,
        course_id=business_data["course1"].id,
    ).count() == 1
    assert db_session.query(KnowledgeMastery).filter_by(
        student_id=business_data["student1"].id,
        course_id=business_data["course1"].id,
    ).count() == 2
    profile_response = client.get(
        f"/api/profiles/{business_data['course1'].id}", headers=_headers(token)
    )
    assert profile_response.status_code == 200
    assert client.post(
        "/api/tests/submit",
        headers=_headers(token),
        json={
            "course_id": business_data["course1"].id,
            "test_type": "pre",
            "answers": [
                {"question_id": business_data["q1"].id, "answer": "A"},
                {"question_id": business_data["q2"].id, "answer": "正确"},
            ],
        },
    ).status_code == 409


def test_posttest_persists_current_mastery_in_by_kp(
    client, db_session, business_data, monkeypatch
):
    monkeypatch.setattr(profile_service.llm_client, "chat_json", lambda *args, **kwargs: {})
    token = _login(client, "student_a")
    course_id = business_data["course1"].id
    pending_kp = KnowledgePoint(
        course_id=course_id,
        name="积分应用",
        difficulty=4,
        importance=0.8,
    )
    db_session.add(pending_kp)
    db_session.commit()
    pre_payload = {
        "course_id": course_id,
        "test_type": "pre",
        "answers": [
            {"question_id": business_data["q1"].id, "answer": "B"},
            {"question_id": business_data["q2"].id, "answer": "错误"},
        ],
    }
    assert client.get(
        f"/api/tests/pre/{course_id}",
        headers=_headers(token),
        params={"count": 2, "test_type": "pre"},
    ).status_code == 200
    assert client.post("/api/tests/submit", headers=_headers(token), json=pre_payload).status_code == 200
    assert client.get(
        f"/api/tests/pre/{course_id}",
        headers=_headers(token),
        params={"count": 2, "test_type": "post"},
    ).status_code == 200
    post = client.post(
        "/api/tests/submit",
        headers=_headers(token),
        json={
            "course_id": course_id,
            "test_type": "post",
            "answers": [
                {"question_id": business_data["q1"].id, "answer": "A"},
                {"question_id": business_data["q2"].id, "answer": "正确"},
            ],
        },
    )
    assert post.status_code == 200
    result = post.json()["data"]
    assert result["score"] == 100.0
    assessed = [item for item in result["by_kp"] if item["assessed"]]
    pending = [item for item in result["by_kp"] if not item["assessed"]]
    assert all(item["post"] == 100.0 for item in assessed)
    assert any(item["kp_id"] == pending_kp.id and item["post"] is None for item in pending)
    current = {
        row.kp_id: row.post_score
        for row in db_session.query(KnowledgeMastery).filter_by(
            student_id=business_data["student1"].id, course_id=course_id
        ).all()
    }
    assert all(current[item["kp_id"]] == item["post"] for item in assessed)
    profile_payload = client.get(
        f"/api/profiles/{course_id}", headers=_headers(token)
    ).json()["data"]
    assert [item["name"] for item in profile_payload["weak_points"]] == ["积分应用"]
    assert len(profile_payload["extra"]["mastered"]) == 2
    assert "已掌握 2 个知识点" in profile_payload["recommendation"]
    assert "薄弱 1 个" in profile_payload["recommendation"]

    # 报告以本次后测的 by_kp 快照为准，避免旧数据中的默认 0 分或陈旧
    # status 造成“后测 0 分但显示已掌握”之类的口径矛盾。
    rows = db_session.query(KnowledgeMastery).filter_by(
        student_id=business_data["student1"].id, course_id=course_id
    ).all()
    for row in rows:
        row.post_score = 0
        row.status = "weak"
    db_session.commit()
    report = report_service.build_student_markdown(
        db_session, business_data["student1"].id, course_id
    )
    assert "| 函数极限 | 0.0 | 100.0 | 已掌握 |" in report
    assert "| 导数 | 0.0 | 100.0 | 已掌握 |" in report
    assert "| 积分应用 | 50.0 | 待复测 | 待复测 |" in report
    assert "另有 1 个知识点未被本次后测覆盖" in report


def test_practice_writes_wrong_book_records_and_enforces_owner(client, business_data):
    token1 = _login(client, "student_a")
    token2 = _login(client, "student_b")
    course_id = business_data["course1"].id
    response = client.post(
        "/api/tests/practice/submit",
        headers=_headers(token1),
        json={
            "course_id": course_id,
            "duration": 90,
            "answers": [{"question_id": business_data["q1"].id, "answer": "B"}],
        },
    )
    assert response.status_code == 200
    assert response.json()["data"]["wrong_added"] == 1
    wrongs = client.get(f"/api/wrong/{course_id}", headers=_headers(token1)).json()["data"]
    assert len(wrongs) == 1
    wrong_id = wrongs[0]["id"]
    assert client.post(f"/api/wrong/{wrong_id}/resolve", headers=_headers(token2)).status_code == 403

    response = client.post(
        "/api/tests/practice/submit",
        headers=_headers(token1),
        json={
            "course_id": course_id,
            "answers": [{"question_id": business_data["q1"].id, "answer": "A"}],
        },
    )
    assert response.json()["data"]["resolved"] == 1
    assert client.get(f"/api/wrong/{course_id}", headers=_headers(token1)).json()["data"] == []
    records = client.get(f"/api/profiles/{course_id}/records", headers=_headers(token1)).json()["data"]
    assert sum(1 for row in records if row["action"] == "practice") == 2


def test_student_resource_visibility_is_isolated(client, db_session, business_data):
    token = _login(client, "student_a")
    course_id = business_data["course1"].id
    response = client.get("/api/resources", params={"course_id": course_id}, headers=_headers(token))
    assert response.status_code == 200
    ids = {item["id"] for item in response.json()["data"]}
    assert business_data["resources"]["general"].id in ids
    assert business_data["resources"]["own"].id in ids
    assert business_data["resources"]["other"].id not in ids
    assert business_data["resources"]["pending"].id not in ids
    assert client.get(f"/api/resources/{business_data['resources']['other'].id}", headers=_headers(token)).status_code == 403
    assert client.get(f"/api/resources/{business_data['resources']['pending'].id}", headers=_headers(token)).status_code == 403
    assert client.get("/api/resources", params={"course_id": course_id}).status_code == 401
    assert client.post(
        "/api/agents/run",
        headers=_headers(token),
        json={"course_id": course_id, "student_id": business_data["student2"].id},
    ).status_code == 403

    generated = client.post(
        "/api/resources/generate",
        headers=_headers(token),
        json={
            "course_id": course_id,
            "kp_id": business_data["kp1"].id,
            "rtype": "exercise",
            "personalized": True,
        },
    )
    assert generated.status_code == 200
    run_id = generated.json()["data"]["run_id"]
    exercise_resource = db_session.query(GeneratedResource).filter_by(
        agent_run_id=run_id, rtype="exercise"
    ).one()
    assert exercise_resource.student_id == business_data["student1"].id
    generated_questions = db_session.query(Question).filter_by(
        ai_resource_id=exercise_resource.id
    ).all()
    assert generated_questions

    blocked_pending = client.post(
        "/api/tests/practice/submit",
        headers=_headers(token),
        json={
            "course_id": course_id,
            "answers": [{"question_id": generated_questions[0].id, "answer": "A"}],
        },
    )
    assert blocked_pending.status_code == 400
    assert "未发布或无权访问" in blocked_pending.json()["detail"]

    before_review = set(test_service.pick_questions(
        db_session, course_id, count=100, student_id=business_data["student1"].id
    ))
    assert not before_review.intersection({question.id for question in generated_questions})

    teacher_token = _login(client, "teacher")
    approved = client.post(
        f"/api/review/{exercise_resource.id}",
        headers=_headers(teacher_token),
        json={"decision": "approved"},
    )
    assert approved.status_code == 200
    assert approved.json()["data"]["published"] is False
    published = client.post(
        f"/api/review/{exercise_resource.id}/publish",
        headers=_headers(teacher_token),
    )
    assert published.status_code == 200
    owner_questions = set(test_service.pick_questions(
        db_session, course_id, count=100, student_id=business_data["student1"].id
    ))
    other_questions = set(test_service.pick_questions(
        db_session, course_id, count=100, student_id=business_data["student2"].id
    ))
    generated_ids = {question.id for question in generated_questions}
    assert generated_ids.issubset(owner_questions)
    assert not generated_ids.intersection(other_questions)
    other_token = _login(client, "student_b")
    blocked_other = client.post(
        "/api/tests/practice/submit",
        headers=_headers(other_token),
        json={
            "course_id": course_id,
            "answers": [{"question_id": generated_questions[0].id, "answer": "A"}],
        },
    )
    assert blocked_other.status_code == 400
    assert "未发布或无权访问" in blocked_other.json()["detail"]

    assert client.post(
        "/api/resources/generate",
        headers=_headers(teacher_token),
        json={"course_id": course_id, "rtype": "wrong_review"},
    ).status_code == 400

    business_data["course1"].status = "archived"
    db_session.commit()
    discovered = client.get(
        "/api/courses", headers=_headers(token), params={"include_archived": True}
    ).json()["data"]
    assert business_data["course1"].id not in {item["id"] for item in discovered}
    assert client.post(
        "/api/resources/generate",
        headers=_headers(token),
        json={"course_id": course_id, "rtype": "lecture"},
    ).status_code == 409
    assert client.get(
        "/api/resources/lecture/stream",
        headers=_headers(token),
        params={"course_id": course_id},
    ).status_code == 403
    assert client.get(
        "/api/resources/lecture/stream",
        headers=_headers(teacher_token),
        params={"course_id": course_id},
    ).status_code == 409
    assert client.post(
        "/api/agents/run", headers=_headers(token), json={"course_id": course_id}
    ).status_code == 409


def test_teacher_ownership_is_enforced_across_course_file_question_and_review(client, business_data):
    owner = _login(client, "teacher")
    outsider = _login(client, "teacher2")
    course_id = business_data["course1"].id
    assert client.put(
        f"/api/courses/{course_id}", json={"description": "越权修改"}, headers=_headers(outsider)
    ).status_code == 403
    assert client.get(
        f"/api/files/course/{course_id}", headers=_headers(outsider)
    ).status_code == 403
    assert client.get(
        f"/api/files/{business_data['file'].id}/download", headers=_headers(outsider)
    ).status_code == 403
    assert client.delete(
        f"/api/files/{business_data['file'].id}", headers=_headers(outsider)
    ).status_code == 403
    assert client.post(
        f"/api/files/{business_data['file'].id}/retry", headers=_headers(outsider)
    ).status_code == 403
    assert client.get(
        "/api/questions", params={"course_id": course_id}, headers=_headers(outsider)
    ).status_code == 403
    assert client.get(f"/api/knowledge/course/{course_id}").status_code == 401
    assert client.get(
        f"/api/knowledge/course/{course_id}", headers=_headers(outsider)
    ).status_code == 403
    assert client.get(
        f"/api/knowledge/graph/{course_id}", headers=_headers(outsider)
    ).status_code == 403
    assert client.post(
        "/api/knowledge",
        headers=_headers(outsider),
        json={"course_id": course_id, "name": "越权知识点"},
    ).status_code == 403
    assert client.put(
        f"/api/knowledge/{business_data['kp1'].id}",
        headers=_headers(outsider),
        json={"course_id": course_id, "name": "越权修改"},
    ).status_code == 403
    assert client.delete(
        f"/api/knowledge/{business_data['kp1'].id}", headers=_headers(outsider)
    ).status_code == 403
    assert client.post(
        "/api/knowledge/relation",
        headers=_headers(outsider),
        json={
            "course_id": course_id,
            "source_id": business_data["kp1"].id,
            "target_id": business_data["kp2"].id,
            "relation": "prerequisite",
        },
    ).status_code == 403
    assert client.post(
        "/api/knowledge",
        headers=_headers(owner),
        json={
            "course_id": course_id,
            "chapter_id": business_data["chapter2"].id,
            "name": "跨课程章节挂载",
        },
    ).status_code == 400
    assert client.get(
        f"/api/stats/teacher/{course_id}", headers=_headers(outsider)
    ).status_code == 403
    assert client.get(
        f"/api/stats/experiment/{course_id}", headers=_headers(outsider)
    ).status_code == 403
    pending_id = business_data["resources"]["pending"].id
    assert client.post(
        f"/api/review/{pending_id}", json={"decision": "approved"}, headers=_headers(outsider)
    ).status_code == 403
    assert client.get(
        f"/api/reports/class/{course_id}.md", headers=_headers(outsider)
    ).status_code == 403
    approved = client.post(
        f"/api/review/{pending_id}", json={"decision": "approved"}, headers=_headers(owner)
    )
    assert approved.status_code == 200
    assert approved.json()["data"]["published"] is False
    published = client.post(f"/api/review/{pending_id}/publish", headers=_headers(owner))
    assert published.status_code == 200
    withdrawn = client.post(f"/api/review/{pending_id}/unpublish", headers=_headers(owner))
    assert withdrawn.status_code == 200
    assert withdrawn.json()["data"]["review_status"] == "approved"
    assert withdrawn.json()["data"]["published"] is False


def test_path_progress_updates_completed_count_and_learning_record(client, business_data):
    token = _login(client, "student_a")
    course_id = business_data["course1"].id
    response = client.post(f"/api/profiles/{course_id}/plan", headers=_headers(token))
    assert response.status_code == 200
    progress = client.post(
        f"/api/profiles/{course_id}/path/progress",
        headers=_headers(token),
        json={"kp_id": business_data["kp1"].id, "status": "done", "duration": 120},
    )
    assert progress.status_code == 200
    assert progress.json()["data"]["completed_nodes"] == 1
    records = client.get(f"/api/profiles/{course_id}/records", headers=_headers(token)).json()["data"]
    assert any(row["action"] == "finish" and row["kp_id"] == business_data["kp1"].id for row in records)


def test_command_center_prefers_latest_complete_pipeline(client, db_session, business_data):
    """A newer one-step parse must not replace the ten-agent command snapshot."""
    course_id = business_data["course1"].id
    full_run = AgentRun(
        trace_id="full-pipeline-trace",
        course_id=course_id,
        workflow="full_pipeline",
        status="success",
        started_at=datetime.now(),
        finished_at=datetime.now(),
        duration_ms=320,
        progress=1.0,
    )
    db_session.add(full_run)
    db_session.flush()
    db_session.add(AgentLog(
        run_id=full_run.id,
        trace_id=full_run.trace_id,
        agent="CourseParserAgent",
        step=1,
        status="success",
        output_summary='{"pages": 2, "chunks": 8, "points": 6}',
        duration_ms=20,
    ))
    parse_run = AgentRun(
        trace_id="newer-parse-trace",
        course_id=course_id,
        workflow="parse",
        status="success",
        started_at=datetime.now(),
        finished_at=datetime.now(),
        duration_ms=12,
        progress=1.0,
    )
    timeout_run = AgentRun(
        trace_id="recovered-timeout-trace",
        course_id=course_id,
        workflow="generate",
        status="failed",
        started_at=datetime.now(),
        finished_at=datetime.now(),
        duration_ms=15 * 60 * 1000,
        progress=0.2,
        error="任务执行进程中断或超时，系统已回收；可从失败记录重新发起。",
    )
    db_session.add(timeout_run)
    db_session.flush()
    db_session.add(parse_run)
    db_session.add_all([
        LLMCallLog(
            provider="mock", model="local-course-engine", purpose="quality",
            trace_id="full-pipeline-trace", success=True,
        ),
        LLMCallLog(
            provider="mock", model="local-course-engine", purpose="quality",
            trace_id="other-course-trace", success=True,
        ),
    ])
    db_session.commit()

    token = _login(client, "teacher")
    response = client.get(
        "/api/agents/command_center",
        params={"course_id": course_id},
        headers=_headers(token),
    )
    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["recent_runs"][0]["trace_id"] == "newer-parse-trace"
    assert payload["active_run"]["trace_id"] == "full-pipeline-trace"
    assert payload["hero"]["active_trace"] == "full-pipeline-trace"
    assert payload["agent_nodes"][0]["status"] == "success"
    assert payload["kpis"]["avg_duration_ms"] == 166
    experiment = client.get(
        f"/api/stats/experiment/{course_id}", headers=_headers(token)
    )
    assert experiment.status_code == 200
    assert experiment.json()["data"]["llm_calls"] == 1


def test_report_html_escapes_active_content():
    html = report_service.md_to_html("# 安全报告\n\n<script>alert('xss')</script>")
    assert "<script" not in html.lower()
    assert "&lt;script&gt;" in html
    assert "Content-Security-Policy" in html


def test_report_pdf_normalizes_unsupported_cid_glyphs():
    assert report_service._inline_markdown("课程·报告•条目") == "课程-报告-条目"


def test_security_headers_are_applied(client):
    response = client.get("/api/health")
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["referrer-policy"] == "strict-origin-when-cross-origin"
    assert client.get("/api/system/info").headers["cache-control"] == "no-store"


def test_upload_rejects_spoofed_pdf(client, business_data):
    token = _login(client, "teacher")
    response = client.post(
        f"/api/files/upload/{business_data['course1'].id}",
        headers=_headers(token),
        files={"file": ("伪造资料.pdf", b"this is not a pdf", "application/pdf")},
    )
    assert response.status_code == 400
    assert "PDF 文件头无效" in response.json()["detail"]


def test_resource_citations_are_course_scoped_and_invalidated_on_file_delete(
    client, db_session, business_data, tmp_path, monkeypatch
):
    from app.core.config import settings

    monkeypatch.setattr(settings, "UPLOAD_DIR", str(tmp_path))
    teacher = business_data["teacher"]
    course1 = business_data["course1"]
    course2 = business_data["course2"]
    local_path = tmp_path / "course-one.md"
    other_path = tmp_path / "course-two.md"
    local_path.write_text("课程一唯一证据", encoding="utf-8")
    other_path.write_text("课程二不可见证据", encoding="utf-8")
    local_file = CourseFile(
        course_id=course1.id,
        uploader_id=teacher.id,
        filename="course-one.md",
        stored_path=str(local_path),
        file_type="md",
        size=local_path.stat().st_size,
        parse_status="parsed",
        indexed=True,
    )
    other_file = CourseFile(
        course_id=course2.id,
        uploader_id=business_data["teacher2"].id,
        filename="course-two.md",
        stored_path=str(other_path),
        file_type="md",
        size=other_path.stat().st_size,
        parse_status="parsed",
        indexed=True,
    )
    db_session.add_all([local_file, other_file])
    db_session.flush()
    local_chunk = DocumentChunk(
        course_id=course1.id,
        file_id=local_file.id,
        chunk_index=0,
        text="课程一唯一证据",
        page=1,
        source_name=local_file.filename,
        vector_id=0,
        tokens=8,
    )
    other_chunk = DocumentChunk(
        course_id=course2.id,
        file_id=other_file.id,
        chunk_index=0,
        text="课程二不可见证据",
        page=1,
        source_name=other_file.filename,
        vector_id=0,
        tokens=8,
    )
    db_session.add_all([local_chunk, other_chunk])
    db_session.flush()

    def citation(file_row, chunk_row):
        return {
            "source_file_id": file_row.id,
            "source_file_name": file_row.filename,
            "source": file_row.filename,
            "chunk_id": chunk_row.id,
            "page": 1,
            "page_number": 1,
            "score": 0.8,
            "relevance_score": 0.8,
            "excerpt": chunk_row.text,
        }

    resource = GeneratedResource(
        course_id=course1.id,
        rtype="lecture",
        title="引用隔离讲义",
        content="# 引用隔离讲义",
        citations=json.dumps(
            [citation(local_file, local_chunk), citation(other_file, other_chunk)],
            ensure_ascii=False,
        ),
        quality_score=80,
        review_status="published",
        published=True,
    )
    db_session.add(resource)
    db_session.commit()
    local_file_id = int(local_file.id)
    local_chunk_id = int(local_chunk.id)
    resource_id = int(resource.id)

    token = _login(client, "teacher")
    listed = client.get(
        "/api/resources",
        params={"course_id": course1.id},
        headers=_headers(token),
    )
    assert listed.status_code == 200
    output = next(row for row in listed.json()["data"] if row["id"] == resource_id)
    assert len(output["citations"]) == 1
    assert output["citations"][0]["source_file_id"] == local_file_id

    deleted = client.delete(f"/api/files/{local_file_id}", headers=_headers(token))
    assert deleted.status_code == 200
    assert deleted.json()["data"]["invalidated_resource_ids"] == [resource_id]
    db_session.refresh(resource)
    assert json.loads(resource.citations) == []
    assert resource.published is False
    assert resource.review_status == "pending"
    assert db_session.get(CourseFile, local_file_id) is None
    assert db_session.get(DocumentChunk, local_chunk_id) is None


def test_student_settings_persist_and_sync_course_profile(
    client, db_session, business_data, monkeypatch
):
    token = _login(client, "student_a")
    course_id = business_data["course1"].id
    profile = StudentProfile(
        student_id=business_data["student1"].id,
        course_id=course_id,
        goal="旧目标",
        weekly_hours=3,
        pref_format="文字",
        pref_style="理解型",
    )
    db_session.add(profile)
    archived_course = Course(
        name="历史归档课程",
        code="ARCHIVED-SETTINGS",
        teacher_id=business_data["teacher"].id,
        status="archived",
    )
    db_session.add(archived_course)
    db_session.flush()
    db_session.add(CourseEnrollment(
        course_id=archived_course.id,
        student_id=business_data["student1"].id,
        goal="历史目标",
        weekly_hours=2,
    ))
    db_session.commit()

    initial = client.get("/api/auth/me/settings", headers=_headers(token))
    assert initial.status_code == 200
    returned_course_ids = {
        item["course_id"] for item in initial.json()["data"]["courses"]
    }
    assert returned_course_ids == {course_id}
    assert archived_course.id not in returned_course_ids

    payload = {
        "full_name": "学生甲·更新",
        "email": "student_a_updated@test.com",
        "course_id": course_id,
        "learning_goal": "能够解释核心概念并完成实践任务",
        "weekly_hours": 9,
        "learning_preferences": ["视觉图解", "实践演练"],
    }
    updated = client.put(
        "/api/auth/me/settings", json=payload, headers=_headers(token)
    )
    assert updated.status_code == 200
    body = updated.json()["data"]
    assert body["user"]["full_name"] == "学生甲·更新"
    assert body["learning_preferences"] == ["视觉图解", "实践演练"]

    db_session.refresh(business_data["student1"])
    db_session.refresh(profile)
    enrollment = db_session.query(CourseEnrollment).filter_by(
        student_id=business_data["student1"].id, course_id=course_id
    ).one()
    assert business_data["student1"].role == "student"
    assert business_data["student1"].learning_goal == payload["learning_goal"]
    assert business_data["student1"].weekly_hours == 9
    assert enrollment.goal == payload["learning_goal"]
    assert enrollment.weekly_hours == 9
    assert profile.goal == payload["learning_goal"]
    assert profile.pref_format == "视觉图解,实践演练"
    assert profile.pref_style == "实践型"

    # 后续重新生成画像时，以学生主动设置为准，不被模型猜测的偏好覆盖。
    monkeypatch.setattr(profile_service.llm_client, "chat_json", lambda *args, **kwargs: {
        "pref_format": "音视频学习",
        "pref_style": "记忆型",
    })
    rebuilt = profile_service.build_profile(
        db_session,
        business_data["student1"].id,
        course_id,
        goal=payload["learning_goal"],
        weekly_hours=9,
        answers=[],
    )
    assert rebuilt.pref_format == "视觉图解,实践演练"
    assert rebuilt.pref_style == "实践型"

    malicious = client.put(
        "/api/auth/me/settings",
        json={**payload, "role": "admin"},
        headers=_headers(token),
    )
    assert malicious.status_code == 422
    assert client.get(
        "/api/auth/me/settings", headers=_headers(_login(client, "teacher"))
    ).status_code == 403


def test_course_parser_rejects_cross_course_file_before_any_write(
    db_session, business_data
):
    """A task may never attach one course's file to another course's knowledge base."""
    source_file = business_data["file"]
    target_course = business_data["course2"]
    initial_file_state = (
        source_file.parse_status,
        source_file.indexed,
        source_file.parse_summary,
    )
    initial_chunk_count = db_session.query(DocumentChunk).filter(
        DocumentChunk.course_id == target_course.id
    ).count()
    initial_chapter_count = db_session.query(CourseChapter).filter(
        CourseChapter.course_id == target_course.id
    ).count()
    initial_point_count = db_session.query(KnowledgePoint).filter(
        KnowledgePoint.course_id == target_course.id
    ).count()

    run = AgentRun(
        trace_id="cross-course-parser-guard",
        course_id=target_course.id,
        workflow="parse",
        status="running",
    )
    parser = CourseParserAgent(db_session, run, run.trace_id)

    with pytest.raises(ValueError, match="不属于当前课程"):
        parser.handle({
            "course_id": target_course.id,
            "file_id": source_file.id,
        })

    db_session.expire_all()
    persisted_file = db_session.get(CourseFile, source_file.id)
    assert (
        persisted_file.parse_status,
        persisted_file.indexed,
        persisted_file.parse_summary,
    ) == initial_file_state
    assert db_session.query(DocumentChunk).filter(
        DocumentChunk.course_id == target_course.id
    ).count() == initial_chunk_count
    assert db_session.query(CourseChapter).filter(
        CourseChapter.course_id == target_course.id
    ).count() == initial_chapter_count
    assert db_session.query(KnowledgePoint).filter(
        KnowledgePoint.course_id == target_course.id
    ).count() == initial_point_count

def test_teacher_can_manage_course_chapters_and_knowledge_relations(
    client, db_session, business_data
):
    owner = _login(client, "teacher")
    outsider = _login(client, "teacher2")
    course_id = business_data["course1"].id

    edited_course = client.put(
        f"/api/courses/{course_id}",
        json={"name": "高等数学·进阶", "code": "MATH-AUDIT-2", "status": "active"},
        headers=_headers(owner),
    )
    assert edited_course.status_code == 200
    assert edited_course.json()["data"]["code"] == "MATH-AUDIT-2"

    created = client.post(
        f"/api/courses/{course_id}/chapters",
        json={"title": "极限与变化率", "summary": "课程核心章节", "order_index": 2},
        headers=_headers(owner),
    )
    assert created.status_code == 200
    chapter_id = created.json()["data"]["id"]
    assert client.put(
        f"/api/courses/{course_id}/chapters/{chapter_id}",
        json={"title": "极限、导数与变化率", "summary": "已更新", "order_index": 1},
        headers=_headers(outsider),
    ).status_code == 403
    updated_chapter = client.put(
        f"/api/courses/{course_id}/chapters/{chapter_id}",
        json={"title": "极限、导数与变化率", "summary": "已更新", "order_index": 1},
        headers=_headers(owner),
    )
    assert updated_chapter.status_code == 200
    assert updated_chapter.json()["data"]["order_index"] == 1

    business_data["kp1"].chapter_id = chapter_id
    db_session.commit()
    relation = client.post(
        "/api/knowledge/relation",
        json={
            "course_id": course_id,
            "source_id": business_data["kp1"].id,
            "target_id": business_data["kp2"].id,
            "relation": "prerequisite",
            "weight": 0.8,
        },
        headers=_headers(owner),
    )
    assert relation.status_code == 200
    relation_id = relation.json()["data"]["id"]
    graph = client.get(
        f"/api/knowledge/graph/{course_id}", headers=_headers(owner)
    ).json()["data"]
    assert any(item["id"] == relation_id for item in graph["edges"])

    assert client.put(
        f"/api/knowledge/relation/{relation_id}",
        json={
            "course_id": course_id,
            "source_id": business_data["kp1"].id,
            "target_id": business_data["kp2"].id,
            "relation": "易混",
            "weight": 0.6,
        },
        headers=_headers(outsider),
    ).status_code == 403
    changed = client.put(
        f"/api/knowledge/relation/{relation_id}",
        json={
            "course_id": course_id,
            "source_id": business_data["kp1"].id,
            "target_id": business_data["kp2"].id,
            "relation": "易混",
            "weight": 0.6,
        },
        headers=_headers(owner),
    )
    assert changed.status_code == 200
    assert changed.json()["data"]["relation"] == "易混"
    assert client.delete(
        f"/api/knowledge/relation/{relation_id}", headers=_headers(owner)
    ).status_code == 200
    assert db_session.get(KnowledgeRelation, relation_id) is None

    deleted = client.delete(
        f"/api/courses/{course_id}/chapters/{chapter_id}", headers=_headers(owner)
    )
    assert deleted.status_code == 200
    db_session.refresh(business_data["kp1"])
    assert business_data["kp1"].chapter_id is None
