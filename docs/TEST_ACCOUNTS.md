# 知岸 — 本地测试账号

> **用途**：本机 Docker + 前端联调、验收权限与资料库流程。  
> **环境**：仅 `localhost`，勿用于生产。  
> **最后更新**：2026-07-08（Eval-Ops M1：S 档测试数据 seed）

---

## 启动（测之前先确认）

```powershell
cd D:\MyPrograms\rag-knowledge-platform
docker compose up -d
docker compose exec api alembic current   # 期望：008 (head)
```

前端（另开终端）：

```powershell
cd D:\MyPrograms\rag-knowledge-platform\frontend
npm run dev
```

- 登录页：<http://localhost:5173/login>
- API 健康：<http://localhost:8000/health> → `database: ok`

若登录异常，先 **退出登录** 或清 Local Storage 里的 `zhian_access_token`、`zhian_user`，再重新登录。

---

## 团队版演示账号（推荐）

同一团队 **「知岸演示公司」**，由种子脚本创建，可重复执行。

> **15 分钟答辩脚本**：见 [`docs/ENTERPRISE_DEMO_SCRIPT.md`](ENTERPRISE_DEMO_SCRIPT.md)

| 角色 | 昵称 | 邮箱 | 用户名 | 密码 |
|------|------|------|--------|------|
| **团队管理员** | 演示管理员 | `demo-admin@example.com` | `demo_admin` | `password123` |
| **团队成员** | 演示成员 | `demo-member@example.com` | `demo_member` | `password123` |

登录时 **邮箱或用户名** 二选一即可。

### 账号不存在时重建

```powershell
cd D:\MyPrograms\rag-knowledge-platform
docker cp backend/scripts/seed_enterprise_demo.py zhiku-api:/tmp/seed_enterprise_demo.py
docker compose exec api env PYTHONPATH=/app python /tmp/seed_enterprise_demo.py
```

### S 档测试数据（Eval-Ops M1 · 10 库 × 5 文档）

用于 demo「库多」、列表搜索与后续 M2 性能基线。**只写数据库元数据**，不上传真实 PDF，**不调用通义 embedding API**。

**前置**：上节 `seed_enterprise_demo.py` 已跑过（需有「知岸演示公司」与 `demo_admin`）。

```powershell
cd D:\MyPrograms\rag-knowledge-platform
docker cp backend/scripts/seed_volume_data.py zhiku-api:/tmp/seed_volume_data.py
docker compose exec api env PYTHONPATH=/app python /tmp/seed_volume_data.py --tier S --workspace team
```

| 参数 | 默认 | 说明 |
|------|------|------|
| `--tier S` | S | 10 个资料库，每库 5 条 `completed` 文档（无 chunk/向量） |
| `--workspace team` | team | 写入演示公司组织空间 |
| `--department 研发部` | 研发部 | 资料库归属部门；不存在则自动创建 |

**幂等**：可重复执行；已存在的库/文档按名称跳过或修正状态，不会 duplicate。

**验收（demo_admin）**：

> **常见误区**：S 档数据写在 **团队空间**，不是侧栏「我的空间」。若只看到「浏览器测试库」「123」等 2 个库，说明还在个人空间——请点侧栏顶部的 **团队名（知岸演示公司）** 切到团队后再看列表。

1. 登录 → 侧栏选 **团队（知岸演示公司）**（不要选「我的空间」）→ `/knowledge-bases` → 列表 **≥10** 个资料库（名称含「产品」「市场」等）
2. 列表搜索框或地址栏 `?q=产品` → 应筛出 **产品需求规范库**、**产品发布清单**
3. API：`GET /api/v1/knowledge-bases?workspace=<组织UUID>` 返回数组长度 ≥10（需先登录拿 token）

**限制**：文档为占位元数据，**不能**用于带引用对话（无切片/向量）；要测 RAG 请另行上传真实文件。

### M 档压测数据（220 库 × 2 文档 · UX/性能试玩）

在 S 档基础上追加 **220 个模拟库**（组织内合计通常 **230+**），用来感受「列表很长」、判断要不要分页/虚拟滚动等**混合方案**。

```powershell
docker cp backend/scripts/seed_volume_data.py zhiku-api:/tmp/seed_volume_data.py
docker compose exec api env PYTHONPATH=/app python /tmp/seed_volume_data.py --tier M --workspace team
```

| 参数 | 说明 |
|------|------|
| `--tier M` | 220 库 · 每库 2 文档 · 名称 `模拟资料库-0001`…；约每 17/23 个插入「产品/市场」前缀便于搜 |
| 幂等 | 可重复跑；第二次应「新增库 0」 |

**试玩建议**：

1. **团队空间**（不是「我的空间」）→ 资料库列表
2. 部门选 **全公司**（Admin 可见全部 M 档库）
3. 试 `?q=模拟` / `?q=产品` 看搜索能否代替长滚动
4. 打开 DevTools → Network，看 `GET /knowledge-bases` 体积与耗时（供 M2 报告参考）

