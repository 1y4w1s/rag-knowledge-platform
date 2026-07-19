# Plan-RAG · RAG 持续优化路线图

> **状态**：🟡 首版（2026-07-05）· 与 WS-2-2 文案/搜索分工同步 · **R6 backlog**（2026-07-09 外部调研落盘 §12）  
> **依据**：`docs/TECH.md` TECH-4 · `docs/PRD.md` P0/P1 · `kb-pages-polish-plan.md` Plan-10  
> **原则**：用户**不直接管理向量索引**；「优化 RAG」= 优化 **好找 → 切好 → 检准 → 答对 → 可测**

---

## 0. 产品口径（答辩 / PRD 统一说法）

| 用户说的 | 实际含义 | 用户操作入口 |
|----------|----------|--------------|
| 「管理资料库」 | 组织文档容器 | 列表：新建/改名/删库 |
| 「上传文档」 | 触发切片 + 嵌入 + 写入 pgvector | 详情：上传 / 失败重试 |
| 「搜某个文档」 | **发现层**，不是改索引 | 见 §1 三层搜索 |
| 「答得准不准」 | **检索 + 生成质量** | 对话 + golden_qa 评测 |

**禁止对用户说的**：「请管理 RAG 索引」「向量库设置」——索引是系统副作用，不是独立管理页。

---

## 1. 发现层 · 三层搜索（与 WS-2-2 / Plan-10 对齐）

> **这节定什么**：列表页、详情页、全局搜各管哪一层；避免一个搜索框包打天下。

| 层 | 页面 | 搜什么 | 现状 | 计划 |
|----|------|--------|------|------|
| **L1 找库** | `/knowledge-bases` | 资料库**名称 / 描述** | ✅ Plan 1.7 前端 `?q=` | WS-2-2 定稿 scope；**不搜文档名** |
| **L2 找库内文档** | `/knowledge-bases/:id` | **文件名**（子串） | ✅ Plan 1.7 + `?q=` | WS-2-4 验收；可与 `?status=` 叠加 |
| **L3 跨库 / 正文** | Dashboard 内容区或 `/search` | 文件名跨库 / PDF 正文 | ✅ R1-1 文件名 · **R1-2 正文** | **Plan-RAG R1**（原 Plan-10） |

**MVP 权宜之计**（R1 未做前）：列表搜库名 → 进库 → 详情搜文件名；或进库对话（记内容不记得文件名）。

**工作区约束（W1 后）**：L3 API 须带 `workspace=personal|org_id`；结果仅当前空间，与 WS-2-1 L3 一致。

---

## 2. 波次路线图

| 波次 | 主题 | 交付什么 | 依赖 | 触发条件 |
|------|------|----------|------|----------|
| **R0** | 用户可见 IA | 列表副文案去「RAG 索引」；三层搜索写进 PRD | WS-2-2 ✅ | workspace Implement 前 |
| **R1** | 发现层增强 | 跨库文件名 · 全文 · 分页 | W1 workspace · WS-2-2 ✅ | 库 ≥5 或 demo 反复「找不到在哪个库」 |
| **R2** | 索引管道 | 切片/嵌入/去重/失败重试体验 | TECH-4 P0 已有 | golden 某类题持续 miss |
| **R3** | 检索质量 | hybrid 调参 · rerank ·（可选）query 改写 | R2 基线稳定 | Hit@3 低于目标 |
| **R4** | 生成与引用 | Prompt · 无依据拒答 · 引用跳转 | R3 | 胡编 / 引用错位 demo 翻车 |
| **R5** | 评测闭环 | 扩展 golden_qa · CI Hit@3 · demo 脚本对齐 | R2～R4 任一项改动 | 每次动 RAG 核心必跑 |
| **R6** | 外部调研 backlog | B 站 RAG 踩坑课 + EagleRAG 对照 · **Research 优先** | R5 基线稳定 · **G2 前端关单后** | golden/生产 miss 或 G3 排期 |

**与 workspace 顺序**：**W1 内核 → WS-2-1/2-2 Implement →** 再排 R1；R2～R5 可与 W2～W4 交错，但 **改检索/切片须过 R5**。R6 **默认只 Research/设计**，Implement 须单开 I 窗 + 触发条件满足。

---

## 3. R0 · 文案与 IA（Implement 小改）

