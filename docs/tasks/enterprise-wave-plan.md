# Plan · 企业化波次（Enterprise Wave）

> **状态**：✅ 阶段 A/B/C/D/E 完成 · **EW-D1～D6 ✅** · **EW-E1 ✅** · **EW-E2 ✅**  
> **依据**：`AGENTS.md` 北极星 · [企业评审 2026-07-06](premium-review-roadmap.md) 结论 · `kb-pages-polish-plan.md` Plan-3E · `rag-optimization-plan.md` · `002-plan.md` Wave 6  
> **边界**：本 plan **不含** 支付/OCR/Agent/跨库搜（除非阶段 E 触发）· **不含 HTTPS/TLS**

---

## §0 · 前提与约束（已拍板）

### 0.1 产品目标

从「MVP 能 demo」推进到「**企业内可信运营**」：删得干净、查得到谁干的、API 不被刷爆、RAG 有据可查、能稳定部署给团队用。

### 0.2 硬约束：HTTPS 做不到 ✅ 已确认（2026-07-06）

| 项 | 决定 | 后果（白话） |
|----|------|--------------|
| **TLS/HTTPS** | ❌ **本波不做**（用户确认 2026-07-06） | 浏览器地址栏是 `http://`，密码和 token **明文走网络**；**只适合内网/VPN/可信局域网**，不能对公网宣传「安全传输已就绪」 |
| **替代验收（阶段 B）** | HTTP 部署 + 健康检查 + 环境变量规范 + 部署文档写清「须内网或前置网关」 | 对外说法：**「支持 Docker 一键部署；传输层加密由客户侧反向代理/内网隔离承担」** |
| **仍必须做** | 登录限流、API 限流、审计、存储清盘 | 弥补无 TLS 的一部分风险；不能替代 HTTPS，但降低暴力破解与滥用 |

### 0.3 阶段顺序（固定，不可跳）

```
A 可运营（清盘→审计→限流）
  → B 可访问（HTTP 部署，无 TLS）
  → C RAG 可证明（golden + 生产抽测）
  → D 企业体验（对话历史、去重、引用失效…）
  → E 发现层（按需）
```

### 0.4 单一事实来源

| 真相 | 文件 |
|------|------|
| 当前企业波次进度 | `docs/cockpit.html` + 本 plan 各节 ✅/🟡 |
| 3E 技术细节 | `kb-pages-polish-plan.md` §Plan-3E |
| 安全档 | `docs/TECH.md` TECH-SEC |

---

## §1 · 总路线图 ✅ 已确认（2026-07-06）

| 阶段 | 代号 | 交付什么 | 企业就绪含义 |
|------|------|----------|--------------|
| **A** | EW-A | 存储清盘 + 审计表 + 限流 | 能追责、删得干净、防刷 |
| **B** | EW-B | 2G HTTP 部署包 + 文档 + smoke | 团队内网能稳定访问 |
| **C** | EW-C | golden 扩题 + 生产嵌入抽测基线 | RAG 不是「感觉能答」 |
| **D** | EW-D | 去重/状态机/引用失效/对话历史 plan 子项 | 日常协作少踩坑 |
| **E** | EW-E | 跨库搜（触发再做） | 库多了才需要 |

**WIP=1**：同一时间只推进 **一个阶段** 里 **一条** 原子任务（I 窗）。

---

## §2 · 阶段 A — 可运营 / 可追责 ✅ 已确认（2026-07-06）

> **这节定什么**：删资料库/文档后磁盘不残留；关键操作进 `audit_logs`；登录与昂贵 API 有限流。  
> **详情对照**：`kb-pages-polish-plan.md` Plan-3E-4、3E-1；`TECH.md` TECH-SEC P1。

### EW-A1 · 存储清盘服务（Plan-3E-4 核心）✅（2026-07-06）

| 项 | 内容 |
|----|------|
| **做什么** | 新建 `services/storage/cleaner.py`：`remove_kb_tree(kb_id)`、`remove_document_tree(kb_id, doc_id)`；从 `lifecycle.py` 抽出现有删文件逻辑为单源 |
| **改谁** | `cleaner.py`（新）· `lifecycle.py`（改调 cleaner）· `knowledge_base/crud.py`（删库前调 `remove_kb_tree`） |
| **不做什么** | 软删、回收站（EW-D）· 改上传白名单 |
| **验收** | pytest：删库后 `upload_dir/{kb_id}/` 不存在；删文档行为与现网一致；全量 pytest 绿 |
| **风险** | 删库与并发上传竞态 → 日志记录失败路径，不阻塞 DB 删除 |

### EW-A2 · 审计表与迁移（Plan-3E-1 基础）✅（2026-07-06）

| 项 | 内容 |
|----|------|
| **做什么** | Alembic migration：`audit_logs`（`id, actor_user_id, action, resource_type, resource_id, kb_id, metadata json, ip, created_at`）；SQLAlchemy model + 写入 helper |
| **不做什么** | 审计**查看页** UI（EW-D 或 P1）· 记聊天正文 |
| **验收** | migration head 可升；helper 单测：写入后可查 · pytest 161 passed |
| **改动** | `011_audit_logs.py` · `models/audit_log.py` · `services/audit/log.py` · `test_audit_logs.py` |

