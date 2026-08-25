# W10 E-B1 — Generation Observation Protocol

> **Type:** research only（观察点协议冻结，不实施）  
> **Date:** 2026-08-24  
> **Product:** 索隐  
> **Status:** **FROZEN** — 定义生成**之后**可观察什么，以及四靶如何定义  
> **Does not:** 产品代码 · LLM / 嵌入 / 本地推理 · 生成管线执行 · pytest 生成套件 · Docker · P2-R1 解阻 · Critic 能力声称 · 与 E-A5 结果合并

本目录冻结 **E-B1（A 轨 · L1 观察点协议）**：在 E-B0 划定生成平面边界之后，钉死「生成后观察窗口」与四靶操作定义，供后续契约/执行窗引用。**本窗不跑任何生成，不写正式观测结果。**

## 编号消歧（必读）

| 符号 | 本目录含义 | **不是** |
|---|---|---|
| **E-B1** | **本目录**：generation-final **观察点协议** | Decision 表 Direction B「污染 `gated_chunks` 可达性探针」 |
| **E-B0（A 轨）** | [`../w10-eb0-generation-boundary/`](../w10-eb0-generation-boundary/) 生成平面边界章程 | Decision DiD E-B0 |
| **E-A5** | plan-construction citation scope 正式窄窗 | 本协议的观察点或声称源 |

## 阅读顺序

1. [`01-observation-boundary.md`](01-observation-boundary.md) — 观察窗口：`gen_plan` **之前** vs `state["content"]` / `state["citations"]` **之后**
2. [`02-measurement-targets.md`](02-measurement-targets.md) — 仅四靶：终态引用 scope 保全 · 无依据断言 · 答案接地 · 拒答行为
3. [`03-claim-restrictions.md`](03-claim-restrictions.md) — 禁止声称（含禁止与 E-A5 合并）
4. [`04-case-eligibility.md`](04-case-eligibility.md) — W9 冻结 12 案对 post-generation 观察的资格与缺口
5. [`05-artifact-schema-draft.md`](05-artifact-schema-draft.md) — **未来**观测工件字段草案（不实现、不落正式结果）

## 一句话结论

| 断言 | 状态 |
|---|---|
| 观察窗口起点（生成前）= `AgentGenerationPlan`（`gen_plan`） | **FROZEN** |
| 观察窗口终点（生成后）= `_stream_generation_phase` 写入的 `state["content"]` + `state["citations"]`（对齐后） | **FROZEN** |
| 四靶仅定义操作语义，**未测量** | **FROZEN** |
| E-A5 11/11 **不是**本协议结果，不得合并 | **钉死** |
| 正式 generation observation 已执行 | **否**（本窗故意不做） |

## 程序指针（权威）

| Role | Path / symbol |
|---|---|
| Plan 构造 | `backend/app/services/agent/finalize.py` · `AgentGenerationPlan` · `prepare_agent_generation` · `gate_agent_chunks` |
| 生成相 | `backend/app/services/agent/stream.py` · `_stream_generation_phase` |
| 终态写入 | 同文件：`state["content"]` · `state["citations"]` · SSE `done.citations` |
| 引用对齐 | `backend/app/services/rag/citation_align.py` · `align_citations_to_answer` |
| 空证据拒答话术 | `backend/app/services/rag/generation.py` · `no_context_reply_for` / `stream_no_context_reply` |
| L0 正式结果（勿覆盖、勿合并） | `backend/tests/fixtures/l4_critic/w10-ea4-formal-window-result.json` |
| W9 冻结案 | `backend/tests/fixtures/l4_critic/w9-critic-cases.json` |
| W9 Critic oracle（**非**本协议金标） | `backend/tests/fixtures/l4_critic/w9-critic-capability-contract.json` |
| 上游章程 | [`../w10-eb0-generation-boundary/`](../w10-eb0-generation-boundary/) |

## 本窗验收（文档）

- [x] 观察窗口内外边界写清，且不重定义 control-plane / Direction A
- [x] 四靶各有：观察物 · 工件 · 操作定义 · **不声称**
- [x] 显式禁止：生成质量先验 · Critic 能力 · 与 E-A5 合并
- [x] W9 冻结案资格表 + 空检索/拒答缺口
- [x] 未来 artifact 字段草案（无 `backend/app`、无正式结果文件、无 LLM）

## Stop

协议冻结即停。**禁止**把本目录写成「生成已测」。下一窗见 [`03-claim-restrictions.md`](03-claim-restrictions.md) §下一窗。
