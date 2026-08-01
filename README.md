# 睿阁（Ruige）— 企业级知识库 RAG 平台

> **从文档到答案，可溯源、可审计、可运营。**  
> 不是 ChatPDF 的平替，而是企业知识管理的基础设施。

```
文档 → 结构入库 → Hybrid 检索 → 溯源对话 → 审计闭环
```

---

## 为什么做睿阁

企业知识管理面临一个结构性矛盾：**文档越管越多，找到答案越来越难。**

传统方案各走极端：
- **NAS / Wiki** — 存得住，找不着。全文检索靠关键词，同义/近义查询全部漏掉
- **ChatPDF / 通用 RAG** — 问得出，不可信。黑盒回答无溯源，企业无法审计"AI 说了什么、依据是什么"
- **纯向量检索** — 语义好，精度差。精确匹配（合同编号、金额、人名）一塌糊涂

**睿阁的选择**：不做最强 AI，做**最可用的企业 RAG**。

| 能力 | 说明 |
|------|------|
| 多格式入库 | PDF / DOCX / PPTX / XLSX / Markdown / TXT（扫描 PDF 可走 OCR）→ 结构优先切片 → 向量 + FTS 混合索引 |
| 溯源对话 | 每个回答附带文档名、位置、原文片段，支持逐条引用查验 |
| 企业权限 | Owner / Admin / Member 三级 + 部门树 + 资料库级别隔离 |
| 审计合规 | 50+ 种操作审计事件，Admin 可查询 / 导出 |
| 可部署 | Docker Compose 一键部署，内网 HTTP，非 root 容器，健康检查三板斧 |
| 可观测 | Prometheus 指标 + OpenTelemetry 追踪 + 熔断器 |

---

## 架构总览

```
┌─────────────────────────────────────────────────────────────┐
│                        浏览器 (React SPA)                    │
│  登录 · 概览 · 资料库 · 对话 · 预览 · 管理 · 组织          │
└─────────────────────────┬───────────────────────────────────┘
                          │ HTTP (REST + SSE)
┌─────────────────────────▼───────────────────────────────────┐
│                    FastAPI (Python 3.11)                     │
│  路由层 → 业务层 → 数据层                                   │
│  JWT 认证 · RBAC 权限 · 限流 · 审计日志 · 熔断器           │
└────┬──────────────┬──────────────┬──────────────────────────┘
     │              │              │
┌────▼──────┐ ┌────▼──────┐ ┌────▼──────────────────┐
│ PostgreSQL │ │   Redis   │ │  文件存储 (Docker volume)│
│ + pgvector │ │ 限流/队列 │ │  PDF · Office · MD · TXT │
│ + FTS      │ │           │ │                        │
└────────────┘ └───────────┘ └────────────────────────┘
     │
┌────▼─────────────────────────────────────────────────────────┐
│  Celery Worker (异步入库)                                    │
│  解析 → 切片 → 嵌入 → 入库 → Webhook 通知                   │
└──────────────────────────────────────────────────────────────┘
```

**三层分离**：
- **API 进程**：处理实时对话、搜索、管理操作，无阻塞任务
- **Worker 进程**：消费入库队列，大文件解析 / OCR / 嵌入异步执行
- **DB + 向量**：PostgreSQL/pgvector 统一存储元数据、全文索引、向量嵌入

---

## 核心设计决策

### 1. 切片：结构优先，而非固定窗口

固定长度滑动窗口是 RAG 最常见的坑——打断段落、混合主题、丢失上下文。

```
朴素切片 (500 字滑动):      结构化切片 (heading_path 感知):
┌──────────────────┐        ┌──────────────────┐
│ 第一章 考勤制度    │        │ 第一章 考勤制度    │ ← 完整段落
│ 1.1 工作时间      │        │ 1.1 工作时间      │
│ 1.2 迟到处理 ...  │        │ 1.2 迟到处理      │
├──────────────────┤        ├──────────────────┤
│ 1.2 迟到处理(续)  │ ← 打断  │ 第二章 薪酬福利    │ ← 完整段落
│ 第二章 薪酬福利    │        │ 2.1 薪资结构      │
└──────────────────┘        └──────────────────┘
```

每个 chunk 携带 `heading_path` 元数据链（如 `员工手册>第一章 考勤>1.2 迟到`），检索时可精准定位章节路径，前端渲染时展开层级面包屑。

### 2. 混合检索：向量 + FTS，RRF 融合