### EW-A3 · 关键事件写审计 ✅（2026-07-06）

| 事件 | action 示例 |
|------|-------------|
| 登录成功/失败 | `auth.login` / `auth.login_failed` |
| 删资料库 | `kb.delete` |
| 删文档 / 重试 | `document.delete` / `document.retry` |
| 成员增删 / 改角色 | `org.member_add` / `org.member_remove` / `org.role_change` |
| 上传文档 | `document.upload`（记 kb_id、filename，**不记内容**） |

**验收**：pytest 或集成测：删库后 `audit_logs` 有对应行；登录失败连点 N 次有记录。✅ pytest 169 passed · `test_audit_events.py`

### EW-A3b · 审计查询 API（Plan-3E-1 后半）✅（2026-07-09）

| 项 | 内容 |
|----|------|
| **做什么** | `GET /api/v1/admin/audit-logs` · limit/offset · 筛选 action / kb_id / created_from / created_to · 组织 Admin only |
| **改谁** | `api/audit.py` · `services/audit/query.py` · `schemas/audit_log.py` · `test_audit_query.py` |
| **不做什么** | 审计页 React UI · org_unit_id 部门筛（ORG PRD P1 backlog） |
| **验收** | Admin 200 + 分页 · Member 403 · pytest 8 passed |

### EW-A4 · 登录失败限流 ✅（2026-07-06）

| 项 | 内容 |
|----|------|
| **做什么** | 按 IP（或 IP+username）滑动窗口：如 5 次/15min → 429 + 审计 `auth.login_rate_limited` |
| **实现** | MVP 可用内存 dict（单实例）；文档注明多副本需 Redis（Wave 2+） |
| **验收** | pytest：第 6 次失败 429；成功登录后计数重置（若采用 per-username）✅ pytest 171 passed · `test_login_rate_limit.py` |

### EW-A5 · API 限流（对话 + 上传）✅（2026-07-06）

| 路由 | 建议阈值（🟡 实现前可微调） |
|------|---------------------------|
| `POST .../chat` | 如 30 次/用户/小时 |
| `POST .../documents` | 如 20 次/用户/小时 |

**验收**：pytest 超限 429；member/admin 同规则（按 user_id）。✅ `test_api_rate_limit.py` · `api_rate_limit.py`

### 阶段 A 退出 DoD

- [x] EW-A1～A5 全 ✅  
- [ ] `pytest` 绿 · 无新增 ≥400 行业务文件  
- [x] `cockpit.html` + `AGENTS.md` 阶段 A ✅  
- [ ] 你能用白话讲：**删库后磁盘去哪了、谁删的在哪查、刷接口会怎样**

---

## §3 · 阶段 B — 可访问部署（HTTP · 无 TLS）✅ 已确认（2026-07-06）

> **替代原 Wave 6.1「HTTPS」**：在无法 TLS 前提下，交付 **可重复的内网 HTTP 部署**。

### EW-B1 · 部署清单与 `.env.production.example` ✅（2026-07-06）

| 项 | 内容 |
|----|------|
| **做什么** | `docs/DEPLOY.md`（或 README 专节）：2G 机要求、端口、**必须内网/VPN** 警示、POSTGRES_PASSWORD、DEEPSEEK/通义 Key、CORS 源 |
| **不做什么** | Caddy/nginx TLS 配置 · 域名证书 |
| **验收** | 按文档从零 `docker compose up` 可访问 `/health` |
| **改动** | `docs/DEPLOY.md` · `.env.production.example` |

### EW-B2 · 生产 compose 调优 ✅（2026-07-06）

| 项 | 内容 |
|----|------|
| **做什么** | `docker-compose.prod.yml`：重启策略、uploads 持久化卷 `uploads_data`、资源 limit 注释 |
| **验收** | 重启容器后数据仍在；`database: ok` |
| **改动** | `docker-compose.prod.yml` · `DEPLOY.md` §3.3/§3.7 · `.env.production.example` |

### EW-B3 · 部署 smoke 脚本 ✅（2026-07-06）

| 项 | 内容 |
|----|------|
| **做什么** | `scripts/smoke-deploy.ps1`：注册/登录→建库→上传小 txt→对话一条→引用非空 |
| **验收** | 脚本 exit 0；写入 `DEPLOY.md` §3.8 |
| **改动** | `scripts/smoke-deploy.ps1` · `scripts/fixtures/smoke-handbook.txt` · `DEPLOY.md` |

### EW-B4 · 前端静态资源托管方式 ✅（2026-07-06）

| 项 | 内容 |
|----|------|
| **方案** | nginx 容器（`web`）构建 `frontend/dist/`，`:80` 托管静态；`/api/` 反代 `api:8000` |
| **改谁** | `frontend/Dockerfile` · `docker/nginx/default.conf` · `docker-compose.prod.yml`（`web` 服务） |
| **不做什么** | HTTPS · Vite dev 服务器上生产 |
| **验收** | 内网 `http://SERVER_IP/` 九页可达 + 一次对话引用非空 · `DEPLOY.md` §3.9 |

