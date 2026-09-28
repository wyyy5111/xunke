"""数据库引擎与会话。"""
from __future__ import annotations
from typing import Generator
from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.orm import sessionmaker, declarative_base, Session

from app.core.config import settings
from app.utils.logger import logger

connect_args = {"check_same_thread": False} if settings.DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(settings.DATABASE_URL, connect_args=connect_args, future=True, echo=False)

# SQLite PRAGMA 配置（全部 try/except，兼容 NFS/FUSE/macOS 挂载目录）
if settings.DATABASE_URL.startswith("sqlite"):
    @event.listens_for(engine, "connect")
    def _sqlite_pragmas(dbapi_conn, _):
        cur = dbapi_conn.cursor()
        try:
            cur.execute("PRAGMA foreign_keys=ON;")
        except Exception as exc:
            logger.debug("SQLite foreign_keys PRAGMA unavailable: %s", exc)
        try:
            cur.execute("PRAGMA journal_mode=WAL;")
        except Exception:
            try:
                cur.execute("PRAGMA journal_mode=MEMORY;")
            except Exception as exc:
                logger.debug("SQLite journal mode fallback unavailable: %s", exc)
        try:
            cur.execute("PRAGMA synchronous=NORMAL;")
            cur.execute("PRAGMA temp_store=MEMORY;")
        except Exception as exc:
            logger.debug("SQLite performance PRAGMA unavailable: %s", exc)
        cur.close()

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
Base = declarative_base()


def init_db() -> None:
    """建表（开发期使用；生产用 alembic）。"""
    import app.models  # noqa: F401  保证所有模型已加载
    Base.metadata.create_all(bind=engine)
    _ensure_compatible_columns()


def _ensure_compatible_columns() -> None:
    """对早期 SQLite 演示库做幂等的小型结构升级。

    这是在引入 Alembic 前的兼容层：补齐新增列，并把旧版本地生成器
    的展示标签归一为当前 Mock Provider；不删除课程、用户或学习数据。
    """
    if not settings.DATABASE_URL.startswith("sqlite"):
        return
    expected = {
        "users": {
            "learning_goal": "VARCHAR(256) DEFAULT '' NOT NULL",
            "weekly_hours": "INTEGER DEFAULT 6 NOT NULL",
            "learning_preferences": (
                "VARCHAR(128) DEFAULT '文本精读,视觉图解,实践演练' NOT NULL"
            ),
        },
        "document_chunks": {
            "vector_id": "INTEGER DEFAULT 0 NOT NULL",
        },
        "llm_call_logs": {
            "response_chars": "INTEGER DEFAULT 0",
            "retry_count": "INTEGER DEFAULT 0",
            "fallback_used": "BOOLEAN DEFAULT 0",
            "estimated_cost": "FLOAT",
        },
        "agent_logs": {
            "role_description": "VARCHAR(256) DEFAULT ''",
            "model_provider": "VARCHAR(32) DEFAULT 'local'",
            "model_name": "VARCHAR(64) DEFAULT 'rule-engine'",
            "citation_count": "INTEGER DEFAULT 0",
            "quality_score": "FLOAT DEFAULT 0",
            "retry_count": "INTEGER DEFAULT 0",
        },
    }
    with engine.begin() as conn:
        inspector = inspect(conn)
        tables = set(inspector.get_table_names())
        for table_name, columns in expected.items():
            if table_name not in tables:
                continue
            existing = {column["name"] for column in inspector.get_columns(table_name)}
            for column_name, ddl in columns.items():
                if column_name not in existing:
                    conn.execute(text(f'ALTER TABLE "{table_name}" ADD COLUMN "{column_name}" {ddl}'))
        if "llm_call_logs" in tables:
            conn.execute(text(
                "UPDATE llm_call_logs SET provider = 'mock' "
                "WHERE lower(coalesce(provider, '')) IN ('builtin', 'local')"
            ))
            conn.execute(text(
                "UPDATE llm_call_logs SET model = 'local-course-engine' "
                "WHERE lower(coalesce(model, '')) IN ('xunkeflow-builtin', 'rule-engine')"
            ))
        if {"generated_resources", "agent_runs"}.issubset(tables):
            # Legacy ExerciseAgent rows were marked personalized but omitted
            # student_id. Recover the owner from the originating AgentRun.
            conn.execute(text(
                "UPDATE generated_resources "
                "SET student_id = ("
                "  SELECT agent_runs.student_id FROM agent_runs "
                "  WHERE agent_runs.id = generated_resources.agent_run_id"
                ") "
                "WHERE is_personalized = 1 AND student_id IS NULL "
                "AND agent_run_id IS NOT NULL "
                "AND EXISTS (SELECT 1 FROM agent_runs "
                "            WHERE agent_runs.id = generated_resources.agent_run_id "
                "            AND agent_runs.student_id IS NOT NULL)"
            ))
            # If ownership still cannot be determined, keep the legacy asset
            # out of every student's published feed until a teacher regenerates it.
            conn.execute(text(
                "UPDATE generated_resources "
                "SET published = 0, review_status = 'risk' "
                "WHERE is_personalized = 1 AND student_id IS NULL"
            ))
        legacy_question_tables = {
            "questions", "question_options", "test_answers", "wrong_questions"
        }
        if legacy_question_tables.issubset(tables):
            # Old ExerciseAgent versions created AI questions before their
            # resource existed. Remove only unlinked rows that have never been
            # answered or placed in a wrong-question record.
            conn.execute(text(
                "DELETE FROM question_options WHERE question_id IN ("
                "  SELECT q.id FROM questions q "
                "  WHERE q.source = 'ai' AND q.ai_resource_id IS NULL "
                "  AND NOT EXISTS (SELECT 1 FROM test_answers ta WHERE ta.question_id = q.id) "
                "  AND NOT EXISTS (SELECT 1 FROM wrong_questions w WHERE w.question_id = q.id)"
                ")"
            ))
            conn.execute(text(
                "DELETE FROM questions WHERE source = 'ai' AND ai_resource_id IS NULL "
                "AND NOT EXISTS (SELECT 1 FROM test_answers ta WHERE ta.question_id = questions.id) "
                "AND NOT EXISTS (SELECT 1 FROM wrong_questions w WHERE w.question_id = questions.id)"
            ))


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
