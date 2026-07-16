# 睿阁 · 下一阶段迭代计划

> 生成于 2026-07-17 · 综合评审意见 + 自补项

---

## 总览

| 优先级 | 阶段 | 主题 | 预估会话数 |
|--------|------|------|-----------|
| 🔴 P0 | Phase 1 | Golden QA 修复 + pytest 全绿 | 2 |
| 🔴 P0 | Phase 2 | CI/CD（GitHub Actions）恢复 | 1 |
| 🟡 P1 | Phase 3 | 日志聚合（Grafana/Loki） | 2 |
| 🟡 P1 | Phase 4 | 性能压测（Locust） | 2 |
| 🟢 P2 | Phase 5 | Celery 异步任务队列 | 4 |
| 🟢 P2 | Phase 6 | OpenTelemetry 全链路追踪 | 3 |
| 🔵 P3 | Phase 7 | 企业级增强功能 | 4-6 |
| ⚪ 评估 | Phase 8 | 知识图谱可行性评估 | 1 |

---

## Phase 1: Golden QA 修复 + pytest 全绿

**目标：** 668 个测试全部通过，50 题 Golden QA Hit@3 达到 48+ PASS。

### 子步骤

   - **1.1 DB 连接池泄漏修复**
     - `conftest.py` 的 `dispose_db_engine` fixture 测试完后释放连接
     - 检查 `SessionLocal` 在所有路径上是否都正确 `close`
   - **1.2 Ingestion 路径手动测试通过**
     - 用 API 上传 golden_handbook.md → 轮询状态 → 确认 completed
     - 如果失败，dump ingestion 管道中的完整错误信息
     - 修复 parser/tokenizer 层面的问题（已修：ChatMessage 映射，_INGESTION_SEMAPHORE 移除）
   - **1.3 Embedding mock 确认生效**
     - 确认 `mock_embedding_for_tests` 在 pytest 中 autouse=True
     - 确认 `try_embed_texts` 走 mock 路径（返回零向量）
   - **1.4 50 题 Golden QA 通过**
     - `pytest tests/test_retrieval_golden.py -v --tb=line`
     - 预期 48 PASS / 2 SKIP（PDF 依赖 OCR，可能需 pdfminer）
   - **1.5 全量 pytest 运行**
     - `pytest tests/ --ignore=tests/test_agent_golden.py -v --tb=line`
     - 优先修所有 ERROR → 再修 FAIL
     - 最后 668 应全部 PASS（预期 3-5 个可接受的 FAIL，如 422 vs 201 这类请求体差异）

---

## Phase 2: CI/CD 恢复

**目标：** 每次 push 到 master，GitHub Actions 自动运行全量测试。

### 子步骤

   - **2.1 Workflow 修复**
     - 根因：`pgvector/pgvector:pg16` 镜像拉取失败
     - 改用 `services.postgres.image: pgvector/pgvector:pg16` 原生 GitHub Actions service 方式
     - 或用 Docker Compose 的 `--build` 替代 service container
   - **2.2 Python 依赖安装**
     - workflow 中 `pip install pytest pytest-asyncio httpx python-docx openpyxl`
   - **2.3 测试执行**
     - `pytest tests/ --ignore=tests/test_agent_golden.py -v --tb=line`
     - 结果输出到 PR comment
   - **2.4 状态 badge**
     - README 添加 `![tests](https://github.com/.../actions/workflows/test.yml/badge.svg)`

---

## Phase 3: 日志聚合（Grafana/Loki）

**目标：** 所有日志统一接入，支持按 `trace_id`/`user_id`/`error` 快速检索。

### 子步骤

   - **3.1 Loki + Grafana 容器**
     - `docker-compose.monitoring.yml` 添加 loki + grafana
   - **3.2 Python logging → Loki**
     - 用 `logging-loki` handler 将日志推送到 Loki
     - 每个 log entry 带 `trace_id`、`user_id`、`duration_ms`
   - **3.3 Grafana dashboard**
     - 驾驶舱面板：最近错误、API 延迟 P50/P95/P99、每分钟请求数
   - **3.4 告警规则**
     - 5xx 率 > 1%、P95 延迟 > 5s、ingestion 失败率 > 5%

