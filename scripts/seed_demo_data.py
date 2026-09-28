"""初始化或显式重建演示数据。

默认执行是幂等的：已有 seed 标志时不会重复插入章节、知识点、题目或资源。
只有显式传入 ``--reset`` 时才会备份并重建 SQLite 演示库。
"""
from __future__ import annotations

import argparse
import shutil
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from app.core.config import settings  # noqa: E402
from app.core.database import SessionLocal, engine, init_db  # noqa: E402
from app.database.seed import ensure_seed  # noqa: E402
from app.models.course import Course  # noqa: E402
from app.models.knowledge import KnowledgePoint  # noqa: E402
from app.models.question import Question  # noqa: E402
from app.models.user import User  # noqa: E402


def sqlite_path() -> Path:
    prefix = "sqlite:///"
    if not settings.DATABASE_URL.startswith(prefix):
        raise SystemExit("--reset 只支持本地 SQLite 演示库；其他数据库请使用正式迁移与备份流程。")
    raw = settings.DATABASE_URL[len(prefix):]
    path = Path(raw)
    return path if path.is_absolute() else (ROOT / path).resolve()


def reset_sqlite() -> Path | None:
    db_path = sqlite_path()
    engine.dispose()
    backup = None
    if db_path.exists():
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup = db_path.with_suffix(db_path.suffix + f".{stamp}.bak")
        shutil.copy2(db_path, backup)
        db_path.unlink()
    for suffix in ("-wal", "-shm"):
        sidecar = Path(str(db_path) + suffix)
        if sidecar.exists():
            sidecar.unlink()
    return backup


def main() -> None:
    parser = argparse.ArgumentParser(description="初始化 XunkeFlow 演示数据")
    parser.add_argument("--reset", action="store_true", help="备份并重建本地 SQLite 演示库")
    args = parser.parse_args()

    backup = reset_sqlite() if args.reset else None
    init_db()
    ensure_seed()
    if backup:
        print(f"[OK] 已重建演示库；旧数据库备份：{backup}")
    else:
        print("[OK] 演示数据已检查；已有数据不会重复写入。")
    db = SessionLocal()
    try:
        active_ids = [row[0] for row in db.query(Course.id).filter(Course.status == "active").all()]
        scoped_ids = active_ids or [-1]
        knowledge_count = db.query(KnowledgePoint).filter(KnowledgePoint.course_id.in_(scoped_ids)).count()
        question_count = db.query(Question).filter(Question.course_id.in_(scoped_ids)).count()
        student_count = db.query(User).filter(User.role == "student", User.is_active == True).count()
    finally:
        db.close()
    print(
        f"[DATA] {len(active_ids)} 门有效跨学科课程 / {knowledge_count} 个知识点 / "
        f"{question_count} 道题库题目 / {student_count} 名学生 / 可追溯 Agent 任务"
    )


if __name__ == "__main__":
    main()
