# 知岸 — 内网 HTTP 部署清单

> **EW-B1** · 阶段 B「可访问」· **无 HTTPS/TLS**  
> 适用：公司内网、VPN、可信局域网 · **不适合** 对公网直接暴露

---

## ⚠️ 内网警示（部署前必读）

| 风险 | 说明 |
|------|------|
| **明文传输** | 浏览器与服务器之间走 **HTTP**，登录密码、JWT token、文档内容 **不加密**。同网段他人可能嗅探。 |
| **适用场景** | ✅ 内网/VPN/隔离 VLAN · ❌ 公网 IP 直接访问、咖啡厅 Wi‑Fi |
| **对外说法** | 「支持 Docker 一键部署；**传输层加密由客户侧反向代理或内网隔离承担**」 |
| **已做的补偿** | 应用层 JWT 鉴权、登录失败限流、chat/upload API 限流、审计日志 — **不能替代 HTTPS** |

**若将来需要 HTTPS**：在知岸容器前加 nginx/Caddy 终止 TLS（本波 EW-B1～B4 **不含** 证书配置）。

---

## 1. 服务器要求

| 项 | 最低建议 |
|----|----------|
| **内存** | **2 GB**（Postgres ~512M + API ~768M，见 `docker-compose.yml` limits） |
| **磁盘** | ≥ 10 GB（镜像 + 数据库 + 上传文件） |
| **系统** | Linux amd64 或 Windows + Docker Desktop |
| **软件** | Docker Engine 24+ 与 Docker Compose v2 |
| **网络** | 能访问 DeepSeek / 通义 API（出站 HTTPS）；**入站仅内网** |

---

## 2. 开放端口

| 端口 | 服务 | 说明 |
|------|------|------|
| **80** | web（nginx） | **EW-B4 生产入口**：静态九页 + `/api` 反代到 api |
| **8000** | API（FastAPI） | 健康检查、REST、SSE 对话；smoke 脚本默认直连 |
| **5432** | PostgreSQL | 默认映射到宿主机；**生产建议仅内网访问或去掉 ports 映射** |
| 5173 | 前端（开发态） | 本机 `npm run dev`；**生产请用 web:80，不用 Vite** |

EW-B1 验收只需 **8000** 上 `/health` 返回 `database: ok`。  
**EW-B4 完整验收**：浏览器打开 `http://SERVER_IP/`（80 端口）可登录并完成对话。

---

## 3. 从零部署清单

按顺序勾选；**跳步可能导致 health 失败或对话不可用**。

### 3.1 准备密钥与配置

- [ ] 克隆仓库到部署机
- [ ] 复制生产环境模板：  
  `Copy-Item .env.production.example .env`（Linux: `cp .env.production.example .env`）
- [ ] 编辑 `.env`，**必改**：
  - [ ] `POSTGRES_PASSWORD` — 强随机密码
  - [ ] `JWT_SECRET` — 至少 32 位随机字符串
  - [ ] `DEEPSEEK_API_KEY` — DeepSeek 对话
  - [ ] `TONGYI_API_KEY` — 通义嵌入（`EMBEDDING_PROVIDER=tongyi`）
  - [ ] `CORS_ORIGINS` — 浏览器访问前端的 origin（EW-B4：**含 `http://SERVER_IP` 无尾斜杠**，见 `.env.production.example`）
- [ ] **确认** `.env` 未提交 Git（已在 `.gitignore`）

### 3.2 Docker 镜像（国内服务器）

- [ ] （Windows）配置 Docker Engine 镜像加速：见 `scripts/docker-engine.example.json`
- [ ] 预拉基础镜像：`.\scripts\docker-pull.ps1`（Linux 可手动 `docker pull` postgres:16 与 python:3.11-slim）

### 3.3 启动栈

**生产推荐**（uploads 持久化卷 + 资源 limit 注释，见 EW-B2）：

