"""管理员角色治理、运行状态与安全数据快照回归测试。"""
from __future__ import annotations

from app.models.course import Course, CourseFile
from app.models.system import SystemConfig
from app.models.user import User


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_role_change_is_admin_only_and_strictly_validated(
    client, admin_token, teacher_token, db_session
):
    teacher = db_session.query(User).filter(User.username == "teacher").one()

    anonymous = client.patch(
        f"/api/admin/users/{teacher.id}/role",
        json={"role": "student"},
    )
    assert anonymous.status_code == 401

    forbidden = client.patch(
        f"/api/admin/users/{teacher.id}/role",
        json={"role": "student"},
        headers=_headers(teacher_token),
    )
    assert forbidden.status_code == 403

    invalid = client.patch(
        f"/api/admin/users/{teacher.id}/role",
        json={"role": "super_admin"},
        headers=_headers(admin_token),
    )
    assert invalid.status_code == 422
    db_session.refresh(teacher)
    assert teacher.role == "teacher"


def test_role_change_rejects_self_and_preserves_last_enabled_admin(
    client, admin_token, db_session
):
    admin = db_session.query(User).filter(User.username == "admin").one()

    self_role = client.patch(
        f"/api/admin/users/{admin.id}/role",
        json={"role": "teacher"},
        headers=_headers(admin_token),
    )
    assert self_role.status_code == 409
    assert "不能修改自己的管理员角色" in self_role.json()["detail"]

    last_admin = client.put(
        f"/api/admin/users/{admin.id}",
        json={"is_active": False},
        headers=_headers(admin_token),
    )
    assert last_admin.status_code == 409
    assert "至少一个启用的管理员" in last_admin.json()["detail"]
    db_session.refresh(admin)
    assert admin.role == "admin"
    assert admin.is_active is True


def test_admin_can_change_another_users_role(client, admin_token, db_session):
    teacher = db_session.query(User).filter(User.username == "teacher").one()

    response = client.patch(
        f"/api/admin/users/{teacher.id}/role",
        json={"role": "admin"},
        headers=_headers(admin_token),
    )
    assert response.status_code == 200
    assert response.json()["data"]["role"] == "admin"
    db_session.refresh(teacher)
    assert teacher.role == "admin"


def test_admin_snapshot_is_downloadable_and_excludes_sensitive_fields(
    client, admin_token, teacher_token, db_session
):
    teacher = db_session.query(User).filter(User.username == "teacher").one()
    course = Course(
        name="运营快照课程",
        code="ADMIN-SNAPSHOT",
        teacher_id=teacher.id,
        status="active",
    )
    db_session.add(course)
    db_session.flush()
    private_path = "/private/var/xunkeflow/should-never-be-exported.md"
    secret_marker = "do-not-export-secret-marker"
    db_session.add(CourseFile(
        course_id=course.id,
        uploader_id=teacher.id,
        filename="internal-course.md",
        stored_path=private_path,
        file_type="md",
        size=128,
        parse_status="parsed",
        indexed=True,
    ))
    db_session.add(SystemConfig(
        key="DEEPSEEK_API_KEY",
        value=secret_marker,
        category="llm",
        remark="测试敏感配置",
    ))
    db_session.commit()

    forbidden = client.get(
        "/api/admin/data-snapshot",
        headers=_headers(teacher_token),
    )
    assert forbidden.status_code == 403

    response = client.get(
        "/api/admin/data-snapshot",
        headers=_headers(admin_token),
    )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")
    assert response.headers["content-disposition"].startswith(
        'attachment; filename="xunkeflow-data-snapshot-'
    )
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-snapshot-format"] == "xunkeflow-admin-snapshot-v1"
    payload = response.json()
    assert payload["snapshot"]["restorable"] is False
    assert payload["table_counts"]["course_files"] == 1
    assert payload["business_summary"]["knowledge_base"]["indexed_files"] == 1
    assert payload["courses"][0]["name"] == "运营快照课程"

    serialized = response.text
    assert "hashed_password" not in serialized
    assert "password_hash" not in serialized
    assert teacher.hashed_password not in serialized
    assert secret_marker not in serialized
    assert private_path not in serialized
    assert "stored_path" not in serialized
    assert "DEEPSEEK_API_KEY" not in serialized
    assert "JWT_SECRET" not in serialized


def test_admin_dashboard_exposes_application_runtime_without_infrastructure_secrets(
    client, admin_token
):
    response = client.get(
        "/api/admin/dashboard",
        headers=_headers(admin_token),
    )
    assert response.status_code == 200
    runtime = response.json()["data"]["runtime_status"]
    assert runtime["database"]["status"] == "healthy"
    assert runtime["database"]["backend"] in {"SQLite", "PostgreSQL", "MySQL", "SQL 数据库"}
    assert runtime["ai"]["mode"] in {"demo", "real"}
    assert runtime["agents"]["status"] in {"ready", "running"}
    assert runtime["application"]["version"]
    assert runtime["application"]["started_at"]
    assert runtime["application"]["uptime_seconds"] >= 0
    assert "database_url" not in response.text.lower()
    assert "jwt_secret" not in response.text.lower()
