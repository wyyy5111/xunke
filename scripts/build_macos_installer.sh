#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

REQUESTED_ARCH="${1:-$(uname -m)}"
case "$REQUESTED_ARCH" in
  arm64)
    PYINSTALLER_ARCH="arm64"
    BUILDER_ARCH="arm64"
    DEFAULT_PYTHON="$ROOT/.venv/bin/python"
    ;;
  x86_64|x64)
    PYINSTALLER_ARCH="x86_64"
    BUILDER_ARCH="x64"
    DEFAULT_PYTHON="$ROOT/.venv/bin/python"
    ;;
  *)
    echo "不支持的 macOS 架构：$REQUESTED_ARCH（仅支持 arm64、x86_64/x64）" >&2
    exit 2
    ;;
esac

PYTHON_BIN="${XUNKEFLOW_MAC_PYTHON:-$DEFAULT_PYTHON}"
if [[ ! -x "$PYTHON_BIN" ]]; then
  echo "未找到可执行 Python：$PYTHON_BIN" >&2
  echo "可通过 XUNKEFLOW_MAC_PYTHON 指定与目标架构一致的 Python 3.12。" >&2
  exit 2
fi

ACTUAL_ARCH="$($PYTHON_BIN -c 'import platform; print(platform.machine())')"
if [[ "$PYINSTALLER_ARCH" == "arm64" && "$ACTUAL_ARCH" != "arm64" ]]; then
  echo "Python 架构为 $ACTUAL_ARCH，无法构建 arm64 后端。" >&2
  exit 2
fi
if [[ "$PYINSTALLER_ARCH" == "x86_64" && "$ACTUAL_ARCH" != "x86_64" ]]; then
  echo "Python 架构为 $ACTUAL_ARCH，无法构建 x86_64 后端。" >&2
  echo "Apple Silicon 交叉构建时，请把 XUNKEFLOW_MAC_PYTHON 指向 Rosetta x86_64 Python。" >&2
  exit 2
fi

echo "[1/5] 构建 Vue 生产前端"
(cd frontend && npm run build)

echo "[2/5] 检查桌面构建依赖"
test -f desktop/assets/AppIcon.icns
test -f desktop/assets/icon.png
test -d desktop/node_modules/electron
"$PYTHON_BIN" -m PyInstaller --version >/dev/null

BACKEND_OUT="desktop/build/backend-macos-$BUILDER_ARCH"
WORK_OUT="desktop/build/pyinstaller-$BUILDER_ARCH"
STAGING="desktop/build/backend-macos"
BACKUP="desktop/build/backend-macos.__restore__"

echo "[3/5] 构建 $PYINSTALLER_ARCH 内置后端"
rm -rf "$BACKEND_OUT" "$WORK_OUT"
XUNKEFLOW_TARGET_ARCH="$PYINSTALLER_ARCH" PYTHONPATH="$ROOT/backend" \
  "$PYTHON_BIN" -m PyInstaller \
  --noconfirm --clean \
  --distpath "$BACKEND_OUT" \
  --workpath "$WORK_OUT" \
  desktop/XunkeFlowBackend.spec

restore_staging() {
  rm -rf "$STAGING"
  if [[ -d "$BACKUP" ]]; then
    mv "$BACKUP" "$STAGING"
  fi
}
trap restore_staging EXIT

echo "[4/5] 准备 Electron 安装资源"
rm -rf "$BACKUP"
if [[ -d "$STAGING" ]]; then
  mv "$STAGING" "$BACKUP"
fi
cp -R "$BACKEND_OUT" "$STAGING"

echo "[5/5] 构建 macOS $BUILDER_ARCH DMG"
(cd desktop && \
  ELECTRON_MIRROR="${ELECTRON_MIRROR:-https://npmmirror.com/mirrors/electron/}" \
  ELECTRON_BUILDER_BINARIES_MIRROR="${ELECTRON_BUILDER_BINARIES_MIRROR:-https://npmmirror.com/mirrors/electron-builder-binaries/}" \
  npm run "dist:mac:$BUILDER_ARCH")

echo "[DONE] desktop/dist/XunkeFlow_macOS_1.1.0_${BUILDER_ARCH}.dmg"
