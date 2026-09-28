#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON="${PYTHON:-$ROOT/.venv/bin/python}"

if [ ! -x "$PYTHON" ]; then
  echo "[ERROR] 未找到项目虚拟环境解释器：$PYTHON" >&2
  echo "请先执行 scripts/start_dev.sh 完成环境初始化，或通过 PYTHON 指定 Python 3.12。" >&2
  exit 1
fi

exec "$PYTHON" "$ROOT/scripts/seed_demo_data.py" "$@"
