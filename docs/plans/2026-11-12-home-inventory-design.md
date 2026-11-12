# 家庭物品存放位置管理系统 — 设计文档

日期：2026-11-12
状态：已确认，待制定实施计划

## 1. 目标

把原来的 Node.js「序列码查询系统」完全替换为一个基于 Python 的家庭物品存放位置管理系统，用来随时回答“这个东西放在哪了”。

- 外网随时可访问，以手机浏览器为主。
- 开放注册；一个账号可以属于多个家庭；每个账号只能看到自己所在家庭的物品。
- 位置是多层级树形结构，例如「主卧 › 衣柜 › 第二层 › 蓝色收纳盒」。
- 可以扫物品条码录入；可以给收纳箱生成二维码，打印后贴上，扫码直接查看箱内物品。

### 不在第一版范围内（YAGNI）

- 物品和位置的照片
- 分类/标签、数量字段、过期提醒
- 通过条码自动查询商品名称（国内没有免费、可靠的接口；名称手动填写）
- 邮箱注册、找回密码
- 验证码、登录频率限制
- 家庭内的角色权限

## 2. 架构

```
手机/电脑浏览器 ──HTTPS──▶ Vercel（同一个项目、同一个域名）
   │                         ├─ /        → Vue 3 前端静态文件（Vite 构建）
   │                         └─ /api/*   → FastAPI（Python 函数）
   │                                          │ SQLAlchemy
   │                                          ▼
   └─ 本地开发：Vite 开发服务器把 /api 转给 uvicorn   Neon Postgres（本地用 SQLite）
```

### 技术栈

- **后端**：Python、FastAPI、SQLAlchemy 2、Alembic、Pydantic、argon2 密码哈希。
- **前端**：Vue 3、Vite、TypeScript、Vue Router、Vant（移动端组件库）、`vue-qrcode-reader`（扫码）、`qrcode`（生成二维码）。
- **数据库**：线上用 Neon Postgres（从 Vercel 应用市场接入），本地开发和测试用 SQLite，通过 `DATABASE_URL` 环境变量切换。
- **部署**：先把代码推到 GitHub 仓库，再由 Vercel 从 GitHub 自动部署。

### 仓库结构

```
api/index.py            Vercel 的 Python 入口，只负责导出 FastAPI 应用
backend/app/            FastAPI：路由、数据模型、请求校验、登录鉴权
backend/alembic/        数据库迁移
backend/tests/          pytest 测试
frontend/               Vue 3 + Vite + TypeScript + Vant + Vue Router
vercel.json             配置前端构建，并把 /api/* 转给 Python 函数
requirements.txt        Python 依赖
```

原有的 Node 代码（`server.js`、`routes/`、`public/`、`data/`、`package*.json`、`node_modules/`）全部删除。

### Vercel 带来的限制

- 函数的文件系统不会保存数据，所以必须用外部数据库，不能用 SQLite。
- 每个请求可能由不同的实例处理，服务端不能在内存里保存状态。登录状态放在签名 Cookie 里；数据库连接使用 Neon 的连接池地址，SQLAlchemy 端不再维护连接池（NullPool）。
- 手机浏览器只有在 HTTPS 下才能调用摄像头，Vercel 自带 HTTPS。

## 3. 账号与家庭

### 账号

- 开放注册，使用用户名和密码。用户名全局唯一，密码至少 8 位，用 argon2 加密存储。
- 登录状态存放在 HttpOnly、Secure、SameSite=Lax 的签名 Cookie 中，签名密钥来自环境变量 `SECRET_KEY`。
- 登录后可以自己修改密码。忘记密码时无法自助找回，由维护者在数据库里重置。

### 家庭

- 一个账号可以属于多个家庭。前端顶部可以切换“当前家庭”，并用 localStorage 记住上次的选择。
- 还没有家庭的账号会被引导去创建一个家庭，或者通过邀请加入别人的家庭。
- 家庭成员的权限完全相同，每个人都能：
  - 增删改位置和物品；
  - 生成或作废邀请；
  - 移除其他成员；
  - 修改家庭名称；
  - 解散家庭（需要手动输入家庭名称确认）。
- 成员可以自行退出家庭。最后一个成员退出时，家庭会连同其中所有数据一起删除。

### 邀请

- 任意成员都可以生成邀请码，对应链接为 `/join/<邀请码>`。邀请默认 7 天后过期，有效期内可以多次使用，也可以随时作废。
- 未登录时打开邀请链接，会先登录或注册，完成后自动加入该家庭。已经是成员时再次加入不报错，直接跳到该家庭。

### 数据隔离（核心约束）

- 所有物品和位置的接口都挂在 `/api/families/{family_id}/...` 下，由统一的依赖项先检查当前账号是不是这个家庭的成员。
- 不是成员时一律返回 404，不暴露“这个家庭存在”这件事。
- 所有查询都同时按 `family_id` 过滤。按 ID 访问位置或物品时，也要确认它属于路径里的那个家庭。
- 请求中引用的其他对象（例如上级位置、所在位置）必须属于同一个家庭。

## 4. 数据模型

所有表的主键都用 UUID，避免编号被按顺序猜出来，也不会暴露数据量。

| 表 | 字段 | 约束 |
|---|---|---|
| `users` | id、username、password_hash、created_at | username 唯一 |
| `families` | id、name、created_at | |
| `memberships` | user_id、family_id、joined_at | (user_id, family_id) 联合主键；删除家庭时级联删除 |
| `invites` | id、family_id、code、created_by、created_at、expires_at、revoked_at | code 唯一；删除家庭时级联删除 |
| `locations` | id、family_id、parent_id、name、note、created_at、updated_at、updated_by | parent_id 可为空（表示顶层）；索引 (family_id, parent_id) |
| `items` | id、family_id、location_id、name、barcode、note、created_at、updated_at、updated_by | location_id 必填；barcode 可为空；索引 (family_id, barcode) |