| 场景 | 向量检索 | 全文检索 | 融合后 |
|------|---------|---------|--------|
| 同义查询（"薪资" → "薪酬福利"） | ✅ | ❌ | ✅ |
| 精确匹配（合同编号 "CT-2024-001"） | ❌ | ✅ | ✅ |
| 中英混合 | ✅ | ⚠️ | ✅ |
| 数字/金额/日期 | ⚠️ | ✅ | ✅ |

权重调优：`w_v=1.0, w_f=1.2`（全文略高，因为企业文档中精确匹配场景更关键）。

### 3. 嵌入选型：BGE-small-zh，不要 GPU

做过完整消融：

**嵌入选型消融**（golden_qa 109 题）：

| 模型 | 维度 | 推理方式 | Hit@3 | P50 |
|------|------|----------|-------|-----|
| 通义 text-embedding-v3 | 1536 | API（阿里云） | 86% | 1,817ms |
| **BGE-small-zh** | **512** | **ONNX CPU** | **86%** | **395ms** |
| BGE-large-zh | 1024 | PyTorch CPU | 86% | 4,897ms |

三者检索质量完全一致。BGE-small-zh 比通义快 4.6 倍、零外部依赖、无需 GPU。

**检索链路消融**（golden_qa 89 题非拒答，BGE-small-zh）：

| 配置 | Hit@1 | Hit@3 | Hit@5 | MRR | 耗时 |
|------|-------|-------|-------|-----|------|
| ① Baseline（纯向量） | 0.888 | 1.000 | 1.000 | 0.944 | 15s |
| ② +FTS（向量+FTS 拼接） | 0.888 | 1.000 | 1.000 | 0.944 | 14s |
| ③ +RRF（RRF 融合） | 0.888 | 1.000 | 1.000 | 0.944 | 15s |
| ④ +Rerank（always） | **0.921** | **1.000** | **1.000** | **0.961** | 50s |
| ⑤ +Multi-turn | N/A¹ | N/A¹ | N/A¹ | N/A¹ | — |
| ⑥ Full（生产配置）² | ~0.915 | ~1.000 | ~1.000 | ~0.958 | ~20s |

> ¹ 多轮改写需多轮对话数据集验证，未在单轮 golden_qa 上评测。
> ² Full = RRF + 条件 Rerank（仅在排序歧义时触发），延迟为条件均值。

**边际提升分析**：

| 优化步骤 | 边际 Hit@1 ↑ | Hit@3 | 延迟代价 |
|---------|-------------|-------|---------|
| Baseline → +FTS | 持平 | 持平 | ✅ 几乎免费 |
| +FTS → +RRF | 持平 | 持平 | ✅ 几乎免费 |
| +RRF → +Rerank | **+3.3pp** | 持平 | ⚠ +35ms/query（always）→ +5ms（conditional） |

**结论**：golden_qa 在当前 BGE 嵌入上 Hit@3 已饱和。Rerank 是唯一有可测收益的优化（Hit@1 +3.3pp），生产上以条件模式控制延迟增量。更显著的对比预计在 enterprise_qa（含 6 份跨领域文档）上出现。

### 4. LLM 选型：DeepSeek + 通义双备

- **主链路**：DeepSeek Chat（性价比高，中文能力强）
- **备用**：阿里云通义千问（国内合规，API 兼容）
- **Key 仅服务端**：前端不接触任何 LLM / Embedding 密钥
- **熔断器**：连续失败达到阈值（默认 5 次）后开路，并按 provider 链切换备用

### 5. 多轮对话：Query 改写 + 引用对齐

```
用户："v3.0 支持哪些格式？"
系统："PDF、DOCX、Markdown、TXT [片段2]。"
用户："那 v2.4 呢？"
  → contextualize_query("那 v2.4 呢？", [历史]) → "v2.4 版本支持哪些文档格式？"
  → 检索 → 回答
```

引用对齐：流式生成时 LLM 输出 `[片段N]`，终态按正文实际出现的标记裁剪。不会出现「引用了片段5但只给了3个片段」的幻觉。

---

## 企业级能力

### 权限模型

```
账号类型 → 个人版 / 企业版
企业版角色 → Company Admin（全组织） / Unit Admin（本部门） / Member（只读+对话）
资料库隔离 → kb_id 注入所有查询，Member 写操作统一 403
部门树     → grant 传播：父部门库 → 子部门可见
```

### 安全架构