| ID | 做什么 | 文件 | 验收 |
|----|--------|------|------|
| R0-1 | 列表副文案 | `KnowledgeBasesPage.tsx` | 改为「整理文档集合，供 AI 带引用回答」（或 PRD 定稿句） |
| R0-2 | 搜索 placeholder 不变 | 「搜索资料库…」 | 不改为「搜索文档」 |
| R0-3 | PRD 同步 | `workspace-prd-ws2.md` §2.6 | WS-2-2 写清 L1 范围 + 链到本文 |

---

## 4. R1 · 发现层（承接 kb-pages-polish Plan-10）

| ID | 项 | 做什么 | API / UI | 优先级 |
|----|-----|--------|----------|--------|
| **R1-1** | 跨库文件名 ✅ | `GET /search/documents?q=&workspace=` | 结果：文件名 + 所属库 + 跳转库详情 `?q=`；入口：**Dashboard 内容区**「找文档」；**非** AppShell 顶栏 | **P1 首选** |
| **R1-2** | 库内/跨库正文 ✅ | tsvector + chunk 子串；高亮片段 | 与 R1-1 同入口 Tab「文件名 / 正文」；`?mode=content` | 记得内容不记得文件名 |
| **R1-3** | 文档列表分页 ✅ | `limit/offset` 或 cursor + 虚拟滚动 | 详情表 | 单库 **>50** 篇卡顿 |
| **R1-4** | 高级筛选 ✅ | 格式、日期、多 status | 详情 toolbar | R1-2 之后 |

**UX 硬约束**（与 Plan-1.7 一致）：搜索框在**内容区**、紧挨被操作的列表；可选 ⌘K **唤起面板**，不占 52px 顶栏。

**不做**：支付 · OCR · KB 级 ACL · Agent 联网（PRD §14）。

### R1-4 · 高级筛选 ✅（2026-07-06）

| 项 | 内容 |
|----|------|
| API | `GET .../documents?file_type=&status=&uploaded_from=&uploaded_to=` · 与 `limit/offset` 联动 · `status=processing` 展开 queued+processing |
| UI | 详情 toolbar「筛选」面板 · PDF/DOCX · 整理中/失败/已完成 · 上传日期起止 · URL 同步 |
| 兼容 | Dashboard `?status=processing\|failed` 仍可用 · 筛选空态与清除 |
| 测试 | `test_document_list_filters.py` 7 用例 · 全量 pytest **221** passed · `npm run build` 绿 |

---

## 5. R2 · 索引管道（入库质量）

| ID | 项 | 做什么 | 参考 |
|----|-----|--------|------|
| **R2-1** | 切片回归 ✅ | 调 chunk 长/overlap/跨页合并 | TECH-4 §4.3；golden 驱动 |
| **R2-2** | 结构增强 P1 ✅ | 表格单独 chunk · Parent-Child | TECH-4 §4.3.6 |
| **R2-3** | 内容去重 ✅ | 同库 SHA-256 指纹 409 | Plan-3E-7 · EW-D1 |
| **R2-4** | 重嵌入策略 ✅ | 换 embedding 模型 → 后台全库 re-embed 任务 | TECH-4 §4.4 锁模型 |
| **R2-5** | 存储一致 ✅ | 删库/删文档清盘 | Plan-3E-4 · EW-A1 |

### R2-1 · 切片回归 ✅（2026-07-06）

| 项 | 内容 |
|----|------|
| 范围 | **不调参**（golden Hit@3 已 10/10）；锁 TECH-4.3.2 默认 1000/80/150 + 跨页合并 |
| 测试 | `test_chunker.py` 8 用例：max_chars 句号切分 · min_chars 同节合并 · overlap ≤150 · 跨页/连字符 |
| 研究 | `docs/tasks/rag-r2-research.md` H1/H2 ✅ |
| 验收 | golden 10/10 · 全量 pytest 绿 · **不动**顶栏/支付/OCR |

### R2-2 · 表格 + Parent-Child ✅（2026-07-06）

| 项 | 内容 |
|----|------|
| 范围 | MD pipe 表格 + DOCX 表格独立 chunk；一节 2+ 子块时建 parent（不入索引），检索命中 child 后 LLM 用 parent 全文 |
| 库 | migration `014`：`parent_chunk_id` · `chunk_kind` text/table/parent |
| 代码 | `table_detection.py` · `chunker.py` · `parser.py` · `pipeline.py` · `retrieval.py` · `generation.py` |
| 测试 | `test_chunker.py` +4 用例 · golden Hit@3 10/10 · pytest **232** passed |
| 研究 | `rag-r2-research.md` H3～H6 ✅ |