### 阶段 B 退出 DoD

- [x] 内网 HTTP 完整路径可走通（web:80 + api:8000 + smoke）  
- [x] 文档明确写：**无 HTTPS 的风险与适用场景**  
- [x] 对外不说「已加密传输」，说「内网部署 + 应用层鉴权与限流」

---

## §4 · 阶段 C — RAG 可证明 ✅ 已确认（2026-07-06）

> **对照** `rag-optimization-plan.md` R5；**不替代** A/B。

### EW-C1 · golden 扩题（≥10 条）✅（2026-07-06）

| 项 | 内容 |
|----|------|
| **做什么** | 扩展 `docs/golden_qa.md` + `test_retrieval_golden.py`：含 DOCX、跨页、条款号、否定问法 |
| **验收** | Hit@3 全绿（mock 嵌入，CI 现状）✅ GQ-1～10 · pytest 10 passed |

### EW-C2 · 生产嵌入抽测基线 ✅（2026-07-06）

| 项 | 内容 |
|----|------|
| **做什么** | `docs/RAG_PRODUCTION_BASELINE.md`：手跑命令（`EMBEDDING_PROVIDER=tongyi`）+ 记录 Hit@3 与 3 条对话截图级现象 |
| **不做什么** | 把通义嵌入塞进 CI（贵、需 Key） |
| **验收** | 文档有日期、结果表；与 mock 差异有说明 · mock 10/10 ✅ · 通义 10/10 ✅（2026-07-06 付费开通后补跑） |

### EW-C3 · Dashboard 指标诚实化 ✅（2026-07-06）

| 项 | 内容 |
|----|------|
| **做什么** | `GET /dashboard/stats` 扩展：`golden_hit_rate_percent`（EW-C2 基线）· `avg_retrieval_latency_ms`（近 7 日对话实测）；前端去掉 87/320 占位 |
| **不做什么** | 改 golden 评测逻辑 · 接 DeepSeek 延迟 |
| **验收** | 企业 demo 不展示无标注假数字 · pytest dashboard/chat 绿 · `npm run build` 绿 |

### 阶段 C 退出 DoD

- [x] golden ≥10 · 生产抽测文档 ✅ · Dashboard 无假指标 ✅

---

## §5 · 阶段 D — 企业体验（P1 子集）✅ 已确认（2026-07-06）

> 每条独立开 I 窗；本波只列顺序，**不在 A/B/C 完成前 Implement**。

| ID | 项 | 来源 |
|----|-----|------|
| EW-D1 | 内容去重 SHA-256（3E-7）✅ | 同库重复上传 409 |
| EW-D2 | 删 processing 文档 409（3E-2）✅ | 状态机 |
| EW-D3 | 引用失效 UX「源文档已删除」（3E-3）✅ | 预览/对话 |
| EW-D4 | 对话历史：GET messages API + 列表 UI ✅ | PRD P1 |
| EW-D5 | 拆 `KnowledgeBaseDetailPage.tsx`（>400 行）✅ | AGENTS 软上限 |
| EW-D6 | CI 加 `npm run build` ✅ | R7 债 · `.github/workflows/ci.yml` frontend job · Node 20 · `npm ci` + build |

---

## §6 · 阶段 E — 发现层（按需触发）✅ 已确认（2026-07-06）

**触发条件**：资料库 ≥5 或用户反复「不知道在哪个库」。

- EW-E1：Plan-RAG R1-1 跨库文件名 API + Dashboard 入口 ✅  
- EW-E2：分页（单库 >50 篇）✅

---

## §7 · 明确不做（本 plan）

- ❌ HTTPS / TLS / 证书 / Let's Encrypt  
- ❌ 支付、积分、SaaS 计费  
- ❌ OCR 扫描件  
- ❌ 多租户公网 SaaS 宣传  
- ❌ 无 plan 的「顺便改预览/UI 抛光」

---

## §8 · 文档同步（每阶段过关必做）

| 过关 | 同步 |
|------|------|
| A | `cockpit.html` · `AGENTS.md` · `TECH-SEC` 审计/限流状态 · 本 plan §2 ✅ |
| B | `README.md` / `DEPLOY.md` · `cockpit` Wave 6 表述改为 HTTP |
| C | `golden_qa.md` · `RAG_PRODUCTION_BASELINE.md` · `cockpit` |
| 任意 I | 面试四件套（`CLAUDE.md`） |

---

## §9 · 下一对话交接（EW-E · 按需）

**触发条件**（§6）：资料库 ≥5 或用户反复「不知道在哪个库」。

```
@rag-knowledge-platform/AGENTS.md
@rag-knowledge-platform/docs/tasks/enterprise-wave-plan.md
@rag-knowledge-platform/docs/cockpit.html

【背景】阶段 D ✅ · EW-D1～D6 全完成 · CI 含 backend pytest + frontend build。
【要求】按需 EW-E1：Plan-RAG R1-1 跨库文件名 API + Dashboard 入口（确认触发后再开 I 窗）。
【验收】见 enterprise-wave-plan.md §6
```
