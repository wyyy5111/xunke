#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "[1/7] 构建 Vue 生产前端"
(cd frontend && npm run build)

echo "[2/7] 准备桌面图标"
mkdir -p desktop/assets desktop/build
test -f desktop/assets/AppIcon.icns
test -f desktop/assets/icon.png

echo "[3/7] 安装桌面构建依赖"
.venv/bin/python -m pip install --disable-pip-version-check -q 'pyinstaller>=6.10,<7'
(cd desktop && npm install --no-audit --no-fund)

echo "[4/7] 构建 macOS 内置后端"
rm -rf desktop/build/backend-macos desktop/build/pyinstaller
PYTHONPATH="$ROOT/backend" .venv/bin/pyinstaller \
  --noconfirm --clean \
  --distpath desktop/build/backend-macos \
  --workpath desktop/build/pyinstaller \
  desktop/XunkeFlowBackend.spec

echo "[5/7] 组装 Windows x64 内置运行时"
.venv/bin/python scripts/build_windows_runtime.py

echo "[6/7] 构建 macOS DMG"
(cd desktop && \
  ELECTRON_MIRROR=https://npmmirror.com/mirrors/electron/ \
  ELECTRON_BUILDER_BINARIES_MIRROR=https://npmmirror.com/mirrors/electron-builder-binaries/ \
  npm run dist:mac)

echo "[7/7] 构建 Windows x64 安装程序"
(cd desktop && \
  ELECTRON_MIRROR=https://npmmirror.com/mirrors/electron/ \
  ELECTRON_BUILDER_BINARIES_MIRROR=https://npmmirror.com/mirrors/electron-builder-binaries/ \
  npm run dist:win)

echo "[DONE] 独立桌面安装包已生成到 desktop/dist"