### R2-4 · 重嵌入策略 ✅（2026-07-06）

| 项 | 内容 |
|----|------|
| 范围 | `embedding_model` 列（migration `015`）· 入库打标签 · stale 检测 · 批量重嵌（parent 跳过） |
| 触发 | 运维 CLI `scripts/re_embed_all.py` · `POST /api/v1/internal/re-embed`（`RE_EMBED_TOKEN`） |
| 配置 | `EMBEDDING_MODEL`（默认 `text-embedding-v2`）· 换模型后跑重嵌，维度变更须另开 migration |
| 测试 | `test_re_embed.py` 3 用例 · golden Hit@3 10/10 · pytest **235** passed |
| 研究 | `rag-r2-research.md` H7～H10 ✅ |

**用户可见**：上传 / 删文档 / **失败重试** = 间接维护索引；详情 status 点 + 轮询即「索引进度 UI」，**不设**独立「索引管理页」。

---

## 6. R3 · 检索质量

| ID | 项 | 做什么 | 参考 |
|----|-----|--------|------|
| **R3-1** | hybrid 调参 ✅ | RRF `k`、tsvector vs vector 权重 | TECH-4 §4.6 |
| **R3-2** | Rerank ✅ | 交叉编码器或 API rerank Top-N | PRD P1 |
| **R3-3** | Query 改写 | 可选：HyDE / 多 query 融合 | 答辩加分项，非 MVP |

### R3-3 · Query 改写选型 ✅ Research 已关（2026-07-07）

| 项 | 内容 |
|----|------|
| 结论 | **不 Implement** · golden + 通义生产 **12/12** · miss 驱动再议 |
| 若将来做 | **多 query + RRF**（非 HyDE 主路径）· `QUERY_REWRITE_ENABLED=false` |
| 研究 | `docs/tasks/rag-r3-research.md` §R3-3 · H13～H24 ✅ |
| 触发 Implement | 通义 Hit@3 连续 miss 或 golden 扩题后某 tag 集中失败 |
| **R3-4** | 安全 ✅ | 强制 `kb_id` + `workspace` 过滤 | TECH SEC-3 |

### R3-1 · hybrid RRF 调参 ✅（2026-07-06）

| 项 | 内容 |
|----|------|
| 范围 | `Settings`：`RRF_K=60` · `RRF_VECTOR_WEIGHT=1.0` · `RRF_FTS_WEIGHT=1.2`；`rrf.py` 支持分路权重 |
| 行为 | 向量 Top-20 + FTS Top-20 不变；融合时全文路略加权，利于条款号/原词问法 |
| 测试 | `test_retrieval_hybrid.py` +2 加权 RRF 单测 · golden Hit@3 10/10 · pytest **237** passed |
| 研究 | `docs/tasks/rag-r3-research.md` H1～H4 ✅ |

### R3-2 · Rerank Top-N ✅（2026-07-06）

| 项 | 内容 |
|----|------|
| 范围 | RRF Top-20 → 通义 `qwen3-rerank`（或 mock 词重叠）→ Top-5；`RERANK_ENABLED` 可关退回 R3-1 |
| 配置 | `Settings`：`RERANK_ENABLED` · `RERANK_PROVIDER` · `RERANK_MODEL` · `RERANK_INPUT_TOP_N=20` |
| 代码 | `services/rag/rerank.py` · `retrieve_chunks` 接入 · API 失败回落 RRF 顺序 |
| 测试 | `test_rerank.py` 5 用例 · golden Hit@3 10/10 · pytest **242** passed |
| 研究 | `rag-r3-research.md` H5～H9 ✅ |

### R3-4 · kb+workspace 安全复核 ✅（2026-07-06）

| 项 | 内容 |
|----|------|
| 范围 | R3-2 rerank 后复核 SEC-3：`RetrievedChunk.kb_id` · rerank 后 `_enforce_kb_scope` 剔除跨库 |
| 测试 | `test_retrieval_security.py` 3 用例：单元剔除 · SA-3 rerank 开启 · enterprise personal/org 隔离 |
| 行为 | recall 仍 `WHERE kb_id`；rerank 仅重排；二次校验防回归 |
| 验收 | golden Hit@3 10/10 · pytest **245** passed |
| 研究 | `rag-r3-research.md` H10～H12 ✅ |

