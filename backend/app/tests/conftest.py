"""pytest 配置：使用内存 SQLite 测试库。"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.main import app
from app.core.security import hash_password
from app.models.user import User


@pytest.fixture(scope="function")
def db_session():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False},
                           poolclass=StaticPool)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    # 预置管理员 + 教师
    session.add(User(username="admin", email="admin@test.com",
                     hashed_password=hash_password("123456", rounds=10_000), role="admin", full_name="管理员"))
    session.add(User(username="teacher", email="teacher@test.com",
                     hashed_password=hash_password("123456", rounds=10_000), role="teacher", full_name="王老师"))
    session.commit()
    yield session
    session.close()


@pytest.fixture(scope="function")
def client(db_session):
    def _override():
        try:
            yield db_session
        finally:
            pass
    app.dependency_overrides[get_db] = _override
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def admin_token(client):
    r = client.post("/api/auth/login", json={"username": "admin", "password": "123456"})
    return r.json()["data"]["access_token"]


@pytest.fixture
def teacher_token(client):
    r = client.post("/api/auth/login", json={"username": "teacher", "password": "123456"})
    return r.json()["data"]["access_token"]