---

## Phase 4: 性能压测（Locust）

**目标：** 量化系统性能指标，找到瓶颈。

### 子步骤

   - **4.1 Locust 测试脚本**
     - `locustfile.py`：覆盖登录 → 创建KB → 上传文档 → 搜索 → 对话 五个典型场景
   - **4.2 基线测试**
     - 1 用户 → 10 用户 → 50 用户 阶梯加压
     - 记录每个场景 P50/P95/P99 延迟
   - **4.3 瓶颈分析**
     - 慢查询 SQL log 分析
     - pgvector 索引是否命中
     - LLM API 调用时间
   - **4.4 优化**
     - 根据瓶颈位置加索引/N+1 优化/缓存（如需要可引入 Redis）
   - **4.5 对标报告**
     - 输出 `docs/benchmark-report.md`，含 QPS、延迟分布、资源使用

---

## Phase 5: Celery 异步任务队列

**目标：** 文档 ingestion 从 BackgroundTasks 迁移到 Celery，支持失败重试、任务追踪。

### 子步骤

   - **5.1 基础设施**
     - `celery worker` 容器 + `redis` 容器（broker + backend）
     - `docker-compose.yml` 添加两种新服务
   - **5.2 Task 定义**
     - `backend/app/services/ingestion/celery_tasks.py`
     - `ingest_document(doc_id)` 替代 `BackgroundTasks.add_task`
   - **5.3 上传链路改造**
     - `upload.py` 不再 `add_task`，改发 `ingest_document.delay(doc_id)`
     - HTTP 响应立即返回 `{"status": "queued", "task_id": "..."}`
   - **5.4 前端支持**
     - 文档列表页显示 task 状态（queued / processing / completed / failed）
     - 可选：Polling API（`GET /tasks/{id}`）查询状态
   - **5.5 失败重试**
     - Celery `autoretry_for=(Exception,), max_retries=3`
   - **5.6 当前 BackgroundTasks 保留**
     - 简单文档（<1MB）仍可用 BackgroundTasks（无额外延迟）
     - 大文档（>10MB）走 Celery
   - **5.7 站内通知**
     - Ingestion 完成后，创建站内通知（`notifications` 表 + 前端红点/列表）
     - 失败时通知 + 重试入口

---

## Phase 6: OpenTelemetry 全链路追踪

**目标：** 端到端追踪每个 RAG 请求，精确到每个子环节的耗时。

### 子步骤

   - **6.1 Jaeger 容器**
     - `docker-compose.monitoring.yml` 添加 jaeger
   - **6.2 OpenTelemetry SDK 集成**
     - FastAPI middleware：自动追踪每个请求
     - httpx client instrumentation：追踪 LLM/Embedding API 调用
     - SQLAlchemy instrumentation：追踪每条 SQL 查询
   - **6.3 自定义 Span**
     - RAG 检索 pipeline 的每个环节创建子 span（向量检索→FTS→RRF→重排序→LLM 生成）
     - 带上关键属性：`kb_id`、`chunk_count`、`token_count`、`latency_ms`
   - **6.4 Jaeger dashboard**
     - 按服务/操作/错误过滤
     - 识别慢 trace
   - **6.5 限流可视化**
     - 在 Grafana 增加 rate_limit_hits 面板
     - 跟踪哪些用户/端点频繁超限
     - 支持导出限流事件报表

---

## Phase 7: 企业级增强功能

**目标：** 补充企业客户刚性需求功能。

