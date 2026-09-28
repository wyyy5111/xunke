"""初始化数据库：建表 + seed 演示数据。"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from app.core.database import init_db
from app.database.seed import ensure_seed


def main():
    print("[1/2] 创建数据表...")
    init_db()
    print("[2/2] 写入演示数据...")
    ensure_seed()
    print("✅ 数据库初始化完成")


if __name__ == "__main__":
    main()
