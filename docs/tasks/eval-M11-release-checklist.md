# Eval-Ops M11 · 发布回归 Checklist

> **状态**：✅ M11-1～M11-2 完成（2026-07-08）  
> **性质**：纯文档 · **不 Implement** · 每次合并 / 发版时照着勾  
> **Plan**：[`eval-ops-plan.md`](eval-ops-plan.md) §3 M11

---

## 0. 一句话（大白话）

**合并代码进主分支前**，先跑自动化（pytest · golden · 前端打包）；**部署到内网环境后**，再花 5～10 分钟点浏览器：健康检查、demo 能登录看库、组织域抽 3 步确认权限没坏。

---

## 1. 什么时候用

| 时机 | 勾哪一节 | 谁来做 |
|------|----------|--------|
| **合并 PR / push 到 main 之前** | §2 合并前（M11-1） | 开发者本机或 CI 已绿仍建议本地再勾一遍 |
| **Docker 重建 / 内网发版之后** | §3 发版后（M11-2） | 产品负责人或运维亲手浏览器点 |
| **只改文档、不动代码** | 可跳过 §2，§3 仍建议大版本发版时做 | — |

> **注意**：`test_retrieval_golden` 用 **mock 嵌入**；CI 绿 ≠ 生产通义嵌入一定绿。动过 RAG/嵌入相关代码时，另见 [`RAG_PRODUCTION_BASELINE.md`](../RAG_PRODUCTION_BASELINE.md) 抽测（本 checklist 不替代 R5-3）。

---

## 2. 合并前 · M11-1

> **目标**：代码合进主分支前，三条自动化门禁全绿。  
> **环境**：本机 `backend` 目录 · Python 3.11 · 本机 Postgres（或 CI 同款 `DATABASE_URL`）· `EMBEDDING_PROVIDER=mock`（默认测试配置）。

### 2.1 准备（30 秒）

> **Windows 本机**：知岸后端要 **Python 3.11**；直接敲 `pytest` 常报「找不到命令」→ 用 **`py -3.11 -m pytest`**（见下）。默认 `py` 若是 3.9 会报 `TypeError: unsupported operand type(s) for |`。

```powershell
cd D:\MyPrograms\rag-knowledge-platform\backend
py -3.11 -m alembic upgrade head
py -3.11 -m alembic current    # 期望：016 (head) 或更新
```

- [ ] Alembic 已到 head，无 pending migration

### 2.2 全量 pytest

```powershell
cd D:\MyPrograms\rag-knowledge-platform\backend
py -3.11 -m pytest -v
```

| 检查项 | 通过标准 |
|--------|----------|
| 退出码 | **0** |
| 失败数 | **0 failed** |
| 基线参考 | 2026-07-08：**350 passed**（随新测试递增，以全绿为准） |

- [ ] **pytest 全绿**（`0 failed`）

### 2.3 Golden Hit@3 门禁（R5-2）

```powershell
cd D:\MyPrograms\rag-knowledge-platform\backend
py -3.11 -m pytest tests/test_retrieval_golden.py -v --tb=short
```

| 检查项 | 通过标准 |
|--------|----------|
| 用例数 | GQ-1～**12** 全部 Pass |
| Hit@3 | **12/12** |
| CI 对照 | GitHub Actions job **`R5-2 golden Hit@3 gate`** 应同为绿 |

- [ ] **golden 12/12**

### 2.4 前端打包

```powershell
cd D:\MyPrograms\rag-knowledge-platform\frontend
npm ci
npm run build
```

| 检查项 | 通过标准 |
|--------|----------|
| 退出码 | **0** |
| 产物 | `frontend/dist/` 生成且无 TypeScript / Vite 报错 |

- [ ] **`npm run build` 绿**

### 2.5 （若改了后端 API）Docker 重建

仅当本次合并动过 `backend/` 且目标环境跑 Docker 时：

```powershell
cd D:\MyPrograms\rag-knowledge-platform
docker compose build api
docker compose up -d api
```

- [ ] （适用时）API 容器已重建并 running

### 2.6 M11-1 小结

| # | 项 | ☐ |
|---|-----|---|
| M11-1a | Alembic head | ☐ |
| M11-1b | pytest 全绿 | ☐ |
| M11-1c | golden **12/12** | ☐ |
| M11-1d | `npm run build` 绿 | ☐ |
| M11-1e | （适用时）API 镜像重建 | ☐ |

**M11-1 全勾 ✅ → 允许合并。**

---

## 3. 发版后 · M11-2

> **目标**：部署到内网（开发 compose 或 prod compose）后，确认服务活着、demo 能用、组织权限没回归。  
> **环境**：见 [`DEPLOY.md`](../DEPLOY.md) · 账号见 [`TEST_ACCOUNTS.md`](../TEST_ACCOUNTS.md)

### 3.1 栈已起

