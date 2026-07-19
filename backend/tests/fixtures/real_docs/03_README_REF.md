# 睿阁 — RAG 企业知识库平台

[![CI](https://github.com/1y4w1s/rag-knowledge-platform/actions/workflows/ci.yml/badge.svg)](https://github.com/1y4w1s/rag-knowledge-platform/actions/workflows/ci.yml)

> 多格式文档上传 → 知识库对话 → **引用溯源**（文档名 + 章节 + 页码）
>
> 代码目录名 `rag-knowledge-platform`；产品对外称 **睿阁**。

---

## 🚀 核心功能

| 功能 | 说明 |
|------|------|
| 📄 **多格式文档上传** | 支持 PDF、TXT、MD、DOCX、XLSX、PPTX，自动解析 + 结构优先切片 |
| 🔍 **Hybrid 检索** | pgvector 向量检索 + PostgreSQL tsvector 全文检索 + **CJK 分词** + RRF 融合 + 条件 Rerank |
| 💬 **RAG 对话** | SSE 流式输出，带引用溯源（文档名 + 段落 + 章节），无依据拒答 |
| 📝 **文档版本管理** | 同名上传自动创建新版本，支持版本回滚 |
| 👥 **组织管理** | 企业版：成员管理（admin/member）、自定义角色权限、部门树 |
| ⚙️ **异步任务** | Celery + Redis 异步 ingestion，支持失败重试 |
| 🔐 **认证与安全** | JWT Bearer、登录限流、API Key 认证、审计日志、Prompt 注入防护 |
| 🔔 **Webhook** | Ingestion 完成后 HTTP 回调，HMAC-SHA256 签名验证 |
| 📊 **可观测性** | OpenTelemetry 链路追踪 + Loki 日志聚合 + Grafana 面板 |
| 🧪 **评估体系** | Golden QA Hit@3 基线（93.6% 命中率），真实 Embedding 评测 |

---

## 🧱 技术栈

| 层级 | 选型 |
|------|------|
| 后端框架 | Python 3.11+ / FastAPI |
| 数据库 | PostgreSQL 16 + pgvector |
| 异步任务 | Celery + Redis |
| 前端 | React 18 + TypeScript + Vite |
| 嵌入模型 | 通义 text-embedding-v2 |
| 对话模型 | DeepSeek Chat（SSE 流式） |
| 重排序 | 通义 qwen3-rerank（条件触发，省 ~85% 费用） |
| 检索 | Hybrid（pgvector + tsvector）+ RRF 融合 + CJK 分词 |
| 切片策略 | 结构优先切片（章节/段落感知，heading-path 追踪） |
| 容器化 | Docker Compose（PostgreSQL + API + Redis + Celery）|
| 可观测性 | OpenTelemetry + Grafana + Loki + Tempo |
| CI/CD | GitHub Actions（自动迁移 + pytest） |

详细架构见 [`docs/TECH.md`](docs/TECH.md)。

---

## 📁 仓库结构

```
rag-knowledge-platform/
├── backend/                    # FastAPI 后端
│   ├── app/
│   │   ├── api/                # 路由（auth / chat / documents / kb / batch / webhooks / roles）
│   │   ├── core/               # 配置、中间件、异常、重试、降级、OTel
│   │   ├── models/             # SQLAlchemy 模型（含 DocumentVersion、CustomRole、Webhook）
│   │   ├── schemas/            # Pydantic 序列化
│   │   └── services/           # 业务逻辑（auth / documents / ingestion / rag / search / webhook）
│   ├── alembic/                # 数据库迁移（34 个版本）
│   └── tests/                  # pytest（含 Golden QA 评估）
├── frontend/                   # React 前端（Vite）
├── docs/                       # PRD、TECH、设计文档
├── docker/                     # PostgreSQL、Loki、Tempo、Grafana 配置
├── docker-compose.yml          # 主栈：postgres + api + redis + celery
├── docker-compose.monitoring.yml  # 监控栈：loki + grafana + tempo
└── .github/workflows/ci.yml    # CI 流水线
```

---

## 🏗️ 快速开始

### 前置条件

- [Docker Desktop](https://www.docker.com/products/docker-desktop/)（Windows AMD64）
- 配置 API Key（通义千问 + DeepSeek）到 `.env`

### 一键启动

```powershell
# 1. 配置环境变量
Copy-Item .env.example .env
# 编辑 .env，填入 DEEPSEEK_API_KEY 和 TONGYI_API_KEY

# 2. 构建并启动
docker compose up -d --build

# 3. 数据库迁移
docker compose exec api alembic upgrade head

# 4. 启动监控栈（可选）
docker compose -f docker-compose.yml -f docker-compose.monitoring.yml up -d

# 5. 验收
curl http://localhost:8000/health
# → {"status":"ok","database":"ok"}
```

### 访问

| 服务 | 地址 |
|------|------|
| API | http://localhost:8000 |
| Grafana | http://localhost:3001（admin/admin） |
| Loki | http://localhost:3100 |

### 测试账号

首次使用请通过注册页自行创建账号。支持个人版和企业版两种账号类型。

---

## 📖 文档入口

| 文件 | 说明 |
|------|------|
| [`docs/PRD.md`](docs/PRD.md) | 产品需求文档 |
| [`docs/TECH.md`](docs/TECH.md) | 技术方案（架构/数据库/API/安全） |
| [`docs/DESIGN.md`](docs/DESIGN.md) | UI/UX 设计系统（Design Token） |
| [`docs/DEPLOY.md`](docs/DEPLOY.md) | 生产/内网部署指南 |
| [`docs/production-checklist.md`](docs/production-checklist.md) | 生产部署检查清单 |
| [`AGENTS.md`](AGENTS.md) | AI 协作规则 |