| 层 | 措施 |
|----|------|
| 传输 | 内网 HTTP（TLS 由客户反代负责）|
| 认证 | JWT 24h + 密码强度 ≥8+大写+小写+数字+特殊字符 |
| 限流 | 登录 3/5min · Chat 30/min · Upload 10/min（Redis 或 Memory 后端）|
| 输入 | magic 字节校验（防伪装上传）+ 安全敏感词过滤 |
| 输出 | PII 脱敏（手机/身份证/邮箱）· 拒绝服务自验证 |
| 审计 | 50+ 操作事件 · Admin 列表/筛选/CSV 导出 · 永久留存（NW-51） |

### 运维可观测

```
/health          → {status, database, redis, degradation}
/health/detailed → {database, redis, embed, ocr, latency, disk, chat}
/health/ready    → {status, database}   (K8s readiness probe)
/metrics         → 手写 Prometheus 指标：延迟分位、拒答计数、积压队列
```

熔断器（6 个独立熔断器）：`deepseek_llm` / `tongyi_llm` / `bge_embed` / `bge_rerank` / `tongyi_embed` / `tongyi_rerank`

---

## 性能基准

> 注意：以下延迟数据来自本机 Docker 栈实测（2026-07-22），一次采样，非长期统计。
> Hit@3 分数除延迟列标注外均来自 CI 环境（mock 嵌入 + mock LLM），不直接代表生产表现。

### 检索延迟（一次采样）

| 指标 | P50 | P95 | SLO |
|------|-----|-----|-----|
| 检索端到端 | 930ms | 1,500ms | ≤ 2,500ms |
| 对话 TTFT (thorough) | 956ms | 982ms | ≤ 5,000ms |

### 检索质量（CI 门禁数据，非生产）

| 测试集 | 题数 | Hit@3 | 嵌入方式 | 说明 |
|--------|------|-------|---------|------|
| Golden QA（中文企业，L1-L4 分层） | 12 | 12/12 ✅ | mock | CI 门禁：R5-2 golden gate，修改检索/入库必过 |
| Enterprise QA（异质企业文档） | 108 | ~25%/54% | mock | 6 份异构企业文档；54% 为修复 test 断言后的诚实基线，25% 为修复前 |
| CRAG English（英文 Wikipedia） | 100 | 26% | 真实 bge-small-en | 外部英文评测集，仅作参考 |

建议：生产验收须用真实嵌入 + 真实 LLM 抽测，不能只看 CI 绿。

### 代码与质量

| 指标 | 值 |
|------|----|
| 后端业务 Python | ≈ 3.4 万行（不含 tests / venv / 本地模型） |
| 前端源码 | ≈ 3.0 万行（TS/TSX/CSS，不含测试） |
| 测试 | ≈ 250 个用例 · 151 个 `test_*.py` 文件（以 `pytest --collect-only` 为准） |
| CI 门禁 | Ruff + pytest A 层 + Hit@3 Golden Gate（**12** 题） |
| 混沌测试 | 容器断连脚本 (PG/Redis/Celery 停服验证) |

---

## 快速开始

> 只要 API 本机联调：`docker compose up -d` → `http://localhost:8000/health`。  
> **要打开产品九页**：用生产覆盖层（含 nginx `web`），入口是 **80**，不是 8000。

```bash
# 1. 克隆
git clone https://github.com/1y4w1s/rag-knowledge-platform.git
cd rag-knowledge-platform

# 2. 配置环境变量（创建 .env；数据库等其余变量 compose 已提供默认值）
cat > .env <<'EOF'
JWT_SECRET=replace-with-a-long-random-string
CHAT_PROVIDER=deepseek
DEEPSEEK_API_KEY=sk-xxx            # 对话主链路（必填之一）
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-chat
TONGYI_API_KEY=                    # 备用 LLM + 嵌入（可选）
EMBEDDING_PROVIDER=tongyi
EMBEDDING_MODEL=text-embedding-v2
EOF

# 3. 启动（API + Worker + 前端 web）
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build

# 4. 验证
curl http://localhost:8000/health
# 期望 database 为 ok（字段以实际响应为准）

# 5. 打开前端
# 浏览器访问 http://localhost/   （web:80 → 静态页 + /api 反代）
```

首次构建视机器而定（常需数分钟）。监控扩展：`docker compose -f docker-compose.yml -f docker-compose.monitoring.yml up -d`。

---

## 技术取舍

