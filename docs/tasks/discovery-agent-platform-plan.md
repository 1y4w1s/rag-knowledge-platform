# G-AGENT · 企业级 Agent 平台路线图（做深版 · Plan）

> **状态**：✅ **P 关**（2026-07-09）→ **G3 ✅ 整线**（2026-07-10）→ **G4-min P ✅**（2026-07-10）→ **G4-min V ✅** → **G4-min R ✅** → **G4-min L ✅** → **G4-min I ✅**（2026-07-11 · 整线）→ **G5 P ✅**（2026-07-11）  
> **SSOT**：本文件 = Agent 全栈总地图 · **G2** thread 见 `discovery-smart-chat-g2-threads-plan.md` · **G1** 跨库 RAG 见 `discovery-smart-chat-plan.md`  
> **北极星不变**：回答仍须 **引用溯源或拒答** · **OrgScope 隔离** · **写操作可审计、可确认、可回滚**

---

## §0 边界 · 极限指什么、什么仍不做

### §0.1 「向着极限做」在本项目里的定义

| 包含（知岸企业级 Agent 平台） | 仍不做（PRD §14 / 北极星） |
|-------------------------------|----------------------------|
| 多 thread 历史（**G2**） | 公网 **联网搜索**（实时新闻/股价） |
| 只读 **RAG Agent** 多步 tool（**G3**） | **无引用纯聊天**模式 |
| **写知识库** Agent：上传、草稿、摘要入库（**G4**） | 支付 / 积分 / SaaS 计费 |
| **内容智能**：FAQ/结构化/重切片建议/质量评分（**G5**） | OCR 扫描件（Format-F4 单线） |
| **工作流 / 触发器**：文档入库后自动摘要、定时 digest（**G6**） | 多租户 SaaS 商业化 |
| **业务连接器**（可选极限层 **G7**）：Webhook、Jira/Slack 出站 | Agent **静默覆盖**用户真源 PDF 无版本 |
| 全链路 **tool trace + audit + 人工确认** | Admin **查看他人对话正文**（H2-1-A） |
| Agent **SSE/UI** 与 UX-P1 对话壳 **一次定稿** | 一次 Implement 全开（**分 Wave WIP=1**） |

### §0.2 能力金字塔（TO-BE 极限态）

```
                    ┌─────────────────────┐
                    │ G7 业务连接器        │  Webhook · 外部工单/IM（可选）
                    ├─────────────────────┤
                    │ G6 工作流/触发器     │  入库触发 · 定时 · 审批链
                    ├─────────────────────┤
                    │ G5 内容智能          │  摘要/FAQ/标签/重切片建议
                    ├─────────────────────┤
                    │ G4 写库 Agent        │  上传/草稿/采纳入库（Admin）
                    ├─────────────────────┤
                    │ G3 只读 RAG Agent    │  多步检索+search+list_kb
                    ├─────────────────────┤
                    │ G2 Thread 历史       │  列表/新建/切换/软删
                    ├─────────────────────┤
                    │ G1 固定 RAG（现网）  │  retrieve→gate→SSE→citation
                    └─────────────────────┘
```

**默认模式**：底层 **G1 精准问答** 始终保留；上层 Agent **按需启用**（**HA-4-A**：用户手动切模式；自动升级进 backlog）。

### §0.3 「做深」策略（P 关签章 · 2026-07-09）

> **路线图可极限（§0.2 金字塔保留）· Implement / 简历只押深度，不押宽度。**

| 层级 | PRD / 架构 | Implement 合同 |
|------|------------|----------------|
| G1 + G2 | ✅ 已交付 | — |
| **G3** 只读 Agent | **下一里程碑 · 必做** | tool trace + agent golden ≥15 题 + TECH-7 |
| **G4-min** 采纳写库 | PRD 愿景 · **可选第二波** | 仅 FAQ/摘要草稿 + Admin 采纳（一条场景做透） |
| G5 内容智能 | PRD 愿景 | **Defer** · rechunk 建议等与 G4-min 叙事合并时可再议 |
| G6 工作流 | PRD 愿景 | **Defer** · 不做通用 flow 引擎；将来最多「入库完成 → 可选摘要钩子」 |
| G7 外联 | **HA-3-C · 不做** | 不出现在 Implement 合同与简历 bullet |

**简历三根柱子**：① RAG 可证明（golden + CI）② 企业边界（OrgScope + audit）③ 克制 Agent（G3 + 可选 G4-min）。

---

## §1 产品形态（极限版 · 用户视角）

### §1.1 一个入口，四种「大脑模式」

