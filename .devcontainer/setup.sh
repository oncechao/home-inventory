#!/usr/bin/env bash
# Codespace 第一次创建时运行：安装依赖、建数据库。
set -euo pipefail
cd "$(dirname "$0")/.."

python -m venv .venv
.venv/bin/pip install --quiet -r requirements-dev.txt
npm --prefix frontend ci
.venv/bin/alembic -c backend/alembic.ini upgrade head
