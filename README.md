# 家庭物品管理

记录家里每样东西放在哪。支持多个家庭、多层级位置（房间 › 柜子 › 收纳盒）、扫物品条码录入、给收纳箱打印二维码。

- 后端：FastAPI + SQLAlchemy（`backend/`），Vercel 入口是 `api/index.py`
- 前端：Vue 3 + Vite + Vant（`frontend/`）
- 设计文档：`docs/plans/2026-11-12-home-inventory-design.md`

## 本地开发

```bash
uv venv .venv --python 3.12
uv pip install --python .venv/bin/python -r requirements-dev.txt
.venv/bin/alembic -c backend/alembic.ini upgrade head
npm --prefix frontend install
```

开两个终端：

```bash
.venv/bin/uvicorn app.main:app --app-dir backend --reload --port 8000
```

```bash
npm --prefix frontend run dev
```

打开 http://localhost:5173 。摄像头扫码只在 localhost 或 HTTPS 下可用。

## 测试

```bash
.venv/bin/pytest -q
npm --prefix frontend run build
```

## 部署到 Vercel

1. 把仓库推到 GitHub，在 Vercel 里 Import 这个仓库。Framework Preset 选 **Other**（`vercel.json` 里已经写了 `"framework": null`），其余用 `vercel.json` 里的配置。
2. 在 Vercel 项目的 Storage / Marketplace 里添加 **Neon** 数据库并连接到项目，它会自动注入 `DATABASE_URL`。
3. 在项目的 Environment Variables 里添加 `SECRET_KEY`（用 `.env.example` 里的命令生成）。
4. 在本地对 Neon 执行迁移（用 Neon 控制台里的 **直连**（unpooled）连接串）：

   ```bash
   DATABASE_URL='postgresql://...' .venv/bin/alembic -c backend/alembic.ini upgrade head
   ```

5. 重新部署，然后检查：
   - 访问 `https://<你的域名>/api/health`，应返回 `{"ok":true}`；
   - 访问 `https://<你的域名>/api/docs`，应能打开接口文档。

   如果这两个地址返回 FastAPI 的 404，说明请求路径在改写时被改掉了，需要排查 `vercel.json` 的 `rewrites`。
6. 以后每次修改模型，都要先生成迁移（`alembic revision --autogenerate`），并在部署前对 Neon 执行 `upgrade head`。

## 注意

- 开放注册，没有验证码和登录频率限制。
- 忘记密码不能自助找回，需要在数据库里重置；改密码后，其他设备上的登录会失效。
- 家庭成员权限完全相同：任何成员都能移除别人、解散家庭。移除某人后，记得也作废还在有效期内的邀请链接，否则对方可以用旧链接重新加入。