| 模式 | 人话 | 谁可用 | 典型场景 |
|------|------|--------|----------|
| **快速** | 搜一次、答一次、带 chip（原「精准」工程名） | 全员 | FAQ、golden 题 |
| **精准** | 多步查库、查透再答、可看 tool 时间线（原「助手」） | 全员 | 跨库对比、找不着库名 |
| **编辑** | 生成摘要/FAQ/优化稿，**你点采纳才入库** | Admin/Owner（Member 仅预览草稿） | 制度库维护、入库后自动文档化 |
| **自动化** | 后台 flow：新文档→摘要→待审队列 | Admin 配置 | 运营、合规留痕 |

对话页 UI：**模式切换器** + 左侧 **thread 列表（G2）** + 中间 **消息与 tool 时间线** + 底部 sticky 输入。

### §1.1.1 首版 Implement 范围（P 关 · 做深）

| 模式 | 首版 | 说明 |
|------|------|------|
| **快速** | ✅ | 默认 · 现网 G1 |
| **精准** | ✅ | **G3 唯一 Implement 目标** · 多步只读 Agent |
| **编辑** | PRD 愿景 | G4-min：Admin 采纳 FAQ/摘要草稿 |
| **自动化** | PRD 愿景 | 不进 Implement 合同 |

**预览对齐**：`preview-agent-platform.html` v4.1 · **快速 / 精准** 手动切换 · **Implement 先 HA-4-A**（「意图驱动」自动升精准进 backlog）。

### §1.2 写操作 · 企业级三板斧（全 Agent 写能力必过）

| 板斧 | 白话 | 验收 |
|------|------|------|
| **确认** | Agent 提议「上传到人事库？」→ 必须点 **采纳/取消** | Member 看不到采纳按钮 |
| **审计** | audit 记 thread_id、tool、库 id、文件名；**不记**问题全文 | 审计页可查 |
| **版本** | 优化内容 → **新文件或 draft**；改源文件 → 版本号 + 可回滚 | citation 不失效或标记 stale |

### §1.3 可溯源 · 三层

| 层 | 用户看见 | 系统存 |
|----|----------|--------|
| **回答** | citation chip（库名·文档·页码） | `citations` JSON |
| **过程** | 「调用了：跨库检索×2 · 文件名搜索×1 · 生成草稿×1」 | `tool_trace[]` |
| **写入** | 「已采纳：FAQ_v1.md → 人事库 · 整理中」 | audit + document_id |

---

## §2 技术总架构（Implement 方向 · 确认后写 TECH-7）

### §2.1 新模块（后端）

| 模块 | 职责 | 软上限 |
|------|------|--------|
| `services/agent/runtime.py` | ReAct / tool-call 循环 · max_steps · 超时 | ≤300 行 |
| `services/agent/tools/` | 每 tool 一文件 · 注册表 + 权限 class | 每文件 ≤200 |
| `services/agent/approvals.py` | 写操作 pending → 用户 confirm → 执行 | ≤250 |
| `services/agent/runs.py` | agent_run / agent_step 落库 | ≤300 |
| `api/agent.py` 或扩 `ask.py` | SSE：`tool_start` `tool_result` `approval_required` | ≤200 |

### §2.2 数据模型（增量）

| 表/列 | 用途 |
|-------|------|
| `chat_threads` | **G2** |
| `chat_messages.thread_id` | **G2** |
| `agent_runs` | 一次用户发问的 Agent 执行（mode、steps、status） |
| `agent_steps` | 每步 tool name、args、result 摘要、latency |
| `agent_approvals` | 写操作待确认（upload、adopt_draft、reindex） |
| `document_drafts` | G4/G5 生成稿（可选独立表或 documents.status=draft） |

### §2.3 Tool 注册表（极限清单 · 分阶段 Implement）

| Tool | 类型 | 阶段 | 权限 |
|------|------|------|------|
| `semantic_search` | 读 | G3 | visible_kb |
| `search_documents` | 读 | G3 | visible_kb |
| `list_knowledge_bases` | 读 | G3 | scope |
| `get_chunk_excerpt` | 读 | G3 | kb read |
| `get_document_metadata` | 读 | G3 | kb read |
| `propose_upload` | 写·待审 | G4 | kb write |
| `upload_document` | 写 | G4 | kb write + approval |
| `generate_faq_draft` | 写·待审 | G4 | kb write |
| `adopt_draft_to_kb` | 写 | G4 | approval |
| `suggest_rechunk` | 建议 | G5 | admin |
| `apply_rechunk` | 写 | G5 | admin + approval |
| `enqueue_workflow` | 自动化 | G6 | admin |
| `webhook_emit` | 外联 | G7 | admin + 配置 |

