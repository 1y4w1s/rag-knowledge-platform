# 05 — Formal execution gate

> Dimension 5. Binary gate only. No execution in this window.

## Gate

```text
E-B_FORMAL_READY = NO
```

**If YES were true:** 本文件只会写「下一任务 = 正式 observation 执行」，并禁止本窗代跑。  
**实际为 NO：** 下列为 **exact blockers only**（不含 nice-to-have）。

---

## Exact blockers

### B1 — No After-window observation executor

E-A 轨在 E-A4 合同模块内提供了 `run_formal_window`（经 E-A2 `execute_product_path_plan`）才能诚实落正式结果。

E-B2 `tests.w10_eb2_generation_observation_contract` **仅有**：

- `validate_reserved_artifact`
- `build_schema_example_artifact`
- `assert_reserved_result_absent`

**没有** `run_formal_observation` / 写入 `FORMAL_OBSERVATION_RESULT` 且填充 After 字段的执行器。

没有该执行器，就无法在不撒谎的前提下打开正式 observation 窗。

### B2 — No After-window snapshots

对全部冻结案：

- `final_content_observation` / `final_citations` 在 schema example 中均为 `null`
- 产品路径从未为本套件留下 `_stream_generation_phase` 终态
- E-B1 明确禁止用 W9 fixture `answer` / `citations` 冒充 After

无快照 = 无可测分母。

### B3 — T2 / T3 claim gold missing

无依据断言与答案接地的操作定义已冻结，但：

- 无独立 claim 金标规程/文件
- Critic `oracle_cases` / `expected_action` **被 E-B2 硬拒绝**，不得当生成命题表

在补齐金标（或正式窗诚实声明 **不测** T2/T3 并改写 `targets_measured` 契约）之前，四靶全集正式窗不可开。

### B4 — T4 empty-gate case missing

`empty_gate_refuse_ok` 需要：**eligible ∧ 空检索/空 gated ∧ `gen_plan.refusal=true`**。

冻结 12：

- 每案至少 1 条 evidence
- E-A5：C01–C11 全部 `plan_refusal=false`
- C07 / C04 **不是**空闸金标

本窗 **不创建**新案；缺口仍在 → 完整 T4 正式窗阻塞。

---

## What is *not* a blocker（勿误列入）

| Item | Why not a readiness blocker |
|---|---|
| Before/After 边界定义 | 已有效（`01`） |
| E-B2 schema / claim / isolation freeze | 已绿（`04`；20 passed） |
| E-A5 11/11 | 错误观察点；不得当 E-B PASS，也不是「缺测」借口去合并 |
| P2-R1 仍 BLOCKED | 期望态；正式窗须保持 BLOCKED |
| Decision DiD E-B0/E-B1 | 本轨故意推迟 |

---

## Narrow-window thought experiment（仍 NO）

即使把第一正式窗收窄为 **仅 T1 · 零 LLM · 同构假正文 → `align_citations_to_answer`**：

- 仍需要 **B1** 的 After 执行器与 **B2** 的诚实快照写入  
- 今日二者皆无 → **窄窗同样 NO-GO**

（T2/T3/T4 金标/空案届时可作为该窄窗的 *out of scope*，但 **不能**取消 B1/B2。）

---

## Next task（仅建议；本窗不执行）

在 B1–B4 消除之前，**不要**开正式 observation 执行窗。

推荐下一原子任务（研究/test-only，零 LLM，除非 owner 书面授权模型窗）：

> **W10 E-B4 — Generation observation After-window executor design（or isomorphic zero-LLM harness freeze）**  
> 严格只做：设计并对齐 E-B2 信封的 After 产出路径（`final_content_observation` / `final_citations` / align 分桶），明确零 LLM vs 授权 LLM；**不**写正式结果、**不**改 `backend/app`、**不**新建 W9 冻结案（空检索案另开 fixture 契约窗）。

备选（一句）：若 owner 优先补 T4 分母，先开「empty-retrieval eligible fixture **研究**」窗（仍零 LLM、不实施产品 case）。

---

## Stop

```text
E-B_FORMAL_READY = NO
```

禁止本窗或口头「差不多了」跳过 blockers 直接执行 generation observation。