```powershell
cd /path/to/rag-knowledge-platform
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

开发 / 快速探活（uploads 在容器内，**重启会丢上传文件**）：

```powershell
docker compose up -d --build
```

或 Windows 一键（含复制 `.env.example` 若缺失 — **生产请先用 `.env.production.example`**）：

```powershell
.\scripts\docker-up.ps1
```

- [ ] 等待 Postgres healthcheck 通过（约 10～30 秒）
- [ ] 查看日志无致命错误：`docker compose logs api postgres`

### 3.4 数据库迁移（首次部署必做）

health 只测连通性；**业务表需 Alembic**：

```powershell
docker compose exec api alembic upgrade head
docker compose exec api alembic current
```

预期：`011 (head)`（版本号随迁移递增，以 `alembic current` 为准）。

### 3.5 验收 `/health`

```powershell
curl http://localhost:8000/health
# 或
Invoke-RestMethod http://localhost:8000/health
```

**通过标准**：

```json
{"status":"ok","database":"ok"}
```

- [ ] `status` 为 `ok`
- [ ] `database` 为 `ok`
- [ ] 无需登录即可访问（`/health` 在鉴权白名单）

内网其他机器验收（将 `SERVER_IP` 换成实际 IP）：

```bash
curl http://SERVER_IP:8000/health
```

### 3.6 （可选）种子演示账号

答辩 / 内网演示：

```powershell
docker compose exec api python scripts/seed_enterprise_demo.py
```

账号见 `docs/TEST_ACCOUNTS.md`。**生产环境请改默认密码或不用种子脚本。**

---

## 4. 环境变量速查

| 变量 | 必填 | 说明 |
|------|------|------|
| `POSTGRES_PASSWORD` | ✅ | Postgres 密码；与 compose 中 `DATABASE_URL` 一致 |
| `JWT_SECRET` | ✅ | JWT 签名；泄露 = 可伪造任意用户 |
| `DEEPSEEK_API_KEY` | ✅* | 对话；无 Key 时对话不可用 |
| `TONGYI_API_KEY` | ✅* | 生产嵌入；`EMBEDDING_PROVIDER=tongyi` 时必填 |
| `EMBEDDING_PROVIDER` | 建议 | 生产固定 `tongyi`；**部署后勿随意更换**（否则全库重嵌） |
| `CORS_ORIGINS` | ✅ | 前端 origin 白名单，逗号分隔 |
| `DATABASE_URL` | 自动 | compose 内 api 服务会覆盖为 `@postgres:5432` |
| `UPLOAD_DIR` | 默认 | 生产 compose 固定 `/app/uploads`（命名卷 `uploads_data`） |

### 4.1 可选 · 扫描 PDF OCR（Format-F4）

默认 **不强制** 装 OCR；未装时扫描件上传 failed（文字层 PDF 不受影响）。

| 项 | 说明 |
|----|------|
| **系统依赖** | **poppler**（`pdf2image` 渲染页图）：Debian `poppler-utils` · macOS `brew install poppler` · Windows 见 [`requirements-ocr.txt`](../backend/requirements-ocr.txt) 注释 |
| **Python 可选包** | `cd backend && pip install -r requirements-ocr.txt`（PaddleOCR + paddlepaddle + pdf2image） |
| **`OCR_ENABLED`** | 默认 `1`；`0` = 关闭 OCR，扫描件仍「不支持扫描件」 |
| **`OCR_MAX_PAGES`** | 默认 `30`；单文件扫描页超限 → failed + 中文拆文件提示 |
| **Docker 注意** | 标准 `docker compose` 镜像**未**预装 Paddle；要在 Dockerfile/compose 里显式加 poppler + OCR 依赖，或接受扫描件 failed |
| **成本** | 本地 CPU，**无 API token**；见 [`eval-M4-cost-model.md`](tasks/eval-M4-cost-model.md) §7 |

完整模板：仓库根目录 **`.env.production.example`**（开发用 **`.env.example`**）。

---

## 5. 常见问题

| 现象 | 排查 |
|------|------|
| `database: error` | Postgres 未就绪 → `docker compose logs postgres`；密码与 `POSTGRES_PASSWORD` 不一致 |
| 拉镜像超时 | 配置镜像加速 → `scripts/docker-pull.ps1` |
| API 502 / 连接拒绝 | `docker compose ps` 确认 api 为 running；防火墙放行 8000 |
| 注册/登录 CORS 错误 | `.env` 中 `CORS_ORIGINS` 与浏览器地址栏 origin **完全一致**（含端口） |
| 对话无响应 | 检查 `DEEPSEEK_API_KEY`；`docker compose logs api` |
| 上传后一直 processing | 检查 `TONGYI_API_KEY` 与嵌入配置 |
| 扫描 PDF 一直 failed | 是否扫描件 · `OCR_ENABLED` · 是否装 poppler + `requirements-ocr.txt` · 页数是否 &gt; `OCR_MAX_PAGES` |

---

### 3.7 生产卷持久化验收（EW-B2）

确认 uploads 与数据库在容器重启后仍在：

```powershell
# 1. 用生产 compose 启动（见 §3.3）
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build

