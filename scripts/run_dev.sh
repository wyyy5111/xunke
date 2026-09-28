#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV="$ROOT/.venv"
PYTHON_BOOTSTRAP="${PYTHON_BOOTSTRAP:-python3.12}"
DEV_HOST="${DEV_HOST:-127.0.0.1}"
BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_PORT="${FRONTEND_PORT:-5173}"

check_port() {
  local port="$1"
  if command -v lsof >/dev/null 2>&1 && lsof -nP -iTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1; then
    echo "[ERROR] 端口 $port 已被占用。请设置 BACKEND_PORT 或 FRONTEND_PORT 后重试。" >&2
    return 1
  fi
}

if [ "$BACKEND_PORT" = "$FRONTEND_PORT" ]; then
  echo "[ERROR] BACKEND_PORT 与 FRONTEND_PORT 不能相同。" >&2
  exit 1
fi

check_port "$BACKEND_PORT"
check_port "$FRONTEND_PORT"

if ! command -v "$PYTHON_BOOTSTRAP" >/dev/null 2>&1; then
  echo "[ERROR] 未找到 Python 3.12。请先安装 Python 3.12，或通过 PYTHON_BOOTSTRAP 指定兼容解释器。" >&2
  exit 1
fi

PYTHON_VERSION="$("$PYTHON_BOOTSTRAP" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
if [ "$PYTHON_VERSION" != "3.12" ]; then
  echo "[ERROR] 当前解释器版本为 $PYTHON_VERSION，本项目启动脚本要求 Python 3.12。" >&2
  exit 1
fi

if ! command -v node >/dev/null 2>&1 || ! command -v npm >/dev/null 2>&1; then
  echo "[ERROR] 未找到 Node.js/npm。请安装 Node.js 24.x。" >&2
  exit 1
fi

if ! node -e 'const [m,n]=process.versions.node.split(".").map(Number); process.exit((m===20&&n>=19)||(m===22&&n>=12)||m>=24?0:1)'; then
  echo "[ERROR] 当前 Node.js $(node --version) 不满足 Vite 8 要求。请安装 Node.js 24.x（或 20.19+/22.12+）。" >&2
  exit 1
fi

if [ ! -f "$ROOT/.env" ]; then
  install -m 600 "$ROOT/.env.example" "$ROOT/.env"
  echo "[INFO] 已创建本地 .env；当前默认使用 Mock 演示模式。"
else
  chmod 600 "$ROOT/.env"
fi

if [ ! -x "$VENV/bin/python" ]; then
  echo "[1/5] 创建 Python 3.12 虚拟环境..."
  "$PYTHON_BOOTSTRAP" -m venv "$VENV"
fi

PYTHON="$VENV/bin/python"

echo "[2/5] 安装后端依赖..."
"$PYTHON" -m pip install --disable-pip-version-check -q -r "$ROOT/backend/requirements.txt"

echo "[3/5] 安装前端依赖..."
(
  cd "$ROOT/frontend"
  npm ci --no-audit --no-fund
)

cleanup() {
  local code=$?
  trap - EXIT INT TERM
  if [ -n "${BACK_PID:-}" ]; then kill "$BACK_PID" 2>/dev/null || true; fi
  if [ -n "${FRONT_PID:-}" ]; then kill "$FRONT_PID" 2>/dev/null || true; fi
  wait 2>/dev/null || true
  exit "$code"
}
trap cleanup EXIT INT TERM

echo "[4/5] 启动 FastAPI：http://$DEV_HOST:$BACKEND_PORT"
(
  cd "$ROOT"
  exec env PYTHONPATH="$ROOT/backend" "$PYTHON" -m uvicorn app.main:app --host "$DEV_HOST" --port "$BACKEND_PORT" --reload
) &
BACK_PID=$!

echo "[5/5] 启动 Vue：http://$DEV_HOST:$FRONTEND_PORT"
(
  cd "$ROOT/frontend"
  exec env BACKEND_PORT="$BACKEND_PORT" FRONTEND_PORT="$FRONTEND_PORT" \
    VITE_DEV_PROXY_TARGET="http://$DEV_HOST:$BACKEND_PORT" \
    npm run dev -- --host "$DEV_HOST" --port "$FRONTEND_PORT"
) &
FRONT_PID=$!

echo "[READY] 按 Ctrl+C 停止前后端服务。"
while kill -0 "$BACK_PID" 2>/dev/null && kill -0 "$FRONT_PID" 2>/dev/null; do
  sleep 1
done

echo "[ERROR] 前端或后端进程已提前退出，正在停止开发环境。" >&2
exit 1
