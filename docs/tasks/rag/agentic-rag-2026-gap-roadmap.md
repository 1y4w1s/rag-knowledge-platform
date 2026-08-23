# Agentic RAG 2026 差距分析与实施路线图

> 日期：2026-08-14（首版）· **2026-08-20 刷新** · **2026-08-23 V1.0 convergence 收口**
> 类型：研究 + 路线图（本窗零业务代码改动）
> 触发：用户要求「达到甚至超过 Agentic RAG 标准」，先做文献与 GitHub 对标
> 范围：只做差距分析与里程碑规划；实施另开窗口
>
> **2026-08-23**：T2 / TOOL selection / MEMORY / ADVERSARIAL 能力测量线 **CLOSED / FROZEN**（见 [`docs/status/v1-convergence-status-2026-08-23.md`](../../status/v1-convergence-status-2026-08-23.md)）。**下一 V1.0 主线：W9 Critic → W10 Multimodal → Final Benchmark → RC**；MCP / Multi-Agent / GraphRAG 仍为 Post-V1.0 backlog。

---

## 1. 结论摘要

### 1.1 一句话定位（2026-08-20）

索隐已经是 **Single-agent + Adaptive + 轻量 Corrective** 的 Agentic RAG 骨架（非 Naive RAG）。  
与「论文/开源完整版」的差距，主要不在再套 LangGraph，而在：**生成后批判闭环、中间能力评测、反馈→评测闭环**；**MCP** 为工程互操作可选项（需产品拍板）。Multi-Agent / 开网页 Deep Research / GraphRAG **不是**企业必达定义项。

### 1.2 骨架层（仍成立）

- Planner-Executor：`QueryDepth` + `LLMPlanner` 双轨，LLM 失败自动回退确定性 `ThoroughReadPlanner`；
- ReAct 循环：≤5 步、120s 预算、E2 反思（low_recall 改写重规划 / complex 拆子查询 / low_confidence 标记）；
- 工具层：11 个白名单工具、写审批、工具级熔断与限流、`web_search` 默认关；
- 记忆层：T5 治理 + T6 分层（tier / importance / summary / 滑动窗口 / 会话折叠）全部收口；
- 评测层：Golden 109 题 / Hit@3 门禁、Enterprise 90、Advanced 14/14、RAGAS 双轨基准；
- **阶段二增量（2026-08）**：M1 子查询漂移守卫（S1/S2）；M2 证据充分性 + 自适应 S1 改写重检（方案 C）；W8 证 `rewrite=… sufficient=True` landing；方案 A（swap）/ multi_query **评估后默认停手**（触发制，见阶段二 M2 W8 报告与方案 A 评估结论）。

### 1.3 Survey 四 Pattern 对照（定义层）