# 2. 健康检查
Invoke-RestMethod http://localhost:8000/health
# 预期：status ok · database ok

# 3. 重启 api 后 uploads 卷仍在（卷名 uploads_data）
docker compose -f docker-compose.yml -f docker-compose.prod.yml restart api
docker volume inspect rag-knowledge-platform_uploads_data
```

- [ ] `database: ok`
- [ ] `uploads_data` 卷存在且 api 重启后挂载路径不变

### 3.10 备份与恢复（Eval-Ops M10）

生产环境定期备份 **PostgreSQL + uploads 卷**；步骤见 [`tasks/eval-M10-backup-runbook.md`](tasks/eval-M10-backup-runbook.md)。

```powershell
.\scripts\backup-prod.ps1
.\scripts\restore-prod.ps1 -BackupDir backups\m10-YYYYMMDD-HHmmss
```

恢复后 `GET http://localhost:8000/health` 应为 `{"status":"ok","database":"ok"}`。备份目录在 `backups/`（已 gitignore）。

### 3.8 部署 smoke 脚本（EW-B3）

端到端验证：**注册 → 建库 → 上传 txt → 等待入库 → 对话 → 引用非空**。  
比 `/health` 多测鉴权、嵌入、DeepSeek 对话与 RAG 引用链路。

**前置**（缺一不可）：

- [ ] §3.3～3.4 栈已起且 `alembic upgrade head` 完成
- [ ] `.env` 中 `DEEPSEEK_API_KEY`、`TONGYI_API_KEY`（`EMBEDDING_PROVIDER=tongyi`）已填
- [ ] API 可从本机访问（默认 `http://localhost:8000`）

**运行**：

```powershell
cd /path/to/rag-knowledge-platform
.\scripts\smoke-deploy.ps1
```

内网其他机器（将 IP 换成实际地址）：

```powershell
.\scripts\smoke-deploy.ps1 -BaseUrl http://192.168.1.10:8000
```

可选参数：`-PollTimeoutSec 180`（入库等待秒数，默认 180）、`-Password`（注册密码）。

**通过标准**：

- [ ] 脚本 **exit 0**
- [ ] 终端最后一行：`EW-B3 smoke passed: register -> kb -> upload -> chat -> citations`
- [ ] 输出含 `citations=N`（N ≥ 1）

**失败排查**：

| 现象 | 排查 |
|------|------|
| `health unreachable` | `docker compose ps` · 防火墙 8000 |
| `ingestion timeout` / `failed` | `TONGYI_API_KEY` · `docker compose logs api` |
| `empty chat SSE` / 无 citations | `DEEPSEEK_API_KEY` · 嵌入是否完成 · `docker compose logs api` |

夹具：`scripts/fixtures/smoke-handbook.txt`（含「年假10天」条款，供检索命中）。

### 3.9 前端静态托管（EW-B4）

生产栈在 EW-B2 基础上增加 **web（nginx）** 容器：构建 `frontend/dist/` 并托管九页；`/api/*` 反代到 `api:8000`（含 SSE 对话）。

**架构（白话）**：

```
浏览器 http://SERVER_IP/
    → nginx:80 静态 HTML/JS/CSS
    → /api/v1/* 反代 → api:8000
```

**前置**：