**每 tool**：服务端 **不信模型传的 kb_id** — 用 OrgScope 校验 args。

> **G3 设计对齐**：只读 tool 形状对照 EagleRAG MCP（`query` / `retrieve_text` / `retrieve_visual`）与 Plan-RAG **R6-7**（`rag-optimization-plan.md` §12）· **Implement G3 前**出 OpenAPI/事件映射表 · **不**部署 EagleRAG 全栈。

### §2.4 SSE 事件（扩展现网）

| 事件 | 含义 |
|------|------|
| `citation` / `token` / `done` | 现网保留 |
| `tool_start` | 开始某 tool |
| `tool_result` | 步骤结果摘要（可折叠） |
| `approval_required` | 弹出确认卡片 payload |
| `approval_resolved` | 采纳/拒绝后 |
| `document_status` | 上传/整理进度（接现有 ingestion） |

### §2.5 前端（与 G2 + UX-P1 合并）

| 组件 | 说明 |
|------|------|
| `ThreadListPanel` | G2 |
| `AgentModeSwitcher` | 快速 / 精准 / 编辑（Member 无编辑） |
| `ToolTimeline` | 步骤折叠条 |
| `ApprovalCard` | 写操作确认 |
| `DraftPreview` | FAQ/优化稿预览 + 采纳 |

**预览**：`preview-agent-platform.html` v3（2026-07-08）· **意图驱动**（非手选四模式）· 历史可折叠 · 步数边界 · 侧栏对齐 `AppSidebar.tsx`。

---

## §3 Wave 路线图（强制顺序 · WIP=1）

| Wave | 代号 | 交付 | 依赖 | 预估 |
|------|------|------|------|------|
| **W0** | **G2** | thread 表 + 列表 UI + 真·新建 | G1 ✅ | 2～3 窗 |
| **W1** | **G3** | 只读 Agent + tool trace + 评测小集 | G2 | 3～4 窗 |
| **W2** | **G4-min** | FAQ/摘要草稿 + approval + adopt（**可选** · 一条场景做透） | G3 | 2～3 窗 |
| **W3** | **G5** | 内容智能 + rechunk 建议 | G4-min | **Defer · backlog** |
| **W4** | **G6** | 触发器/workflow 引擎（内置） | G5 | **Defer · backlog** |
| **W5** | **G7** | Webhook + 可选连接器 | G6 | **HA-3-C · 不做** |
| **并行** | **UX** | agent 壳层 V 冻结 → Implement | W0 起 | 与 W1 对齐 · W2 可选 |

**Golden gate**：动 `retrieve_*` 时仍 12/12；Agent 独立 **`test_agent_*.py`** + **`golden_agent_qa.json`**（≥15 题，含多步+拒答+越权）。

---

## §4 文档矩阵（极限版要补的 PRD/TECH）

| 文档 | 内容 |
|------|------|
| `discovery-agent-platform-prd.md` | §Agent-1 模式 · §Agent-2 写确认 · §Agent-3 乱操作 |
| `discovery-smart-chat-g2-threads-plan.md` | 已 P ✅ |
| `discovery-agent-g3-read-plan.md` | W1 原子任务（G3 确认后拆） |
| `discovery-agent-g4-write-plan.md` | W2 |
| `TECH.md` **TECH-7** | Agent runtime · tool 权限 · SSE · 数据流 |
| `docs/golden_agent_qa.json` | Agent 评测集 |
| `INTERVIEW_STORY.md` | Agent 决策故事 |

---

## §5 拍板记录（HA-1～HA-4 · ✅ 用户确认 2026-07-09 · 做深）

| 假设 | 选定 | 状态 |
|------|------|------|
| **HA-1 默认模式** | **A** · 默认**快速**；复杂自动升精准 **进 backlog** | ✅ |
| **HA-2 编辑模式** | **A** · 仅 Admin/Owner 可采纳；Member 可预览草稿不可采纳 | ✅ |
| **HA-3 G7 外联** | **C** · 不做 G7（PRD 金字塔保留愿景 · Implement/简历不写） | ✅ |
| **HA-4 自动升级** | **A** · 用户手动切模式；模型判断多步 **进 backlog** | ✅ |

<details><summary>拍板时后果摘要（归档）</summary>

| 假设 | 选定的后果（白话） |
|------|---------------------|
| HA-1-A | 打开对话仍是现网速度；golden/demo 稳；限流 30/h 不被多步打满 |
| HA-2-A | 和现网 Member 只读一致；写库故事集中在 Admin 采纳一条线 |
| HA-3-C | 省 2～3 窗集成债；答辩/简历讲 RAG+Agent+审计，不讲 Slack |
| HA-4-A | 用户显式切「精准」；成本/步数可控；与 preview「意图驱动」Implement 分期 |

