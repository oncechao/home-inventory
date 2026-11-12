#!/usr/bin/env bash
# Codespace 每次启动时运行：构建前端，后台启动后端（8000，仅内部）和前端（5173，对外）。
# 日志：/tmp/backend.log、/tmp/frontend.log
set -euo pipefail
cd "$(dirname "$0")/.."

# 仓库是公开的，代码里的默认密钥人人可见，所以每个 Codespace 生成自己的随机密钥并保存下来
SECRET_FILE="$HOME/.home-inventory-secret"
if [ ! -s "$SECRET_FILE" ]; then
  python -c 'import secrets; print(secrets.token_urlsafe(32))' > "$SECRET_FILE"
  chmod 600 "$SECRET_FILE"
fi
export SECRET_KEY="$(cat "$SECRET_FILE")"
export COOKIE_SECURE=true  # 对外地址是 HTTPS

# 先停掉上一次启动留下的进程（重复运行本脚本时）
pkill -f 'uvicorn app.main:app' || true
pkill -f 'vite preview' || true

.venv/bin/alembic -c backend/alembic.ini upgrade head
npm --prefix frontend run build > /tmp/frontend-build.log 2>&1

setsid nohup .venv/bin/uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000 \
  > /tmp/backend.log 2>&1 < /dev/null &
setsid nohup npm --prefix frontend run preview -- --host 0.0.0.0 --port 5173 --strictPort \
  > /tmp/frontend.log 2>&1 < /dev/null &

echo "已启动：前端 5173，后端 8000。日志在 /tmp/backend.log 和 /tmp/frontend.log"