- [ ] §3.3 使用 **生产 compose**（含 `docker-compose.prod.yml`，会 build `web`）
- [ ] `.env` 中 `CORS_ORIGINS` **包含** `http://SERVER_IP`（80 端口，无尾斜杠）
- [ ] §3.4 `alembic upgrade head` 已完成

**启动（与 §3.3 相同，会一并 build web）**：

```powershell
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
docker compose ps
# 预期：zhiku-web / zhiku-api / zhiku-postgres 均为 running
```

**九页验收清单**（将 `SERVER_IP` 换成内网 IP；Windows 若 80 被占，compose 改 `8080:80` 则 URL 带 `:8080`）：

| # | 路由 | 你怎么验 |
|---|------|----------|
| 1 | `/login` | 未登录访问 `/dashboard` 应落到登录页 |
| 2 | `/dashboard` | 登录后概览、侧栏可见 |
| 3 | `/knowledge-bases` | 资料库列表 |
| 4 | `/knowledge-bases/{id}` | 点进某库详情 |
| 5 | `/knowledge-bases/{id}/documents/{docId}` | 有文档时点预览 |
| 6 | `/knowledge-bases/{id}/chat` | 对话页；**发一条问题，右侧/下方出现引用** |
| 7 | `/settings/account` | 账号设置 |
| 8 | `/organization/members` | 成员管理（个人账号可能无入口，企业 member/admin 测） |
| 9 | `/organization/settings` | 团队设置（Admin/Owner） |

**快速对话验收**（与 B3 同链路，经 nginx）：

1. 浏览器打开 `http://SERVER_IP/login`，注册或登录  
2. 新建资料库 → 上传 `scripts/fixtures/smoke-handbook.txt` → 等状态「就绪」  
3. 进入该库对话页，问「年假有多少天？」→ 回答含引用（文档名 + 片段）

**经 web 探活**（可选，与直连 8000 等价）：

```powershell
Invoke-RestMethod http://SERVER_IP/health
Invoke-RestMethod http://SERVER_IP/api/v1/...  # 须带 JWT，一般用手动登录验
```

**通过标准**：

- [ ] `http://SERVER_IP/` 返回知岸登录/概览（非 nginx 404）
- [ ] 深链刷新（如直接打开 `/knowledge-bases`）不 404（SPA fallback）
- [ ] 完成一次对话且 **citations 非空**
- [ ] 九页上表关键路由均可达（权限页按账号类型跳过并注明）

**失败排查**：

| 现象 | 排查 |
|------|------|
| 页面空白 / 404 | `docker compose logs web` · `docker compose ps` 确认 zhiku-web running |
| 登录后 API 失败 / CORS | `CORS_ORIGINS` 与地址栏 **完全一致**（`http://IP` vs `http://IP:8080`）；**本机 prod :80 须含 `http://localhost`（无端口）** |
| 经 nginx 502、直连 8000 正常 | 重建 `api` 后执行 `docker compose restart web`（nginx 解析旧 api IP） |
| 对话无 SSE | nginx 已关 `proxy_buffering`；查 `docker compose logs api web` |
| 80 端口被占 | `docker-compose.prod.yml` 改 `"8080:80"` 并更新 CORS |

**文件**：`frontend/Dockerfile` · `docker/nginx/default.conf` · `docker-compose.prod.yml`（`web` 服务）

---

## 6. 本波不做（见 `enterprise-wave-plan.md`）

| 任务 | 内容 |
|------|------|
| EW-B2 | ✅ 生产 compose 调优（`docker-compose.prod.yml`） |
| EW-B3 | ✅ smoke 脚本（`scripts/smoke-deploy.ps1`） |
| EW-B4 | ✅ 前端 nginx 静态托管（`web` 容器 · 端口 80） |
| — | HTTPS / TLS / 证书 |

---

## 7. 相关文档

- 开发环境（本机）：[`README.md`](../README.md)「本地开发」
- 技术栈与 Docker 结构：[`TECH.md`](TECH.md) §6
- 企业波次计划：[`tasks/enterprise-wave-plan.md`](tasks/enterprise-wave-plan.md)
- 测试账号：[`TEST_ACCOUNTS.md`](TEST_ACCOUNTS.md)