```powershell
cd D:\MyPrograms\rag-knowledge-platform
docker compose up -d
# 生产态：
# docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

前端（开发联调时另开终端）：

```powershell
cd D:\MyPrograms\rag-knowledge-platform\frontend
npm run dev
```

| 模式 | 前端地址 | API / health |
|------|----------|--------------|
| 开发 | http://localhost:5173/login | http://localhost:8000 |
| 生产 compose | http://localhost/ | http://localhost:8000/health 或经 web 反代 |

- [ ] 容器 / 前端 dev 已起，无致命启动错误

### 3.2 `/health` 健康检查

```powershell
Invoke-RestMethod http://localhost:8000/health
```

**通过标准**：

```json
{"status":"ok","database":"ok"}
```

- [ ] `status` = `ok`
- [ ] `database` = `ok`
- [ ] 无需登录即可访问

### 3.3 Demo 登录 · 资料库列表

| 步 | 操作 | 预期 |
|----|------|------|
| 1 | 打开登录页 → `demo_admin` / `password123` | 进入概览 |
| 2 | 侧栏选 **知岸演示公司**（团队空间，**不是**「我的空间」） | 顶栏显示团队名 |
| 3 | 点 **知识库** | 列表加载成功 |
| 4 | 看库数量 | **≥10** 个（若已跑 M1 S 档 seed；未 seed 时至少见答辩演示库） |
| 5 | 搜索框或 `?q=产品` | 能筛出含「产品」的库名 |

账号缺失时：

```powershell
docker compose exec api env PYTHONPATH=/app python /tmp/seed_enterprise_demo.py
docker compose exec api env PYTHONPATH=/app python /tmp/seed_volume_data.py --tier S --workspace team
```

（需先 `docker cp` 脚本进容器，见 `TEST_ACCOUNTS.md`。）

- [ ] **demo_admin** 登录成功
- [ ] 团队空间资料库列表 **≥10**（或已 seed 环境下的实际数）
- [ ] 列表搜索 `?q=产品` 有结果（S 档 seed 环境下）

### 3.4 ORG 15 步 · 抽验 3 步（M11-2）

完整脚本：[`ORG_DEPARTMENTS_ACCEPTANCE.md`](../ORG_DEPARTMENTS_ACCEPTANCE.md)（15 步 · 2026-07-08 已 **15/15**）。

**发版后不必每次 15 步全跑**——抽 **3 步**覆盖四段主线（研发隔离 · 市场硬闯 · grant 对话）：

| 抽验 # | 原步骤 | 账号 | 操作（简） | 预期（看见什么） | 覆盖段 |
|--------|--------|------|------------|------------------|--------|
| **A** | **6** | `demo_member` | 知识库列表 | 有「研发内部库」· **无**「市场机密库」 | 研发隔离 |
| **B** | **7** | `demo_member` | 地址栏硬闯步骤 4 记下的市场库 URL | Toast「该资源不在当前工作区」→ 跳概览 | 市场 · E1 |
| **C** | **13** | `demo_member` | 进「员工手册（人事）」→ 对话问「年假有多少天？」 | 流式回答 + **引用 chip**（含年假/10） | grant · RAG |

**前提（重要）**：

- DB 里仍保留 ORG-5.1 验收时的部门树、库、grant（**不是**全新空库）。
- 若刚 `docker compose down -v` 清库，须先跑完 `ORG_DEPARTMENTS_ACCEPTANCE.md` **全 15 步**或至少步骤 1～12 再抽 A～C。
- 步骤 7 需要 admin 在步骤 4 记下的市场库 URL；可从 admin 团队空间市场部列表进详情复制。

- [ ] 抽验 **A**（步骤 6）✅
- [ ] 抽验 **B**（步骤 7）✅
- [ ] 抽验 **C**（步骤 13）✅

> **UX 已知**：Admin「当前部门 ▾」切部门有 **UX-7** bug；验收时 admin 建库用「指定部门」绕过（见 ORG 脚本 §7 备注）。

### 3.5 M11-2 小结

| # | 项 | ☐ |
|---|-----|---|
| M11-2a | 栈 / 前端可访问 | ☐ |
| M11-2b | `/health` · database ok | ☐ |
| M11-2c | demo_admin 登录 · 团队列表 ≥10（或已 seed） | ☐ |
| M11-2d | ORG 抽验 A（步骤 6） | ☐ |
| M11-2e | ORG 抽验 B（步骤 7） | ☐ |
| M11-2f | ORG 抽验 C（步骤 13） | ☐ |

**M11-2 全勾 ✅ → 本次发版回归通过。**

---

## 4. 发版记录（请你每次发版后填）

| 项 | 值 |
|----|-----|
| 日期 | |
| 版本 / commit | |
| 环境 | dev compose / prod compose / 内网 IP |
| 执行人 | |
| M11-1 pytest | passed / failed（数：） |
| M11-1 golden | /12 |
| M11-1 build | 绿 / 红 |
| M11-2 health | ok / 失败原因 |
| M11-2 demo 列表库数 | |
| M11-2 ORG 抽验 A/B/C | ✅/❌ |
| 备注 | |

---

## 5. M11 DoD（plan 对照）

| # | 退出条件 | 本文 |
|---|----------|------|
| M11-1 | 合并前 pytest · build · golden 12/12 | §2 |
| M11-2 | 发版后 ORG 抽 3 步 · health · demo 登录列表 | §3.2～§3.4 |
| — | checklist 可勾选 | §2.6 · §3.5 · `- [ ]` 行 |

---

## 6. 关联文档

| 文档 | 关系 |
|------|------|
| [`eval-ops-plan.md`](eval-ops-plan.md) | M11 原子任务来源 |
| [`DEPLOY.md`](../DEPLOY.md) | 发版 / health / smoke |
| [`TEST_ACCOUNTS.md`](../TEST_ACCOUNTS.md) | demo 账号 · S 档 seed |
| [`ORG_DEPARTMENTS_ACCEPTANCE.md`](../ORG_DEPARTMENTS_ACCEPTANCE.md) | 15 步全量脚本 |
| [`RAG_PRODUCTION_BASELINE.md`](../RAG_PRODUCTION_BASELINE.md) | 通义真嵌入抽测（动 RAG 时） |
| [`eval-M2-report.md`](eval-M2-report.md) | 读路径性能（**不阻塞**本 checklist） |
| [`.github/workflows/ci.yml`](../../.github/workflows/ci.yml) | CI 三门禁 + backend + frontend |