| Pattern（[2501.09136](https://arxiv.org/abs/2501.09136)） | 索隐 | 判定 |
|------|------|------|
| **Planning** | QueryDepth 路由 + 分解子查询 | ✅ |
| **Tool Use** | 白名单工具化检索；外网默认关（企业定位） | ✅ |
| **Reflection** | E2 / drift / 证据不足→S1；缺生成后 claim 级 critic | ⚠️→❌ 硬差距在生成侧 |
| **Multi-Agent** | 刻意不做 | ➖ 非必达 |

Taxonomy 落点：接近 **Adaptive**（复杂度路由）+ **Corrective 轻量版**（证据不足→改写重检）；非 Multi-Agent / Graph 主路径。

### 1.4 硬差距表（2026-08-20 刷新）

| 差距 | 状态 | 说明 | 论文/开源对标 |
|------|------|------|---------------|
| **G1 批判闭环不在主链路** | ❌ **仍硬** | 无生成后 critic 逐 claim 校验；规则 verify ≠ LLM critic | RAG-Critic；Survey Reflection |
| **G2 自适应检索默认不触发** | ⚠️ **部分关闭** | M2 已接证据充分性 + S1 landing（W8）；multi_query/HyDE/rerank 默认关；S2 在 A0=3 难达；方案 A/multi_query 停手 | CogPlanner / FAIR-RAG / CRAG |
| **G3 工具不可被外部 Agent 发现** | ❌ **可选硬** | 无 MCP；产品需重决策 | TURA；ragent / haiku.rag |
| **G4 反馈未形成评测闭环** | ❌ **仍硬** | thumbs-down 不自动归因入 golden；缺 RAGCap 中间能力评测 | RAGCap-Bench / RAG-Critic |

另有两条「证据层」差距（非定义核心）：百万级向量 + 并发压测报告缺失；成本报告（缓存命中率 / 模型路由 / per-run 预算）缺失。

**RAGCap-Bench 四中间能力**（Planning / Evidence Extraction / Grounded Reasoning / Noise Robustness）：端到端评测有，**中间能力独立基准几乎无** → 与 G4 同源，列入「可运营 Agentic」缺口。

---

## 2. 最新 RAG 研究基线（2025-2026）

| 论文 | 核心主张 | 对索隐的含义（刷新） |
|------|---------|-------------|
| Agentic RAG Survey（arXiv 2501.09136） | 四 Pattern + Adaptive/Corrective/Multi-Agent taxonomy | 骨架对齐 Adaptive+轻 Corrective；差距在 Reflection 生成侧与评测证据 |
| RAG-Critic（ACL 2025 · 2025.acl-long.179） | critic-guided workflow + 分层 error | 仍缺 critic↔人工一致率指标（G1/G4） |
| FAIR-RAG（2025-10） | evidence-driven 迭代精炼 | 检索侧轻闭环已有（M2）；生成侧迭代仍缺 |
| TokenRAG（2025-11） | 检索/推理 token 压缩 + DPO | 成本方向；规则压缩 ≠ LLM 摘要评估 |
| RAGCap-Bench（arXiv 2510.13910） | 中间子任务细粒度评测 | **G4 强化**：缺 Planning/抽证/推理/抗噪独立评测 |
| CogPlanner（arXiv 2501.15470） | 迭代改写 + 检索策略规划（偏多模态） | 文本侧有改写阶梯骨架；多模态 MRAG 后置 |
| MAO-ARAG（arXiv 2508.01005） | multi-agent orchestration | 多 Agent 与产品冲突，不跟进 |
| Tool-to-Agent Retrieval（arXiv 2511.01854） | 动态工具发现 | 可做白名单内轻量发现；MCP 另议 |
| TURA（arXiv 2508.04604） | DAG planner + MCP | MCP 暴露参照（G3） |
| AgentMaster（arXiv 2507.21105） | A2A + MCP | Wave 2 再评估 |

---

## 3. GitHub 开源对标

### 3.1 首版对标（2026-08-14，仍参考）

| 仓库 | Stars（当时） | 可借鉴点 | 索隐的差异点 |
|------|-------|---------|-------------|
| dify | 152k | 工作流编排、插件生态、评测运营 | 索隐更轻、引用溯源与审计更强 |
| agents/servers（MCP） | 89.6k | MCP server 规范、工具发现 | 索隐未接入 |
| RAGFlow | 88k | 深度文档解析、模板化 RAG | 索隐自研解析链路 |
| autogen / crewAI | 60k / 57k | Multi-Agent | 产品定位不符 |
| llama_index / langgraph | 51.6k / 39.7k | 组件生态 / 图状态机 | 自研 ReAct + planner |
| openai-agents | 28.6k | 工具协议、guardrails | 可对齐协议，不引入依赖 |
| R2R | 8k | 服务化 + 评测 | 对标评测闭环证据 |
| cortex | ~0 | MCP-native + critic + 成本天花板 | 缺 MCP 与成本报告 |

### 3.2 2026-08-20 增补（Agentic 叙事更贴）

| 仓库 | Stars（约） | 可借鉴点 | 索隐差异 |
|------|-------------|----------|----------|
| [asinghcsu/AgenticRAG-Survey](https://github.com/asinghcsu/AgenticRAG-Survey) | ~1.7k | 定义与 taxonomy 权威配套 | 对标用，非实现 |
| [nageoffer/ragent](https://github.com/nageoffer/ragent) | ~3.7k | 全链路 + **MCP** + 深度思考 | MCP /「深度思考」叙事差 |
| [ggozad/haiku.rag](https://github.com/ggozad/haiku.rag) | ~0.6k | hybrid + rerank + **MCP server** + 幻觉抑制 | 自托管最接近；互操作=MCP |
| [GiovanniPasq/agentic-rag-for-dummies](https://github.com/GiovanniPasq/agentic-rag-for-dummies) | ~3.9k | LangGraph + HITL 澄清 | HITL 非当前优先级 |

结论（刷新）：功能面仍不落后；对外叙事差距集中在 **G1 批判 / G4 评测闭环 /（可选）G3 MCP**；G2 已从「完全缺失」降为「轻闭环已有、深阶梯停手」。

---

## 4. 索隐现状能力地图（代码核对 · 含阶段二）

| 维度 | 现状 | 证据 |
|------|------|------|
| Planner | QueryDepth + LLMPlanner 双轨，失败回退 | `services/agent/planners.py` |
| ReAct | ≤5 步、120s、E2 反思 | `services/agent/runtime.py` |
| 漂移守卫（阶段二 M1） | 子查询漂移 → S1 改写 / S2 直检 + 预算 | `guard_sub_query_drift` |
| 证据充分性 + 自适应（阶段二 M2） | `check_evidence_sufficiency`；不足 → S1（方案 C）；默认关开关 | `evidence.py` + `guard_evidence_insufficiency`；W8 landing 审计 |
| 工具 | 11 白名单、写审批、熔断/限流；web_search 默认关 | `services/agent/tools/registry.py` |
| 记忆 | T5 + T6 | `services/agent/memory_*.py` |
| 评测 | Golden / Hit@3 / Enterprise / RAGAS；C3 `evidence_sufficiency_rate` + `adaptive_retries_total` | `tests/benchmark/` + 评测侧聚合 |
| 可观测/降级 | Prometheus + OTel + L0-L4 + 熔断 | `core/degradation.py` |
| 安全 | kb_id/workspace 隔离、Member 403、审计 | `api/` + `audit/` |

---

## 5. 硬差距详解

### 5.1 批判闭环不在主链路（G1 · 仍硬）

现状：`runtime.py` 有 E2 反思（low_recall / low_confidence），但预算受限；生成后校验（verify / citation density）在 `generation.py`，仅做规则级二次生成。检索侧已有充分性判定，**不等于**生成后逐 claim critic。

目标：引入「critic 步骤」——生成完成后逐 claim 校验引用与证据一致性，失败时按预算重检索/重生成；错误按分层 taxonomy 自动归因并落审计。

### 5.2 自适应检索默认不触发（G2 · 部分关闭）

**已关闭（阶段二）**：

- 证据充分性规则接入 agent 链路（observation → 策略可开）；
- 证据不足 → S1 query_rewrite 重检（W4 方案 C 解除预算饿死；W8 landing `rewrite=… sufficient=True`）；
- C3 常驻观测字段上线。

**仍开放 / 停手**：

- multi_query / HyDE / rerank 默认关；完整阶梯 Step 2+ 未落地；
- S2 在 A0=3 分解链上难达；方案 A（swap）评估结论 = **不做（默认停手）**，触发条件见阶段二评估（T1 S1 系统性不够 / T2 要 S2 且坚持 A0=3 / T3 要 multi_query 且坚持 A0=3）；
- 图谱召回已回滚（维持）。

目标（若再开）：仅在触发条件成立时立项加深阶梯；不得未评估抬 A0 或改 M1 定案。

### 5.3 工具不可被外部 Agent 发现（G3 · 可选硬）

现状：工具是进程内枚举；审计曾明确「不做 MCP」，产品需重新决策。

目标：只读工具（search / retrieve / excerpt）以 MCP/标准接口暴露，继承 kb_id/workspace 隔离、审计与限流。  
**非 Survey 四 Pattern 必需项**；是开源工程标配叙事项。

### 5.4 反馈未形成评测闭环（G4 · 仍硬）

现状：已有 thumbs-down → golden 人工评审流程（NW-14/NW-17），但不会自动归因、不会自动入 golden；无 RAGCap 式中间能力基准。

目标：bad case 自动归因 → 建议入 golden → 人工确认后增量回归；可选补中间能力抽检；critic 判错与人工评审一致率成为可量化指标。

---

## 6. 里程碑路线（刷新编号说明）

> **编号注意**：首版 §6 的 M1=反馈闭环、M2=自适应检索。阶段二实施时按 init-assessment **重排**：阶段二 M1=漂移守卫、阶段二 M2=证据充分性（对应原 G2 主路径）。下表用「路线图编号 / 阶段二编号」双标，避免混淆。

| 路线图 | 主题 | 状态（2026-08-20） | 对标 | 建议 |
|--------|------|-------------------|------|------|
| 原 M2 ≈ **阶段二 M1+M2** | 预算内自适应 / 证据闭环 | ✅ **渐进口径收口**（landing 可证；深阶梯停手） | CogPlanner / FAIR-RAG / CRAG | 默认队空；仅 T1–T3 触发再开 |
| 原 M1 | 反馈驱动评测闭环 | ❌→📋 **已立项 G4** | RAG-Critic / RAGCap-Bench | 见 `agentic-rag-g1g4-init-assessment.md`；首窗 G4-W1 |
| （新）Critic | 生成后批判闭环 | ❌ **后置** | RAG-Critic；Survey Reflection | 等 G4 taxonomy / 一致率；本批不立 |
| 原 M3 | 知识库工具 MCP 暴露 | ❌ 未做 | TURA；ragent/haiku | 需产品边界确认（G3） |
| 原 M4 | 成本与运营证据 | ❌ 未做 | cortex | 低风险增量观测 |
| 原 M5 | 规模与韧性证据 | ❌ 未做 | R2R | 独立压测环境 |

安全红线（所有里程碑通用）：

- 动检索/入库/切片 → CI Hit@3 gate 绿；
- 动模型/迁移 → `alembic check` 空 diff；迁移 `CREATE INDEX CONCURRENTLY`；
- 动权限/审计/删除链路 → 补齐审计断言与 pytest；
- MCP 暴露必须带 scope / 审计 / 限流，禁止绕过 kb_id 隔离。

---

## 7. 建议下一步（2026-08-23 · V1.0 FINALIZATION）

1. **W9 Critic Hardening** — V1.0 下一主线（见 [`docs/status/v1-convergence-status-2026-08-23.md`](../../status/v1-convergence-status-2026-08-23.md)）。
2. **W10 Multimodal Vertical Slice** — queued after W9。
3. **Final Frozen Benchmark → Flag Audit → Docs/Demo → RC → v1.0.0 tag**。
4. **默认停手加深检索阶梯**（方案 A / multi_query）：已评估；无 T1–T3 不开窗。
5. **G4 反馈闭环**：见 [`agentic-rag-g1g4-init-assessment.md`](agentic-rag-g1g4-init-assessment.md)；纳入 Post-V1.0 或 W9+ 触发，**非**当前 closed 能力线 remediation。
6. **G3 MCP**：Post-V1.0 backlog；仅在产品明确「要被外部 Agent 调用」后立项。
7. **T2 / TOOL selection / MEMORY / ADVERSARIAL remediation**：**DEFER / CLOSED** — 见 [`v1-known-limitations.md`](../../status/v1-known-limitations.md)。

按项目流程：W9 先出实施文档（范围 / 文件 / 验收命令），确认后再动代码。