### 子步骤

   - **7.1 文档版本管理**
     - 同名字文档上传时不做覆盖，创建新版本
     - `document_versions` 表：存 diff / 完整快照
     - UI：文档详情页增加版本切换/回滚入口
     - 审计日志记录版本变更
   - **7.2 批处理操作**
     - 多选文档 → 批量删除 / 批量重新 ingestion / 批量移动
     - 前端：checkbox 列 + 顶栏操作按钮
     - 后端：POST`/batch/delete`、`/batch/re-ingest`
   - **7.3 国际化 i18n**
     - 前端接入 `react-intl` 或 `i18next`
     - 提取中文文案到 `zh.json`
     - 制作英文文案 `en.json`
     - 设置页增加语言切换
   - **7.4 自定义角色权限**
     - 在 admin/member 基础上增加 custom role
     - 按资料库粒度设置：read / write / admin / deny
     - 前端：角色管理页面
   - **7.5 Webhook 集成**
     - 文档完成 ingestion 后触发 webhook
     - 支持自定义 URL + 签名密钥
     - 管理页配置 webhook

---

## Phase 8: 知识图谱可行性评估

**目标：** 评估 RAG + KG 融合的必要性和实施方案。

### 子步骤

   - **8.1 业务场景对齐**
     - 盘点当前用户提问中「多跳推理」占比（如：A部门和B部门哪个离职率高）
     - 如果此类问题 < 10%，KG 投入产出比偏低
   - **8.2 技术选型**
     - Neo4j（成熟/社区大/资源重）vs NebulaGraph（国产/轻量/文档少）
     - 如果是论证阶段，推荐 **Neo4j**（有 Docker 镜像，学习成本最低）
   - **8.3 概念验证**
     - 小规模构建：选取 1-2 个资料库，抽取实体 + 关系
     - 验证检索质量提升是否 > 5%
   - **8.4 决策**

---

## 交接提示词

> 当你首次被分派到本项目时，请依次执行以下操作：
>
> 1. 阅读 `AGENTS.md` 了解项目北极星和协作约束
> 2. 阅读 `docs/PRD.md`、`docs/TECH.md` 了解产品需求和技术方案
> 3. **先不要开始新功能开发**，而是：
>    - 检查 Docker 三容器是否健康：`docker ps`
>    - 运行 `pytest tests/ --ignore=tests/test_agent_golden.py -v --tb=line` 看当前测试状态
>    - 如果测试大面积失败，优先按 `docs/test-report.md` 中的已知问题修复
>    - 特别关注 `test_retrieval_golden.py`（50 题 Golden QA）和 `test_smoke.py`
> 4. 修复完成后，执行 **Phase 1→2→3→4→5→6→7→8** 的顺序迭代
> 5. 每次改动前阅读相关 plan 文档再动手
> 6. 改动后更新 `docs/test-report.md`
> 7. 不要随意修改 `.env`、`docker-compose.yml`、`AGENTS.md`

---

## 关键文件索引

| 文件 | 说明 |
|------|------|
| `AGENTS.md` | AI 协作规则（必读） |
| `docs/PRD.md` | 产品需求文档 |
| `docs/TECH.md` | 技术方案 |
| `docs/DESIGN.md` | 设计系统 |
| `docs/test-report.md` | 当前测试状态 |
| `docs/next-phase-plan.md` | 本计划（迭代路线图） |
| `backend/tests/fixtures/golden_qa.json` | 50 题 Golden QA 数据 |
| `backend/tests/golden_qa_loader.py` | QA 数据加载器 |
| `backend/app/services/ingestion/pipeline.py` | Ingestion 管道 |
| `backend/tests/conftest.py` | pytest 共享 fixture |

## 当前遗留问题（已知）

| 问题 | 状态 |
|------|------|
| Golden QA 50 题 ingestion 不通 | 等待 embedding mock 生效后重试 |
| pytest 异步配置 | asyncio_mode=auto 已设置 ✅ |
| ChatMessage SQLAlchemy 映射 | ✅ 已修 |
| _INGESTION_SEMAPHORE 导致测试挂起 | ✅ 已移除 |
| GitHub Actions Docker daemon | ❌ 未修 → Phase 2 |
| agent_golden.py 数据缺失 | ❌ 需 Agent 场景 QA 数据 |