---

## 7. R4 · 生成与引用

| ID | 项 | 做什么 | 验收 |
|----|-----|--------|------|
| **R4-1** | System prompt ✅ | 仅依据检索片段；中英分离；反注入 | 注入类问题不泄露 |
| **R4-2** | 无依据拒答 | 检索空或分数整体过低 → 固定话术 | PRD P0 禁止胡编 |
| **R4-3** | 引用块 | 文档名 + 章节/页码 + 摘录；可点预览 | golden + 答辩演示 |
| **R4-4** | 流式 UX ✅ | SSE 引用与正文同步稳定 | Wave 5.2 已有，回归即可 |

### R4-1 · System prompt ✅（2026-07-06）

| 项 | 内容 |
|----|------|
| 范围 | 扩 `SYSTEM_PROMPT`：仅依据片段 · 中英分离 · 禁止编造 · **反注入**（不泄露系统提示 · 忽略片段/用户越权指令） |
| 结构 | `build_messages` 保持【检索片段】与【用户问题】分离（SEC-5） |
| 测试 | `test_generation.py` 5 用例 · golden Hit@3 10/10 · pytest **250** passed |
| 研究 | `docs/tasks/rag-r4-research.md` H1～H4 ✅ |
| 跳过 | R3-3（golden 10/10，非 MVP 触发条件未满足） |

### R4-2 · 无依据拒答 ✅（2026-07-06）

| 项 | 内容 |
|----|------|
| 范围 | `should_refuse_answer` · 词面重叠优先于 `retrieval_min_top1_similarity` · 中/英固定拒答话术 · 无依据不调 LLM |
| 代码 | `relevance.py` · `generation.py` `no_context_reply_for` · `chat.py` 传 message |
| 测试 | `test_rag_relevance.py` +6 · `test_generation.py` +1 · AC-4 chat 回归 · golden Hit@3 10/10 · pytest **257** passed |
| 研究 | `docs/tasks/rag-r4-research.md` H5～H8 ✅ |
| 跳过 | R4-3 引用 UI · 顶栏/支付/OCR |

### R4-3 · 引用块 ✅（2026-07-06）

| 项 | 内容 |
|----|------|
| 范围 | `chunk_to_citation` 六字段契约 · SSE citation 先于 token · 答完自动展开首条引用 · 预览标题含 doc_name |
| 代码 | `test_citations.py` · `test_chat.py` R4-3 契约 · `use-chat-session.ts` · `CitationPreview.tsx` |
| 测试 | `test_citations.py` 4 用例 · `test_r4_3_citation_block_contract` · golden Hit@3 10/10 · pytest **262** passed · `npm run build` 绿 |
| 研究 | `docs/tasks/rag-r4-research.md` H9～H12 ✅ |
| 跳过 | R4-4 流式时序 · 顶栏/支付/OCR |

### R4-4 · 流式 UX 回归 ✅（2026-07-06）

| 项 | 内容 |
|----|------|
| 范围 | SSE 帧格式 · citation 严格先于 token · token 拼接=落库 · done 与流式 citation 一致 · 拒答无 citation · GET messages 与 SSE 聚合一致 |
| 代码 | `test_r4_4_streaming.py` 7 用例 · 不动 `chat.py` / `use-chat-session` 协议 |
| 测试 | golden Hit@3 10/10 · pytest **269** passed · `npm run build` 绿 |
| 研究 | `docs/tasks/rag-r4-research.md` H13～H16 ✅ |
| 跳过 | vitest 前端分片 · 顶栏/支付/OCR · R5 评测闭环 |

---

## 8. R5 · 评测闭环（每次动 RAG 必过）

| ID | 项 | 做什么 | 命令 / 产物 |
|----|-----|--------|-------------|
| **R5-1** | golden_qa 集 ✅ | 维护 `tests/fixtures/golden_qa.json` SSOT + `golden_qa_loader.py` | 12 条：跨页/条款号/表格/改写问法 |
| **R5-2** | Hit@3 自动化 ✅ | `pytest tests/test_retrieval_golden.py` | CI job `R5-2 golden Hit@3 gate`；目标见 TECH-4 §4.3.8 |
| **R5-3** | 对话抽检 | 人工：问 golden 题 → 引用章节页码对 | 答辩前 1 轮 |
| **R5-4** | demo 脚本 | `docs/ENTERPRISE_DEMO_SCRIPT.md` 与 golden 对齐 | Plan-D8 试跑 |