### L 档高负载数据（6000 库 × 1 文档 · 分页压测）

清空演示公司内 **所有 eval-ops 标记**（S/M/L）后，写入 **6000** 个模拟库，供列表分页 / M2 性能基线。

```powershell
docker cp backend/scripts/seed_volume_data.py zhiku-api:/tmp/seed_volume_data.py
docker compose exec api env PYTHONPATH=/app python /tmp/seed_volume_data.py --purge-eval-ops --tier L --workspace team
```

| 参数 | 说明 |
|------|------|
| `--tier L` | 6000 库 · 每库 1 文档 · 名称 `高负载模拟库-000001`… |
| `--purge-eval-ops` | **先删**演示公司里带 `eval-ops:` 标记的库/文档，再写入 L 档 |
| `--batch-size 200` | 默认每 200 库提交一次；终端会打 `[monitor]` 进度 |

**验收（demo_admin）**：团队空间 · 部门 **全公司** → 列表 total **≥6000** · 每页 24 卡 · `?page=2` 翻页正常。

---

## 个人版（需自行注册）

仓库 **没有** 预置个人版固定账号。可在登录页 **注册 → 个人版** 自建，例如：

| 字段 | 示例 |
|------|------|
| 邮箱 | `demo-personal@example.com`（勿与已有邮箱冲突） |
| 用户名 | `demo_personal` |
| 密码 | `password123`（至少 8 位） |

或用 API 注册：

```powershell
Invoke-RestMethod -Uri "http://localhost:8000/api/v1/auth/register" -Method POST -ContentType "application/json" -Body '{"email":"demo-personal@example.com","username":"demo_personal","password":"password123","account_type":"personal"}'
```

---

## 登录页「演示登录」按钮

与 **团队管理员** 种子账号一致：

- 用户名：`demo_admin`
- 密码：`password123`

（不会自动登录成员账号；测 member 请用上表 `demo_member`。）

---

## 建议验收清单（测完再决定是否继续开发）

### 团队管理员 `demo_admin`

- [ ] 登录后进 `/knowledge-bases`，可 **新建 / 删除** 资料库
- [ ] 进入某库，可 **上传文档**，状态变为「完成」
- [ ] 文档表可 **预览 · 删除**；失败文档可 **重试**
- [ ] 侧栏可见 **成员管理、团队设置**
- [ ] 可 **开始对话**，回答带引用

### 团队成员 `demo_member`

- [ ] 登录后能看到 **同一团队** 的资料库列表（与 admin 共享）
- [ ] **没有**「新建资料库」按钮；卡片 **没有**「删除/编辑」
- [ ] 列表有库时显示 **成员只读提示**
- [ ] 进入库详情：**上传/编辑为灰色不可点**（点按 Toast）；可 **预览、对话**；操作列**只有预览**，无删/重试
- [ ] 侧栏可见 **「团队成员」**（非「成员管理」）；**没有**「团队设置」
- [ ] 侧栏或 Dashboard **「N 名成员 ›」** badge → `/organization/members` **只读花名册**（邮箱、角色、加入时间；无添加/发码/移除）
- [ ] 直输 `/organization/settings` → 回概览 + toast「无权限」（**不**拦 `/organization/members`）
- [ ] Dashboard **没有**「创建资料库」；CTA 为「查看资料库」

### 个人版（若已注册）

- [ ] 资料库 CRUD 全流程（建库 → 上传 → 对话）
- [ ] 侧栏无企业菜单

---

## 已知限制（当前代码，非账号问题）

| 功能 | 状态 |
|------|------|
| 列表卡片「今天更新」、状态点 | ✅ Plan 1.2（2026-07-04） |
| 文档删除 / 失败重试 | ✅ Plan 1.3 + 1.4（2026-07-04）· **改过后端代码须** `docker compose up -d --build api` |
| 资料库改名 / 描述 UI | ✅ 列表卡片 + 详情页「编辑」→ Dialog（Plan 1.5） |
| 回收站 | 未做 |
| 成员管理页（邀请成员 API） | ✅ Wave 5.4 |
| 成员权限 UX 全站一致 | ✅ Plan-11/2C（2026-07-04） |
| Member 只读花名册（`/organization/members`） | ✅ W5+-4 · 侧栏「团队成员」+ Dashboard badge · Admin 仍见「成员管理」 |
| 答辩 demo 脚本 | ✅ 002-W5.5 · `docs/ENTERPRISE_DEMO_SCRIPT.md` |

---

## 安全说明

- 密码 `password123` 仅用于 **本机开发库**。
- 部署到公网前必须改密、改 `JWT_SECRET`、改 Postgres 密码，**勿提交** `.env` 中的密钥。
