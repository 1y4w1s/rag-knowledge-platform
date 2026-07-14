# 002 — 知岸开发计划书（Plan）

> **版本**：v0.1  
> **状态**：✅ 用户确认（2026-07-03）  
> **依据**：`docs/PRD.md` v0.1、`docs/tasks/003-feasibility.md`  
> **原则**：**不因 MVP 阶段偷懒**——第一版交付完整企业级页面壳 + RAG 核心 + 安全基线  
> **答辩目标**：2027 年 5 月  
> **最后更新**：2026-07-07（Wave 6.4 驾驶舱同步）

---

## 1. 交付定义（什么叫「第一版做完」）

| 维度 | 标准 |
|------|------|
| 页面 | **9 主路由 + 全局侧栏** 全部可点、可演示 |
| RAG | 上传 → 入库 → 对话 → **引用** → 预览跳转 |
| 企业 | 双账号真演示 + 权限拦截 |
| 安全 | TECH-SEC MVP 档 + SA-1～3 测试绿 |
| 部署 | 2G 云 Docker 精简栈可访问 |
| UI 视觉 | Implement 前端 Wave 再定 `DESIGN.md`（**不砍页面**） |

---

## 2. 不做什么（防 scope 失控）

- ❌ OCR / 扫描 PDF 主路径
- ❌ 支付 / 积分 / 真 SSO / 微信登录
- ❌ 复杂 Agent、知识图谱、混合检索（P1）
- ❌ 解散组织、KB 级 ACL（Wave 2）
- ❌ UI 全站 i18n（P1；对话中英随问随答在 P0 Prompt 实现）
- ❌ 独立 Qdrant + Celery（2G 云；用 pgvector + BackgroundTasks）

---

## 3. 架构决策（相对 TECH-1 原案）

| 项 | 第一版采用 | 原因 |
|----|------------|------|
| 向量库 | **pgvector** | 2 核 2G 云 |
| 异步任务 | **FastAPI BackgroundTasks** | 减 Redis/Celery |
| 前端 | React + Vite + shadcn/ui | AI 主写，用户验收 |
| 设计稿 | **前端 Wave 开工前** `docs/DESIGN.md` | 用户要求届时再敲定风格 |

---

## 4. 页面与 Wave 映射（9 页不砍）

| 页面 | 路由 | 开发 Wave |
|------|------|-----------|
| 登录/注册 | `/login` | W4 前端 |
| 概览 Dashboard | `/dashboard` | W4 |
| 知识库列表 | `/knowledge-bases` | W4 |
| 知识库详情 | `/knowledge-bases/:id` | W4 |
| 文档预览 | `/knowledge-bases/:id/documents/:docId` | W5 |
| 对话 | `/knowledge-bases/:id/chat` | W5 |
| 账号设置 | `/settings/account` | W5 |
| 成员管理 | `/organization/members` | W5 |
| 组织设置 | `/organization/settings` | W5 |

**全局侧栏 + 顶栏**：W4 搭壳，W5 补全导航项。

---

## 5. 开发 Wave（按顺序，禁止跳）

### Wave 0 — 工程底座（不写业务 UI）

| # | 任务 | 完成标准 |
|---|------|----------|
| 0.1 | 目录结构、`.env.example`、Git | 能 `git clone` 后看懂结构 |
| 0.2 | Docker Compose（Postgres+pgvector、API）2G 版 | 云上一键 `up` |
| 0.3 | Alembic 迁移脚手架 | 空库 migrate 成功 |
| 0.4 | pytest + CI 骨架 | `pytest` 可跑（0 test 也行） |
| 0.5 | TECH-3～6 文档确认完毕 | ✅ 2026-07-03 |

### Wave 1 — 身份与权限

| # | 任务 | 完成标准 |
|---|------|----------|
| 1.1 | users / org / members 表 + 注册登录 API | AC-1、企业注册 |
| 1.2 | JWT 中间件 + RBAC 依赖 | SA-1 403 |
| 1.3 | 组织设置 API（读/改名称） | admin 可改 org 名 |

### Wave 2 — 知识库与文档入库

