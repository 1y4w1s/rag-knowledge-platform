# 知岸

个人自用 + 毕业设计的 RAG 知识平台：多格式文档上传 → 知识库对话 → **引用溯源**（文档名 + 章节 + 页码）。

> 代码目录名仍为 `rag-knowledge-platform`；产品对外称 **知岸**。

## 技术栈（摘要）

| 层级 | 选型 |
|------|------|
| 后端 | Python 3.11+ / FastAPI |
| 数据库 | PostgreSQL + pgvector |
| 异步任务 | FastAPI BackgroundTasks |
| 前端 | React + Vite + shadcn/ui（Wave 4 开工） |
| RAG | LangChain · 结构优先切片 · hybrid 检索 |

详细架构见 [`docs/TECH.md`](docs/TECH.md)，开发顺序见 [`docs/tasks/002-plan.md`](docs/tasks/002-plan.md)。

## 仓库结构

```
rag-knowledge-platform/
├── backend/          # FastAPI 后端
│   ├── app/          # 应用代码（api / core / models / schemas / services）
│   ├── alembic/      # 数据库迁移（Wave 0.3）
│   └── tests/        # pytest（Wave 0.4）
├── frontend/         # React 前端（Wave 4 再写页面）
├── docs/             # PRD、TECH、计划、驾驶舱
├── docker-compose.yml          # 自建：postgres + api
├── docker-compose.dev.yml      # 自建：仅 postgres
├── docker-compose.api.yml      # 仅 api（外部库时用）
├── scripts/                    # docker-pull.ps1、docker-up.ps1
├── .env.example
└── README.md
```

用资源管理器或 `tree` 打开根目录，应能一眼看出：**后端在 `backend/`、前端在 `frontend/`、文档在 `docs/`**。

## 生产 / 内网部署

> **HTTP 无 TLS** · 仅适合内网/VPN · 详见 [`docs/DEPLOY.md`](docs/DEPLOY.md)

```powershell
Copy-Item .env.production.example .env
# 编辑 .env：POSTGRES_PASSWORD、JWT_SECRET、DEEPSEEK/TONGYI Key、CORS_ORIGINS
docker compose up -d --build
docker compose exec api alembic upgrade head
curl http://localhost:8000/health   # → {"status":"ok","database":"ok"}
```

## 本地开发（Docker 为主，与 2G 云部署一致）

### 前置条件

