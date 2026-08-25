# W10 E-A1 — C12 / 对等 case 产品路径测量协议

> **Type:** research / measurement protocol **design** (+ E-A2 harness pointer)  
> **Date:** 2026-08-24  
> **Product:** 索隐  
> **Status:** E-A1 design frozen · E-A2 measurement harness in `backend/tests/w10_ea2_scope_eligibility.py` · **does not change product behavior**  
> **Does not:** `backend/app` I · runtime change · model call · PR · merge · product PASS claim  
> **Does not unblock:** W9 **P2-R1**（仍为 **BLOCKED** / `MEASUREMENT_PROTOCOL_MISMATCH`）

本目录冻结 **E-A1**：在 W10 Scope Ownership Decision 已选定 **Direction A（system-owned plan-front）** 之后，如何**诚实**测量 C12 及对等 case——不把 harness 注入当成产品路径故障，也不把「尚未映射的冻结 oracle」偷偷改成 PASS。

## 程序位置（必须尊重）

| 断言 | 本协议如何对待 |
|---|---|
| Direction A 已选定 | **PROVEN**（[`../project-boundary/w10-scope-ownership-decision.md`](../project-boundary/w10-scope-ownership-decision.md)） |
| Scope / provenance 所有权 = plan-front；Critic **advisory** | 本协议的测量语义 |
| P2-R1 **BLOCKED** | **仍 BLOCKED**。本文不宣称解阻 |
| C12 既往问题 = **harness injection** | **PROVEN**（H1 CONFIRMED_PRIMARY）。**未**证明产品路径隔离失败 |
| C12 是否可在产品路径上执行并打分 | **EXPERIMENTAL** / 待本协议分类；默认保持 `INVALID_FOR_PRODUCT_PATH_EXECUTION` 直至 oracle 可映射 |

## 阅读顺序

1. [`01-production-path.md`](01-production-path.md) — 产品路径定义（对齐现网代码，非再设计）
2. [`02-eligibility-rules.md`](02-eligibility-rules.md) — 合法产品路径 case vs 非法 harness-only
3. [`03-oracle-mapping.md`](03-oracle-mapping.md) — 原 oracle 何时仍有效；何时必须保持 INVALID
4. [`04-scoring-contract.md`](04-scoring-contract.md) — `final citation ⊆ allowed scope`（Direction A）
5. [`05-dod-checklist.md`](05-dod-checklist.md) — 何时才允许进入 **后续** measurement harness / eval runner I（本窗不实施）

## 目的 / 非目标

**目的**

- 给后续 E-A1 **测量适配器**（另一窗）一份可执行的资格与计分契约。
- 在**不跑模型**的前提下，规定如何把 C12 及 C01–C11 标成 eligible / invalid。
- 把「纵深防御探针」与「产品路径分母」分开，避免再次出现 P2-R1 的协议错配。

**非目标**

- 不改 `backend/app`、不改 flags、不改 Critic 接口、不引入 `CriticScopeContext`。
- 不实施 harness / scorer 代码（E-A1 设计窗为零代码；**E-A2** 已落地测量适配器，见 `backend/tests/w10_ea2_scope_eligibility.py` + `test_w10_ea2_scope_eligibility.py`）。
- 不把 H2（污染 plan 后 recovery merge 缺再授权）写成已证明的生产可达漏洞。
- 不把 Direction B（finalize/Critic 纵深）提前授权。
- 不启动 multimodal W10、Critic rollout、P3 产品声称。
- **不**把 P2-R1 标成 PASS、PARTIAL-unblocked 或「可以开始产品修复」。

## 无模型分类（摘要）

完整规则见 `02` / `03`。分类只读冻结 fixture + 入口函数身份，**禁止**为分类调用 LLM。

| Case | 冻结套件 | 无模型结论（本协议） |
|---|---|---|
| **C12** `C12-out-of-scope-provenance` | `backend/tests/fixtures/l4_critic/w9-critic-cases.json` | **`INVALID_FOR_PRODUCT_PATH_EXECUTION`**。初始 evidence 仅 foreign workspace/KB；合法产品路径不会把该 evidence 送进 `AgentGenerationPlan.gated_chunks`。P2-R1 的 raw 失败来自 harness 直注入，不能当产品分母。 |
| **C01–C11** | 同套件 12 案中其余 11 | **valid product-path case**（资格层面）。evidence `provenance=current_run_retrieval` 且 KB ∈ `allowed_kb_ids`。原 oracle **保持有效**。不得用 C12 探针模式执行它们。 |

## P2-R1 状态（钉死）

> **P2-R1 remains BLOCKED.**  
> 本协议是测量设计，不是解阻证明。即使后续 I 实现了真实 `AgentToolScope` + plan construction 适配器，只要 C12 仍为 `INVALID_FOR_PRODUCT_PATH_EXECUTION`（或 scorer 仍只比正文 diff），独立复核门禁就仍不得改为 PASS。

## 与已有测试代码的关系

P2-R2 已有 **test-only** 草稿：`backend/tests/w9_critic_p2_r2_protocol.py`（`assess_case_product_path_eligibility` / `execute_production_path_case` / `score_final_output`）。那是协议探索，**不是**本 E-A1 已完工，也**不是**产品行为变更。后续 I 必须以本目录契约为准，不得从旧 P2-R1 `execute_frozen_case` 注入路径给产品分母计分。

## Stop

本目录写完即停。无代码、无 runtime、无模型、无 PR。