| # | 任务 | 完成标准 |
|---|------|----------|
| 2.1 | knowledge_bases / documents CRUD API | AC-1 |
| 2.2 | 上传 + BackgroundTasks 入库管道 | AC-2 |
| 2.3 | TECH-4 **结构优先切片** + pgvector 写入 | golden_qa 章节+页码命中 |
| 2.4 | 文档预览 API（PDF/文本） | 预览接口 200 |
| 2.5 | 入库预留字段（chunk_count、耗时） | Dashboard 数据可查 |

### Wave 3 — RAG 对话

| # | 任务 | 完成标准 |
|---|------|----------|
| 3.1 | 检索 + DeepSeek SSE | AC-3、AC-10 |
| 3.2 | 引用 metadata + citations 落库 | 引用含页码 |
| 3.3 | 无依据拒绝胡编 | AC-4 |
| 3.4 | kb_id filter + **hybrid RRF** | SA-3 + golden Hit@3 |
| 3.5 | `golden_qa.md` + `test_retrieval_golden.py` | pytest 绿 |

### Wave 4 — 前端壳（页面 1～4）

| # | 任务 | 完成标准 |
|---|------|----------|
| 4.0 | `docs/DESIGN.md` 用户确认风格 | 再写组件 |
| 4.1 | 侧栏布局 + 路由 | 9 路由占位 |
| 4.2 | 登录/注册页 | 能登录进 Dashboard |
| 4.3 | Dashboard 统计卡片 | 数字与 API 一致 |
| 4.4 | 知识库列表 + 详情 + 上传 UI | AC-2 可点 |

### Wave 5 — 前端完页 + 企业演示

| # | 任务 | 完成标准 |
|---|------|----------|
| 5.1 | 文档预览页 | 点击文件名可预览 |
| 5.2 | 对话页 + 引用卡片 + 跳转预览 | AC-3 |
| 5.3 | 账号设置（改密） | 改密后重新登录 |
| 5.4 | 成员管理 + 组织设置 | AC-5、6、9 | ✅ |
| 5.5 | 企业答辩脚本走通 | 双账号 15 分钟 demo |

### Wave 6 — 部署与答辩包

| # | 任务 | 完成标准 | 状态 |
|---|------|----------|------|
| 6.1 | 本机 **HTTP 内网** prod 部署（`enterprise-wave-plan.md` 替代原 HTTPS） | `docker-compose.prod.yml` · web :80 · smoke exit 0 · 答辩演示库对话引用 | ✅ 2026-07-07 |
| 6.2 | SA-1～3 + 核心 pytest 全绿 | CI job `W6-2 SA-1~3 gate` · pytest **273** | ✅ 2026-07-07 |
| 6.3 | 答辩 PPT 数据流 + 安全七层 | `presentation-defense-w6-3.html` · `DEFENSE_SCRIPT_2MIN.md` 可脱稿 2min | ✅ 2026-07-07 |
| 6.4 | 驾驶舱 HTML 进度同步 | `cockpit.html` 与上表 + 双轨清单一致 | ✅ 2026-07-07 |

**Wave 6 回归参考（不阻塞关单）**：`ENTERPRISE_DEMO_SCRIPT.md` §8 ① **15min 计时全稿** — 须用户亲手跑一行后再改 ✅。deferred backlog：Plan-10 · D-5 · D-6。

### P1 Wave（第一版后，2027 答辩前可选）

- 审计日志页、UI i18n、混合检索、多 thread、限流、帮助页

---

## 6. 风险与缓解

| 风险 | 缓解 |
|------|------|
| 9 页 + 不会 React | Wave 4～5 专留时间；AI 写组件；用户只验收 |
| 2G OOM | 严格 pgvector 单库；监控内存 |
| 50 元 API | 限流（P1 必做；开发期手动小心） |
| 无 demo PDF | Wave 3 前完成手册 PDF + golden_qa |

---

## 7. 成功指标（答辩当天）

- [ ] 15 分钟完整 demo：企业注册 → 上传 → Dashboard 有数 → 预览 → 对话引用 → member 权限拒绝
- [ ] AC-1～10 + SA-1～3 全过
- [ ] 9 页面侧栏均可导航，无 404 占位死链

---

## 8. 确认签字

- [x] 我同意 **9 页进 P0**，不因 MVP 砍页面
- [x] 我同意架构调整为 **pgvector + BackgroundTasks**
- [x] UI 风格 **前端 Wave 再定**，但页面数量不减

**确认人**：用户　**日期**：2026-07-03