</details>

### §5.1 用户可见命名（2026-07-09 · V 窗 UX 拍板）

| 工程/旧文案 | **用户可见名** | 说明 |
|-------------|----------------|------|
| precise / 精准 / G1 | **快速** | 默认 · 单次检索 |
| assistant / 助手 / G3 Agent | **精准** | 多步查透 · tool 时间线 |

> 用户原话：「精准/助手不明不白」→ 改为 **快速 / 精准**。Implement 组件 prop 可仍用 `mode=fast|thorough`，UI 文案以本表为准。

---

## §6 P 关 DoD

| # | 条件 | 状态 |
|---|------|------|
| P1 | §0 极限边界用户确认（含 §0.3 做深策略） | ✅ 2026-07-09 |
| P2 | §1 四模式 + 三板斧 + §1.1.1 首版范围确认 | ✅ 2026-07-09 |
| P3 | §3 Wave 顺序确认（G3 必做 · G4-min 可选 · G5+ Defer） | ✅ 2026-07-09 |
| P4 | §5 HA-1～HA-4 拍板 | ✅ 2026-07-09 |

---

## §7 当前进度与下一窗

| 线 | 状态 | 下一窗 |
|----|------|--------|
| **G2** | **整线 ✅** | — |
| **G-AGENT 总图** | **P ✅** | — |
| **G3 V** | **✅ v4.1 · V2 冻结**（2026-07-09 · 用户：「可以」） | — |
| **G3 R** | **✅** `discovery-agent-g3-read-research.md` · tool 对照 · SSE · 乱操作 | — |
| **G3 L** | **✅** `discovery-agent-g3-read-plan.md` · G3-0～G3-5 · H3-1～H3-6 | — |
| **G3 I** | **✅ G3-0～G3-5.3** · pytest **523** · golden 15/15 | — |
| **G3** | **整线 ✅**（2026-07-10） | — |
| **G4-min P** | **✅** `discovery-agent-g4-write-prd.md` · G4-1～G4-5 · H4-1～H4-6 | **V** preview G4 真交互 → **R** research |
| **G4-min V** | **✅** `preview-agent-platform.html` v4.2 · 采纳卡真交互 · V2 冻结 | **R** research |
| **G4-min R** | **✅** `discovery-agent-g4-write-research.md` · tool/SSE/approval 对照 · E 表 20 条 | **L** plan |
| **G4-min L** | **✅** `discovery-agent-g4-write-plan.md` · G4-0～G4-5 原子任务 17 条 · H4-1～H4-6 | **I** G4-0.1 |
| **G4-min I** | **✅ G4-0.1～G4-5.4 整线** · 后端 157 passed · agent golden 16/16 · retrieval 10/12（2 skipped 非回归）· 前端 25 passed · build 绿 · SSE 零回归（2026-07-11） | **G5**（摘要草稿第二条线）或 **G6**（E2E） |
| **G4-min** | **整线 ✅**（2026-07-11） | — |
| **G5 P** | **✅** `discovery-agent-g5-content-prd.md` · G5-1～G5-5 · 四条能力线（摘要/rechunk/标签/评分）· Tool 白名单 10 tool · E 表 24 条（2026-07-11） | **V** preview G5 交互（rechunk 对比卡 · 标签多选卡） |
| **G1** | 整线 ✅ | — |

**V 窗交付（G3 · v4.1 · 2026-07-09）**：
- `preview-agent-platform.html` v4.1 · **HA-4-A 手动切模式**（**快速 / 精准**）· 编辑灰钮愿景占位
- **精准**模式 **Tool 时间线**（`list_knowledge_bases` / `semantic_search` / `search_documents` / `get_chunk_excerpt`）
- **步数上限** 快速 1 步 · 精准 5 步 · E-budget 触顶提示
- G4 采纳卡片 → 「愿景占位」区 · 无真交互
- 验收试玩 S1～S8 + E + G4 占位

**G3 R 交付（2026-07-09）**：
- `discovery-agent-g3-read-research.md` · §2 只读 tool 对照（现网 + EagleRAG）· §3 SSE 映射 · §4 乱操作 G3-E
- 快速 = 现网单次检索 · 精准 = 5 步 tool + `tool_start`/`tool_result` · citation 仍先于 token

**G3 PRD 第一节建议提纲**（L 窗前）：模式定义 · 只读 tool 清单 · SSE 事件 · 乱操作 · agent golden 验收口径。