原则不是「功能永远关着」，而是：**默认走低成本主路径；用可观测信号决定何时加贵一步**（评测门禁不绿则不加）。

### 基础设施（偏硬约束）

| 取舍 | 现状 | 何时重新审视 |
|------|------|----------------|
| 向量索引 | ivfflat | chunk 规模到数万级、召回明显掉点 → 评估 HNSW |
| 缓存 | LRU TTL≈3600s | 文档高频更新导致「改完仍旧答案」→ 主动失效或缩短 TTL |
| TLS | 内网 HTTP | 公网暴露 → 客户侧反代 HTTPS（本仓不做公网 TLS） |
| 会话 | JWT 24h + localStorage | 安全审计强制 Cookie/CSRF 时再开（Research 已有，Implement 触发制） |

### 检索增强（默认关开关 ≠ 放弃效果）

A2 真路径评测表明：对企业异构题集 **全程默认开 BGE rerank** 会打散大量本已在 Top-3 的题（RRF Hit@3 高、开 rerank 后跌）。因此默认 `RERANK_ENABLED=false`，但正确方向是 **条件介入**，而不是永久不用：

| 能力 | 默认 | 介入思路（控成本） | 验收门槛 |
|------|------|-------------------|----------|
| **Rerank** | 关 | 仅在「值得精排」时开：如 thorough 模式、Top 分差过小、诊断为 RANK_4_20（针在 4～20 名）、短列表歧义高；fast 路径可继续纯 RRF | 同池诊断：`diagnose_enterprise_rank.py --rerank`；Golden 12/12 不掉；企业题 Hit@3 不劣于关 |
| **多查询 / 改写** | `query_rewrite_enabled=False` | 多轮已有 contextualize；单轮仅在 miss_pool / 短问指代不清时扩展，避免每问×N 倍检索 | 延迟预算内；Hit@3 有增益或持平 |
| **OCR** | 能力已落地（Format-F4）；镜像是否带 Paddle/poppler 看部署 | 扫描件 / 无文字层 PDF 才走 OCR；文字层 PDF 走版式降噪，不付 OCR 成本 | `/health/detailed.ocr` 可读；失败文案可区分「未安装 / 未启用 / 缺 poppler」 |

一句话：**贵能力按「题型 × 模式 × 分数信号」触发；用评测证明「加钱买到了排序」，再扩默认面。**

---

## 技术栈

| 层 | 技术 | 选型理由 |
|----|------|---------|
| 后端框架 | FastAPI (Python 3.11) | 异步原生 · Pydantic 集成 · 自动 OpenAPI |
| 数据库 | PostgreSQL 16 + pgvector | 关系+向量+全文索引同实例，零 ETL |
| 异步任务 | Celery + Redis | 成熟稳定，入库队列不丢消息 |
| 向量嵌入 | BGE-small-zh (ONNX CPU) | 零外部依赖 · 无需 GPU · 延迟 395ms P50 |
| LLM | DeepSeek + 通义千问 | 性价比高 · 双备熔断 |
| 前端 | React + Vite + Tailwind | 轻量 · 设计 token 可控 · 无全局状态库 |
| 部署 | Docker Compose | 单机足够 · 非 root 容器 · 健康检查 |

---

## 项目结构

```
backend/
├── app/
│   ├── api/            # 路由层（≤200 行/文件）
│   ├── services/       # 业务层（认证·入库·检索·对话·审计·组织）
│   ├── models/         # SQLAlchemy ORM 模型
│   ├── schemas/        # Pydantic 请求/响应
│   └── core/           # 配置·DB·Redis·安全·熔断·可观测
└── tests/              # pytest（A 层门禁 + golden / 场景拆分）

frontend/
└── src/
    ├── pages/          # 页面组件
    ├── components/     # 业务组件（按域分目录）
    └── lib/            # API 客户端·Hooks·Context
```

---

## 评测与质量门禁

```
Golden 门禁（12 题，CI Hit@3 必须 12/12）
    → 企业 / CRAG 等更大题集：诊断与回归，不作 PR 硬红灯（除非另开 job）
    → 生产抽测: 真实嵌入 + 真实 LLM
    → 👎 人工审题: 导出候选 → 人工判断 → 可手工扩 golden（禁止脚本直写门禁）
```

```bash
# 检索向评测入口
python scripts/run_benchmark.py --dataset all --mode retrieval
```

---

## 许可证

本项目采用 MIT License。

---

*从文档到答案，每一行都可追溯。*