### R5-1 · golden_qa JSON SSOT ✅（2026-07-06）

| 项 | 内容 |
|----|------|
| 范围 | `golden_qa.json` v0.4（GQ-1～12）· `golden_qa_loader.py` · 扩 `golden_handbook.md` 表格节 |
| 新增 | GQ-11 MD 表格切片（R2-2）· GQ-12 改写问法（带薪年休假） |
| 测试 | golden Hit@3 **12/12** · 全量 pytest **271** passed |
| 研究 | `docs/tasks/rag-r5-research.md` H1～H5 ✅ |
| 跳过 | R5-3 人工 · R5-4 demo · 顶栏/支付/OCR |

### R5-2 · Hit@3 CI 门禁 ✅（2026-07-06）

| 项 | 内容 |
|----|------|
| 范围 | `.github/workflows/ci.yml` 独立 job **`R5-2 golden Hit@3 gate`**；`backend` job `needs` 该 gate |
| 命令 | `pytest tests/test_retrieval_golden.py -v --tb=short` · `EMBEDDING_PROVIDER=mock` |
| 门槛 | **12/12** Pass（`golden_qa.json` GQ-1～12 · Top-3 至少 1 条命中期望字段） |
| 文档 | `AGENTS.md` 验收口径 · `TECH.md` §6.6 · `golden_qa.md` §自动化 |
| 验收 | 本地 golden 12/12 · 全量 pytest **271** passed · CI 三 job 绿（golden + backend + frontend） |
| 跳过 | R5-3 人工抽检 · R5-4 demo 对齐 · 顶栏/支付/OCR |

**门禁**：改 `services/rag/`、`services/ingestion/`、`services/retrieval/` 任一 → **必须先 R5-2 CI job 绿**再合并。mock 绿 ≠ 生产通义/DeepSeek 抽测（见 `RAG_PRODUCTION_BASELINE.md` · R5-3）。

### R5-4 · demo 脚本 golden 对齐 ✅（2026-07-07）

| 项 | 内容 |
|----|------|
| 范围 | `docs/ENTERPRISE_DEMO_SCRIPT.md` v1.1 · §2.3 答辩库 **md+pdf** · §3 步骤 9～12 = **P1～P3** · 步骤 13 **AC-4** · §8.1 ① 15min 计时说明合并 |
| 对齐 | 问题/引用期望 ↔ `golden_qa.md` GQ-1/4/8 ↔ `RAG_PRODUCTION_BASELINE.md` §5 |
| 验收 | 脚本步骤与 golden P1～P3 一致 · 注明 demo 库需 `golden_handbook.md` + pdf · cockpit R5-4 ✅ |
| 跳过 | R3-3 Query 改写 · `services/rag/` · 顶栏/支付/OCR · §8 ① 用户亲手计时（回归参考） |

---

## 9. 与 WS-2-2 的边界（Implement 时不扩 scope）

| WS-2-2 做 | WS-2-2 不做（→ Plan-RAG） |
|-----------|---------------------------|
| 当前 workspace 下列表 | L3 跨库搜文档 |
| `?q=` 过滤库名/描述 | 搜 PDF 正文 |
| 副文案 R0-1 | 索引管理页 |
| 链到 Plan-RAG §1 | Rerank / 切片调参 |

---

## 10. 下一步（对话确认后）

1. **WS-2-2** 确认 §2.6 + 副文案 → 落盘 ✅  
2. **workspace-plan.md** W1 开工（含 workspace query + 列表 scope）  
3. **R1 评估**：资料库数量 / demo 是否触发 R1-1  
4. 动 RAG 核心前：跑 **R5-2** 建基线  
5. **R6 backlog**：外部调研项见 §12 · **G2-2 前端关单后**再开 R6 Research 窗

---

## 11. 文档索引

| 文档 | 内容 |
|------|------|
| `docs/TECH.md` TECH-4 | 切片 · hybrid · golden |
| `kb-pages-polish-plan.md` Plan-10 | R1 原 backlog 明细 |
| `workspace-prd-ws2.md` WS-2-2 | 列表页 + L1 搜索 |
| `workspace-prd-ws2.md` WS-2-4 | L2 库内文档（待确认） |
| `workspace-prd-ws2.md` WS-2-6 | 对话 + RAG 用户入口 |
| `docs/tasks/rag-r3-research.md` | R3-3 Query 改写 · HyDE 选型（已关 Implement） |
| `docs/tasks/discovery-agent-platform-plan.md` | G3 Agent tool · 对齐 R6-7 |