### 规则

- **同一个条码可以对应多个物品**（例如两瓶同样的洗发水放在不同地方）。扫码时如果匹配到多个物品，就列出来让用户选。
- **只能删除空位置**：位置下面还有子位置或物品时，返回 409。
- **移动位置时防止循环**：新的上级位置不能是它自己，也不能是它的任何下级位置，否则返回 409。
- **路径计算**：一个家庭的位置数量在几百个以内，所以直接一次读出这个家庭的全部位置，在内存里拼出完整路径，不用递归 SQL。

## 5. API 概要

| 方法与路径 | 作用 |
|---|---|
| `POST /api/auth/register`、`POST /api/auth/login`、`POST /api/auth/logout` | 注册、登录、退出 |
| `GET /api/auth/me`、`POST /api/auth/password` | 当前账号信息、修改密码 |
| `GET /api/families`、`POST /api/families` | 我的家庭列表、创建家庭 |
| `GET/PATCH/DELETE /api/families/{fid}` | 家庭详情（含成员列表）、改名、解散 |
| `DELETE /api/families/{fid}/members/{uid}` | 移除成员；`uid` 是自己时就是退出家庭 |
| `GET/POST /api/families/{fid}/invites`、`DELETE .../invites/{id}` | 邀请列表、生成邀请、作废邀请 |
| `GET /api/invites/{code}`、`POST /api/invites/{code}/accept` | 查看邀请对应的家庭、接受邀请 |
| `GET/POST /api/families/{fid}/locations` | 位置列表（平铺，带路径）、新建位置 |
| `GET/PATCH/DELETE /api/families/{fid}/locations/{lid}` | 位置详情（含子位置和物品）、修改或移动、删除 |
| `GET /api/locations/{lid}` | 二维码入口：返回这个位置所属的家庭 ID（仅成员可见，否则 404） |
| `GET/POST /api/families/{fid}/items` | 搜索物品（`q`、`barcode` 参数）、新建物品 |
| `GET/PATCH/DELETE /api/families/{fid}/items/{iid}` | 物品详情、修改或移动、删除 |

## 6. 页面流程（以手机为主，底部三个标签）

1. **登录 / 注册**：注册后如果没有家庭，进入“创建家庭”或“输入邀请码加入”。`/join/<邀请码>` 在登录后自动加入。
2. **找东西（首页）**：
   - 搜索框按名称、条码、备注搜索，结果显示完整位置路径。
   - 📷 扫码按钮：
     - 扫到物品条码：没有匹配就进入新建物品页并预填条码；一个匹配就打开这个物品；多个匹配就显示列表。
     - 扫到本系统生成的位置二维码：直接打开那个位置。
3. **位置**：从顶层逐级浏览。位置详情页 `/l/<位置ID>` 就是二维码打开的页面，包括：
   - 可点击的路径；
   - 子位置和物品列表；
   - 新建子位置、在这里放物品、编辑、移动、删除、打印二维码。
4. **物品详情 / 编辑**：名称、条码（旁边有扫码按钮）、备注；用逐级选择器选位置。移动物品就是修改它的位置。
5. **家庭与我**：
   - 切换、创建或加入家庭；
   - 成员列表和移除成员；
   - 邀请链接的生成、复制和作废；
   - 改名、退出、解散家庭；
   - 修改密码、退出登录。
6. **打印页**：勾选位置后，生成标签网格，每张标签包含二维码、位置名称和完整路径。用打印专用样式适配 A4 纸，通过浏览器打印。

二维码内容为 `https://<域名>/l/<位置ID>`，用手机系统相机扫码就能打开。未登录时会先登录再跳回；当前账号属于那个家庭时会自动切换过去；不属于时显示“找不到这个位置”。

## 7. 错误处理

- 接口统一返回 HTTP 状态码和 `{"detail": "中文提示"}`，前端用 Vant 的轻提示显示。
- 401：前端跳到登录页，带上 `redirect` 参数，登录后跳回原页面。
- 404：资源不存在，或者不是这个家庭的成员。
- 409：用户名已被占用、删除的位置不为空、移动位置形成循环。
- 422：请求参数校验失败（Pydantic），前端显示第一条错误。

## 8. 测试

- **后端（pytest + 内存 SQLite + FastAPI TestClient）**：
  - 注册、登录、退出、修改密码；
  - 邀请的过期、作废、重复加入；最后一个成员退出时删除家庭；
  - **跨家庭隔离**：每类接口都有用例，确认 A 家庭成员对 B 家庭的数据读写都返回 404，并且不能引用 B 家庭的位置作为上级位置或所在位置；
  - 位置树的循环检测、只能删除空位置、路径计算；
  - 条码匹配多个物品、搜索。
- **前端**：用 `vue-tsc` 做类型检查，再执行生产构建；在内置浏览器里用手机尺寸走一遍主要流程：注册 → 建家庭 → 建位置 → 加物品 → 搜索 → 打开 `/l/<位置ID>` → 打印页。
- **摄像头扫码**：需要真实手机和 HTTPS，部署到 Vercel 后由用户在手机上确认。

## 9. 环境变量

| 变量 | 用途 |
|---|---|
| `DATABASE_URL` | 数据库连接地址；本地默认 `sqlite:///./dev.db` |
| `SECRET_KEY` | Cookie 签名密钥，线上必须设置 |
| `COOKIE_SECURE` | 本地 HTTP 开发时设为 `false` |