- [Docker Desktop](https://www.docker.com/products/docker-desktop/)（Windows AMD64）
- Python 3.11+（本机 venv 调试 API 时用，可选）

### 国内 Docker 拉镜像失败？按这个顺序来

| 步骤 | 做什么 | 解决啥 |
|------|--------|--------|
| **0 配置加速** | 见下「Docker Engine 配置」 | 避免直连 docker.io 超时 |
| **1 预拉镜像** | `.\scripts\docker-pull.ps1` | 多镜像源自动切换 + 重试，避免 `unexpected EOF` |
| **2 启动栈** | `docker compose up -d --build` | Postgres + API 与云上相同 |
| **3 验收** | `curl http://localhost:8000/health` | `database: ok` = Wave 0.2 过关 |

**一键（1+2+3）**：

```powershell
cd d:\MyPrograms\rag-knowledge-platform
.\scripts\docker-up.ps1
```

---

### Docker Engine 配置（必做一次）

1. Docker Desktop → **Settings** → **Docker Engine**
2. 打开 `scripts/docker-engine.example.json`，**整段复制**替换 Engine 里原有 JSON
3. **Apply and restart**，等左下角 **Engine running**

要点：

- 用 `registry-mirrors`（DaoCloud + 1ms），**不要**在命令里写 `docker.xuanyuan.me/...` 直链（易 429）
- 不要用两段 JSON、不要多打 `}`

---

### 手动分步启动

```powershell
cd d:\MyPrograms\rag-knowledge-platform
Copy-Item .env.example .env -ErrorAction SilentlyContinue

# 先拉基础镜像（postgres + python），成功后再 build
.\scripts\docker-pull.ps1

docker compose up -d --build
curl http://localhost:8000/health
```

预期：`{"status":"ok","database":"ok"}`

浏览器：<http://localhost:8000/docs>

---

### Wave 0.3：Alembic 数据库迁移

| 做什么 | 解决啥 | 怎么验 |
|--------|--------|--------|
| Alembic 脚手架 | 改表有版本、可回滚 | `alembic current` → `001 (head)` |
| 001 迁移 | 确保 pgvector 扩展 | `upgrade head` 无报错 |

Docker 栈已启动时：

```powershell
docker compose exec api alembic upgrade head
docker compose exec api alembic current
```

本机 venv（`DATABASE_URL` 指向 `localhost:5432`）：

```powershell
cd backend
pip install -r requirements.txt -i https://mirrors.aliyun.com/pypi/simple/
python -m alembic upgrade head
```

> 业务表（users、知识库等）从 **Wave 1.1** 起逐步加入；Wave 1.1 含 users / organizations / organization_members。

---

### Wave 1.1：注册 / 登录 API

| 做什么 | 解决啥 | 怎么验 |
|--------|--------|--------|
| Alembic 002 迁移 | users / org / members 三表 | `alembic current` → `002 (head)` |
| `POST /api/v1/auth/register` | 个人版 / 企业版注册 | curl 见下 |
| `POST /api/v1/auth/login` | 登录返回 JWT（中间件在 1.2） | curl 见下 |

Docker 栈已启动时：

```powershell
docker compose exec api alembic upgrade head
docker compose exec api alembic current
```

**curl 验收（个人版）**：

```powershell
curl -X POST http://localhost:8000/api/v1/auth/register `
  -H "Content-Type: application/json" `
  -d "{\"email\":\"demo@example.com\",\"password\":\"password123\",\"account_type\":\"personal\"}"

curl -X POST http://localhost:8000/api/v1/auth/login `
  -H "Content-Type: application/json" `
  -d "{\"email\":\"demo@example.com\",\"password\":\"password123\"}"
```

**curl 验收（企业版）**：

```powershell
curl -X POST http://localhost:8000/api/v1/auth/register `
  -H "Content-Type: application/json" `
  -d "{\"email\":\"admin@corp.com\",\"password\":\"password123\",\"account_type\":\"enterprise\",\"org_name\":\"答辩演示公司\"}"
```

预期：注册 201 返回 `user`；登录 200 返回 `access_token` + `user`（企业版含 `org_id`、`org_role: admin`）。

也可打开 <http://localhost:8000/docs> 在 Swagger 里点 **auth** 分组测试。

---

### Wave 1.2：JWT 中间件 + RBAC

| 做什么 | 解决啥 | 怎么验 |
|--------|--------|--------|
| `JWTAuthMiddleware` | 除 register/login/health 外，`/api/v1/*` 须 Bearer token | 无 token 调 `/api/v1/auth/me` → 401 |
| `get_current_user` / `CurrentUser` | 路由层拿到已认证用户 | 有效 token 调 `GET /auth/me` → 200 |
| 占位路由 `GET /placeholder/resources/{owner_user_id}` | SA-1 骨架：A 访问 B 资源 → 403 | pytest `test_permissions.py` 绿 |
| `require_kb_access` | kb_id 二次校验：归属 + 角色动作矩阵 | `test_knowledge_bases.py` SA-1 绿 |

**curl 验收**（先登录拿 token）：

```powershell
$login = Invoke-RestMethod -Uri http://localhost:8000/api/v1/auth/login -Method POST -ContentType "application/json" -Body '{"email":"demo@example.com","password":"password123"}'
$token = $login.access_token

# 有效 token → 200
Invoke-RestMethod -Uri http://localhost:8000/api/v1/auth/me -Headers @{ Authorization = "Bearer $token" }

# 无 token → 401
Invoke-RestMethod -Uri http://localhost:8000/api/v1/auth/me
```

**pytest**（需 Postgres 可达，`alembic upgrade head`）：

```powershell
cd backend
python -m pytest -v
```

预期：**16 passed**（含 `test_permissions.py` SA-1 用例）。

---

### Wave 1.3：组织设置 API

| 做什么 | 解决啥 | 怎么验 |
|--------|--------|--------|
| `GET/PATCH /api/v1/organization/settings` | 企业 admin 读/改组织名称 | admin token → 200 |
| `require_org_role(admin)` | member / 个人版 → 403 | pytest `test_organization.py` 绿 |

**curl 验收**（先注册企业 admin 并登录）：

```powershell
# 注册企业 admin
$email = "corp-admin-$(Get-Random)@example.com"
$regBody = @{ email=$email; password="password123"; account_type="enterprise"; org_name="答辩演示公司" } | ConvertTo-Json
Invoke-RestMethod -Uri "http://localhost:8000/api/v1/auth/register" -Method POST -ContentType "application/json" -Body $regBody

# 登录
$login = Invoke-RestMethod -Uri "http://localhost:8000/api/v1/auth/login" -Method POST -ContentType "application/json" -Body (@{ email=$email; password="password123" } | ConvertTo-Json)
$h = @{ Authorization = "Bearer $($login.access_token)" }

# GET 组织信息 → 200
Invoke-RestMethod -Uri "http://localhost:8000/api/v1/organization/settings" -Headers $h

# PATCH 改名 → 200
Invoke-RestMethod -Uri "http://localhost:8000/api/v1/organization/settings" -Method PATCH -ContentType "application/json" -Headers $h -Body '{"name":"新公司名称"}'
```

**pytest**：预期 **21 passed**（含 `test_organization.py`）。

---

### Wave 2.1：知识库 CRUD API

| 做什么 | 解决啥 | 怎么验 |
|--------|--------|--------|
| Alembic 003 迁移 | `knowledge_bases` 表；个人 `owner_user_id` / 企业 `owner_org_id` 二选一 | `alembic current` → `003 (head)` |
| `GET/POST/PATCH/DELETE /api/v1/knowledge-bases` | 个人/企业 admin 管理自己的库 | curl 见下 |
| `require_kb_access` | kb_id 二次校验 + 角色矩阵（member 只读） | A 访问 B 的 kb → 403（SA-1） |

Docker 栈已启动时：

```powershell
docker compose exec api alembic upgrade head
docker compose exec api alembic current
```

**curl 验收**（先登录个人版拿 token）：

```powershell
$login = Invoke-RestMethod -Uri http://localhost:8000/api/v1/auth/login -Method POST -ContentType "application/json" -Body '{"email":"demo@example.com","password":"password123"}'
$h = @{ Authorization = "Bearer $($login.access_token)" }

# 创建知识库 → 201
Invoke-RestMethod -Uri "http://localhost:8000/api/v1/knowledge-bases" -Method POST -ContentType "application/json" -Headers $h -Body '{"name":"我的毕设库","description":"测试"}'

# 列表 → 200
Invoke-RestMethod -Uri "http://localhost:8000/api/v1/knowledge-bases" -Headers $h
```

**pytest**：预期 **29 passed**（含 `test_knowledge_bases.py` SA-1 / member 403 用例）。

---

### Wave 2.2：文档上传 + BackgroundTasks 入库管道

| 做什么 | 解决啥 | 怎么验 |
|--------|--------|--------|
| Alembic 004 迁移 | `documents` 表 + `document_status` 枚举 | `alembic current` → `004 (head)` |
| `GET/POST /api/v1/knowledge-bases/{kb_id}/documents` | multipart 上传；响应 `status=queued` | curl / Swagger 见下 |
| `require_kb_access(write)` | 上传须写权限；member POST → 403 | pytest `test_upload.py` 绿 |
| `BackgroundTasks` + `process_document_ingestion` stub | 异步入库管道占位（Wave 2.3 接解析/切片） | 上传后 DB 中 `processing_started_at` 有值 |

Docker 栈已启动时：

```powershell
docker compose exec api alembic upgrade head
docker compose exec api alembic current
```

**curl 验收**（先登录并创建知识库，将 `$kbId` 换成真实 id）：

```powershell
$login = Invoke-RestMethod -Uri http://localhost:8000/api/v1/auth/login -Method POST -ContentType "application/json" -Body '{"email":"demo@example.com","password":"password123"}'
$h = @{ Authorization = "Bearer $($login.access_token)" }
$kb = Invoke-RestMethod -Uri "http://localhost:8000/api/v1/knowledge-bases" -Method POST -ContentType "application/json" -Headers $h -Body '{"name":"上传测试库"}'

# multipart 上传 → 201，documents[0].status = queued
curl.exe -X POST "http://localhost:8000/api/v1/knowledge-bases/$($kb.id)/documents" `
  -H "Authorization: Bearer $($login.access_token)" `
  -F "files=@README.md;type=text/markdown"
```

**pytest**：预期 **36 passed**（含 `test_upload.py` 上传 / member 403 / BackgroundTask stub 用例）。

---

### Wave 2.3：结构优先切片 + pgvector 写入

| 做什么 | 解决啥 | 怎么验 |
|--------|--------|--------|
| Alembic 005 迁移 | `document_chunks` 表 + pgvector + tsvector GIN | `alembic current` → `005 (head)` |
| `parser.py` / `chunker.py` / `embedder.py` | PDF/TXT/MD/DOCX 解析 → 结构优先切片 → 通义嵌入（测试 mock） | `test_ingestion_golden.py` 绿 |
| `pipeline.py` 完整管道 | BackgroundTask：解析→切片→嵌入→写库；`status=completed` + `chunk_count` + 耗时 | 上传 txt 后 DB 可查 chunks |
| `docs/golden_qa.md` | 章节 + 页码 + **Hit@3** 验收集（GQ-1～4） | `test_retrieval_golden.py` 绿 |

Docker 栈已启动时：

```powershell
docker compose build api
docker compose up -d api
docker compose exec api alembic upgrade head
docker compose exec api alembic current
```

**pytest**（本机 `backend/`，需 Postgres 已 migrate 到 005）：

```powershell
cd backend
pip install -r requirements-dev.txt -i https://mirrors.aliyun.com/pypi/simple/
$env:EMBEDDING_PROVIDER='mock'
pytest -v
```

预期：**39 passed**（含 `test_ingestion_golden.py` 3 例 + 原 36 例）。

> 生产嵌入：`.env` 配置 `TONGYI_API_KEY` + `EMBEDDING_PROVIDER=tongyi`；CI/本地测试默认 `mock` 不调 API。

---

### Wave 2.4：文档预览 API

| 做什么 | 解决啥 | 怎么验 |
|--------|--------|--------|
| `GET .../documents/{doc_id}/preview` | 已完成文档返回原文件流；PDF/文本正确 Content-Type | curl / pytest 见下 |
| `require_kb_access(read)` | member 可读；越权 kb → 403（SA-1） | `test_preview.py` 绿 |
| 状态门禁 | 仅 `status=completed` 可预览；否则 409 | 未完成文档 → 409 |

**curl 验收**（先登录、建库、上传 txt，将 `$kbId` / `$docId` 换成真实 id）：

```powershell
$login = Invoke-RestMethod -Uri http://localhost:8000/api/v1/auth/login -Method POST -ContentType "application/json" -Body '{"email":"demo@example.com","password":"password123"}'
$h = @{ Authorization = "Bearer $($login.access_token)" }
$kb = Invoke-RestMethod -Uri "http://localhost:8000/api/v1/knowledge-bases" -Method POST -ContentType "application/json" -Headers $h -Body '{"name":"预览测试库"}'

curl.exe -X POST "http://localhost:8000/api/v1/knowledge-bases/$($kb.id)/documents" `
  -H "Authorization: Bearer $($login.access_token)" `
  -F "files=@README.md;type=text/markdown"

# 将 docId 换成上一步返回的 documents[0].id
curl.exe -i "http://localhost:8000/api/v1/knowledge-bases/$($kb.id)/documents/$docId/preview" `
  -H "Authorization: Bearer $($login.access_token)"
```

预期：`HTTP/1.1 200`；`Content-Type: text/plain; charset=utf-8`（txt/md）或 `application/pdf`（pdf）。

**pytest**（本机 `backend/`，需 Postgres 已 migrate 到 005）：

```powershell
cd backend
$env:EMBEDDING_PROVIDER='mock'
pytest -v
```

预期：**45 passed**（含 `test_preview.py` 6 例 + 原 39 例）。

---

### Wave 2.5：Dashboard 统计 API

| 做什么 | 解决啥 | 怎么验 |
|--------|--------|--------|
| `GET /api/v1/dashboard/stats` | 聚合知识库数、文档各状态、chunk 总量、平均入库耗时、成功率 | curl / pytest 见下 |
| 个人版 scope | 只统计 `owner_user_id` 为自己的库 | A 用户看不到 B 的数据 |
| 企业版 scope | admin / member 均看 `owner_org_id` 组织数据 | member 与 admin 统计一致 |

**curl 验收**（先登录、建库、上传 txt，再查统计）：

```powershell
$login = Invoke-RestMethod -Uri http://localhost:8000/api/v1/auth/login -Method POST -ContentType "application/json" -Body '{"email":"demo@example.com","password":"password123"}'
$h = @{ Authorization = "Bearer $($login.access_token)" }

Invoke-RestMethod -Uri "http://localhost:8000/api/v1/dashboard/stats" -Headers $h
```

预期：`scope=personal`；`knowledge_base_count` ≥ 1；`documents_by_status.completed` ≥ 1；`total_chunk_count` > 0；`avg_processing_duration_seconds` 非 null。

**pytest**（本机 `backend/`，需 Postgres 已 migrate 到 005）：

```powershell
cd backend
$env:EMBEDDING_PROVIDER='mock'
pytest -v
```

预期：**56 passed**（含 `test_dashboard.py` 6 例 + 原 45 例）。

---

### Wave 3.1：RAG 对话 SSE API

| 做什么 | 解决啥 | 怎么验 |
|--------|--------|--------|
| `POST /api/v1/knowledge-bases/{kb_id}/chat` | 用户提问 → 向量检索 → DeepSeek 流式回答 | SSE `citation` / `token` / `done` 事件 |
| `services/rag/retrieval.py` | pgvector + tsvector 双路召回，RRF 融合 Top-5（`kb_id` 强制过滤） | 空库不胡编；跨库检索不到 |
| `services/rag/generation.py` | DeepSeek SSE（无 Key 时 mock 流） | 测试不调真实 API |
| `require_kb_access(read)` | member 可对话；越权 kb → 403 | `test_chat.py` 绿 |

**curl 验收**（先登录、建库、上传 md/txt 并等入库完成，将 `$kbId` 换成真实 id）：

```powershell
$login = Invoke-RestMethod -Uri http://localhost:8000/api/v1/auth/login -Method POST -ContentType "application/json" -Body '{"email":"demo@example.com","password":"password123"}'
$h = @{ Authorization = "Bearer $($login.access_token)" }

curl.exe -N -X POST "http://localhost:8000/api/v1/knowledge-bases/$kbId/chat" `
  -H "Authorization: Bearer $($login.access_token)" `
  -H "Content-Type: application/json" `
  -d "{\"message\":\"员工年假有几天？\"}"
```

预期：`Content-Type: text/event-stream`；依次出现 `event: citation`、`event: token`、`event: done`。

> 生产对话：`.env` 配置 `DEEPSEEK_API_KEY`；CI/本地测试默认无 Key 走 mock 流。

**pytest**（本机 `backend/`，需 Postgres 已 migrate 到 005）：

```powershell
cd backend
$env:EMBEDDING_PROVIDER='mock'
py -3.11 -m pytest -v
```

预期：**58 passed**（含 `test_chat.py` 7 例 + 原 51 例）。

---

### Wave 3.2：对话 citations 落库

| 做什么 | 解决啥 | 怎么验 |
|--------|--------|--------|
| Alembic `006_chat_messages` | 对话消息与引用持久化，便于溯源与仪表盘 | `alembic upgrade head` 到 006 |
| `chat_messages` 表 | user/assistant 各一行；assistant 行带 JSONB `citations` | 按 `message_id` 可查到页码、片段 |
| `services/rag/persistence.py` | SSE 流结束后写入一轮问答 | `test_chat_persists_citations_to_db` 绿 |
| `stream_chat_events` 落库 | done 事件的 `message_id` = assistant 行主键 | 空库 citations 为 `[]` 也落库 |

**DB 验收**（对话 curl 完成后，将 `$messageId` 换成 done 事件里的 id）：

```sql
SELECT id, role, citations FROM chat_messages WHERE id = '$messageId';
```

预期：`role=assistant`；`citations` JSON 含 `chunk_id`、`doc_name`、`page`、`excerpt`。

**pytest**（本机 `backend/`，需 Postgres 已 migrate 到 **006**）：

```powershell
cd backend
$env:EMBEDDING_PROVIDER='mock'
py -3.11 -m pytest -v
```

预期：**58 passed**（含 `test_chat.py` 7 例 + 原 51 例）。

---

### Wave 3.3：无依据拒绝胡编（AC-4）

| 做什么 | 解决啥 | 怎么验 |
|--------|--------|--------|
| `services/rag/relevance.py` | 检索后 gate：向量分低且无词面重叠 → 未找到 | `test_rag_relevance.py` 绿 |
| `filter_relevant_chunks` | 无关问题不喂 LLM、不吐 citation | `test_chat_irrelevant_question_*` 绿 |
| `RETRIEVAL_MIN_TOP1_SIMILARITY` | 通义嵌入 Top-1 底线（默认 0.35） | `.env` 可调 |

**curl 验收**（库内已有文档，问一个库里没有的问题）：

```powershell
'{"message":"公司火星殖民计划的政策是什么？"}' | Out-File "$env:TEMP\chat-irrelevant.json" -Encoding utf8 -NoNewline
curl.exe -N -X POST "http://localhost:8000/api/v1/knowledge-bases/$kbId/chat" `
  -H "Authorization: Bearer $token" -H "Content-Type: application/json" --data-binary "@$env:TEMP\chat-irrelevant.json"
```

预期：无 `event: citation`；回答含「未找到」；`done.citations` 为 `[]`。

**pytest**：

```powershell
cd backend
$env:EMBEDDING_PROVIDER='mock'
py -3.11 -m pytest -v
```

预期：**64 passed**。

---

### Wave 3.4：kb_id filter + hybrid RRF

| 做什么 | 解决啥 | 怎么验 |
|--------|--------|--------|
| `services/rag/retrieval.py` | 向量 Top-20 + 全文 tsvector Top-20，同 `kb_id` 过滤 | `test_retrieval_hybrid.py` 绿 |
| `services/rag/rrf.py` | RRF 融合取 Top-5 喂 LLM | 双路都命中的 chunk 排名更靠前 |
| 入库 `content_tsv` | `heading_path` + `section_title` + `content` 入全文索引 | 章节编号类查询可走 FTS 路 |
| SA-3 | 检索结果 chunk 的 `kb_id` 与请求一致，跨库不泄漏 | `test_retrieve_chunks_sa3_kb_id_isolation` 绿 |

**pytest**：

```powershell
cd backend
$env:EMBEDDING_PROVIDER='mock'
py -3.11 -m pytest -v
```

预期：**68 passed**（含 `test_retrieval_hybrid.py` 4 例 + 原 64 例）。

---

### Wave 3.5：golden_qa + Hit@3 自动化

| 做什么 | 解决啥 | 怎么验 |
|--------|--------|--------|
| `docs/golden_qa.md` v0.2 | 标准问题集 GQ-1～4 + Hit@3 定义落盘 | 与 TECH-4 §4.3.8 一致 |
| `tests/test_retrieval_golden.py` | hybrid 检索 Top-3 内须命中预期 chunk/章节/页码；词重叠 mock 稳定向量路 | 4 题 parametrized 全绿 |

**pytest**：

```powershell
cd backend
$env:EMBEDDING_PROVIDER='mock'
py -3.11 -m pytest tests/test_retrieval_golden.py -v
```

预期：**4 passed**（仅 Hit@3）；全量 **72 passed**（含原 68 例）。

---

### Wave 0.4：pytest + CI 骨架

| 做什么 | 解决啥 | 怎么验 |
|--------|--------|--------|
| `pytest.ini` + `tests/conftest.py` | 后续 Wave 1+ 测试有统一入口 | 本机 `pytest` 退出码 0 |
| `requirements-dev.txt` | 测试依赖不进生产 Docker 镜像 | `pip install -r requirements-dev.txt` |
| `.github/workflows/ci.yml` | 推送/PR 自动跑迁移 + pytest | GitHub Actions 绿 |

本机（在 `backend/` 目录）：

```powershell
cd backend
pip install -r requirements-dev.txt -i https://mirrors.aliyun.com/pypi/simple/
pytest
```

预期：`no tests ran` 或 `0 passed` 均可（Wave 0.4 允许 0 个测试用例）。

> 前端 `npm run build` 在 **Wave 4** 开工后再加入 CI（TECH-6.6）。

---

### 仍失败时

| 现象 | 怎么办 |
|------|--------|
| `unexpected EOF` / 0B 一直不动 | `docker builder prune -f` 后 **重跑** `docker-pull.ps1` |
| 所有镜像源都 FAIL | **手机热点** 或 **VPN** 开一次，再跑脚本（拉完会缓存） |
| 429 Too Many Requests | 去掉轩辕镜像；Engine 里只留 example.json 里两个源 |
| 想改 Python 热更新 | Postgres 仍 Docker；API 用 venv：`uvicorn app.main:app --reload` |

### 备选：本机 Windows 安装 PostgreSQL

Docker 实在搞不定时临时用，见 [postgresql.org/download/windows](https://www.postgresql.org/download/windows/) + `.env` 改 `localhost`。**答辩部署仍以 Docker 为准**。

### 常用命令

```powershell
docker compose ps
docker compose logs api
docker compose logs postgres
docker compose down          # 停服务，数据保留
docker compose down -v       # 删库数据（慎用）
```

### Wave 进度

| Wave | 状态 | 你能做什么 |
|------|------|------------|
| 0.1 | ✅ | 目录、`.env.example` |
| **0.2** | ✅ | Docker 栈 + `/health` |
| **0.3** | ✅ | `alembic upgrade head` → `001 (head)` |
| **0.4** | ✅ | `pytest` 骨架 + GitHub Actions CI |
| **1.1** | ✅ | users/org/members 表 + 注册登录 API |
| **1.2** | ✅ | JWT Bearer 中间件 + RBAC + `GET /auth/me` |
| **1.3** | ✅ | 组织设置 API（admin GET/PATCH `/organization/settings`） |
| **2.1** | ✅ | knowledge_bases 表 + CRUD API + `require_kb_access` |
| **2.2** | ✅ | documents 表 + multipart 上传 + BackgroundTasks 入库 stub |
| **2.3** | ✅ | 结构优先切片 + pgvector 写入 |
| **2.4** | ✅ | 文档预览 API（PDF/文本 + require_kb_access read） |
| **2.5** | ✅ | Dashboard 统计 API（chunk_count / 耗时 / 权限 scope） |
| **3.1** | ✅ | RAG 对话 SSE（向量检索 + DeepSeek 流式 + kb_id 隔离） |
| **3.2** | ✅ | citations 落库 `chat_messages` |
| **3.3** | ✅ | 无依据拒绝胡编（AC-4 相关性 gate） |
| **3.4** | ✅ | hybrid RRF（向量+全文 tsvector、kb_id 隔离、SA-3） |
| 3.5 | ✅ | golden_qa.md + Hit@3 自动化（GQ-1～4） |

## 文档入口

| 文件 | 说明 |
|------|------|
| [`docs/cockpit.html`](docs/cockpit.html) | 项目驾驶舱（进度、下一步） |
| [`docs/PRD.md`](docs/PRD.md) | 产品需求 |
| [`docs/TECH.md`](docs/TECH.md) | 技术方案 |
| [`docs/tasks/002-plan.md`](docs/tasks/002-plan.md) | 开发 Wave 清单 |
| [`AGENTS.md`](AGENTS.md) | AI 协作规则 |

## 许可证

毕业设计自用项目；未指定开源许可证前请勿公开传播 API Key 或 `.env`。