---

## 12. R6 · 外部调研 backlog（2026-07-09）

> **来源**：B 站 [`BV1sUTf6FEbi`](https://www.bilibili.com/video/BV1sUTf6FEbi)「RAG 落地踩坑 · 17 条优化」（通用教程，**非** EagleRAG 官方演示）· GitHub [zhiweio/EagleRAG](https://github.com/zhiweio/EagleRAG)（多模态 RAG 参考实现 · Milvus 双集合 · Knowhere + PixelRAG · MCP）。  
> **原则**：**不整库替换**知岸（pgvector + RBAC + audit 已落地）· **miss 驱动** · 动 retrieval/ingestion 仍须 **R5-2 12/12** · WIP=1。

### 12.1 对照摘要（已有 vs 待议）

| 主题 | 视频/EagleRAG 提法 | 知岸现状 | R6 处置 |
|------|-------------------|----------|---------|
| 混合检索 | hybrid + 权重调参 | ✅ R3-1 RRF | **已有** · 仅运维调 `.env` |
| Rerank | Top-N 精排 | ✅ R3-2 qwen3-rerank | **已有** |
| 动态/语义切片 | 按章节/语义边界切 | ✅ R2-1/2 结构切片 + Parent-Child | **R6-1** Research 是否引入外部解析树 |
| HyDE | 假想答案走向量 | ❌ R3-3 已拍板不做 | **R6-2** backlog · 触发见下 |
| 多 query 改写 | 2～3 问法各搜再 RRF | ❌ 同上 | **R6-3** backlog · 优先于 HyDE |
| 反馈学习 | 点踩/纠错调检索 | ❌ | **R6-4** backlog · **默认隐藏** · 必要条件才露出 · 接 eval-ops |
| 扫描 PDF | OCR / 视觉向量 | ✅ F4 PaddleOCR 文本路 | **R6-6** 图表版式 → F5 · **不**混 F4 |
| 多模态 Milvus | eagle_text + eagle_visual | ❌ pgvector 单向量 | **不迁移** · 借鉴思路不进栈 |
| MCP / Agent | ingest/query/retrieve tools | G3 规划中 | **R6-7** 设计对齐 G3 |
| 异步入库队列 | Celery 分队列 | BackgroundTasks | **R6-8** 大库卡顿时再议 |

### 12.2 原子任务（Implement 须单开 I 窗）

| ID | 优先级 | 做什么 | 触发条件 | 验收（Implement 时） | 明确不做 |
|----|--------|--------|----------|----------------------|----------|
| **R6-1** | P2 · **R** | **语义解析 Research**：对照 Knowhere/MinerU 章节树 vs 现 `parser+chunker` · 输出「借/不借/借哪段」 | golden 某 **doc 类型**（长 PDF/制度）集中 miss；或 G2 关单后 | Research 文档落 `docs/tasks/` · 不动代码 | 引入 Milvus · 替换 F4 OCR |
| **R6-2** | P3 · **R→I** | **HyDE**（仅向量路；FTS **始终原问**） | 通义 Hit@3 **连续 miss** + R6-3 仍不够 | `QUERY_HYDE_ENABLED=false` 默认 · golden 12/12 | HyDE 写进 audit 全文 |
| **R6-3** | P2 · **R→I** | **多 query 变体**（2～3 问法 · 各走 recall · RRF 合并） | GQ-12 类 **口语改写**生产 miss；R3-3 授权 | `QUERY_REWRITE_ENABLED=false` · 限流+可观测 · golden 绿 | 每问 5+ 变体 · FTS 用假想文 |
| **R6-4** | P2 · **R→I** | **反馈闭环**：消息级 👍/👎 → golden 候选或检索权重日志（**不自动改索引**）· **UX：日常隐藏，仅必要条件触发才显示**（见 §12.2.1） | G2 thread UI ✅ · eval-ops 排期 | audit/表只记元数据 · Admin 可看聚合 · **非**每条消息常驻按钮 | 自动 re-embed 全库 · 每条回答底部常驻 👍/👎 |
| **R6-5** | P2 · **R** | **chunk 元数据增强**：`section_path` / `doc_type` / 可选 `year` 进检索 filter | R1-4 筛选 UX 稳 · 跨库问「2025 制度」类 miss | migration + filter 单测 · golden 扩 1～2 题 | 用户-facing「索引管理页」 |
| **R6-6** | P3 · **R** | **图表/版式视觉检索**（PixelRAG 思路 · pgvector 存 visual 或 caption 代理） | F5 多模态 **单独立项** · 非 F4 延伸 | Research + 5 题抽测 | 换 EagleRAG 全栈 |
| **R6-7** | P1 · **设计** | **G3 只读 tool 契约**：`semantic_search` / `retrieve_text` 对齐 EagleRAG MCP 四 tool 形状 | **G3 Implement 前**（G2 关单后） | `discovery-agent-platform-plan` §2.3 增补 · OpenAPI 草案 | 部署独立 EagleRAG 服务 |
| **R6-8** | P3 · **I** | **入库分队列**：OCR/大 PDF 独立 worker（Celery 或等价） | M2/实测 ingestion **>N 分钟**阻塞 API | 队列可观测 · 详情 status 不变 | MVP 即上 Celery 全家桶 |
| **R6-9** | P2 · **R** | **离线 RAGAS 脚本**：Hit@3 外补 context precision/recall 抽样 | eval-ops Phase 1 | 脚本 + 1 页结论 · CI **不**挡合并 | 替代 golden gate |

#### §12.2.1 R6-4 · 👍/👎 露出规则（产品拍板 · 2026-07-09）

> **原则**：企业对话页 **不像问卷**；反馈能力要有，但 **默认不打扰**。Implement 前须写进 PRD/UX 一节，与 G2 消息区同一 compare 冻结。

| 场景 | 是否显示 👍/👎 | 怎么露 |
|------|----------------|--------|
| **日常** · 有引用且正常回答 | ❌ **不显示** | 无底部常驻条 |
| **用户主动** | ✅ | 消息 **⋯ 菜单** →「这条回答有帮助吗？」点开后再出现 👍/👎（或等价二级操作） |
| **无引用拒答**（R4-2 固定话术） | ✅ **轻量一次** | 拒答气泡下方 **单行**「没帮上忙？」→ 点开展 👍/👎；**不**自动弹出 modal |
| **引用全灰**（E14 `source_inaccessible`） | ✅ 同上 | 与拒答同组件 · 文案区分「引用不可用」 |
| **Admin 评测模式**（可选） | ✅ | 设置/URL `?eval=1` 或内部开关 · **仅** admin/内测 · 仍 **非**每条强制 |
| **其它普通有引用回答** | ❌ | 仅 ⋯ 菜单路径 |

**后端**：反馈 API 与 audit 元数据 **不依赖** UI 常驻；未反馈 = 无记录。**不做**：每条 assistant 消息默认双按钮 · toast 催评 · 反馈后弹问卷。

### 12.3 建议排期（与 G2 / G3 对齐）

| 顺序 | 窗类型 | 条目 | 理由 |
|------|--------|------|------|
| 1 | **I** | G2-2～G2-2.5 thread UI | 用户 P0 体验债 · 不动 RAG 核心 |
| 2 | **R** | R6-7 G3 tool 契约 | G3 只读 Agent 前置设计 · 零 retrieval 风险 |
| 3 | **R** | R6-1 语义解析 | 仅当 golden/生产有 **doc 型 miss** 证据 |
| 4 | **R→I** | R6-3 多 query | 仅在 R6-1 结论 + miss 清单支持时 |
| 5 | **R** | R6-4 / R6-9 | eval-ops 并行 · 不挡 G3 |

### 12.4 下一窗交接（可选 · R6-7 设计）

```
@rag-knowledge-platform/docs/tasks/rag-optimization-plan.md §12
@rag-knowledge-platform/docs/tasks/discovery-agent-platform-plan.md §2.3

【背景】R5 ✅ · G2 API+audit ✅ · 外部调研 EagleRAG/B 站课已落 R6 backlog

【要求】严格只做 R6-7（G3 只读 tool OpenAPI/事件契约草案）· 不动 retrieval · 不写 Agent 循环

【验收】§2.3 tool 表 + 与现 `/ask` `/search` API 映射表 · 无 Implement 代码
```
