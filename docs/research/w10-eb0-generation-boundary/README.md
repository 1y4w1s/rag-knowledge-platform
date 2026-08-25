# W10 E-B0 — L1 Generation Plane Boundary Charter

> **Type:** research charter only（边界冻结，不实施）  
> **Date:** 2026-08-24  
> **Product:** 索隐  
> **Status:** **FROZEN** — 定义 L0 实测之后、L1 生成平面**下一步研究**的合法边界  
> **Does not:** 产品代码 · pytest 新套件 · LLM / 本地推理调用 · 正式评测执行 · P2-R1 解阻 · Direction B 补丁

本目录冻结 **E-B0（A 轨 · 生成平面）**：在 E-A1～E-A5 已把 **plan-construction citation scope compliance** 测完之后，哪些声称可以写进进度、哪些生成问题仍然未知、下一窗只允许开哪一条原子研究。

## 编号消歧（必读）

| 符号 | 本目录含义 | **不是** |
|---|---|---|
| **E-B0** | **本目录**：L1 generation-plane 研究边界章程 | Decision 表里 Direction B 的「DiD merge re-filter 架构评审」 |
| **E-B1**（本目录推荐） | 下一窗：生成终态**观察点协议设计**（仍零 LLM） | Decision 表里「污染 `gated_chunks` 可达性探针」（仅当 *那个* DiD-E-B0 = yes） |
| Decision **E-B0 / E-B1** | Direction B **残差**，本窗 **DEFER** | 本窗不重新打开 A vs B 所有权 |

Decision 原文见 [`../project-boundary/w10-scope-ownership-decision.md`](../project-boundary/w10-scope-ownership-decision.md) 实验表。A 轨 L0 测完后，程序上的**下一条唯一研究窗**是生成平面边界，而不是立刻做 DiD 探针。两套编号不得混写成一条 backlog。

## 阅读顺序

1. [`01-analysis.md`](01-analysis.md) — **PROVEN** / **UNKNOWN** / **FUTURE EXPERIMENT**（三节互不混写）
2. [`02-evaluation-targets.md`](02-evaluation-targets.md) — 四类候选靶：无依据断言 · 引用保全 · 答案接地 · 拒答行为
3. [`03-non-claims-and-next.md`](03-non-claims-and-next.md) — L0 **禁止声称** + **唯一**推荐下一窗（E-B1）

## 平面切分（本章程 SSOT）

| 平面 | 本章程称呼 | 观察点（已测 / 未测） |
|---|---|---|
| **Runtime L0** | 确定性安全：scope · retrieve · gate · plan citations · 空检索拒答闸 | E-A5 已测：**plan-construction citations ⊆ allowed scope** |
| **Runtime L1** | 生成平面：草稿 token（至多一次 completion） | **未测**答案正文、接地、引用标记、生成后终态 citation |
| **Cite-align（实现挂在 L0）** | `align_citations_to_answer` 在生成**之后**裁剪 `done`/落库列表 | 机制在代码里 **PROVEN**；对生成质量的效果 **UNKNOWN**。L1 测量必须观察对齐**后**列表，否则重犯 E-A3「错观察点」 |

依据：[`../resource-constrained-agent-runtime/architecture.md`](../resource-constrained-agent-runtime/architecture.md) L0/L1；[`../resource-constrained-agent-runtime/capability-ownership.md`](../resource-constrained-agent-runtime/capability-ownership.md) Generation = model-owned L1、Citation honesty = L0。

## 一句话结论

| 断言 | 状态 |
|---|---|
| L0 窄窗「plan-construction citation scope compliance」已正式记录 | **PROVEN**（E-A5 artifact） |
| 该成功 **许可**「eligible 11 案的 *计划引用* 落在允许 KB/gated 集合内」 | **PROVEN** |
| 该成功 **不许可**「回答质量 / 生成终态安全 / 拒答正确 / P2-R1 PASS」 | **钉死**（见 `03`） |
| 下一原子窗 | **E-B1**：生成终态观察点 + 四靶指标契约（research / schema freeze，**不跑模型**） |

## 程序指针

| Role | Path |
|---|---|
| Ownership | `docs/research/project-boundary/w10-scope-ownership-decision.md` |
| E-A1 | `docs/research/w10-ea1-scope-eligibility/` |
| E-A2 | `backend/tests/w10_ea2_scope_eligibility.py` |
| E-A3 | `docs/research/w10-ea3-measurement-readiness-review.md` |
| E-A4 | `docs/research/w10-ea4-formal-window-contract/` |
| E-A5 正式结果 | `backend/tests/fixtures/l4_critic/w10-ea4-formal-window-result.json` |
| P0 引用/拒答 | `docs/PRD.md` §2.1 |
| 硬对齐 | `docs/TECH.md` §5.12 · `backend/app/services/rag/citation_align.py` |

## 本窗验收（文档）

- 三档分离：PROVEN 必带路径；UNKNOWN 必写「L0 为何盖不住」；FUTURE EXPERIMENT 标明测什么 / 不测什么 / 依赖 fixture / 禁止换模型当自变量。
- 未调用任何 LLM API，未新增 `backend/app` 行为，未新增评测执行。

## Stop

章程冻结即停。**禁止**本窗或下一窗把 E-A5 11/11 写成生成 PASS。下一窗只开 **E-B1 观察点协议**，不开生成实验、不开 DiD 产品补丁。
